"""SR-58 #57 — Audited apply path for matcher-pattern suggestions.

================================================================================
ZWECK
================================================================================

``survey learn apply <inbox.jsonl>`` ist der EINZIGE Pfad, ueber den eine
akzeptierte Pattern-Erweiterung in ``survey/profile_loader.py::FIELD_PATTERNS``
landet. Wir gehen NIEMALS ueber ``sed``/Regex-on-source, weil:

  - Regex-on-source verliert bei Klammern/Quotes leise Daten oder produziert
    Tokens, die zwar wie Patterns aussehen, aber von Python anders geparsed
    werden.
  - ``ast.unparse(modified_tree)`` zerstoert Kommentare + Formatierung in
    den existierenden FIELD_PATTERNS (extensive Doku, Reihenfolge-Hints,
    ``re.I``-Konventionen).

Stattdessen: **AST-guided text editing**. Wir parsen mit ``ast``, lokalisieren
das exakte Tupel ``("family", re.compile(...))``, finden ueber ``tokenize`` den
RECHTSESTEN String-Literal in der ``re.compile(r"...", ...)``-Argument-Kette
(implizite String-Konkatenation kommt im File vor), und injecten
``|<escaped_keyword>`` direkt vor dem letzten ``)`` im Regex-Body. Validierung
laeuft auf zwei Stufen:

  1. AST-Reparse → Datei ist noch valides Python.
  2. ``re.compile(neuer_pattern)`` → Regex ist noch syntaktisch korrekt.
  3. Subprocess pytest auf einen Smoke-Testset → semantisch keine Regression.

Bei JEDEM Fehler wird auf den Vorzustand zurueckgerollt (datei-byte-genau).

================================================================================
SICHERHEITSGURT
================================================================================

``_AUTO_APPLY = False`` (Modul-Konstante) bleibt False. ``apply_inbox`` ist
explizit und erfordert entweder ``--interactive`` (jeder Eintrag wird einzeln
abgefragt) oder ``--approve-all`` (alle Eintraege oberhalb der Confidence-
Schwellen werden uebernommen, der Reviewer-Hash landet im Audit-Log fuer
spaetere Forensik). ``--dry-run`` schreibt nichts und gibt nur einen Diff aus.

Confidence-Schwellen:
  - source="substring":  >= 0.7  (FCTC-ES Phase-1 heuristic suggester)
  - source="llm":        >= 0.85 (FCTC-ES Phase-2 LLM suggester, SR-57 #56)
  - alle anderen:        immer abgelehnt
"""

from __future__ import annotations

import ast
import datetime
import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple


# ── Konstanten — NICHT aendern ohne §12 Update ──────────────────────────────
_AUTO_APPLY: bool = False
_SUBSTRING_MIN_CONFIDENCE: float = 0.7
_LLM_MIN_CONFIDENCE: float = 0.85

# Pfad zum profile_loader.py, relativ zur Repo-Root.
_TARGET_REL_PATH: str = "survey-cli/survey/profile_loader.py"


# ── Datentypen ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InboxEntry:
    """Einzelner Eintrag aus pattern-suggestions-accepted.jsonl.

    Felder spiegeln das Schema von ``aggregator.write_suggestions`` (Phase 1)
    plus die Phase-2-Felder (``source``, ``model``, ``prompt_hash``) aus
    SR-57 #56.
    """

    role: str
    normalized_label: str
    suggested_family: Optional[str]
    confidence: float
    source: str  # "substring" | "llm" | "manual"
    count: int = 0
    sample_labels: List[str] = field(default_factory=list)
    matched_tokens: List[str] = field(default_factory=list)
    model: Optional[str] = None  # LLM model id, falls source=="llm"
    prompt_hash: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "InboxEntry":
        return cls(
            role=str(d.get("role", "")),
            normalized_label=str(d.get("normalized_label", "")),
            suggested_family=d.get("suggested_family"),
            confidence=float(d.get("confidence", 0.0)),
            source=str(d.get("source", "substring")),
            count=int(d.get("count", 0)),
            sample_labels=list(d.get("sample_labels", [])),
            matched_tokens=list(d.get("matched_tokens", [])),
            model=d.get("model"),
            prompt_hash=d.get("prompt_hash"),
        )


@dataclass
class ApplyResult:
    """Was ``apply_inbox`` an den Caller zurueckgibt — fuer Tests + CLI-Print."""

    accepted: int = 0
    rejected: int = 0
    skipped: int = 0
    applied_keywords: List[Tuple[str, str]] = field(default_factory=list)
    audit_log_path: Optional[str] = None
    rolled_back: bool = False
    error: Optional[str] = None


# ── Confidence-Gate ─────────────────────────────────────────────────────────


def _gate_confidence(entry: InboxEntry) -> Tuple[bool, str]:
    """Akzeptanz-Gate: Confidence >= Schwelle abhaengig von ``source``.

    Returns:
        ``(passes, reason_if_rejected)``.
    """
    if entry.suggested_family is None:
        return False, "no suggested_family (new family needed)"
    if entry.source == "substring":
        if entry.confidence < _SUBSTRING_MIN_CONFIDENCE:
            return (False,
                    f"substring confidence {entry.confidence:.2f} "
                    f"< {_SUBSTRING_MIN_CONFIDENCE}")
        return True, ""
    if entry.source == "llm":
        if entry.confidence < _LLM_MIN_CONFIDENCE:
            return (False,
                    f"llm confidence {entry.confidence:.2f} "
                    f"< {_LLM_MIN_CONFIDENCE}")
        return True, ""
    if entry.source == "manual":
        # Manuell eingetragen vom Reviewer → kein Schwellwert-Check, der
        # Mensch hat unterzeichnet.
        return True, ""
    return False, f"unknown source {entry.source!r}"


# ── AST + Token-Stream Locator ──────────────────────────────────────────────


def _find_field_patterns_tuple(
    tree: ast.Module, family: str,
) -> Optional[ast.Tuple]:
    """Walk AST, find ``FIELD_PATTERNS`` list, return the tuple for ``family``.

    Returns:
        ``ast.Tuple`` node or ``None`` wenn family nicht existiert.
    """
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef) or cls.name != "ProfileLoader":
            continue
        for stmt in cls.body:
            target_node = None
            if isinstance(stmt, ast.AnnAssign) \
                    and isinstance(stmt.target, ast.Name) \
                    and stmt.target.id == "FIELD_PATTERNS":
                target_node = stmt.value
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "FIELD_PATTERNS":
                        target_node = stmt.value
                        break
            if target_node is None or not isinstance(target_node, ast.List):
                continue
            for tup in target_node.elts:
                if not isinstance(tup, ast.Tuple) or len(tup.elts) < 2:
                    continue
                fst = tup.elts[0]
                if isinstance(fst, ast.Constant) and fst.value == family:
                    return tup
    return None


def _line_col_to_offset(source: str, line: int, col: int) -> int:
    """Konvertiere 1-indexed ``(line, col)`` → 0-indexed byte offset im Source."""
    # AST: line ist 1-indexed, col_offset ist 0-indexed Byte-Offset auf der Zeile.
    lines = source.splitlines(keepends=True)
    return sum(len(li) for li in lines[: line - 1]) + col


def _last_string_token_in_range(
    source: str, start: int, end: int,
) -> Optional[Tuple[int, int, str, str]]:
    """Finde den rechtesten STRING-Token zwischen byte offsets [start, end).

    Returns:
        ``(token_start, token_end, prefix, content)`` wobei
        ``prefix`` Quote-Praefix ist (z.B. ``r"`` oder ``"``) und ``content``
        der Roh-Inhalt zwischen den Quotes (ohne Quotes). ``None`` wenn kein
        String-Token im Range.

    Warum tokenize statt Regex: implizite String-Konkatenation
    (``r"a" r"b"`` als zwei Tokens, die Python automatisch zu ``"ab"``
    zusammenfuehrt) wird vom tokenize-Modul korrekt als zwei STRING-Tokens
    geliefert. Eine naive Regex-Suche wuerde nur das letzte ``r"..."`` finden
    OHNE zu wissen, dass es Teil eines konkatenierten Pattern-Arguments ist.
    """
    snippet = source[start:end]
    last: Optional[Tuple[int, int, str, str]] = None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(snippet).readline))
    except (tokenize.TokenError, IndentationError):
        return None
    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue
        # tok.start/end sind (row, col) im SNIPPET. Konvertiere → absolute
        # byte offset im Source.
        rel_start = _line_col_to_offset(snippet, tok.start[0], tok.start[1])
        rel_end = _line_col_to_offset(snippet, tok.end[0], tok.end[1])
        abs_start = start + rel_start
        abs_end = start + rel_end
        raw = source[abs_start:abs_end]
        # Praefix erkennen: r"..", rb"..", "..", '...', """...""", etc.
        m = re.match(r"^([rRbBuUfF]{0,2})(['\"]{1,3})", raw)
        if not m:
            continue
        prefix = m.group(1) + m.group(2)
        quote_kind = m.group(2)
        if not raw.endswith(quote_kind):
            continue
        content = raw[len(prefix): -len(quote_kind)]
        last = (abs_start, abs_end, prefix, content)
    return last


def apply_keyword_to_family(
    source: str, family: str, keyword: str,
) -> str:
    """Inject ``keyword`` als neue Alternation-Variante in ``family``'s Regex.

    Konkret: lokalisiere ``("family", re.compile(r"(...)", ...))``, finde den
    rechtesten String-Literal-Token, splice ``|<re.escape(keyword)>`` vor den
    letzten ``)`` der aeusseren Gruppe ein.

    Args:
        source: Voller Inhalt von ``profile_loader.py``.
        family: Logischer Schluessel (z.B. ``"phone"``).
        keyword: Normalisiertes Label (z.B. ``"mobilfunknummer"``).

    Returns:
        Modifizierter Source-String.

    Raises:
        ValueError: wenn family nicht gefunden, AST-Modifikation invalide,
                    oder Regex nach Modifikation nicht mehr kompiliert.
    """
    if not keyword.strip():
        raise ValueError("keyword must be non-empty")

    tree = ast.parse(source)
    tup = _find_field_patterns_tuple(tree, family)
    if tup is None:
        raise ValueError(
            f"family {family!r} not in FIELD_PATTERNS — "
            "creating new families is out of scope for #57 (manual only).",
        )

    # re.compile(...) Call ist das zweite Tuple-Element.
    call = tup.elts[1]
    if not (isinstance(call, ast.Call) and call.args):
        raise ValueError(
            f"unexpected AST shape for family {family!r}: "
            "expected re.compile(...) as 2nd tuple element",
        )

    # Byte-Range des ersten Arguments (= das Regex-Pattern, evtl. implizit
    # konkateniert ueber mehrere String-Tokens).
    arg = call.args[0]
    if arg.end_lineno is None or arg.end_col_offset is None:
        raise ValueError("AST node missing end position info")
    arg_start = _line_col_to_offset(source, arg.lineno, arg.col_offset)
    arg_end = _line_col_to_offset(source, arg.end_lineno, arg.end_col_offset)

    last_tok = _last_string_token_in_range(source, arg_start, arg_end)
    if last_tok is None:
        raise ValueError(
            f"could not locate string literal in re.compile arg for "
            f"family {family!r}",
        )
    tok_start, tok_end, prefix, content = last_tok

    # Injection-Strategie: falls ``content`` mit ``)`` endet (= dieser String
    # schliesst die aeussere Capture-Gruppe), splice davor ein
    # ``|<escaped>``. Sonst (Gruppe wurde in einem frueheren konkat-Teil
    # geschlossen, der letzte String ist NACH der Gruppe — sollte in
    # FIELD_PATTERNS nicht vorkommen, aber sicherheitshalber) → fail.
    if not content.rstrip().endswith(")"):
        raise ValueError(
            f"last string literal of family {family!r} regex does not end "
            f"with ')'; pattern shape not supported by AST-guided splice. "
            f"Run apply via manual review only.",
        )

    # Escape — Backslashes/quotes/regex-Sonderzeichen.
    esc = re.escape(keyword.strip())

    # In raw-strings ist ``\b`` als ``\\b`` zu schreiben, in normalen
    # strings ebenfalls. re.escape liefert backslashes als ``\\`` im output
    # repr, aber als string-content ist es das Zeichen ``\``. Da der
    # vorhandene Pattern-String r"..." ist, sind backslashes literal — wir
    # muessen also NUR den Quote-Stil pruefen. Wenn ``prefix`` NICHT mit r
    # beginnt (sehr ungewoehnlich in FIELD_PATTERNS, aber moeglich), muesste
    # jeder backslash verdoppelt werden. Wir lehnen den Apply in dem Fall
    # bewusst ab — kein Risiko fuer falsches Escaping.
    if not (prefix.startswith("r") or prefix.startswith("R")):
        raise ValueError(
            f"family {family!r} uses non-raw string literal "
            f"({prefix!r}); apply requires r\"...\" for safe escaping.",
        )

    # Splice: finde Position des LETZTEN ``)`` in content, fuege davor
    # ``|<esc>`` ein. Sonderfall: content kann auf ``)`` mit Whitespace
    # enden — wir matchen die Position des letzten ``)``.
    splice_pos = content.rfind(")")
    if splice_pos < 0:
        raise ValueError(
            "content unexpectedly has no closing ')' — "
            "should be unreachable",
        )
    new_content = content[:splice_pos] + "|" + esc + content[splice_pos:]

    # Replace token in source.
    new_token = prefix + new_content + source[tok_end - 1: tok_end]
    # ^ kludge: ``prefix`` includes opening quote, original token's last char
    # is closing quote → recover it from source[tok_end-1:tok_end]
    new_source = source[:tok_start] + new_token + source[tok_end:]

    # Validate 1: re-parse AST → still valid Python?
    try:
        new_tree = ast.parse(new_source)
    except SyntaxError as e:
        raise ValueError(f"AST re-parse failed after splice: {e}") from e

    # Validate 2: re.compile the **merged** pattern → still valid regex?
    # WICHTIG: Python merged implicit-concat string literals waehrend
    # ast.parse() zu EINEM ast.Constant. Wir muessen also den vollen
    # zusammengesetzten Pattern validieren, NICHT nur den Token, in den wir
    # gespliced haben — bei Mehrzeilen-Patterns steckt das oeffnende ``(``
    # im fruheren Token und wir wuerden faelschlich "unbalanced parenthesis"
    # sehen, obwohl das gemergte Resultat korrekt ist.
    new_tup = _find_field_patterns_tuple(new_tree, family)
    if new_tup is None:
        raise ValueError(
            f"post-splice AST: family {family!r} no longer findable")
    new_call = new_tup.elts[1]
    if not (isinstance(new_call, ast.Call) and new_call.args):
        raise ValueError("post-splice AST: re.compile shape broken")
    new_pattern_node = new_call.args[0]
    if not isinstance(new_pattern_node, ast.Constant) \
            or not isinstance(new_pattern_node.value, str):
        raise ValueError(
            "post-splice AST: first arg of re.compile is not a string "
            "Constant — implicit-concat may have failed",
        )
    try:
        re.compile(new_pattern_node.value)
    except re.error as e:
        raise ValueError(
            f"regex compile failed after splice: {e}",
        ) from e

    return new_source


# ── Diff + Validation ───────────────────────────────────────────────────────


def compute_diff(before: str, after: str, path: str = _TARGET_REL_PATH) -> str:
    """Unified diff fuer Dry-Run-Anzeige."""
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=2,
    ))


def _run_smoke_tests(
    project_root: str, test_paths: Iterable[str],
) -> Tuple[bool, str]:
    """Subprocess ``pytest`` auf einer Smoke-Test-Liste.

    Wir testen NICHT die volle Suite — Apply ist eine Pattern-Aenderung,
    relevante Regressionen schlagen in den profile/loader-Tests sofort an.
    Args:
        project_root: Pfad zu survey-cli/ (das ``tests/`` direkt enthaelt).
        test_paths: Relative Pfade zu Test-Files (z.B. ``["tests/test_profile_loader.py"]``).
    Returns:
        ``(passed, output_text)``.
    """
    cmd = [sys.executable, "-m", "pytest", "-q", *test_paths]
    try:
        proc = subprocess.run(
            cmd, cwd=project_root, capture_output=True, text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "pytest timeout (>120s)"
    except FileNotFoundError as e:
        return False, f"pytest invocation failed: {e}"
    output = proc.stdout + proc.stderr
    return proc.returncode == 0, output


# ── Reviewer-Hash + Audit-Log ───────────────────────────────────────────────


def _reviewer_hash() -> str:
    """Stabiler Hash fuer den aktuellen Apply-Lauf — keine PII.

    Kombiniert Username + Host (wenn verfuegbar) und schneidet auf 12 Hex-
    Chars. Reicht fuer "war derselbe Reviewer wie damals?"-Forensik, ist
    aber kein Audit-Trail-Ersatz; der echte Trail ist der Git-Commit, der
    den Apply-Output enthaelt.
    """
    parts = []
    for env in ("USER", "USERNAME", "LOGNAME"):
        v = os.environ.get(env)
        if v:
            parts.append(v)
            break
    parts.append(os.uname().nodename if hasattr(os, "uname") else "?")
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def _git_head_sha(project_root: str) -> Optional[str]:
    """Best-effort ``git rev-parse HEAD`` — None wenn nicht in Git oder kein git."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root,
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _audit_log_path(log_dir: str) -> str:
    """logs/learn-applied-{ISO8601-z}.jsonl"""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")
    return os.path.join(log_dir, f"learn-applied-{ts}.jsonl")


# ── Orchestrator ────────────────────────────────────────────────────────────


def _resolve_paths(target_path: Optional[str]) -> Tuple[str, str, str]:
    """Returns (target_file, project_root_for_pytest, log_dir).

    project_root ist das Verzeichnis, das ``tests/`` direkt enthaelt
    (= ``survey-cli/`` bei Default-Layout).
    """
    if target_path:
        target = os.path.abspath(target_path)
    else:
        # apply.py liegt in survey-cli/survey/learn/apply.py → 3 hoch
        here = os.path.dirname(os.path.abspath(__file__))
        target = os.path.normpath(
            os.path.join(here, "..", "profile_loader.py"))
    # project_root = parent of "survey/" dir = survey-cli/
    survey_pkg = os.path.dirname(target)  # survey-cli/survey/
    project_root = os.path.dirname(survey_pkg)  # survey-cli/
    log_dir = os.path.normpath(os.path.join(project_root, "..", "logs"))
    return target, project_root, log_dir


def _read_inbox(path: str) -> List[InboxEntry]:
    out: List[InboxEntry] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(InboxEntry.from_dict(rec))
    return out


def _decide_per_entry(
    entry: InboxEntry, mode: str,
) -> str:
    """Returns one of {"accept", "reject", "skip", "quit"}.

    ``mode``:
      - "approve-all": always accept (after confidence gate).
      - "interactive": prompt user.
      - "dry-run": accept in-memory (so the diff PREVIEWS the apply),
                   the orchestrator suppresses the actual file write at the
                   end. Skipping here would render dry-run useless.
    """
    if mode == "approve-all":
        return "accept"
    if mode == "dry-run":
        return "accept"
    # interactive
    if not sys.stdin.isatty():
        # Non-tty (CI) → skip by default — apply MUST be explicit.
        return "skip"
    prompt = (
        f"  Apply '{entry.normalized_label}' to family "
        f"'{entry.suggested_family}'? [a]ccept / [r]eject / [s]kip / [q]uit: "
    )
    while True:
        choice = input(prompt).strip().lower()
        if choice in ("a", "accept"):
            return "accept"
        if choice in ("r", "reject"):
            return "reject"
        if choice in ("s", "skip", ""):
            return "skip"
        if choice in ("q", "quit"):
            return "quit"
        print("    bitte a / r / s / q")


def apply_inbox(
    inbox_path: str,
    target_path: Optional[str] = None,
    mode: str = "interactive",
    smoke_tests: Optional[List[str]] = None,
    skip_tests: bool = False,
    audit_log_dir: Optional[str] = None,
) -> ApplyResult:
    """Hauptfunktion — orchestriert Read → Gate → Modify → Validate → Audit.

    Args:
        inbox_path: Pfad zu accepted-Inbox (JSONL).
        target_path: Pfad zu profile_loader.py (default: auto-detect).
        mode: "interactive" | "approve-all" | "dry-run".
        smoke_tests: Liste relativer Test-Paths, die VOR und NACH Apply
                     gruen sein muessen. Default:
                     ["tests/test_profile_loader.py",
                      "tests/test_profile_match_field.py"]
        skip_tests: Nur fuer Tests — ueberspringt das pytest-Gate.
        audit_log_dir: Pfad zum logs/-Verzeichnis (default: auto).

    Returns:
        ApplyResult.
    """
    if _AUTO_APPLY:
        # Defensiv: sollte nie zutreffen.
        raise RuntimeError("_AUTO_APPLY MUST be False")

    if mode not in ("interactive", "approve-all", "dry-run"):
        raise ValueError(f"unknown mode {mode!r}")

    target, project_root, default_log_dir = _resolve_paths(target_path)
    log_dir = audit_log_dir or default_log_dir
    if smoke_tests is None:
        smoke_tests = [
            "tests/test_profile_loader.py",
            "tests/test_profile_match_field.py",
        ]

    entries = _read_inbox(inbox_path)
    if not entries:
        return ApplyResult(error="inbox is empty")

    # PRE-flight: Tests gruen vor dem Apply? (sonst rollback bringt nichts)
    if not skip_tests and mode != "dry-run":
        ok, out = _run_smoke_tests(project_root, smoke_tests)
        if not ok:
            return ApplyResult(
                error=f"pre-apply tests FAIL — aborting before changes:\n{out[-1500:]}",
            )

    with open(target, encoding="utf-8") as f:
        original_source = f.read()
    current_source = original_source

    result = ApplyResult()

    audit_records: List[dict] = []
    for entry in entries:
        ok, reason = _gate_confidence(entry)
        if not ok:
            result.rejected += 1
            audit_records.append({
                "decision": "rejected_by_gate",
                "reason": reason,
                "entry": entry.__dict__,
            })
            continue

        decision = _decide_per_entry(entry, mode)
        if decision == "skip":
            result.skipped += 1
            continue
        if decision == "reject":
            result.rejected += 1
            audit_records.append({
                "decision": "rejected_by_reviewer",
                "entry": entry.__dict__,
            })
            continue
        if decision == "quit":
            break
        # decision == "accept"
        try:
            new_source = apply_keyword_to_family(
                current_source, entry.suggested_family,
                entry.normalized_label,
            )
        except ValueError as e:
            result.rejected += 1
            audit_records.append({
                "decision": "rejected_by_ast",
                "reason": str(e),
                "entry": entry.__dict__,
            })
            continue
        current_source = new_source
        result.accepted += 1
        result.applied_keywords.append(
            (entry.suggested_family, entry.normalized_label))
        audit_records.append({
            "decision": "applied",
            "family": entry.suggested_family,
            "keyword": entry.normalized_label,
            "source": entry.source,
            "confidence": entry.confidence,
            "model": entry.model,
            "prompt_hash": entry.prompt_hash,
            "timestamp": datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"),
        })

    # Dry-run: kein Write, kein Audit-Log, nur Diff stdout
    if mode == "dry-run":
        diff = compute_diff(original_source, current_source)
        sys.stdout.write(diff if diff else "(no changes)\n")
        return result

    # Nichts angewandt → kein Write, kein Audit-Log.
    if not result.applied_keywords:
        return result

    # Write modifiziertes profile_loader.py atomar.
    try:
        _atomic_write(target, current_source)
    except OSError as e:
        return ApplyResult(error=f"atomic write failed: {e}")

    # POST-flight: Tests gruen nach Apply?
    if not skip_tests:
        ok, out = _run_smoke_tests(project_root, smoke_tests)
        if not ok:
            # ROLLBACK
            try:
                _atomic_write(target, original_source)
            except OSError as e:
                return ApplyResult(
                    error=(
                        "POST-apply tests FAIL **and rollback ALSO FAILED**: "
                        f"{e}\nTests:\n{out[-1500:]}"
                    ),
                    rolled_back=False,
                )
            return ApplyResult(
                error=f"post-apply tests FAIL — rolled back:\n{out[-1500:]}",
                rolled_back=True,
            )

    # Audit-Log erst NACH erfolgreichem Post-Test schreiben.
    os.makedirs(log_dir, exist_ok=True)
    audit_path = _audit_log_path(log_dir)
    reviewer = _reviewer_hash()
    head_sha = _git_head_sha(project_root)
    with open(audit_path, "w", encoding="utf-8") as f:
        header = {
            "kind": "header",
            "ts": datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
            "inbox_path": os.path.abspath(inbox_path),
            "target_path": os.path.abspath(target),
            "reviewer_hash": reviewer,
            "git_head": head_sha,
            "issue": "SR-58 #57",
        }
        f.write(json.dumps(header, ensure_ascii=False) + "\n")
        for rec in audit_records:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    result.audit_log_path = audit_path
    return result


def _atomic_write(path: str, content: str) -> None:
    """tempfile + os.replace → kein partieller Write bei Crash."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".apply-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise

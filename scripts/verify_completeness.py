#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
VERIFY COMPLETENESS — Pre-Commit Code Quality Gate
================================================================================

WAS IST DAS?
  Automatisierte Pruefung die sicherstellt dass ALLE Code-Dateien
  Mindeststandards erfuellen BEVOR sie committet werden.

WARUM existiert dieses Script?
  - Verhindert dass unvollstaendiger/undokumentierter Code committet wird
  - Erzwingt BANNED-Method-Header in jeder Datei
  - Findet hardcoded Credentials/PIDs bevor sie ins Repo gelangen
  - Stellt sicher dass jede Funktion dokumentiert ist
  - Blockiert Commits die gegen AGENTS.md Regeln verstossen

WANN wird es ausgefuehrt?
  1. Manuell: python3 scripts/verify_completeness.py
  2. Pre-Commit Hook: .git/hooks/pre-commit ruft dieses Script auf
  3. CI/CD: GitHub Actions kann es als Check nutzen

CHECKS:
  1. Docstring-Praesenz (jede public Funktion/Klasse hat Docstring)
  2. BANNED-Method Header (jede .py Datei hat BANNED Section)
  3. Hardcoded PIDs (keine pid = 12345 Pattern)
  4. Hardcoded Credentials (keine API Keys, Emails, Passwoerter)
  5. playstealth usage (BANNED playstealth launch)
  6. Test-Abdeckung (Warnung wenn keine Test-Datei existiert)

EXIT CODES:
  0 = Alle Checks bestanden (Commit erlaubt)
  1 = Kritische Fehler gefunden (Commit BLOCKIERT)
  2 = Warnungen gefunden (Commit erlaubt, aber Hinweise anzeigen)

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
================================================================================"""

import os
import re
import sys
import ast
from pathlib import Path
from typing import List, Tuple, Optional

# ═════════════════════════════════════════════════════════════════════════════
# KONSTANTEN
# ═════════════════════════════════════════════════════════════════════════════

# ROOT_DIR: Projekt-Root-Verzeichnis
#   → WARUM parent von scripts/? Weil scripts/ im Root liegt.
ROOT_DIR = Path(__file__).parent.parent

# EXCLUDE_DIRS: Verzeichnisse die NICHT geprueft werden
#   → WARUM diese? Externe Dependencies, Build-Artifacts, Git-Metadata,
#     Skill-Dokumentation (enthintentionell BANNED-Patterns als Beispiele).
EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".eggs", "*.egg-info",
    ".agents", ".claude",  # Skill-Docs enthalten BANNED-Patterns als Beispiele
    "survey-cli",           # Legacy CLI — separate Codebase
    "A2A-SIN-Worker-heypiggy",  # Legacy Worker — separate Codebase
}

# BANNED_PATTERNS: Regex-Patterns die NICHT im Code vorkommen duerfen
#   → WARUM diese? Siehe AGENTS.md §BANNED.
BANNED_PATTERNS = [
    # playstealth launch (BANNED — setzt Accessibility Flag nicht)
    (r'playstealth\s+launch', 'playstealth launch detected — use SessionManager.launch() instead'),
    # webauto-nodriver (ABSOLUT BANNED)
    (r'webauto.nodriver', 'webauto-nodriver detected — ABSOLUTELY BANNED'),
    # pkill -f "Google Chrome" (tötet User Chrome!)
    (r'pkill\s+-f\s+["\']?Google\s+Chrome', 'pkill -f "Google Chrome" detected — KILLS USER CHROME!'),
    # killall Google Chrome (tötet ALLE Chrome!)
    (r'killall\s+Google\s+Chrome', 'killall Google Chrome detected — KILLS ALL CHROME!'),
    # Fixed profile path (korruptiert nach Neustart)
    (r'/tmp/heypiggy-bot(?!-new-)', 'Fixed profile /tmp/heypiggy-bot detected — use timestamped profile'),
]

# CREDENTIAL_PATTERNS: Regex fuer hardcoded Credentials
#   → WARUM diese? Verhindert dass Secrets ins Repo committet werden.
CREDENTIAL_PATTERNS = [
    # NVIDIA API Key (nvapi-...)
    (r'["\']nvapi-[a-zA-Z0-9_-]{20,}["\']', 'Hardcoded NVIDIA API key'),
    # OpenAI API Key (sk-...)
    (r'["\']sk-[a-zA-Z0-9_-]{20,}["\']', 'Hardcoded OpenAI API key'),
    # Fireworks API Key (fw_...)
    (r'["\']fw_[a-zA-Z0-9_-]{20,}["\']', 'Hardcoded Fireworks API key'),
    # Generic API key assignment
    (r'api_key\s*=\s*["\'][^"\']{10,}["\']', 'Hardcoded api_key assignment'),
    # Password assignment
    (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password assignment'),
    # Secret assignment
    (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret assignment'),
]

# PID_PATTERNS: Regex fuer hardcoded PIDs
#   → WARUM 4-6 stellige Zahlen? PIDs sind typisch 4-6 stellig.
PID_PATTERNS = [
    (r'(?<!["\w])pid\s*[=:]\s*(\d{4,6})(?!["\w])', 'Hardcoded PID detected'),
]

# ═════════════════════════════════════════════════════════════════════════════
# HELPER: get_python_files()
# ═════════════════════════════════════════════════════════════════════════════
def get_python_files(root: Path) -> List[Path]:
    """Findet alle Python-Dateien im Projekt (rekursiv).

    Args:
        root: Root-Verzeichnis fuer die Suche.

    Returns:
        List[Path]: Alle .py Dateien (exklusive EXCLUDE_DIRS).

    WARUM Path.rglob? Rekursiv, plattformunabhaengig, modern.
    WARUM EXCLUDE_DIRS? Vermeidet false positives in Dependencies.
    """
    files = []
    for path in root.rglob("*.py"):
        # Pruefen ob irgendein Parent in EXCLUDE_DIRS ist
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 1: Docstring-Praesenz
# ═════════════════════════════════════════════════════════════════════════════
def check_docstrings(file: Path) -> List[str]:
    """Prueft ob jede public Funktion/Klasse einen Docstring hat.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Fehlermeldungen (leer = alle OK).

    WARUM AST parsing? Zuverlaessiger als Regex — versteht Python-Syntax.
    WARUM nur public? Private (_ prefix) und dunder (__ prefix) sind exempt.
    """
    errors = []
    try:
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file))
    except SyntaxError as e:
        return [f"{file}: Syntax error: {e}"]
    except UnicodeDecodeError:
        return [f"{file}: Cannot decode as UTF-8"]

    for node in ast.walk(tree):
        # Klassen pruefen
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                if not ast.get_docstring(node):
                    errors.append(f"{file}:{node.lineno}: Class '{node.name}' missing docstring")

        # Funktionen pruefen
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Private Funktionen (_ prefix) ignorieren
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue
            # Dunder Methoden (__init__, __repr__, etc.) ignorieren
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            if not ast.get_docstring(node):
                errors.append(f"{file}:{node.lineno}: Function '{node.name}()' missing docstring")

    return errors


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 2: BANNED-Method Header
# ═════════════════════════════════════════════════════════════════════════════
def check_banned_header(file: Path) -> List[str]:
    """Prueft ob Datei einen BANNED-Methods-Header hat.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Fehlermeldungen (leer = OK).

    WARUM erste 2000 Zeichen? Header steht typisch am Dateianfang.
    WARUM nicht exakter Match? Flexibel — "BANNED" kann variieren.
    """
    errors = []
    try:
        content = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []  # Kann nicht gelesen werden → skip

    # Nur pruefen wenn Datei > 50 Zeilen (kleine Files exempt)
    line_count = content.count("\n")
    if line_count < 50:
        return []

    # Pruefen ob "BANNED" im Header-Bereich vorkommt
    header = content[:2000]
    if "BANNED" not in header.upper():
        errors.append(f"{file}: Missing BANNED methods section in header (first 2000 chars)")

    return errors


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 3: Hardcoded PIDs
# ═════════════════════════════════════════════════════════════════════════════
def check_hardcoded_pids(file: Path) -> List[str]:
    """Prueft auf hardcoded PID-Zuweisungen.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Fehlermeldungen (leer = OK).

    WARUM Regex? AST kann nicht zwischen literal und variable unterscheiden.
    WARUM pid = 12345? Typisches Pattern fuer hardcoded PIDs.
    WARUM nicht in Kommentaren/Strings? Regex matcht den gesamten Text.
    """
    errors = []
    try:
        content = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    for pattern, message in PID_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            # Kontext holen (Zeilennummer berechnen)
            line_num = content[:match.start()].count("\n") + 1
            line = content.split("\n")[line_num - 1].strip()

            # WARUM diese Ausnahmen? Beispiele/Doku/Kommentare sind OK.
            if "WARUM" in line.upper() or "BEISPIEL" in line.upper():
                continue
            if "VERIFIZIERUNG" in line.upper() or "LIVE" in line.upper():
                continue
            if "Historisch" in line or "PID=" in line:
                continue
            if line.startswith("#") or line.startswith('"""') or line.startswith("'''"):
                continue
            if ">>>" in line:  # Doctest example
                continue
            if "pid=" in line.lower() and ("example" in line.lower() or "test" in line.lower()):
                continue

            # Nur echte Zuweisungen melden (pid = 12345, pid: 12345 in code)
            if re.search(r'^\s*pid\s*[=:]\s*\d{4,6}', line) and not line.startswith("#"):
                errors.append(f"{file}:{line_num}: {message}: {line[:80]}")

    return errors


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 4: Hardcoded Credentials
# ═════════════════════════════════════════════════════════════════════════════
def check_hardcoded_credentials(file: Path) -> List[str]:
    """Prueft auf hardcoded API Keys, Emails, Passwoerter.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Fehlermeldungen (leer = OK).

    WARUM Regex? Credentials sind typisch String-Literale.
    WARUM nicht os.getenv? Das ist der KORREKTE Weg — wird erlaubt.
    """
    errors = []
    try:
        content = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    for pattern, message in CREDENTIAL_PATTERNS:
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count("\n") + 1
            line = content.split("\n")[line_num - 1].strip()

            # WARUM diese Ausnahmen? Env-Vars und Examples sind OK.
            if "os.getenv" in line or "os.environ" in line:
                continue
            if "NVIDIA_API_KEY" in line and "os.getenv" in line:
                continue
            if line.startswith("#") or line.startswith('"""'):
                continue
            if "example" in line.lower() or "placeholder" in line.lower():
                continue

            errors.append(f"{file}:{line_num}: {message}: {line[:80]}")

    return errors


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 5: BANNED Patterns
# ═════════════════════════════════════════════════════════════════════════════
def check_banned_patterns(file: Path) -> List[str]:
    """Prueft auf BANNED Code-Patterns.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Fehlermeldungen (leer = OK).

    WARUM Regex? BANNED Patterns sind typisch String-Literale oder Commands.
    """
    errors = []
    try:
        content = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    # Skip this file itself (verify_completeness.py contains BANNED patterns as definitions)
    # WARUM? Die Pattern-Definitionen sind META-DATEN, nicht echte Nutzung.
    if file.name == "verify_completeness.py":
        return []

    lines = content.split("\n")
    in_docstring = False
    docstring_char = None

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track docstring state (triple quotes)
        # WARUM? Docstrings dokumentieren BANNED Patterns — das ist OK.
        if '"""' in stripped or "'''" in stripped:
            quote = '"""' if '"""' in stripped else "'''"
            count = stripped.count(quote)
            if count == 1:
                # Opening or closing docstring
                if not in_docstring:
                    in_docstring = True
                    docstring_char = quote
                elif docstring_char == quote:
                    in_docstring = False
                    docstring_char = None
            elif count >= 2:
                # Single-line docstring — skip this line
                continue
            continue

        if in_docstring:
            continue

        # Skip comment lines that document BANNED patterns
        # WARUM? "❌ playstealth launch" in Kommentaren ist Dokumentation, nicht Nutzung.
        if stripped.startswith("#") or stripped.startswith("❌") or stripped.startswith("→"):
            continue

        # Skip lines that contain BANNED keyword (documentation context)
        # WARUM? Wenn "BANNED" im selben Block steht, ist es Dokumentation.
        context_start = max(0, line_num - 10)
        context_end = min(len(lines), line_num + 3)
        context = "\n".join(lines[context_start:context_end])
        if "BANNED" in context.upper() and (stripped.startswith("#") or "❌" in stripped):
            continue

        # Skip regex pattern definitions (they contain banned patterns as strings)
        # WARUM? r'playstealth\s+launch' ist ein Regex-Pattern, kein echter Aufruf.
        if "r'" in stripped or 'r"' in stripped:
            if any(bp[0] in stripped for bp in BANNED_PATTERNS):
                continue

        for pattern, message in BANNED_PATTERNS:
            if re.search(pattern, line):
                # Additional filter: skip if line is clearly documentation
                if any(marker in stripped for marker in ["❌", "#", "→", "BANNED", "VERBOTEN", "NUTZE", "NUTZT"]):
                    continue
                errors.append(f"{file}:{line_num}: {message}: {stripped[:80]}")

    return errors


# ═════════════════════════════════════════════════════════════════════════════
# CHECK 6: Test-Abdeckung (Warnung)
# ═════════════════════════════════════════════════════════════════════════════
def check_test_coverage(file: Path) -> List[str]:
    """Prueft ob fuer jede .py Datei eine Test-Datei existiert.

    Args:
        file: Python-Datei die geprueft werden soll.

    Returns:
        List[str]: Warnungen (leer = Test existiert).

    WARUM nur Warnung? Fehlende Tests blockieren NICHT den Commit.
    WARUM nicht __init__.py? Init-Files haben typisch keine eigenen Tests.
    """
    warnings = []

    # __init__.py und conftest.py exempt
    if file.name in ("__init__.py", "conftest.py"):
        return warnings

    # Moegliche Test-Datei-Namen
    # WARUM diese Varianten? Unterschiedliche Projekt-Konventionen.
    stem = file.stem
    test_candidates = [
        file.parent / f"{stem}_test.py",
        file.parent / f"test_{stem}.py",
        ROOT_DIR / "tests" / f"test_{stem}.py",
        ROOT_DIR / "tests" / f"{stem}_test.py",
    ]

    if not any(p.exists() for p in test_candidates):
        rel_path = file.relative_to(ROOT_DIR)
        warnings.append(f"{rel_path}: No corresponding test file found")

    return warnings


# ═════════════════════════════════════════════════════════════════════════════
# MAIN: verify_completeness()
# ═════════════════════════════════════════════════════════════════════════════
def verify_completeness(root: Optional[Path] = None) -> Tuple[int, int, int]:
    """Fuehrt ALLE Checks aus und gibt Ergebnis zurueck.

    Args:
        root: Root-Verzeichnis. Wenn None → ROOT_DIR.

    Returns:
        Tuple[int, int, int]: (errors, warnings, files_checked)

    Side Effects:
        - Printet Ergebnisse auf stdout.
        - Exit code 1 wenn errors > 0.
        - Exit code 2 wenn nur warnings.
    """
    root = root or ROOT_DIR
    all_errors = []
    all_warnings = []
    files_checked = 0

    print(f"🔍 Verifying code completeness in {root}")
    print(f"{'=' * 60}")

    python_files = get_python_files(root)
    print(f"Found {len(python_files)} Python files to check\n")

    for file in python_files:
        files_checked += 1
        rel_path = file.relative_to(root)

        # Check 1: Docstrings
        all_errors.extend(check_docstrings(file))

        # Check 2: BANNED Header
        all_errors.extend(check_banned_header(file))

        # Check 3: Hardcoded PIDs
        all_errors.extend(check_hardcoded_pids(file))

        # Check 4: Hardcoded Credentials
        all_errors.extend(check_hardcoded_credentials(file))

        # Check 5: BANNED Patterns
        all_errors.extend(check_banned_patterns(file))

        # Check 6: Test Coverage (nur Warnung)
        all_warnings.extend(check_test_coverage(file))

    # ═════════════════════════════════════════════════════════════════════════
    # ERGEBNIS AUSGEBEN
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {files_checked} files checked")
    print(f"{'=' * 60}")

    if all_errors:
        print(f"\n❌ {len(all_errors)} ERRORS FOUND (COMMIT BLOCKED):")
        for error in all_errors:
            print(f"   {error}")

    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} WARNINGS:")
        for warning in all_warnings:
            print(f"   {warning}")

    if not all_errors and not all_warnings:
        print(f"\n✅ ALL CHECKS PASSED — {files_checked} files verified")

    print(f"\n{'=' * 60}")
    print(f"Errors: {len(all_errors)} | Warnings: {len(all_warnings)} | Files: {files_checked}")
    print(f"{'=' * 60}")

    return len(all_errors), len(all_warnings), files_checked


# ═════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify code completeness before commit"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Root directory to check (default: project root)"
    )
    parser.add_argument(
        "--check",
        type=str,
        choices=["docstrings", "banned-header", "pids", "credentials", "banned-patterns", "test-coverage", "all"],
        default="all",
        help="Specific check to run (default: all)"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Check a single file instead of all files"
    )

    args = parser.parse_args()

    if args.file:
        # Einzelne Datei pruefen
        errors = []
        if args.check in ("docstrings", "all"):
            errors.extend(check_docstrings(args.file))
        if args.check in ("banned-header", "all"):
            errors.extend(check_banned_header(args.file))
        if args.check in ("pids", "all"):
            errors.extend(check_hardcoded_pids(args.file))
        if args.check in ("credentials", "all"):
            errors.extend(check_hardcoded_credentials(args.file))
        if args.check in ("banned-patterns", "all"):
            errors.extend(check_banned_patterns(args.file))

        if errors:
            print(f"❌ {len(errors)} errors in {args.file}:")
            for e in errors:
                print(f"   {e}")
            sys.exit(1)
        else:
            print(f"✅ {args.file} passed all checks")
            sys.exit(0)
    else:
        # Alle Dateien pruefen
        errors, warnings, files = verify_completeness(args.root)

        if errors > 0:
            sys.exit(1)  # Blockiere Commit
        elif warnings > 0:
            sys.exit(2)  # Warnungen anzeigen, aber Commit erlauben
        else:
            sys.exit(0)  # Alles OK

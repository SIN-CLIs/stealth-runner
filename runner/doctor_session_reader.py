"""doctor_session_reader.py — Lies OpenCode-Session-Daten + analysiere via Vercel AI Gateway.

Liest:
  1. ~/.local/share/opencode/auth.json → Vercel API Key
  2. ~/.local/share/opencode/storage/session_diff/ → Session-Änderungen
  3. Session-Transcript via session_read (open-code intern)

Analysiert via:
  vercel/deepseek/deepseek-v4-flash (kostenlos über Vercel AI Gateway)
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
from typing import Any

import httpx

HOME = Path.home()
AUTH_FILE = HOME / ".local/share/opencode/auth.json"
STORAGE = HOME / ".local/share/opencode/storage"
GATEWAY_URL = "https://gateway.ai.vercel.com/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-flash"


def _get_gateway_key() -> str:
    """Hole Vercel API Key aus auth.json."""
    if not AUTH_FILE.exists():
        raise RuntimeError("Kein auth.json gefunden — Vercel Gateway nicht konfiguriert")
    auth = json.loads(AUTH_FILE.read_text())
    for provider in ["vercel", "vercel-plugin:vercel"]:
        if provider in auth and auth[provider].get("type") == "api":
            return auth[provider]["key"]
    raise RuntimeError("Kein Vercel API Key in auth.json")


def _call_gateway(prompt: str, max_tokens: int = 500) -> str:
    """Rufe Vercel AI Gateway mit DeepSeek Flash auf (kostenlos)."""
    key = _get_gateway_key()
    r = httpx.post(
        GATEWAY_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gateway error {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"].strip()


def read_session_changes(session_id: str | None = None) -> dict[str, Any]:
    """Lese alle Änderungen einer Session aus session_diff/."""
    diff_dir = STORAGE / "session_diff"
    if not diff_dir.exists():
        return {"files": [], "diffs": []}
    files = sorted(diff_dir.glob("*.json"))
    if session_id:
        files = [f for f in files if session_id in f.name]
    if not files:
        files = files[-3:]  # Letzte 3 Sessions
    result = {"files": [], "diffs": []}
    for f in files:
        try:
            data = json.loads(f.read_text())
            result["files"].extend([d.get("file", "") for d in data[:20]])
            result["diffs"].extend([d.get("patch", "")[:500] for d in data[:5] if d.get("patch")])
        except Exception:
            pass
    return result


def analyze_session_context(session_changes: dict, repo_path: str) -> dict:
    """LLM analysiert Session-Kontext + Code-Änderungen.

    Returns dict mit:
      - protected_files: Dateien die NICHT automatisch geändert werden dürfen
      - intentional_changes: Welche Änderungen absichtlich waren
      - warnings: Warnungen vor gefährlichen Änderungen
    """
    files = session_changes.get("files", [])[:30]
    diffs = session_changes.get("diffs", [])[:3]
    prompt = (
        "Du bist ein Code-Review-Assistent. Analysiere die folgenden Änderungen "
        "aus einer AI-Entwicklungs-Session.\n\n"
        f"REPOSITORY: {repo_path}\n\n"
        f"GEÄNDERTE DATEIEN ({len(files)}):\n"
        + "\n".join(f"- {f}" for f in files[:20]) + "\n\n"
        f"DIFFS (Auszüge):\n"
        + "\n".join(d[:300] for d in diffs) + "\n\n"
        "AUFGABE:\n"
        "1. Identifiziere Dateien die ARCHITEKTUR-DOKUMENTATION enthalten "
        "(banned.md, brain.md, fix.md, AGENTS.md, etc.) — diese dürfen NIEMALS "
        "automatisch durch blinde Text-Replacements verändert werden.\n"
        "2. Identifiziere ABSICHTLICHE Code-Änderungen (z.B. neue Features, "
        "Bugfixes, Tool-Integration) die erhalten bleiben müssen.\n"
        "3. Erkenne gefährliche Muster wie 'cua-driver → skylight-cli' Ersetzungen "
        "die Architektur-Regeln verletzen.\n\n"
        "Antworte NUR mit gültigem JSON:\n"
        '{"protected_docs":["datei1.md","datei2.md"],'
        '"intentional_features":["feature1","feature2"],'
        '"dangerous_replacements":["muster1"],'
        '"summary":"<1 Satz Zusammenfassung>"}'
    )
    try:
        resp = _call_gateway(prompt, max_tokens=800)
        import re
        m = re.search(r"\{.*\}", resp, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"error": "JSON parse failed", "raw": resp[:300]}
    except Exception as e:
        return {"error": str(e)[:200]}


def gatekeeper_check(repo_path: str) -> dict:
    """Vollständiger Pre-Doctor Gatekeeper-Check.

    Returns dict mit go/no-go Entscheidung + Begründung.
    """
    changes = read_session_changes()
    analysis = analyze_session_context(changes, repo_path)

    protected = analysis.get("protected_docs", [])
    dangerous = analysis.get("dangerous_replacements", [])
    intentional = analysis.get("intentional_features", [])

    can_proceed = len(dangerous) == 0
    reason = (
        f"OK: {len(intentional)} Features, {len(protected)} Docs geschützt"
        if can_proceed
        else f"BLOCKED: {len(dangerous)} gefährliche Ersetzungen erkannt"
    )

    return {
        "can_proceed": can_proceed,
        "reason": reason,
        "protected_docs": protected,
        "dangerous_replacements": dangerous,
        "intentional_features": intentional,
        "analysis": analysis,
    }


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    print("🔍 Gatekeeper-Check...", flush=True)
    result = gatekeeper_check(repo)
    print(json.dumps(result, indent=2, ensure_ascii=False))

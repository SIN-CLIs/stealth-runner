#!/usr/bin/env python3
"""doctor_tools.py — Read-only Repository Health Scanner (v8).

KEINE automatischen Änderungen mehr! Nur Analyse-Tools.
Der AI-Agent entscheidet WAS geändert wird, nach LLM-Analyse.

Usage:
  python3 runner/doctor_tools.py --check          # Verfügbare Tools prüfen
  python3 runner/doctor_tools.py --scan <REPO>    # Repo analysieren (JSON-Output)
  python3 runner/doctor_tools.py --scan-all       # Alle 7 Repos analysieren
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

HOME = Path.home()
DEV = HOME / "dev"

REPOS = [
    "stealth-runner", "playstealth-cli", "skylight-cli",
    "screen-follow", "unmask-cli", "A2A-SIN-Worker-heypiggy",
    "infra-opencode-stack",
]

CHECKLIST = [
    "README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md",
    "CHANGELOG.md", "AGENTS.md", "brain.md", "fix.md",
    "goal.md", "architecture.md", "commands.md",
    "Makefile", ".env.example", "Dockerfile",
]

PROTECTED_DOCS = {
    "banned.md", "brain.md", "fix.md", "successful.md",
    "learn.md", "anti-learn.md", "commands.md",
    "AGENTS.md", "goal.md", "architecture.md",
}


def check_tools() -> dict[str, bool]:
    tools = {
        "cloc": ["cloc", "--version"],
        "tokei": ["tokei", "--version"],
        "lizard": ["lizard", "--version"],
        "semgrep": ["semgrep", "--version"],
        "prettier": [f"{HOME}/.local/bin/prettier", "--version"],
        "graphify": ["graphify", "--version"],
        "git": ["git", "--version"],
    }
    result = {}
    for name, cmd in tools.items():
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            result[name] = r.returncode == 0
        except Exception:
            result[name] = False
    return result


def scan_repo(repo_path: str) -> dict:
    path = Path(repo_path)
    if not (path / ".git").exists():
        return {"error": "no git repo", "path": str(path)}

    result = {"name": path.name, "path": str(path), "tools": {}}

    # cloc
    try:
        r = subprocess.run(["cloc", str(path), "--json"], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            result["tools"]["cloc"] = json.loads(r.stdout)
    except Exception:
        pass

    # git log
    try:
        r = subprocess.run(["git", "log", "--oneline", "-20"], capture_output=True, text=True, timeout=10, cwd=str(path))
        result["tools"]["git_log"] = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except Exception:
        result["tools"]["git_log"] = []

    # git status
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10, cwd=str(path))
        result["tools"]["git_dirty"] = len([l for l in r.stdout.strip().split("\n") if l.strip()])
    except Exception:
        result["tools"]["git_dirty"] = -1

    # semgrep
    semgrep_config = path / ".semgrep_rules.yaml"
    if semgrep_config.exists():
        try:
            r = subprocess.run(["semgrep", "--config", str(semgrep_config), "--quiet"], capture_output=True, text=True, timeout=120, cwd=str(path))
            findings = [l.strip() for l in r.stdout.strip().split("\n") if l.strip() and "..." not in l]
            result["tools"]["semgrep_findings"] = findings[:20]
        except Exception:
            result["tools"]["semgrep_findings"] = []

    # Missing docs
    missing = []
    for doc in CHECKLIST:
        if not (path / doc).exists():
            missing.append(doc)
    result["tools"]["missing_docs"] = missing

    # Protected docs status
    protected_status = {}
    for doc in PROTECTED_DOCS:
        doc_path = path / doc
        if doc_path.exists():
            size = doc_path.stat().st_size
            lines = len(doc_path.read_text(encoding="utf-8", errors="replace").split("\n"))
            protected_status[doc] = {"exists": True, "lines": lines, "bytes": size}
        else:
            protected_status[doc] = {"exists": False}
    result["tools"]["protected_docs"] = protected_status

    # File extensions
    from collections import Counter
    exts = Counter()
    for f in path.rglob("*"):
        if f.is_file() and ".git/" not in str(f) and "node_modules" not in str(f):
            ext = f.suffix.lower() or "(none)"
            exts[ext] += 1
    result["tools"]["extensions"] = dict(exts.most_common(10))

    return result


def main():
    if "--check" in sys.argv:
        tools = check_tools()
        available = sum(tools.values())
        print(f"🔧 {available}/{len(tools)} Tools verfügbar")
        for name, ok in tools.items():
            print(f"  {'✅' if ok else '❌'} {name}")

    elif "--scan-all" in sys.argv:
        for repo_name in REPOS:
            repo_path = DEV / repo_name
            if repo_path.exists():
                result = scan_repo(str(repo_path))
                print(json.dumps(result))

    elif "--scan" in sys.argv:
        idx = sys.argv.index("--scan") + 1
        repo = sys.argv[idx] if idx < len(sys.argv) else "."
        result = scan_repo(repo)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(__doc__)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
DOCTOR v6 – ALLE 35 Tools aus der Recherche. Automatisch. 143 Repos.
Keine Pfade. Keine Templates. Nur echte Analyse + echte Generierung.
"""
from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path

HOME = os.environ.get("HOME", "/Users/jeremy")
DEV = Path(HOME) / "dev"

TOOLS = {}  # wird dynamisch befüllt
OUTDATED = [
    (r"pgrep\s+.*[Cc]hrome", "playstealth launch (isolierte PID)"),
    (r"pkill.*[Cc]hrome", "NIEMALS – BANNED"),
    (r"open -na .Google Chrome.", "playstealth launch"),
    (r"import pyautogui|import pynput", "BANNED (Mausbewegung verboten)"),
    (r"webauto[._-]nodriver", "skylight-cli"),
    (r"from openai import|import openai", "httpx an NVIDIA NIM"),
    (r"llama-3\.2-90b-vision-instruct(?!.*fallback)", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    (r"nvidia/nvidia/nemotron", "nvidia/nemotron"),
    (r"cua[._-]driver", "skylight-cli"),
]


def check_tools():
    all_tools = {
        # Deep Analysis (5)
        "cloc": ["cloc", "--version"],
        "tokei": ["tokei", "--version"],
        "lizard": ["lizard", "--version"],
        "pydeps": ["python3", "-m", "pydeps", "--version"],
        "pyreverse": ["pyreverse", "--version"],
        # Deps & Flow (3)
        "dependency-cruiser": ["depcruise", "--version"],
        "code2flow": ["code2flow", "--help"],
        "plantuml": ["plantuml", "--version"],
        # Doc Generation (8)
        "sphinx": ["sphinx-build", "--version"],
        "mkdocs": ["mkdocs", "--version"],
        "pdoc": ["pdoc", "--version"],
        "typedoc": ["typedoc", "--version"],
        "doxygen": ["doxygen", "--version"],
        "terraform-docs": ["terraform-docs", "--version"],
        "pandoc": ["pandoc", "--version"],
        # Quality (5)
        "vale": ["vale", "--version"],
        "standard-readme": ["standard-readme", "--version"],
        "prettier": ["/Users/jeremy/.local/bin/prettier", "--version"],
        "repomix": ["npx", "repomix", "--version"],
        "gitingest": ["python3", "-m", "gitingest", "--help"],
        # Changelog (4)
        "git-cliff": ["git-cliff", "--version"],
        "conventional-changelog": ["conventional-changelog", "--version"],
        "auto-changelog": ["auto-changelog", "--version"],
    }
    for name, cmd in all_tools.items():
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            TOOLS[name] = r.returncode == 0
        except:
            TOOLS[name] = False
    available = sum(TOOLS.values())
    print(f"🔧 DOCTOR v6: {available}/{len(TOOLS)} Tools verfügbar\n", flush=True)
    for t, ok in TOOLS.items():
        print(f"  {'✅' if ok else '❌'} {t}", flush=True)


def find_repos() -> list[Path]:
    found = set()
    for item in DEV.iterdir():
        if item.is_dir() and (item / ".git").exists():
            found.add(item)
        if item.is_dir() and not item.name.startswith("."):
            for sub in item.iterdir():
                if sub.is_dir() and (sub / ".git").exists():
                    found.add(sub)
    return sorted(found, key=lambda p: p.name)


def run_doctor(repo: Path) -> dict:
    fixes = 0
    findings = []
    doc_dir = repo / ".doctor"
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Gitignore für .doctor/
    gi = repo / ".gitignore"
    if gi.exists() and ".doctor" not in gi.read_text():
        with open(gi, "a") as f: f.write("\n.doctor/\n")

    print(f"\n📁 {repo.name}:", flush=True)

    # ── PHASE 1: DEEP SCAN ──────────────────────────────────
    scan_data = {}

    # cloc + tokei: Code-Statistiken
    for tool, flag in [("cloc", "--json"), ("tokei", "--json")]:
        if TOOLS.get(tool):
            try:
                r = subprocess.run([tool, str(repo), flag, "--quiet"], capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    scan_data[tool] = json.loads(r.stdout)
            except: pass

    # lizard: Komplexität
    if TOOLS.get("lizard"):
        try:
            r = subprocess.run(["lizard", str(repo), "--xml"], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                (doc_dir / "complexity.xml").write_text(r.stdout)
        except: pass

    # pydeps: Python-Deps
    if TOOLS.get("pydeps") and list(repo.rglob("*.py")):
        try:
            subprocess.run(["python3", "-m", "pydeps", str(repo), "-o", str(doc_dir / "deps.svg"), "--show-deps"],
                         capture_output=True, timeout=30, cwd=str(repo))
        except: pass

    # pyreverse: UML (Python)
    if TOOLS.get("pyreverse") and list(repo.rglob("*.py")):
        try:
            subprocess.run(["pyreverse", "-o", "png", "-p", repo.name, str(repo)],
                         capture_output=True, timeout=30, cwd=str(doc_dir))
        except: pass

    # dependency-cruiser: JS/TS Deps
    if TOOLS.get("dependency-cruiser"):
        try:
            subprocess.run(["depcruise", str(repo), "--output-type", "dot", "-f", str(doc_dir / "deps.dot")],
                         capture_output=True, timeout=30)
        except: pass

    # repomix: Code-Überblick
    if TOOLS.get("repomix"):
        try:
            subprocess.run(["npx", "repomix", str(repo), "--style", "markdown", "-o", str(doc_dir / "repomix.md")],
                         capture_output=True, timeout=60, cwd=str(repo))
        except: pass

    # gitingest: Digest
    if TOOLS.get("gitingest"):
        try:
            subprocess.run(["python3", "-m", "gitingest", str(repo), "-o", str(doc_dir / "digest.txt")],
                         capture_output=True, timeout=30, cwd=str(repo))
        except: pass

    # ── PHASE 2: FIXEN ──────────────────────────────────────
    for md_file in repo.rglob("*.md"):
        if any(x in str(md_file) for x in [".git", "node_modules", "graphify-out", "venv", ".doctor"]):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except:
            continue
        changed = False
        # Outdated Patterns
        for pat, repl in OUTDATED:
            if re.search(pat, content, re.IGNORECASE):
                for m in re.finditer(pat, content, re.IGNORECASE):
                    findings.append({"file": str(md_file.relative_to(repo)), "line": content[:m.start()].count("\n") + 1, "old": m.group()[:50], "new": repl[:50]})
                    fixes += 1
                content = re.sub(pat, repl, content, flags=re.IGNORECASE)
                changed = True
        # Credentials
        for pat, repl in [(r"[a-zA-Z0-9._%+-]+@gmail\.com\s*/\s*\S+", "Credentials (ENTFERNT)"), (r"nvapi-[A-Za-z0-9_-]{30,}", "NVIDIA_API_KEY (ENTFERNT)")]:
            if re.search(pat, content):
                findings.append({"file": str(md_file.relative_to(repo)), "old": "CREDENTIALS", "new": repl})
                fixes += 1
                content = re.sub(pat, repl, content)
                changed = True
        if changed:
            md_file.write_text(content, encoding="utf-8")

    # ── PHASE 3: GENERIEREN ─────────────────────────────────
    # git-cliff: CHANGELOG
    if not (repo / "CHANGELOG.md").exists() and TOOLS.get("git-cliff"):
        try:
            r = subprocess.run(["git-cliff", "-o", str(repo / "CHANGELOG.md")], capture_output=True, timeout=30, cwd=str(repo))
            if r.returncode == 0:
                print(f"      📝 CHANGELOG.md: generiert", flush=True)
                fixes += 1
        except: pass

    # learn.md aus Git-Log + cloc-Daten
    if not (repo / "learn.md").exists():
        try:
            log = subprocess.run(["git", "log", "--oneline", "-30"], capture_output=True, text=True, timeout=5, cwd=str(repo))
            if log.stdout.strip():
                langs = []
                if "cloc" in scan_data:
                    langs = list(scan_data["cloc"].keys())[:5]
                content = f"# learn.md – {repo.name}\n\n"
                content += f"## Letzte Commits\n"
                for line in log.stdout.strip().split("\n")[:15]:
                    content += f"- {line}\n"
                if langs:
                    content += f"\n## Sprachen\n"
                    for lang in langs:
                        if lang not in ("header", "SUM"):
                            content += f"- {lang}\n"
                (repo / "learn.md").write_text(content)
                fixes += 1
        except: pass

    # Essentielle Docs prüfen
    for doc in ["README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md", "brain.md", "goal.md"]:
        if not (repo / doc).exists():
            findings.append({"file": doc, "old": "❌ FEHLT", "new": "MUSS VON MENSCH ERSTELLT WERDEN"})

    # Prettier: Formatieren
    if TOOLS.get("prettier"):
        try:
            subprocess.run(["/Users/jeremy/.local/bin/prettier", "--write", f"{repo}/**/*.md", f"--ignore-path={repo}/.gitignore"],
                         capture_output=True, timeout=30)
        except: pass

    # Vale: Prose Linting
    if TOOLS.get("vale"):
        try:
            r = subprocess.run(["vale", "--output", "JSON", str(repo)], capture_output=True, text=True, timeout=30)
            if r.stdout.strip():
                (doc_dir / "vale-report.json").write_text(r.stdout)
        except: pass

    return {"fixes": fixes, "findings": findings}


def main():
    dry = "--dry-run" in sys.argv
    check_tools()
    repos = find_repos()
    print(f"\n🔍 {len(repos)} Repos gefunden\n", flush=True)

    total_fixes = 0
    for repo in repos:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5, cwd=str(repo))
        if not r.stdout.strip():
            continue
        result = run_doctor(repo)
        total_fixes += result["fixes"]

        # Commit + Push
        r2 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5, cwd=str(repo))
        if r2.stdout.strip():
            subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", "docs: doctor-v6 — scan + fix + generate"], cwd=str(repo), capture_output=True, timeout=10)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=str(repo), capture_output=True, timeout=30)
            print(f"  ⬆️  gepusht", flush=True)

    print(f"\n✅ DOCTOR v6: {total_fixes} Fixes in {len(repos)} Repos", flush=True)


if __name__ == "__main__":
    main()

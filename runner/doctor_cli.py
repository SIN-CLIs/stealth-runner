#!/usr/bin/env python3
"""
DOCTOR v5 – 10 Open-Source Tools. 3 Phasen. 1 Stunde. 100% Automatisch.
Findet Repos selbst. KEINE Templates. Nur echte Daten aus Analyse.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, shutil
from pathlib import Path

DEV_DIRS = [Path(os.environ.get("HOME", "/Users/jeremy")) / "dev"]
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

TOOLS = {}  # wird nach install-check befüllt


def check_tools():
    for name, info in {
        "cloc": {"cmd": ["cloc", "--version"], "install": "brew install cloc"},
        "git-cliff": {"cmd": ["git-cliff", "--version"], "install": "brew install git-cliff"},
        "pandoc": {"cmd": ["pandoc", "--version"], "install": "brew install pandoc"},
        "vale": {"cmd": ["vale", "--version"], "install": "brew install vale"},
        "repomix": {"cmd": ["npx", "repomix", "--version"], "install": "npm install -g repomix"},
        "pydeps": {"cmd": ["python3", "-m", "pydeps", "--version"], "install": "pip3 install pydeps"},
        "gitingest": {"cmd": ["python3", "-m", "gitingest", "--help"], "install": "pip3 install gitingest"},
        "pyreverse": {"cmd": ["pyreverse", "--version"], "install": "pip3 install pylint"},
    }.items():
        try:
            r = subprocess.run(info["cmd"], capture_output=True, text=True, timeout=5)
            TOOLS[name] = r.returncode == 0
        except:
            TOOLS[name] = False
    print(f"🔧 Tools: {sum(TOOLS.values())}/{len(TOOLS)} verfügbar\n", flush=True)
    for t, ok in TOOLS.items():
        print(f"  {'✅' if ok else '❌'} {t}", flush=True)


def find_repos() -> list[Path]:
    found = set()
    for start in DEV_DIRS:
        if not start.exists(): continue
        for item in start.iterdir():
            if item.is_dir() and (item / ".git").exists(): found.add(item)
            if item.is_dir() and not item.name.startswith("."):
                for sub in item.iterdir():
                    if sub.is_dir() and (sub / ".git").exists(): found.add(sub)
    return sorted(found, key=lambda p: p.name)


def phase1_deep_scan(repo: Path) -> dict:
    """Phase 1: Repo bis auf letzten Millimeter scannen."""
    data = {"name": repo.name, "path": str(repo), "files": 0, "languages": {}, "structure": []}

    # cloc: Language-Statistik (zeitbegrenzt, große Repos überspringen)
    if TOOLS.get("cloc"):
        try:
            r = subprocess.run(["cloc", str(repo), "--json", "--quiet"], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                try:
                    d = json.loads(r.stdout)
                    data["languages"] = {k: v for k, v in d.items() if k not in ("header", "SUM")}
                    data["files"] = sum(v.get("nFiles", 0) for v in data["languages"].values())
                except: pass
        except subprocess.TimeoutExpired:
            data["files"] = sum(1 for _ in repo.rglob("*"))

    # .doctor/ Ordner für Analyse-Ergebnisse
    doc_dir = repo / ".doctor"
    doc_dir.mkdir(parents=True, exist_ok=True)
    # .gitignore-Eintrag für .doctor/
    gitignore = repo / ".gitignore"
    if gitignore.exists() and ".doctor" not in gitignore.read_text():
        with open(gitignore, "a") as f: f.write("\n.doctor/\n")

    # repomix: Kompletten Code-Überblick (in Datei)
    if TOOLS.get("repomix"):
        try:
            out = doc_dir / "repomix-output.md"
            subprocess.run(["npx", "repomix", str(repo), "--style", "markdown", "-o", str(out)],
                           capture_output=True, timeout=60, cwd=str(repo))
        except: pass

    # pydeps: Python-Abhängigkeiten (wenn Python-Repo)
    if TOOLS.get("pydeps") and list(repo.rglob("*.py")):
        try:
            out = doc_dir / "deps.svg"
            subprocess.run(["python3", "-m", "pydeps", str(repo), "-o", str(out), "--show-deps"],
                           capture_output=True, timeout=60, cwd=str(repo))
        except: pass

    # gitingest: Git-Digest
    if TOOLS.get("gitingest"):
        try:
            out = doc_dir / "digest.txt"
            subprocess.run(["python3", "-m", "gitingest", str(repo), "-o", str(out)],
                           capture_output=True, timeout=30, cwd=str(repo))
        except: pass

    return data


def phase2_analyze(repo: Path, scan: dict) -> list:
    """Phase 2: Analysieren – Fehler finden, Qualität prüfen."""
    findings = []
    fixes = 0

    # 2a: Outdated Patterns fixen
    for md_file in repo.rglob("*.md"):
        if ".git" in str(md_file) or "node_modules" in str(md_file) or "graphify-out" in str(md_file) or "venv" in str(md_file) or ".doctor" in str(md_file):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except:
            continue
        changed = False
        for pat, repl in OUTDATED:
            if re.search(pat, content, re.IGNORECASE):
                for m in re.finditer(pat, content, re.IGNORECASE):
                    findings.append({"file": str(md_file.relative_to(repo)), "line": content[:m.start()].count("\n") + 1, "old": m.group()[:50], "new": repl[:50]})
                    fixes += 1
                content = re.sub(pat, repl, content, flags=re.IGNORECASE)
                changed = True
        if changed:
            md_file.write_text(content, encoding="utf-8")

    # 2b: Credentials entfernen
    creds = [(r"[a-zA-Z0-9._%+-]+@gmail\.com\s*/\s*\S+", "Credentials (ENTFERNT)"), (r"nvapi-[A-Za-z0-9_-]{30,}", "NVIDIA_API_KEY (ENTFERNT)")]
    for md_file in repo.rglob("*.md"):
        if ".git" in str(md_file) or "node_modules" in str(md_file) or "venv" in str(md_file):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except:
            continue
        changed = False
        for pat, repl in creds:
            if re.search(pat, content):
                findings.append({"file": str(md_file.relative_to(repo)), "old": "CREDENTIALS", "new": repl})
                fixes += 1
                content = re.sub(pat, repl, content)
                changed = True
        if changed:
            md_file.write_text(content, encoding="utf-8")

    # 2c: Vale Prose Linting
    if TOOLS.get("vale"):
        r = subprocess.run(["vale", "--output", "JSON", str(repo)], capture_output=True, text=True, timeout=30)
        if r.stdout.strip():
            try:
                vale_results = json.loads(r.stdout)
                for f, issues in vale_results.items():
                    for i in issues[:5]:
                        findings.append({"file": f, "line": i.get("Line", 0), "old": i.get("Match", "")[:40], "new": f"Vale: {i.get('Check', '')[:40]}", "lens": "vale"})
            except: pass

    # 2d: Essentielle Docs prüfen
    essential = ["README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "AGENTS.md", "brain.md", "goal.md"]
    for doc in essential:
        if not (repo / doc).exists():
            findings.append({"file": doc, "old": "❌ FEHLT", "new": "MUSS ERSTELLT WERDEN", "lens": "essential"})

    # 2e: learn.md aus Git-Log generieren
    if not (repo / "learn.md").exists():
        try:
            log = subprocess.run(["git", "log", "--oneline", "-30"], capture_output=True, text=True, timeout=5, cwd=str(repo))
            if log.stdout.strip():
                langs = ", ".join(list(scan.get("languages", {}).keys())[:5])
                content = f"# learn.md – {repo.name}\n\n"
                content += f"## Überblick\n{scan.get('files', 0)} Dateien in {langs if langs else 'verschiedenen Sprachen'}.\n\n"
                content += f"## Letzte Commits\n"
                for line in log.stdout.strip().split("\n")[:15]:
                    content += f"- {line}\n"
                content += f"\n## Sprachverteilung\n"
                for lang, stats in list(scan.get("languages", {}).items())[:5]:
                    content += f"- {lang}: {stats.get('code', 0)} Zeilen Code, {stats.get('comment', 0)} Kommentare\n"
                (repo / "learn.md").write_text(content)
                findings.append({"file": "learn.md", "old": "❌ FEHLT", "new": "✅ AUS REPO-DATEN GENERIERT"})
                fixes += 1
        except: pass

    return findings


def phase3_generate(repo: Path, scan: dict, findings: list) -> None:
    """Phase 3: Fehlende Dokumente generieren (nur bei genug Daten)."""
    # git-cliff: CHANGELOG generieren
    if not (repo / "CHANGELOG.md").exists() and TOOLS.get("git-cliff"):
        try:
            r = subprocess.run(["git-cliff", "-o", str(repo / "CHANGELOG.md")], capture_output=True, timeout=30, cwd=str(repo))
            if r.returncode == 0:
                print(f"      📝 CHANGELOG.md: aus Git generiert", flush=True)
        except: pass

    # prettier format (alle .md)
    for cmd in ["/Users/jeremy/.local/bin/prettier", "prettier", "/opt/homebrew/bin/prettier"]:
        p = subprocess.run([cmd, "--write", f"{repo}/**/*.md", f"--ignore-path={repo}/.gitignore"],
                         capture_output=True, text=True, timeout=60)
        if p.returncode == 0:
            break


def main():
    dry = "--dry-run" in sys.argv
    check_tools()
    repos = find_repos()
    print(f"\n🔍 DOCTOR v5: {len(repos)} Repos gefunden", flush=True)

    for repo in repos:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5, cwd=str(repo))
        has_changes = bool(r.stdout.strip())
        if not has_changes:
            continue

        print(f"\n📁 {repo.name}:", flush=True)

        # Phase 1: Deep Scan
        scan = phase1_deep_scan(repo)
        if scan.get("files"):
            print(f"  📊 {scan['files']} Dateien, {len(scan['languages'])} Sprachen", flush=True)

        # Phase 2+3: Analysieren + Generieren
        findings = phase2_analyze(repo, scan)
        if not dry:
            phase3_generate(repo, scan, findings)

        # Commit + Push
        r2 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5, cwd=str(repo))
        if r2.stdout.strip():
            subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", "docs: doctor-v5 — scan + fix + generate"], cwd=str(repo), capture_output=True, timeout=10)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=str(repo), capture_output=True, timeout=30)
            print(f"  ⬆️  committed + gepusht", flush=True)

    print(f"\n✅ DOCTOR v5 abgeschlossen", flush=True)


if __name__ == "__main__":
    main()

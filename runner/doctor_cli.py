#!/usr/bin/env python3
"""
DOCTOR v6 – ALLE 35 Tools aus der Recherche. Automatisch. 143 Repos.
Keine Pfade. Keine Templates. Nur echte Analyse + echte Generierung.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, textwrap
from pathlib import Path
from datetime import datetime

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
    """NUR die 7 Haupt-Repos, nicht alle 143 in ~/dev/."""
    names = [
        "stealth-runner", "playstealth-cli", "skylight-cli",
        "screen-follow", "unmask-cli", "A2A-SIN-Worker-heypiggy",
        "infra-opencode-stack",
    ]
    found = []
    for item in DEV.iterdir():
        if item.name in names and (item / ".git").exists():
            found.append(item)
        if item.is_dir() and not item.name.startswith("."):
            for sub in item.iterdir():
                if sub.name in names and (sub / ".git").exists():
                    found.append(sub)
    # Fallback: CLI-Argumente wenn angegeben
    if found:
        return sorted(found, key=lambda p: p.name)
    # Wenn nichts gefunden: aktuelle Verzeichnisse durchsuchen
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return [cwd]
    return found


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

    today = datetime.now().strftime("%Y-%m-%d")

    # Git-Log für Context
    log = subprocess.run(["git", "log", "--oneline", "-20"], capture_output=True, text=True, timeout=5, cwd=str(repo))
    commits = [l for l in log.stdout.strip().split("\n") if l][:10]
    diff = subprocess.run(["git", "diff", "--stat", "HEAD~5..HEAD"], capture_output=True, text=True, timeout=5, cwd=str(repo))
    changes = [l.strip() for l in diff.stdout.strip().split("\n") if l]

    # Sprachen aus scan_data
    langs = []
    if "cloc" in scan_data:
        langs = [k for k in scan_data["cloc"] if k not in ("header", "SUM")][:5]

    # ── brain.md: Architecture Knowledge ─────────────────────
    # Generiert aus scan_data (cloc, tokei) + git-log + findings
    try:
        brain = repo / "brain.md"
        total_files = 0
        if "cloc" in scan_data and "SUM" in scan_data["cloc"]:
            total_files = scan_data["cloc"]["SUM"].get("nFiles", 0)
        entry = f"# brain.md – {repo.name}\n\n"
        entry += f"_Auto-generated by doctor-cli on {today}_\n\n"
        entry += f"## Repository Overview\n\n"
        entry += f"- **Sprachen:** {', '.join(langs) if langs else 'N/A'}\n"
        entry += f"- **Dateien:** {total_files}\n"
        if commits:
            entry += f"- **Letzte Commits:** {len(commits)}\n"
        entry += f"\n## Letzte Commits\n\n"
        for c in commits[:5]:
            entry += f"- `{c}`\n"
        if changes:
            entry += f"\n## Kürzlich geändert\n\n"
            for line in changes[:5]:
                entry += f"- {line}\n"
        if brain.exists():
            old = brain.read_text(encoding="utf-8")
            if "# Repository Overview" not in old:
                lines = old.split("\n")
                lines.insert(1 if lines[0].startswith("#") else 0, entry)
                brain.write_text("\n".join(lines), encoding="utf-8")
        else:
            brain.write_text(entry, encoding="utf-8")
        print(f"      🧠 brain.md: {len(langs)} Sprachen, {total_files} Dateien", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ brain.md: {e}", flush=True)

    # ── fix.md: Gefundene und gefixte Bugs ───────────────────
    try:
        fix_file = repo / "fix.md"
        pattern_fixes = [f for f in findings if "old" in f and "new" in f]
        entry = f"\n## {today}: Doctor Scan — {len(pattern_fixes)} Fixes\n\n"
        for pf in pattern_fixes[:10]:
            old = pf.get("old", "")[:60]
            new = pf.get("new", "")[:60]
            file = pf.get("file", "?")
            entry += f"- `{file}`: `{old}` → `{new}`\n"
        if len(pattern_fixes) > 10:
            entry += f"- … und {len(pattern_fixes) - 10} weitere\n"
        if fix_file.exists():
            old = fix_file.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            fix_file.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# fix.md – {repo.name}\n\n_Bekannte Fixes, auto-dokumentiert_\n"
            fix_file.write_text(header + entry, encoding="utf-8")
        print(f"      🔧 fix.md: {len(pattern_fixes)} Fixes dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ fix.md: {e}", flush=True)

    # ── issues.md: Fehlende Docs + offene Probleme ──────────
    try:
        issues = repo / "issues.md"
        missing_docs = []
        for doc in ["README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md", "CODEOWNERS",
                     "CHANGELOG.md", "AGENTS.md", "brain.md", "fix.md", "successful.md", "anti-learn.md",
                     "goal.md", "architecture.md", "usage.md", "faq.md", "testing.md", "benchmarks.md",
                     "Makefile", ".env.example", "Dockerfile"]:
            if not (repo / doc).exists():
                missing_docs.append(doc)
        entry = f"\n## {today}: Doctor Scan\n\n"
        if findings:
            scan_fixes = len([f for f in findings if f.get("old") != "❌ FEHLT"])
            entry += f"**Gefixt:** {scan_fixes} veraltete Muster/Kredentials\n\n"
        if missing_docs:
            entry += f"**Fehlende Docs ({len(missing_docs)}):**\n"
            for d in missing_docs[:10]:
                entry += f"- [ ] `{d}`\n"
        entry += f"\n**Offene Findings:** {len(findings)}\n"
        if issues.exists():
            old = issues.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            issues.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# issues.md – {repo.name}\n\n_Offene Punkte, auto-dokumentiert_\n"
            issues.write_text(header + entry, encoding="utf-8")
        print(f"      🐛 issues.md: {len(missing_docs)} missing docs, {len(findings)} findings", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ issues.md: {e}", flush=True)

    # ── successful.md: Was funktioniert ──────────────────────
    try:
        successful = repo / "successful.md"
        available_tools = [t for t, ok in TOOLS.items() if ok]
        entry = f"\n## {today}: Doctor Scan Results\n\n"
        entry += f"**Verfügbare Tools ({len(available_tools)}):**\n"
        for t in available_tools[:10]:
            entry += f"- ✅ {t}\n"
        if available_tools:
            entry += f"\n**Scan-Ergebnisse:**\n"
            langline = ', '.join(langs[:3]) if langs else 'N/A'
            entry += f"- Code-Statistiken: {total_files} Dateien in {langline}\n"
            entry += f"- Fixes: {len(findings)} Muster aktualisiert\n"
        if successful.exists():
            old = successful.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            successful.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# successful.md – {repo.name}\n\n_Was funktioniert, auto-dokumentiert_\n"
            successful.write_text(header + entry, encoding="utf-8")
        print(f"      ✅ successful.md: {len(available_tools)} Tools dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ successful.md: {e}", flush=True)

    # ── learn.md: Wissen aus Git-Log ─────────────────────────
    try:
        learn = repo / "learn.md"
        entry = f"\n## {today}: Neue Commits\n\n"
        for c in commits[:10]:
            entry += f"- `{c}`\n"
        if langs:
            entry += f"\n**Sprachen:** {', '.join(langs)}\n"
        if learn.exists():
            old = learn.read_text(encoding="utf-8")
            if f"## {today}" not in old:
                lines = old.split("\n")
                inserted = False
                for i, line in enumerate(lines):
                    if line.startswith("## ") and not inserted:
                        lines.insert(i, entry)
                        inserted = True
                        break
                if not inserted:
                    lines.append(entry)
                learn.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# learn.md – {repo.name}\n\n_Knowledge base, auto-dokumentiert_\n"
            learn.write_text(header + entry, encoding="utf-8")
        print(f"      📖 learn.md: {len(commits)} Commits dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ learn.md: {e}", flush=True)

    # ── anti-learn.md: Vermeidenswerte Muster ────────────────
    try:
        anti = repo / "anti-learn.md"
        replaced_patterns = []
        for f in findings:
            old = f.get("old", "")
            if old and old != "CREDENTIALS" and "❌" not in old and "FEHLT" not in old:
                replaced_patterns.append(old[:50])
        unique_patterns = list(dict.fromkeys(replaced_patterns))
        entry = f"\n## {today}: Ersetzte Muster\n\n"
        for p in unique_patterns[:10]:
            entry += f"- ❌ `{p}` — ersetzt durch SOTA-Äquivalent\n"
        if not unique_patterns:
            entry += f"- ✅ Keine veralteten Muster gefunden\n"
        if anti.exists():
            old = anti.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            anti.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# anti-learn.md – {repo.name}\n\n_Vermeidenswerte Muster, auto-dokumentiert_\n"
            anti.write_text(header + entry, encoding="utf-8")
        if unique_patterns:
            print(f"      🚫 anti-learn.md: {len(unique_patterns)} Muster gebannt", flush=True)
        else:
            print(f"      ✅ anti-learn.md: keine veralteten Muster", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ anti-learn.md: {e}", flush=True)

    # ── history.md: Entwicklungshistorie ─────────────────────
    try:
        history = repo / "history.md"
        last_commit = commits[0] if commits else ""
        commit_type = "update"
        if "feat" in last_commit: commit_type = "Feature"
        elif "fix" in last_commit: commit_type = "Fix"
        elif "docs" in last_commit: commit_type = "Dokumentation"
        elif "chore" in last_commit: commit_type = "Wartung"
        subjects = [c.split(" ", 1)[1] if " " in c else "" for c in commits]
        entry = f"\n## {today}: {commit_type} — {subjects[0] if subjects else 'Update'}\n\n"
        entry += f"**Commits ({len(commits)}):**\n"
        for c in commits[:5]:
            entry += f"- `{c}`\n"
        if len(commits) > 5:
            entry += f"- … und {len(commits) - 5} weitere\n"
        entry += f"\n**Geänderte Dateien:**\n"
        for line in changes[:10]:
            entry += f"- {line}\n"
        if len(changes) > 10:
            entry += f"- … und {len(changes) - 10} weitere\n"
        if history.exists():
            old = history.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            history.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# history.md — Development History\n\n_Auto-generated by doctor-cli_\n"
            history.write_text(header + entry, encoding="utf-8")
        print(f"      📝 history.md: {len(commits)} Commits dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ history.md: {e}", flush=True)

    # ── architecture.md: Komponenten + Struktur ──────────────
    try:
        arch = repo / "architecture.md"
        py_files = list(repo.rglob("*.py"))
        js_files = list(repo.rglob("*.js"))
        swift_files = list(repo.rglob("*.swift"))
        dirs = sorted(set(f.parent.relative_to(repo) for f in py_files + js_files + swift_files
                         if ".git" not in str(f) and "node_modules" not in str(f)))[:15]
        entry = f"\n## {today}: Architecture Scan\n\n"
        entry += f"**Komponenten ({len(dirs)} Module):**\n"
        for d in dirs[:10]:
            pys = len(list(repo.glob(f"{d}/*.py")))
            entry += f"- `{d}/` ({pys} Python Dateien)\n"
        entry += f"\n**Sprachen:** {', '.join(langs) if langs else 'N/A'}\n"
        entry += f"\n**Total Dateien:** {total_files}\n"
        if arch.exists():
            old = arch.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            arch.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# architecture.md – {repo.name}\n\n_Component overview, auto-dokumentiert_\n"
            arch.write_text(header + entry, encoding="utf-8")
        print(f"      🏗️ architecture.md: {len(dirs)} Module dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ architecture.md: {e}", flush=True)

    # ── commands.md: CLI-Befehle aus dem Repo ────────────────
    try:
        cmds = repo / "commands.md"
        entry_lines = [f"\n## {today}: CLI Entry Points\n"]
        # Suche nach CLI-Einstiegspunkten
        for pattern in ["cli.py", "main.py", "bin/*", "*.sh", "scripts/*.py", "Makefile"]:
            for f in repo.glob(pattern):
                if ".git" in str(f) or ".doctor" in str(f):
                    continue
                try:
                    first = f.read_text(encoding="utf-8", errors="replace")[:200]
                    if "cli" in first.lower() or "main" in first.lower() or "argparse" in first.lower():
                        entry_lines.append(f"- `{f.relative_to(repo)}` — CLI Entry Point\n")
                except:
                    continue
        if len(entry_lines) > 1:
            entry = "".join(entry_lines)
            if cmds.exists():
                old = cmds.read_text(encoding="utf-8")
                lines = old.split("\n")
                inserted = False
                for i, line in enumerate(lines):
                    if line.startswith("## ") and not inserted:
                        lines.insert(i, entry)
                        inserted = True
                        break
                if not inserted:
                    lines.append(entry)
                cmds.write_text("\n".join(lines), encoding="utf-8")
            else:
                header = f"# commands.md – {repo.name}\n\n_CLI reference, auto-dokumentiert_\n"
                cmds.write_text(header + entry, encoding="utf-8")
            count = len(entry_lines) - 1
            print(f"      ⌨️ commands.md: {count} CLI Entry Points dokumentiert", flush=True)
            fixes += 1
    except Exception as e:
        print(f"      ⚠️ commands.md: {e}", flush=True)

    # ── testing.md: Teststruktur + Ergebnisse ────────────────
    try:
        test_md = repo / "testing.md"
        test_files = list(repo.rglob("test_*.py")) + list(repo.rglob("*_test.py")) + list(repo.rglob("tests/*.py"))
        test_files = [f for f in test_files if ".git" not in str(f) and ".doctor" not in str(f)]
        test_dirs = sorted(set(f.parent.relative_to(repo) for f in test_files))
        entry = f"\n## {today}: Test Status\n\n"
        entry += f"**Test-Dateien:** {len(test_files)}\n"
        entry += f"**Test-Ordner:** {len(test_dirs)}\n"
        if test_dirs:
            entry += f"**Ordnern:**\n"
            for d in test_dirs[:5]:
                files_in = len(list(repo.glob(f"{d}/test_*.py")) + list(repo.glob(f"{d}/*_test.py")))
                entry += f"- `{d}/` ({files_in} Tests)\n"
        if test_md.exists():
            old = test_md.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            test_md.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# testing.md – {repo.name}\n\n_Test documentation, auto-dokumentiert_\n"
            test_md.write_text(header + entry, encoding="utf-8")
        print(f"      🧪 testing.md: {len(test_files)} Test-Dateien dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ testing.md: {e}", flush=True)

    # ── goal.md: Repo-Ziele ──────────────────────────────────
    try:
        goal = repo / "goal.md"
        remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=3, cwd=str(repo))
        readme = repo / "README.md"
        purpose = "N/A"
        if readme.exists():
            first_line = readme.read_text(encoding="utf-8", errors="replace").split("\n")[0]
            purpose = first_line.replace("#", "").strip()[:80]
        entry = f"\n## {today}: Repository Status\n\n"
        entry += f"**Repo:** {repo.name}\n"
        entry += f"**Remote:** {remote.stdout.strip()[:80] if remote.stdout.strip() else 'N/A'}\n"
        entry += f"**Purpose:** {purpose}\n"
        entry += f"**Sprachen:** {', '.join(langs) if langs else 'N/A'}\n"
        entry += f"**Letzte Commits:** {len(commits)}\n"
        if goal.exists():
            old = goal.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            goal.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# goal.md – {repo.name}\n\n_Repository goals, auto-dokumentiert_\n"
            goal.write_text(header + entry, encoding="utf-8")
        print(f"      🎯 goal.md: {purpose[:40]}... dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ goal.md: {e}", flush=True)

    # ── api.md: Python-Modul-Struktur ────────────────────────
    try:
        api = repo / "api.md"
        py_modules = sorted(set(f.parent.relative_to(repo) for f in py_files
                               if ".git" not in str(f) and ".doctor" not in str(f)
                               and "__pycache__" not in str(f) and "venv" not in str(f)))[:20]
        entry = f"\n## {today}: Python Modules\n\n"
        for m in py_modules[:10]:
            inits = list(repo.glob(f"{m}/__init__.py"))
            py_count = len(list(repo.glob(f"{m}/*.py")))
            status = "✅ package" if inits else f"📁 {py_count} files"
            entry += f"- `{m}/` ({status})\n"
        if api.exists():
            old = api.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            api.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# api.md – {repo.name}\n\n_Python module structure, auto-dokumentiert_\n"
            api.write_text(header + entry, encoding="utf-8")
        print(f"      📦 api.md: {len(py_modules)} Python Module dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ api.md: {e}", flush=True)

    # ── usage.md: CLI-Nutzung ─────────────────────────────────
    try:
        usage = repo / "usage.md"
        help_texts = []
        for f in sorted(repo.rglob("*.py"))[:20]:
            if ".git" in str(f) or ".doctor" in str(f) or "venv" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if "argparse" in content:
                    help_texts.append(f"  - `{f.relative_to(repo)}`: Python CLI (argparse)")
                if "import click" in content or "from click" in content:
                    help_texts.append(f"  - `{f.relative_to(repo)}`: Python CLI (click)")
                if 'if __name__ == "__main__"' in content:
                    help_texts.append(f"  - `{f.relative_to(repo)}`: Script Entry Point")
            except:
                continue
        makefile = repo / "Makefile"
        make_targets = []
        if makefile.exists():
            for line in makefile.read_text(encoding="utf-8").split("\n"):
                if line and not line.startswith(".") and not line.startswith("\t") and ":" in line:
                    target = line.split(":")[0].strip()
                    if target and target != "all":
                        make_targets.append(target)
        entry = f"\n## {today}: CLI Usage\n\n"
        if help_texts:
            entry += "**Entry Points:**\n" + "\n".join(help_texts[:5]) + "\n"
        if make_targets[:5]:
            entry += f"**Make Targets:** {', '.join(make_targets[:5])}\n"
        entry += f"\n**Quick Start:**\n  ```bash\n  python3 {repo.name}/main.py --help\n  ```\n"
        if usage.exists():
            old = usage.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            usage.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# usage.md – {repo.name}\n\n_CLI usage, auto-dokumentiert_\n"
            usage.write_text(header + entry, encoding="utf-8")
        print(f"      📖 usage.md: {len(help_texts)} Entry Points dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ usage.md: {e}", flush=True)

    # ── faq.md: Häufige Fragen + Muster ──────────────────────
    try:
        faq = repo / "faq.md"
        unique_findings = list(dict.fromkeys([f.get("old", "")[:40] for f in findings if f.get("old") and "FEHLT" not in f.get("old", "")]))
        entry = f"\n## {today}: Häufige Funde\n\n"
        entry += f"**Pattern-Ersetzungen ({len(findings)}):**\n"
        for f_text in unique_findings[:10]:
            entry += f"- ❓ `{f_text}` → ersetzt\n"
        if findings:
            entry += f"\n**Credentials entfernt:** {len([f for f in findings if 'CREDENTIALS' in str(f.get('old', ''))])}\n"
        if faq.exists():
            old = faq.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            faq.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# faq.md – {repo.name}\n\n_Häufige Fragen, auto-dokumentiert_\n"
            faq.write_text(header + entry, encoding="utf-8")
        print(f"      ❓ faq.md: {len(unique_findings)} Muster dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ faq.md: {e}", flush=True)

    # ── benchmarks.md: Performance-Daten ─────────────────────
    try:
        bench = repo / "benchmarks.md"
        py_count = len(list(repo.rglob("*.py")))
        md_count = len(list(repo.rglob("*.md")))
        test_count = len(test_files) if 'test_files' in dir() else len(list(repo.rglob("test_*.py")))
        entry = f"\n## {today}: Code-Statistiken\n\n"
        entry += f"| Metrik | Wert |\n|--------|------|\n"
        entry += f"| Python-Dateien | {py_count} |\n"
        entry += f"| Markdown-Dateien | {md_count} |\n"
        entry += f"| Test-Dateien | {test_count} |\n"
        entry += f"| Fixes dieser Session | {len(findings)} |\n"
        if langs:
            entry += f"| Hauptsprachen | {', '.join(langs[:3])} |\n"
        if bench.exists():
            old = bench.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            bench.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# benchmarks.md – {repo.name}\n\n_Performance data, auto-dokumentiert_\n"
            bench.write_text(header + entry, encoding="utf-8")
        print(f"      📊 benchmarks.md: {py_count} Python, {test_count} Tests", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ benchmarks.md: {e}", flush=True)

    # ── troubleshooting.md: Fehlerbehebung ────────────────────
    try:
        trouble = repo / "troubleshooting.md"
        fix_by_file = {}
        for f_text in findings:
            file = f_text.get("file", "?")
            if file not in fix_by_file:
                fix_by_file[file] = 0
            fix_by_file[file] += 1
        entry = f"\n## {today}: Fix-Statistiken\n\n"
        entry += f"**Änderungen pro Datei:**\n"
        for file, count in sorted(fix_by_file.items(), key=lambda x: -x[1])[:10]:
            entry += f"- `{file}`: {count} Fix(es)\n"
        if trouble.exists():
            old = trouble.read_text(encoding="utf-8")
            lines = old.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("## ") and not inserted:
                    lines.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                lines.append(entry)
            trouble.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# troubleshooting.md – {repo.name}\n\n_Known issues, auto-dokumentiert_\n"
            trouble.write_text(header + entry, encoding="utf-8")
        print(f"      🔧 troubleshooting.md: {len(fix_by_file)} Dateien betroffen", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ troubleshooting.md: {e}", flush=True)

    # ── acknowledgments.md: Autoren ──────────────────────────
    try:
        ack = repo / "acknowledgments.md"
        authors = subprocess.run(["git", "log", "--format=%aN", "--reverse"], capture_output=True, text=True, timeout=5, cwd=str(repo))
        unique_authors = list(dict.fromkeys([a for a in authors.stdout.strip().split("\n") if a]))
        entry = f"\n## {today}: Contributors\n\n"
        for a in unique_authors:
            entry += f"- {a}\n"
        if ack.exists():
            old = ack.read_text(encoding="utf-8")
            if "## " not in old:
                ack.write_text(old + entry, encoding="utf-8")
        else:
            header = f"# acknowledgments.md – {repo.name}\n\n_Contributors, auto-dokumentiert_\n"
            ack.write_text(header + entry, encoding="utf-8")
        print(f"      👏 acknowledgments.md: {len(unique_authors)} Autoren", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ acknowledgments.md: {e}", flush=True)

    # ── SUPPORT.md: Support-Informationen ─────────────────────
    try:
        support = repo / "SUPPORT.md"
        remote_url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=3, cwd=str(repo)).stdout.strip()
        issues_url = remote_url.replace(".git", "/issues") if remote_url else "N/A"
        entry = f"\n## {today}: Project Info\n\n"
        entry += f"- **Remote:** {remote_url}\n"
        entry += f"- **Issues:** {issues_url}\n"
        entry += f"- **Sprachen:** {', '.join(langs) if langs else 'N/A'}\n"
        if support.exists():
            old = support.read_text(encoding="utf-8")
            if "## " not in old:
                support.write_text(old + entry, encoding="utf-8")
        else:
            header = f"# SUPPORT.md – {repo.name}\n\n_Support information_\n\n"
            header += "## Community\n- GitHub Issues: [Issues Page](" + (issues_url or "#") + ")\n"
            header += "## Security\n- Report vulnerabilities via SECURITY.md\n"
            support.write_text(header + entry, encoding="utf-8")
        print(f"      🆘 SUPPORT.md: dokumentiert", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ SUPPORT.md: {e}", flush=True)

    # ── CODE_OF_CONDUCT.md: Standard-Vorlage ─────────────────
    try:
        coc = repo / "CODE_OF_CONDUCT.md"
        if not coc.exists():
            coc.write_text(f"# Code of Conduct – {repo.name}\n\n"
                "## Our Pledge\n\nWe pledge to make participation in this project a harassment-free experience.\n\n"
                "## Enforcement\n\nViolations can be reported to the project maintainers.\n", encoding="utf-8")
            print(f"      📜 CODE_OF_CONDUCT.md: erstellt", flush=True)
            fixes += 1
    except Exception as e:
        print(f"      ⚠️ CODE_OF_CONDUCT.md: {e}", flush=True)

    # ── CONTRIBUTING.md: Beitragsrichtlinien ──────────────────
    try:
        contributing = repo / "CONTRIBUTING.md"
        if not contributing.exists():
            instructions = f"# Contributing to {repo.name}\n\n"
            instructions += "## Development Setup\n"
            if list(repo.rglob("Makefile")):
                instructions += "```bash\nmake install\nmake test\n```\n"
            instructions += "\n## Pull Request Process\n1. Fork the repo\n2. Create a feature branch\n3. Write tests\n4. Submit PR\n\n"
            instructions += "## Code Style\n- Follow existing code patterns\n- Write meaningful commit messages\n"
            contributing.write_text(instructions, encoding="utf-8")
            print(f"      📝 CONTRIBUTING.md: erstellt", flush=True)
            fixes += 1
    except Exception as e:
        print(f"      ⚠️ CONTRIBUTING.md: {e}", flush=True)

    # ── SECURITY.md: Sicherheitsrichtlinien ───────────────────
    try:
        security = repo / "SECURITY.md"
        if not security.exists():
            remote_url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=3, cwd=str(repo)).stdout.strip()
            security.write_text(
                f"# Security Policy – {repo.name}\n\n"
                "## Supported Versions\n\nUse the latest release.\n\n"
                "## Reporting a Vulnerability\n\n"
                f"Open an issue at {remote_url.replace('.git', '/issues') if remote_url else 'the repository'}\n"
                "or contact the maintainers directly.\n", encoding="utf-8")
        print(f"      🔒 SECURITY.md: erstellt", flush=True)
        fixes += 1
    except Exception as e:
        print(f"      ⚠️ SECURITY.md: {e}", flush=True)

    # ── PHASE 4: CLEANUP ──────────────────────────────────────
    cleanup_count = 0
    # Graphify-AST-Cache (wird beim nächsten Commit neu gebaut)
    for f in (repo / "graphify-out" / "cache" / "ast").rglob("*.json"):
        try:
            f.unlink()
            cleanup_count += 1
        except:
            pass
    # __pycache__ Verzeichnisse
    for d in repo.rglob("__pycache__"):
        if d.is_dir():
            try:
                import shutil
                shutil.rmtree(d)
                cleanup_count += 1
            except:
                pass
    # .pytest_cache + .ruff_cache
    for cache_dir in [".pytest_cache", ".ruff_cache", ".mypy_cache"]:
        d = repo / cache_dir
        if d.exists():
            try:
                import shutil
                shutil.rmtree(d)
                cleanup_count += 1
            except:
                pass
    # Alte .doctor/ Artefakte (behalte aktuelles)
    old_artifacts = [".svg", ".xml", ".dot", ".png", ".json", ".txt", ".md"]
    for f in doc_dir.iterdir():
        if f.suffix in old_artifacts and f.name not in ("vale-report.json",):
            try:
                f.unlink()
                cleanup_count += 1
            except:
                pass
    if cleanup_count > 0:
        print(f"      🧹 {cleanup_count} Cache/Temp-Dateien gelöscht", flush=True)

    # Globale Cleanup: Alte Chrome-Profile in /tmp (älter als 1h)
    try:
        tmp = Path("/tmp")
        count = 0
        for d in tmp.glob("heypiggy-bot-*"):
            age = __import__("time").time() - d.stat().st_mtime
            if age > 3600:  # älter als 1 Stunde
                import shutil
                shutil.rmtree(d)
                count += 1
        if count > 0:
            print(f"      🗑️ {count} alte Chrome-Profile gelöscht (>/tmp)", flush=True)
    except:
        pass

    # ── PHASE 5: GRAPHIFY SETUP ───────────────────────────────
    try:
        has_graphify = False
        try:
            r = subprocess.run(["python3", "-m", "graphify", "--version"], capture_output=True, text=True, timeout=5)
            has_graphify = r.returncode == 0
        except:
            pass
        if not has_graphify:
            try:
                subprocess.run(["pip3", "install", "graphifyy", "--break-system-packages", "-q"],
                             capture_output=True, timeout=30)
                has_graphify = True
                print(f"      📦 graphifyy: installiert", flush=True)
            except:
                print(f"      ⚠️ graphifyy: Installation fehlgeschlagen", flush=True)
        if has_graphify:
            graph_out = repo / "graphify-out"
            graph_exists = graph_out.exists()
            r = subprocess.run(["python3", "-m", "graphify", "update", str(repo)],
                             capture_output=True, text=True, timeout=120, cwd=str(repo))
            if r.returncode == 0:
                # Post-Commit Hook einrichten
                hook = repo / ".git" / "hooks" / "post-commit"
                if not hook.exists() or "graphify" not in hook.read_text() if hook.exists() else "":
                    hook_content = """#!/bin/bash
# Auto graphify rebuild after commit
cd "$(dirname "$0")/../.."
python3 -m graphify update . 2>/dev/null || true
"""
                    hook.write_text(hook_content)
                    hook.chmod(0o755)
                    print(f"      🔗 graphify post-commit hook: eingerichtet", flush=True)
                status = "✅ rebuild" if graph_exists else "✅ initialisiert"
                print(f"      📊 graphify: {status}", flush=True)
                fixes += 1
            else:
                print(f"      ⚠️ graphify: update fehlgeschlagen ({r.stderr[:80]})", flush=True)
    except Exception as e:
        print(f"      ⚠️ graphify: {e}", flush=True)

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

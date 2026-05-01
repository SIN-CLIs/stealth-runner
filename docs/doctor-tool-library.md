# Doctor-Tool-Library – 23 SOTA Open-Source Tools

> **Automatische Dokumentation: Code-Analyse, Generierung, Qualität, Diagramme.**
> Alle 23 Tools werden via `infra-opencode-stack/install.sh` installiert und via `sin-sync` verteilt.

---

## 📊 1. Code-Statistiken (cloc, tokei)

| Tool | Stars | Install | Befehl | Ergebnis |
|------|-------|---------|--------|----------|
| **[cloc](https://github.com/AlDanial/cloc)** | ⭐20k | `brew install cloc` | `cloc . --json` | Zeilen pro Sprache |
| **[tokei](https://github.com/XAMPPRocky/tokei)** | ⭐12k | `brew install tokei` | `tokei .` | Schnelle Code-Stat |

### stealth-runner Ergebnisse
```json
{"Python": "3.536 Zeilen", "Markdown": "2.603 Zeilen", "BASH": "490 Zeilen", "C": "100 Zeilen"}
```

---

## 🧮 2. Code-Komplexität (lizard)

| Tool | Stars | Install | Befehl | Ergebnis |
|------|-------|---------|--------|----------|
| **[lizard](https://github.com/terryyin/lizard)** | ⭐5k | `brew install lizard` | `lizard . --xml` | NLOC, Zyklomatische Komplexität |

---

## 🔗 3. Abhängigkeitsanalyse (pydeps, pyreverse, dependency-cruiser, code2flow)

| Tool | Stars | Sprache | Install | Befehl | Ergebnis |
|------|-------|---------|---------|--------|----------|
| **[pydeps](https://github.com/thebjorn/pydeps)** | ⭐2.1k | Python | `pip install pydeps` | `pydeps . --show-deps` | SVG-Dependency-Graph |
| **[pyreverse](https://github.com/PyCQA/pylint)** | ⭐1.5k | Python | `pip install pylint` | `pyreverse -o png runner/` | UML-Klassendiagramm |
| **[dependency-cruiser](https://github.com/sverweij/dependency-cruiser)** | ⭐6.6k | JS/TS | `npm install -g dependency-cruiser` | `depcruise src --output-type dot` | JS-Dependency-Graph |
| **[code2flow](https://github.com/scottrogowski/code2flow)** | ⭐3k | Python/JS | `pip install code2flow` | `code2flow runner/ -o flow.png` | Flussdiagramme |

### Generierte Artefakte
- `classes_stealth_runner.png` – UML-Klassendiagramm (45 Module, 534KB)
- `packages_stealth_runner.png` – UML-Package-Diagramm
- `runner.svg` – Python-Dependency-Graph (pydeps)

---

## 🧬 4. UML-Diagramme (plantuml)

| Tool | Stars | Install | Befehl |
|------|-------|---------|--------|
| **[plantuml](https://github.com/plantuml/plantuml)** | ⭐10k | `brew install plantuml` | `plantuml diagram.puml` |

Wird via `dot -Tpng` aus pyreverse-DOT-Dateien genutzt.

---

## 📝 5. Dokumentationsgenerierung (sphinx, mkdocs, pdoc, typedoc, doxygen, terraform-docs, pandoc)

| Tool | Stars | Sprache | Install | Befehl | Ausgabe |
|------|-------|---------|---------|--------|---------|
| **[sphinx](https://github.com/sphinx-doc/sphinx)** | ⭐7.8k | Python | `pip install sphinx` | `sphinx-apidoc -o docs/ runner/` | HTML |
| **[mkdocs](https://github.com/mkdocs/mkdocs)** | ⭐20k | Python | `pip install mkdocs` | `mkdocs build` | HTML |
| **[pdoc](https://github.com/mitmproxy/pdoc)** | ⭐3k | Python | `pip install pdoc` | `pdoc runner -o docs/` | HTML |
| **[typedoc](https://github.com/TypeStrong/typedoc)** | ⭐8.4k | TypeScript | `npm install -g typedoc` | `typedoc src/` | HTML |
| **[doxygen](https://github.com/doxygen/doxygen)** | ⭐6.1k | C/C++ | `brew install doxygen` | `doxygen Doxyfile` | HTML |
| **[terraform-docs](https://github.com/terraform-docs/terraform-docs)** | ⭐4.8k | Terraform | `npm install -g terraform-docs` | `terraform-docs markdown .` | Markdown |
| **[pandoc](https://github.com/jgm/pandoc)** | ⭐36k | Universal | `brew install pandoc` | `pandoc README.md -o README.html` | HTML, PDF, EPUB |

### Aktiv für stealth-runner
- **pdoc**: `pdoc runner -o /tmp/stealth-api-docs` → API-Dokumentation
- **doxygen**: `doxygen /tmp/Doxyfile` → C-API-Docs für mac_eye (in `/tmp/doxygen/`)
- **pandoc**: README → HTML konvertiert

---

## ✅ 6. Qualität & Linting (vale, standard-readme, prettier, repomix, gitingest)

| Tool | Stars | Install | Befehl | Auto-Fix |
|------|-------|---------|--------|----------|
| **[vale](https://github.com/errata-ai/vale)** | ⭐7.4k | `brew install vale` | `vale README.md` | ❌ Report |
| **[standard-readme](https://github.com/RichardLitt/standard-readme)** | ⭐3k | `npm install -g standard-readme` | `standard-readme README.md` | ❌ Report |
| **[prettier](https://github.com/prettier/prettier)** | ⭐51.8k | `npm install -g prettier` | `prettier --write "**/*.md"` | ✅ Ja |
| **[repomix](https://github.com/repomix/repomix)** | ⭐24k | `npm install -g repomix` | `repomix .` | ❌ Report |
| **[gitingest](https://github.com/cyclotruc/gitingest)** | ⭐12k | `pip install gitingest` | `gitingest . -o digest.txt` | ❌ Report |

### Aktiv für stealth-runner
- **prettier**: Formatiert ALLE `.md` Dateien automatisch
- **standard-readme**: Erkannte: `README.md` Titel enthält Emoji (nicht standard-konform)
- **vale**: Prose-Linting auf Docs
- **gitingest**: 340 Dateien, 2.8M Tokens → `/tmp/repo_digest.txt` (9.6MB)

---

## 📋 7. CHANGELOG-Generierung (git-cliff, conventional-changelog, auto-changelog)

| Tool | Stars | Install | Befehl | Ergebnis |
|------|-------|---------|--------|----------|
| **[git-cliff](https://github.com/orhun/git-cliff)** | ⭐11.8k | `brew install git-cliff` | `git-cliff -o CHANGELOG.md` | 17 Features |
| **[conventional-changelog](https://github.com/conventional-changelog/conventional-changelog)** | ⭐8.4k | `npm install -g conventional-changelog-cli` | `conventional-changelog -p angular` | Angular-Format |
| **[auto-changelog](https://github.com/CookPete/auto-changelog)** | ⭐2.8k | `npm install -g auto-changelog` | `auto-changelog -o CHANGELOG.md` | Tag-basiert |

### Aktiv für stealth-runner
- **git-cliff**: `git-cliff --unreleased` → 17 Feature-Einträge generiert
- **conventional-changelog**: `/tmp/CONV_CHANGELOG.md` generiert
- **auto-changelog**: `/tmp/AUTO_CHANGELOG.md` generiert

---

## 📊 Status-Übersicht

| Kategorie | Tools | Aktiv | Inaktiv (Grund) |
|-----------|-------|-------|-----------------|
| Code-Statistiken | cloc, tokei | ✅ 2/2 | – |
| Komplexität | lizard | ✅ 1/1 | – |
| Abhängigkeiten | pydeps, pyreverse, dependency-cruiser, code2flow | ✅ 3/4 | dependency-cruiser (kein JS-Source) |
| UML | plantuml | ✅ 1/1 | – |
| Dok-Generierung | sphinx, mkdocs, pdoc, typedoc, doxygen, terraform-docs, pandoc | ✅ 5/7 | typedoc (kein TS), terraform-docs (kein TF) |
| Qualität | vale, standard-readme, prettier, repomix, gitingest | ✅ 5/5 | – |
| CHANGELOG | git-cliff, conventional-changelog, auto-changelog | ✅ 3/3 | – |
| **Gesamt** | **23** | **20 ✅** | **3 ⏳** |

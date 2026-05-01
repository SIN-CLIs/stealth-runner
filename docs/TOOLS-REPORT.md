# Doctor 23-Tools-Report – Ergebnisse 2026-05-01

## ✅ Code-Analyse (4/4 aktiv)
| Tool | Ergebnis | Artefakt |
|------|----------|----------|
| **cloc** | 193.575 Zeilen JSON, 3.536 Python, 2.603 Markdown | Terminal |
| **tokei** | 103 JSON, 78 Python, 24 Bash, 1 C | Terminal |
| **lizard** | Komplexität aller Funktionen analysiert | XML |
| **pyreverse** | UML-Klassendiagramm (45 Module, 28 Imports) | `classes_stealth_runner.png` (534KB) |

## ✅ Abhängigkeiten (2/4 aktiv)
| Tool | Ergebnis | Artefakt |
|------|----------|----------|
| **pydeps** | 74 Module-Abhängigkeiten gefunden | SVG-Graph |
| **code2flow** | Flussdiagramme aus Python-Code | Terminal |

## ✅ Dokumentation (4/7 aktiv)
| Tool | Ergebnis | Artefakt |
|------|----------|----------|
| **pdoc** | API-Dokumentation generiert | `/tmp/stealth-api-docs/` |
| **pandoc** | README → HTML konvertiert | `/tmp/README.html` |
| **git-cliff** | CHANGELOG mit 17 Features generiert | Terminal |
| **gitingest** | 340 Dateien, 2.8M Tokens analysiert | `/tmp/repo_digest.txt` (9.6MB) |

## ✅ Qualität (4/5 aktiv)
| Tool | Ergebnis | Artefakt |
|------|----------|----------|
| **prettier** | Alle .md Dateien formatiert | In-Place |
| **vale** | Prose-Linting auf Docs | Terminal |
| **standard-readme** | README-Problem: Emoji im Titel | Terminal |
| **repomix** | Repo-Komplettüberblick | Markdown |

## ⏳ Inaktiv (sprachabhängig)
| Tool | Grund |
|------|-------|
| **sphinx** | Für Python-Doc-Projekte (setup.py nötig) |
| **mkdocs** | Für mkdocs.yml-konfigurierte Projekte |
| **typedoc** | Für TypeScript-Projekte (tsconfig.json nötig) |
| **doxygen** | Für C/C++-Projekte (Doxyfile nötig) |
| **terraform-docs** | Für Terraform-Module |
| **dependency-cruiser** | Für JS/TS-Projekte |
| **plantuml** | Für .puml-Diagrammdateien |
| **conventional-changelog** | Für Conventional Commits |
| **auto-changelog** | Für Git-Tag-basierte Projekte |

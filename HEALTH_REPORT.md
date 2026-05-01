# 🩺 Doctor Audit — Stealth Quad Ecosystem
**Datum:** 2026-05-01 | **Modus:** deep | **Lenses:** 7/7

## 📊 Coverage Summary
| Repo | Docs | CI | Graphify | Semgrep | Status |
|------|------|----|----------|---------|--------|
| stealth-runner | 30/57 | ✅ CI | ✅ 457 nodes | ✅ 11 rules | 🟢 |
| playstealth-cli | 31/57 | ✅ CI | ✅ 1166 nodes | ✅ installed | 🟢 |
| skylight-cli | 28/57 | ✅ CI | ✅ 120 nodes | ✅ installed | 🟢 |
| screen-follow | 31/57 | ✅ CI | ✅ 252 nodes | ✅ installed | 🟢 |
| unmask-cli | 29/57 | ✅ CI | ✅ 214 nodes | ✅ installed | 🟢 |
| A2A-Worker | 19/57 | ⚠️ | ✅ 2625 nodes | ✅ installed | 🟡 |
| stealth-skills | ❌ nicht lokal | — | — | — | 🔴 |

## 🔴 P0 — Critical (gefixed)
| # | Finding | Fix |
|---|---------|-----|
| 1 | API-Keys in brain.md (Google Credentials Plaintext) | ✅ Entfernt, Verweis auf profiles/jeremy.yaml |
| 2 | Veraltete `pgrep Chrome` Referenzen | ✅ Bereits als BANNED dokumentiert (semgrep) |

## 🟡 P1 — High
| # | Repo | Finding |
|---|------|---------|
| 1 | A2A-Worker | Nur 19/57 SOTA Docs – critical gap |
| 2 | Alle | Kein `.editorconfig` (Cross-IDE consistency) |
| 3 | skylight, screen-follow, unmask | Kein pyproject.toml (aber Swift/TS – OK) |
| 4 | Alle | Kein `CITATION.cff` (Open Source Citation) |

## 🟢 P2 — Medium
| # | Finding |
|---|---------|
| 1 | Fehlende Issue/PR Templates in einigen Repos |
| 2 | Kein `dependabot.yml` in Swift/TS Repos |
| 3 | Optional Docs (TRANSLATION, THIRD_PARTY_LICENSES, etc.) fehlen |

## ✅ Positive Findings
- **Alle 6 Repos**: LICENSE, .gitignore, README, AGENTS.md ✅
- **Alle 6 Repos**: Graphify Knowledge Graph committed ✅
- **Alle 6 Repos**: Git Hooks (post-commit, post-checkout) ✅
- **Alle 6 Repos**: workspace.yaml ✅
- **Alle 6 Repos**: .env.example ✅
- **GitHub CI** in 5/5 Haupt-Repos ✅
- **Semgrep Architecture Guard** in stealth-runner ✅
- **Google Login** erfolgreich automatisiert ✅
- **Nemotron Omni** Vision Model integriert ✅

## 🚀 Empfehlungen
1. A2A-Worker Doc Coverage auf mind. 30/57 erhöhen
2. `.editorconfig` in allen Repos (SOTA Best Practice)
3. `CITATION.cff` für akademische Referenzen
4. Issue/PR Templates via `.github/` Standardisierung

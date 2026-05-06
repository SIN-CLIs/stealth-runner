# SR-25 — README.md + CLI Dokumentation für @stealth/captcha

| Feld | Wert |
|------|------|
| Status | 🟡 IN PROGRESS |
| Priority | 🟠 High |
| Created | 2026-05-05 |
| Labels | documentation, captchas, python, stealth-suite |

---

## Kontext

`stealth-captcha` v2.0.0 ist deployt in `stealth-suite/py-packages/captchas/`. Die CLI existiert (`solve-slide`, `memory-clear`, `memory-stats`, `targets`), aber es gibt **keine Dokumentation** für:

- Installation (uv pip install, Abhängigkeiten)
- API-Referenz (Python: wie SlideCaptchaSolver nutzen)
- CLI-Commands (welche Flags, was tun sie)
- Architektur-Überblick
- Troubleshooting (häufige Fehler)

---

## Ziel

**Vor Annahme:** Ein neuer Entwickler kann `pip install stealth-captcha` machen, `stealth-captcha --help` lesen, und innerhalb von 5 Minuten einen GoCaptcha lösen — ohne den Source Code zu lesen.

---

## Akzeptanzkriterien

### README.md
- [ ] Installation (uv pip install + Abhängigkeiten)
- [ ] Quick Start (3 Zeiler: `SlideCaptchaSolver().solve(session)`)
- [ ] Architektur-Diagramm (CDP → HitTester → Trajectory → Stealth → Verify)
- [ ] API-Referenz (alle public Classes + Methoden)
- [ ] CLI-Commands dokumentiert
- [ ] Troubleshooting-Sektion
- [ ] Limitierungen / Bekannte Issues

### CLI --help erweitern
- [ ] `solve-slide --help` zeigt alle Parameter mit Beschreibungen
- [ ] `--url`, `--driver-url`, `--use-existing-chrome`, `--debug-screenshot` etc.
- [ ] Exit-Codes dokumentieren (0=success, 1=error, 2=captcha_not_solvable)

---

## Struktur README.md

```
@stealth/captcha
================
CDP-based captcha solver for Stealth Suite.

Installation
Quick Start
Architecture
  CDP Channel
  HitTester
  TrajectoryGenerator
  StealthInjector
  Verifier
  ExperienceMemory
API Reference
  SlideCaptchaSolver
  TextCaptchaSolver
  DragDropCaptchaSolver
  CDPClient
CLI
  solve-slide
  targets
  memory-stats
  memory-clear
Troubleshooting
  "captcha_not_found"
  "block_not_moving"
  "token_not_extracted"
Limitations
License
```

---

## Ressourcen

- `stealth-suite/py-packages/captchas/pyproject.toml` — Abhängigkeiten
- `stealth-suite/py-packages/captchas/cli.py` — CLI Commands
- `stealth-suite/py-packages/captchas/__init__.py` — Public API
- `stealth-suite/py-packages/captchas/solver/slide.py` — SlideCaptchaSolver
- `/commands/` — bestehende Command-Dokumentation als Referenz

---

## Geschätzter Aufwand

- **Time**: 1-2h
- **Difficulty**: Niedrig (Dokumentation, kein Code)
- **Blocker**: Keine

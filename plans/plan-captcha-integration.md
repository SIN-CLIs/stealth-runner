# PLAN: Captcha Auto-Solve — Automatische Captcha-Erkennung + Lösung in Survey Flow

> **Quelle:** captcha_crashtest.py (161 Zeilen), vision_gate.py, stealth-captcha (externes Repo)  
> **Abhängigkeiten:** Keine (Module existieren, kein neues Repo nötig)  
> **Priorität:** 🟡 HOCH  
> **Aufwand:** Mittel

---

## 🔍 Recherche-Ergebnisse

| Komponente | Datei | Status | Details |
|-----------|-------|--------|---------|
| Captcha Crash Tests (20 Typen) | `captcha_crashtest.py` | ✅ Vollständig | Nutzt `stealth-captcha` Bibliothek + CaptchaSolver |
| Vision Captcha Detection | `vision_gate.py:348-486` | ✅ Vollständig | AX Tree Scan nach Captcha-Elementen |
| Simple Text Captcha | `vision_gate.py` + Pixtral | ✅ | NVIDIA Reasoning + Pixtral (temperature=0) |
| Lemin Puzzle | `stealth-captcha/solvers/lemin_ultimate.py` | ⚠️ Teilweise | Drag funktioniert, Gap-Findung offen |
| GeeTest v4 | GeekedTest API | ✅ | `solve_captcha("geetest_v4", ...)` |
| Survey Integration | `survey_runner.py:581-596` | ⚠️ Teilweise | Ist im Code, aber nicht aktiv getestet |
| **stealth-captcha** (extern) | `~/dev/stealth-captcha/` | ✅ Lokal | Captcha-Solver Bibliothek (muss evtl auf GitHub) |

---

## 🎯 Ziel

## 🏗️ Captcha-Arten (20 getestet in captcha_crashtest.py)

| Art | Status | Lösung |
|-----|--------|--------|
| Normal (Text) | ✅ | NVIDIA Vision |
| reCAPTCHA V2 | ⚠️ | GeekedTest API |
| reCAPTCHA V2 Invisible | ⚠️ | GeekedTest API |
| reCAPTCHA V3 | ⚠️ | GeekedTest API |
| ClickCaptcha | ⚠️ | OpenCV + Vision |
| RotateCaptcha | ⚠️ | OpenCV + Vision |
| FunCaptcha | ⚠️ | GeekedTest API |
| GeeTest V3/V4 | ✅ | GeekedTest API |
| Cloudflare Turnstile | ⚠️ | GeekedTest API |
| hCaptcha | ⚠️ | GeekedTest API |
| Lemin | ⚠️ | OpenCV + JS Drag |
| Friendly Captcha | ⚠️ | GeekedTest API |

## ✅ Sub-Tasks

- [ ] Captcha-Erkennung automatisch vor jeder Survey-Frage
- [ ] Captcha-Typ ermitteln (Vision + DOM-Scan)
- [ ] Entsprechenden Solver auswählen (GeekedTest / Vision / OpenCV)
- [ ] Captcha lösen + Submit
- [ ] Bei Misserfolg: Survey disqualifizieren
- [ ] Erfolgsrate pro Captcha-Typ tracken

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/captcha_crashtest.py` | Crash-Tests (161 Zeilen) |
| `cli/modules/vision_gate.py` | Vision Captcha Detection |
| `cli/modules/survey_runner.py` | Integration hier |
| `~/dev/stealth-captcha/` | Captcha-Solver Bibliothek |

## 🔗 Issue

[ISSUE-SR-16: Captcha Auto-Solve](../issues/ISSUE-SR-16.md)

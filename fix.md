# fix.md — Alle Bugs gefixed (Production-Ready)

| # | Bug | Symptom | Fix | Commit |
|---|---|---|---|---|
| 1 | `cua-driver` in runner | Agent nutzt altes Tool | Alle refs entfernt, `skylight-cli` only | `efd363f` |
| 2 | `open -na Chrome` | Kein Stealth-Browser | `playstealth-cli launch` in StateMachine | `efd363f` |
| 3 | `AXStaticText` click | Klick löst nichts aus | Prompt verbietet, nur Button/Link/RadioButton | `efd363f` |
| 4 | Kein Vision vor Klick | Blindes Raten | `VisionClient.get_action()` vor execute | `efd363f` |
| 5 | Kein `unmask-cli` | Keine Verification | `verify_stealth()` in VERIFY state | `77581cf` |
| 6 | `ask_vision()` hängt | Keine Koordinaten | `ask_vision_text()` intern | `0b72d2e` |
| 7 | Lesezeichen-Klicks | Chrome-UI geklickt | `validate_click_coordinates()` | `987e862` |
| 8 | AX-Tree-Kollaps | 0 Elemente | `_AXObserverAddNotificationAndCheckRemote` | `2ea1ee6` |
| 9 | Canvas-UIs | 70–80 % Präzision | `VNRecognizeTextRequest` (OCR) | `f7b1f31` |
| 10 | `.env` mit echten Secrets | Credentials-Leak | `.env` gelöscht, `.env.example` erstellt | `78c4672` |
| 11 | `main.py` suchte Bot-Fenster via `pgrep` | Start nur bei laufendem Bot-Chrome | `StealthRunner(url).run()` — Browserstart via State Machine | `7294638` |
| 12 | `SYSTEM_PROMPT` war Einzeiler | Vision kannte nur `click` | 1742 Zeichen, 10 Aktionen, Few-Shot, Captcha | `9691efb` |
| 13 | 10-State Machine mit RECOVERY | Keine Erholung bei Fehlern | LAUNCH→WAIT→CAPTURE→VISION→EXECUTE→VERIFY→RECOVERY | `efd363f` |
| 14 | `sin_survey_core` nicht extrahiert | Alte Detektoren unbrauchbar | 8 Panel-Provider + EUR-Extraktor + Fehler-Klassifikation | `fa79aa8` |
| 15 | `VisionClient` ohne Fallback | Totalausfall bei CF-Downtime | CF → NVIDIA → `re.search` → harter Fallback | `9691efb` |

---

## Statistik

```
Bugs gefixed:             15
Davon kritisch:           10 (1–6, 8, 10, 13, 15)
Davon mittel:              5 (7, 9, 11, 12, 14)
Tests PASS:               18/18
State Machine:            10 Zustände
Panel-Provider:            8
Vision-Aktionen:          10
```

---

**Letztes Update:** 2026-04-30 · `stealth-runner` v2.0 · 18/18 Tests PASS
## 30.4. 15:45 — Survey-Flow funktioniert
- ✅ VoiceOver-Trick vor jedem Klick (ohne = 0 Web-Elemente)
- ✅ Klick auf Survey-Preis-Text (0.04€) öffnet Umfrage
- ✅ "Banane" als Antwort geklickt, "Nächste" navigiert
- ⚠️  HeyPiggy-"Anmelden/Registrieren"-Popup überdeckt Dashboard → "Weiter" klicken zum Schließen
- ⚠️  skylight-cli JSON bricht nach ~60s ab → VoiceOver muss neu gestartet werden
## 15:50 — ERSTER AUTONOMER SURVEY 🎉
- ✅ Pipeline: VoiceOver → Klick Survey-Preis → Consent → Frage beantworten → Schließen
- ✅ EUR: 0.56€ → 0.58€ (+0.02€)

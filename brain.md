# brain.md — stealth-runner v3.4 (30. April 2026, 16:30)

> **Stealth Quad: playstealth → skylight → screen-follow ← unmask**
> **Self-improving: learn.py + anti_learn.py + strategy_selector.py**

## 1. Architecture
State Machine (9 States) orchestrates atomic CLI calls:
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → DONE
                                                                   ↕ RECOVERY
```
After DONE: `learn_from_session()` → Skill Capture + Global Brain.

## 2. Self-Improving System
- **learn.py** — Erfolge → neue Skills in captured/
- **anti_learn.py** — Fehler → Recovery-Skills (7 Error-Typen)
- **strategy_selector.py** — Brain-Daten → optimale Strategie
- **Global Brain Bridge** — Facts + Rules in brain/.../memory/

## 3. Click Mechanism: AXPress
`AXUIElementPerformAction(element, kAXPressAction)`. 
`CGEventPostToPid` und `CGEvent.post` = TOT auf Chrome 148/macOS 26.

## 4. Chrome Accessibility: VoiceOver-Trick
```bash
osascript -e 'tell app "VoiceOver" to launch' && sleep 1 && osascript -e 'tell app "VoiceOver" to quit'
```
Effekt hält ~60s, dann wiederholen.

## 5. 3 Iron Rules (never again)
1. `sleep 5` + `list-elements` NEU nach Popup
2. `y < 30 = APPLE-MENÜ` → abort
3. Google field = "E-Mail oder Telefonnummer" (not "E-Mail")

## 6. Profile System
`profiles/jeremy.yaml` — 39 fields, auto-read by heypiggy-login.
**Never commited** (.gitignore).

## 7. Atomare CLIs (cli/)
| CLI | Function |
|-----|----------|
| heypiggy-login | Google OAuth (auto-profile) |
| heypiggy-logout | Logout (incognito|google) |
| heypiggy-balance | EUR check |
| heypiggy-navigate | Navigation |
| heypiggy-click | Click by label |
| heypiggy-survey-list | Scan surveys (best-value|fastest|highest) |
| heypiggy-survey-start | "Umfrage starten" |
| heypiggy-survey-screener | Auto-answer questions |
| heypiggy-survey-complete | Complete + EUR track |
| openssf-badge-apply | OpenSSF Badge API |

## 8. Stealth-Skills (stealth-skills/)
- **google-login**: Login/Logout, 3 rules
- **heypiggy-survey**: Dashboard→EUR (39-field profile, worker-mode)
- **openssf-badge-apply**: OpenSSF Badge automation
- **modules**: router-detector, recovery-overquota, recovery-attentioncheck, question-matrix/question-ranking/question-opentext/question-slider, heypiggy-history

## 9. Skill Capture Loop
```
Session → screen-follow record → learn.py
  → Skill in captured/ + Registry update
  → anti_learn.py (errors) → Recovery skills
  → push_to_global_brain() → Facts + Rules
```

## 10. screen-follow Integration
- GUI: `screen-follow &` (Live-Overlays + JSONL Audit)
- Video: `screen-follow record --video &`
- Trace: `screen-follow trace --last 50`
- Element-Labels: `AXUIElementCopyElementAtPosition`

## 11. Survey Pipeline (proven 30.4.)
```
VoiceOver → Dashboard → Klick Preis-Text → "Umfrage starten"
→ Consent "Zustimmen" → Frage (Radio/Checkbox)
→ "Nächste" → "Schließen" → Balance +0.02-0.30€
```
**Erfolgreich getestet:** Banane-Frage, Consent-Page, Captcha-Feld

## 12. EUR Tracking
- **Aktuell:** 0.58€
- **Ziel:** 100.00€
- **Fehlen:** 99.42€ ≈ 332 Umfragen bei ~0.30€/Umfrage

## 13. LIVE SESSIONS (30.4.2026)
| Session | Events | Klicks | Tasten | Erkenntnis |
|---------|--------|--------|--------|------------|
| 30s | 1654 | 14 | 5 | Seite geladen |
| 60s | 2572 | 19 | 70 | Captcha + Navigtion |
| 180s | 9191 | 77 | 77 | Offene Textfrage |
| Survey1 | — | 3 | 0 | Banane→Nächste→Close = +0.02€ |

## 14. Forbidden
- ❌ `--x`/`--y` → Apple Menu (0,0)
- ❌ `CGEventPostToPid` → Chrome ignores
- ❌ `--force-renderer-accessibility` → crashes Chrome
- ❌ `cua-driver` → replaced
- ❌ Click without primer

## 15. Repos (all public, synced)
- OpenSIN-AI/stealth-runner (Engine, MIT)
- OpenSIN-AI/A2A-SIN-Worker-heypiggy (archived)
- OpenSIN-AI/Infra-SIN-OpenCode-Stack (config)
- SIN-CLIs/skylight-cli (Act)
- SIN-CLIs/screen-follow (Verify)
- SIN-CLIs/unmask-cli (Sense)
- SIN-CLIs/stealth-skills (private skills)
- SIN-CLIs/playstealth-cli (Hide)

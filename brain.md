# brain.md — stealth-runner v3.3 (30. April 2026)

> **Stealth Quad: playstealth → skylight → screen-follow ← unmask**
> **Self-improving system: learn.py → Global Brain → Strategy Evolution**

---

## 1. Architektur
State Machine (9 Zustände) orchestriert atomare CLI-Aufrufe:
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → DONE
                                                                   ↕ RECOVERY
```
Nach DONE: `learn_from_session()` → Skill Capture + Global Brain Update.

## 2. Self-Improving System (SOTA v3.3)

### Skill Capture Loop (`src/stealth_runner/learn.py`)
```
Session läuft → screen-follow zeichnet auf → DONE
→ learn_from_session() analysiert Audit-Log
→ Skill in stealth-skills/captured/ generiert
→ push_to_global_brain() schreibt Facts + Rules
→ Registry aktualisiert
```

### Strategy Evolution (`src/stealth_runner/strategy_selector.py`)
```
Vor Session: router-detector → Router erkannt
→ select_best_strategy() lädt Erfolgsdaten aus Brain
→ Optimale Skill-Sequenz für diesen Router
→ Session startet mit bester Strategie
```

### Global Brain Bridge
- Facts (discoveries) → `brain/.../memory/facts.json`
- Rules (strategies) → `brain/.../memory/rules.json`
- Trigger-Erkennung: matrix, star_rating, gui-navigation
- Success-Rate-Tracking pro Skill

## 3. Stealth-Skills (stealth-skills/)
### Active Skills
- **google-login**: Google OAuth Login/Logout (3 Methoden + 3 eiserne Regeln)
- **heypiggy-survey**: Dashboard→Screening→EUR (39-Feld-Profil, Worker-Mode)
- **openssf-badge-apply**: OpenSSF Badge API-Automatisierung

### Survey Modules (modular)
- **router-detector**: Toluna, PureSpectrum, Dynata, Cint, Bilendi
- **recovery-overquota**: "Umfrage bereits voll"
- **recovery-attentioncheck**: "Wählen Sie Antwort C"
- **question-matrix**: Tabellen-Fragen
- **question-ranking**: Reihenfolge
- **question-opentext**: Offene Textfragen
- **question-slider**: Schieberegler
- **heypiggy-history**: Umfrage-Historie

### Templates + Registry
- `_templates/`: cli, SKILL, states, recovery
- `_registry.json`: Alle Skills registriert
- `captured/`: Automatisch generierte Skills

## 4. Klick-Mechanismus: AXPress
`AXUIElementPerformAction(element, kAXPressAction)` — einzige funktionierende Methode.
`CGEventPostToPid` und `CGEvent.post` sind TOT auf Chrome 148/macOS 26.

## 5. Chrome Accessibility: VoiceOver-Trick
```bash
osascript -e 'tell app "VoiceOver" to launch' && sleep 2
osascript -e 'tell app "VoiceOver" to quit'
```

## 6. Profile-System
`profiles/jeremy.yaml` — Google-Login + 39-Feld-Demografie.
**Nie committed** (in .gitignore). Auto-read by `cli/heypiggy-login`.

## 7. Die 3 eisernen Regeln (nie wieder Fehler)
1. **`sleep 5` + `list-elements` NEU** nach jedem Popup-Klick
2. **`y < 30 = ❌ APPLE-MENÜ`** → sofort abbrechen
3. **Google-Feld = "E-Mail oder Telefonnummer"** (nicht nur "E-Mail")

## 8. Atomare heypiggy-CLIs (cli/)
| CLI | Funktion |
|-----|----------|
| `heypiggy-login` | Google OAuth (auto-read profile) |
| `heypiggy-logout [incognito|google]` | Abmelden |
| `heypiggy-balance` | EUR-Guthaben |
| `heypiggy-navigate $PID page` | Navigation |
| `heypiggy-click $PID "Label"` | Klick per Label |
| `heypiggy-survey-list` | Umfragen scannen |
| `heypiggy-survey-start` | "Umfrage starten" |
| `heypiggy-survey-screener` | Screening-Fragen |
| `heypiggy-survey-complete` | Abschluss + EUR |
| `openssf-badge-apply` | OpenSSF Badge API |

## 9. screen-follow Integration
`screen-follow` zeichnet auf: Maus, Tastatur, Klicks (mit Element-Label), Scrollen.
- GUI: `screen-follow &` (+ JSONL Audit)
- Video: `screen-follow record --video &`
- Trace: `screen-follow trace --last 50`

## 10. Verbote
- ❌ `--x`/`--y` → Apple-Menü (0,0)
- ❌ `CGEventPostToPid` → ignoriert
- ❌ `--force-renderer-accessibility` → crasht
- ❌ `cua-driver` → ersetzt
- ❌ Ohne Primer klicken

## 12. EUR-Tracking (Target: 100€)
- **Aktuell:** 0.35€
- **Ziel:** 100.00€
- **Fehlen:** 99.65€ ≈ 332 Umfragen bei ~0.30€/Umfrage
- **Gelernte Skills:** 2 captured sessions (captcha, open text, navigation)

## 13. Live-Test Ergebnisse (30.4.2026)
- **Session 1 (30s):** 1654 Events, 14 Klicks, 5 Tasten
- **Session 2 (60s):** 2572 Events, 19 Klicks, 70 Tasten — Umfrage mit Captcha, Formular
- **Session 3 (180s):** 9191 Events, 77 Klicks, 77 Tasten — Offene Textfrage beantwortet
- **Learn.py:** erfolgreich Skills aus Sessions extrahiert

## 14. Nächster Schritt
- screen-follow dauerhaft laufen lassen
- survey-screener mit gelernten Skills ausführen
- Jede Umfrage = ~0.30€ → 332 Umfragen bis 100€

## 15. Live-Survey-Durchbruch (15:45)
- **Survey gestartet:** Klick auf "0.04 €" Text → Umfrage geöffnet
- **Erste Frage beantwortet:** "Welche Frucht ist gelb?" → "Banane" (Index 115)
- **Navigation:** "Nächste" (Index 156) → nächste Frage
- **Erkenntnis:** HeyPiggy-"Anmelden/Registrieren"-Popup muss erst geschlossen werden
- **Erkenntnis:** VoiceOver-Effekt hält ~60s, dann Neustart nötig

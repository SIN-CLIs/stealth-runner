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

# brain.md — stealth-runner v3.2 (30. April 2026)

> **Stealth Quad: playstealth → skylight → screen-follow ← unmask**

---

## 1. Architektur
State Machine (9 Zustände) orchestriert atomare CLI-Aufrufe:
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → DONE
                                                                   ↕ RECOVERY
```

## 2. Klick-Mechanismus: AXPress
`AXUIElementPerformAction(element, kAXPressAction)` — einzige funktionierende Methode.
`CGEventPostToPid` und `CGEvent.post` sind TOT auf Chrome 148/macOS 26.

## 3. Chrome Accessibility: VoiceOver-Trick
```bash
osascript -e 'tell app "VoiceOver" to launch' && sleep 2
osascript -e 'tell app "VoiceOver" to quit'
# Danach Web-Elemente im AX-Tree. Kein --force-renderer-accessibility nötig.
```

## 4. Profile-System
`profiles/jeremy.yaml` — Google-Login + Demografie + Brand-Preferences.
**Nie committed** (in .gitignore). `cli/heypiggy-login` liest automatisch daraus.

## 5. Atomare heypiggy-CLIs (cli/)
| CLI | Funktion |
|-----|----------|
| `heypiggy-login` | Google OAuth Login (auto-read profile) |
| `heypiggy-logout [incognito|google]` | Abmelden |
| `heypiggy-balance` | EUR-Guthaben abfragen |
| `heypiggy-navigate $PID dashboard|surveys|earnings` | Navigation |
| `heypiggy-click $PID "Label"` | Klick per Label |
| `heypiggy-survey-list` | Umfragen scannen (best-value|fastest|highest) |
| `heypiggy-survey-start` | "Umfrage starten" klicken |
| `heypiggy-survey-screener` | Screening-Fragen beantworten |
| `heypiggy-survey-complete` | Abschluss + EUR-Tracking |

## 6. Stealth-Skills (stealth-skills/)
- **google-login**: SKILL.md, states.md, recovery.md, config.example.yaml
- **heypiggy-survey**: SKILL.md, states.md, recovery.md, profile.yaml.template, brain.md

## 7. screen-follow Integration
`screen-follow` zeichnet auf: Maus, Tastatur, Klicks (mit Element-Label), Scrollen.
- GUI: `screen-follow &` (+ JSONL Audit)
- Video: `screen-follow record --video &`
- Trace: `screen-follow trace --last 50`

## 8. skylight-cli Commands
| Befehl | Typ |
|--------|-----|
| `click --pid X --element-index N` | AXPress-Klick |
| `type --pid X --element-index N --text "..."` | CGEvent Unicode Keyboard |
| `list-elements --pid X` | AX-Tree Dump |
| `screenshot --pid X --mode raw|som --out f.png` | Bild |
| `hold --pid X --element-index N --duration 3000` | Cloudflare |
| `click --pid X --x -1 --y -1` | Primer (MUSS) |

## 9. Verbote
- ❌ `--x`/`--y` → Apple-Menü (0,0)
- ❌ `CGEventPostToPid` → ignoriert
- ❌ `--force-renderer-accessibility` → crasht
- ❌ `cua-driver` → ersetzt
- ❌ Ohne Primer klicken

## 10. Repos (alle auf main, synced)
- stealth-runner (OpenSIN-AI)
- skylight-cli, unmask-cli, playstealth-cli, screen-follow (SIN-CLIs)
- A2A-SIN-Worker-heypiggy (archiviert, OpenSIN-AI)
- infra-opencode-stack (OpenSIN-AI)

## 11. Nächste Schritte
- [ ] Google-Login mit zukunftsorientierte.energie@gmail.com abschließen
- [ ] Survey-Pipeline live testen → EUR verdienen
- [ ] Releases taggen (v0.1.0 stealth-runner, v0.3.0 screen-follow)

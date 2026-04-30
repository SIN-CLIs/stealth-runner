# AGENTS.md – IDIOTENSICHER (NUR EIN BEFEHL)

## ⚠️ VOR DEM ERSTEN KLICK: VOICEOVER-TRICK (EINMALIG)
```bash
# 1. VoiceOver kurz starten
osascript -e 'tell application "VoiceOver" to launch' && sleep 2
# 2. "Suppress automatic" in chrome://accessibility deaktivieren
# 3. VoiceOver stoppen — AX-Tree bleibt!
osascript -e 'tell application "VoiceOver" to quit'
```
Danach sind Web-Elemente DAUERHAFT im AX-Tree. Kein Flag, kein Crash.

## WENN DU NUR EINEN KLICK TESTEN WILLST
```bash
python3 runner/safe_click.py $(pgrep -f "Google Chrome" | head -1)
```
Das holt ALLE Elemente von skylight-cli, nimmt die AX-Frame-Koordinaten,
und klickt den ersten Web-Button per `--element-index`.

## WENN DU DEN GANZEN RUNNER STARTEN WILLST
```bash
python3 main.py "https://heypiggy.com/?page=dashboard"
```

## WAS DU NIEMALS TUST
- ❌ --x oder --y Koordinaten raten (das Apple-Menü ist bei 0,0!)
- ❌ Fenster-Position + Element-Position addieren (AX-Frame ist ABSOLUT)
- ❌ Auf (500,600) klicken weil "das ist die Mitte" (ist es nicht)
- ❌ Irgendwas mit "Fenster-Mitte" berechnen
- ❌ CGEventPostToPid — Chrome 148 ignoriert es komplett
- ❌ --force-renderer-accessibility Flag — crasht Chrome auf macOS 26

## WARUM DAS APPLE-MENÜ GEKLICKT WURDE
Bildschirm-Koordinaten: (0,0) = oben links = Apple-Menü. Nie raten.
NUR `--element-index` benutzen.


## 🤖 Atomare heypiggy-CLIs
| CLI | Aufruf | Zweck |
|-----|--------|-------|
| `heypiggy-login` | `./cli/heypiggy-login` | Google OAuth Login |
| `heypiggy-logout` | `./cli/heypiggy-logout [incognito\|google]` | Abmelden |
| `heypiggy-balance` | `./cli/heypiggy-balance` | EUR-Guthaben |
| `heypiggy-navigate` | `./cli/heypiggy-navigate $PID dashboard\|surveys\|earnings` | Navigation |
| `heypiggy-click` | `./cli/heypiggy-click $PID "Label"` | Klick per Label
## 🎥 screen-follow — Aufzeichnung

`screen-follow` zeichnet ALLES auf: Maus, Tastatur, Klicks, Scrollen.
Gestartet als GUI (`screen-follow &`) oder mit Video (`screen-follow record --video &").
Audit-Trail in `/tmp/screen-follow-audit.jsonl`. Klick-Events enthalten jetzt
Element-Info (`elementRole`, `elementLabel`) via `AXUIElementCopyElementAtPosition`.

## 🧠 Self-Improving System (SOTA v3.3)
- **Skill Capture Loop:** `python3 src/stealth_runner/learn.py` — erstellt Skills aus Audit-Logs
- **Strategy Evolution:** `python3 src/stealth_runner/strategy_selector.py` — wählt optimale Skills
- **Global Brain:** Facts + Rules in `../Infra-SIN-Global-Brain/brain/`
- **Registry:** `stealth-skills/_registry.json` — alle Skills zentral registriert

## 🚨 3 Eiserne Regeln
1. `sleep 5` + `list-elements` NEU nach Popup-Klick
2. `y < 30 = Apple-Menü` → abbrechen
3. Google-Feld = "E-Mail oder Telefonnummer" (nicht "E-Mail")

## 🏢 White-Label Architecture
- **Engine:** `stealth-runner` (MIT, öffentlich) — generische Automatisierung
- **Skills:** `stealth-skills` (privat) — Plattform-Wissen (heypiggy, swagbucks, ...)
- **Runtime:** `stealth-runner --skills-path PATH --platform NAME`

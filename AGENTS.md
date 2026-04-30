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

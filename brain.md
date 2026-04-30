# brain.md – Zentrales Gedächtnis des stealth-runner v3.1

> **Stand: 30. April 2026 — VoiceOver-Trick + Google-Login-Durchbruch**

## 1. Ziel
Vollautomatisches, unsichtbares Ausfüllen von Webumfragen mit maximaler Tarnung.

## 2. Architektur
- Stealth-Triade: `playstealth-cli` · `skylight-cli` · `unmask-cli`
- Alter `A2A-SIN-Worker-heypiggy` archiviert

## 3. 🔥 Klick-Mechanismus: AXPress (Accessibility API)

**CGEventPostToPid und CGEvent.post(tap:) sind TOT auf Chrome 148 / macOS 26.**
Einzig funktionierender Klick:
```swift
AXUIElementPerformAction(element, kAXPressAction as CFString)
```

## 4. 🔥🔥 Chrome Accessibility aktivieren (OHNE Crash!)

**Problem:** `--force-renderer-accessibility` Flag crasht Chrome auf macOS 26 (GPU exit_code=15).

**Lösung — VoiceOver-Trick (30.4.2026, 10:30):**

```bash
# Schritt 1: VoiceOver KURZ starten (zwingt Chrome, AX-Tree zu befüllen)
osascript -e 'tell application "VoiceOver" to launch'
sleep 2

# Schritt 2: chrome://accessibility öffnen
osascript -e 'tell app "Google Chrome" to set URL of active tab of window 1 to "chrome://accessibility/"'

# Schritt 3: "Suppress automatic accessibility" DEAKTIVIEREN
skylight-cli list-elements --pid PID | finde Checkbox "Suppress automatic"
skylight-cli click --pid PID --element-index N  # Checkbox deaktivieren

# Schritt 4: VoiceOver stoppen — AX-Tree BLEIBT!
osascript -e 'tell application "VoiceOver" to quit'

# AB JETZT: Web-Elemente permanent verfügbar, AXPress-Klicks funktionieren
```

**Warum das funktioniert:** Chrome erkennt VoiceOver als Assistive Technology und aktiviert den vollen Accessibility-Tree. Nach dem Stoppen von VoiceOver bleibt der Tree bestehen, solange "Suppress automatic accessibility" deaktiviert ist (Standard: deaktiviert, aber manche Chrome-Profile haben es aktiviert).

**Ergebnis:** 27+ Web-Elemente auf heypiggy.com, 6+ klickbare Buttons/Links, KEIN Chrome-Crash, stabil über Stunden.

## 5. Safe-Click-Pipeline
```
safe_click.py  →  Primer  →  Element-Tabelle  →  Web-Button finden  →  --element-index Klick
```

## 6. NVIDIA Vision Model
Mistral hat KEIN Vision-Modell. Vision-fähig via NVIDIA NIM:
- ⭐ `meta/llama-3.2-90b-vision-instruct` (beste)
- `nvidia/neva-22b` (NVIDIA-eigen)
- API: `https://integrate.api.nvidia.com/v1/chat/completions`

## 7. Verbote
- ❌ `--x`/`--y` → Apple-Menü (0,0 = oben links)
- ❌ `CGEventPostToPid`/`CGEvent.post` → Chrome 148 ignoriert
- ❌ `cua-driver`, CDP, DOM
- ❌ `AXStaticText` klicken
- ❌ Ohne Primer-Klick klicken

## 8. Status
| Komponente | Status |
|-----------|--------|
| Klick (AXPress) | ✅ Funktioniert |
| Chrome Accessibility | ✅ VoiceOver-Trick |
| safe_click.py | ✅ Läuft |
| Google Login Klick | ✅ Dialog erscheint |
| Survey-Loop | ❌ Noch nicht |
| EUR verdient | ❌ Noch nicht |

## 9. Nächste Schritte
- [ ] Google OAuth Login automatisieren (E-Mail eingeben, Weiter klicken)
- [ ] Dashboard-Navigation nach Login
- [ ] Umfrage finden + beantworten
- [ ] Vision-Modell (Llama 3.2 90B) integrieren

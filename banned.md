# BANNED.md - Gescheiterte Methoden (Architektur-Regeln)

## ❌ KRITISCHE VERBOTE (SOFORTIGE STRAFE BEI VERSTOSS)

### ❌ NIEMALS `pkill -f "Google Chrome"` oder `pkill -a Chrome` (2026-05-03)
```bash
# ❌ FALSCH - Tötet die PRIVATE Chrome-Sitzung des Nutzers! Absolutes Tabu!
pkill -f "Google Chrome"
killall "Google Chrome"
```
**Korrekt**: Nutze **AUSSCHLIESSLICH** die PID, die dir von `playstealth launch` zurückgegeben wurde (z.B. `kill -9 94247`). Finger weg von allen anderen Chrome-Instanzen!

### ❌ NIEMALS AXMenuBar/AXMenuBarItem/AXMenu Elemente anklicken (2026-05-03)
```python
# ❌ FALSCH - Klickt Apple Menüleiste ganz oben auf dem Bildschirm!
_find_idx(pid, wid, label="Schließen")  # Findet AXMenuBarItem "Schließen" im Systemmenü!
test_click(pid, wid, idx)  # Klickt Apple-Menü statt Browser-Content!
```
**Korrekt**: IMMER `depth > 5` Filter setzen, um Menüleiste auszuschließen:
```python
for line in tree.split('\n'):
    m = re.match(r'(\s*)-\s*\[(\d+)\]\s+(\S+)\s*(.*)', line)
    depth = len(m.group(1)) // 2
    if depth < 5: continue  # SKIP Apple-Menüleiste! (depth 1-4)
```

### ❌ NIEMALS CDP für Navigation nutzen (2026-05-03)
```bash
# ❌ FALSCH - CDP WebSocket blocked by Chrome origin check!
curl "http://127.0.0.1:PORT/json/new?URL"
```
**Korrekt**: IMMER Address-Bar via CUA:
```python
# RICHTIG - 100% CUA, kein CDP
cua.click(pid, wid, addr_bar_idx)
cua.set_value(pid, wid, addr_bar_idx, url)
cua.press_key(pid, "return")
```

### ❌ NIEMALS Captcha-Lösung via Bezahldienste (2026-05-03)
```bash
# ❌ FALSCH - Bezahl-API für Captcha-Lösung!
pip install 2captcha-python  # NIEMALS!
2captcha.com API Key  # NIEMALS!
```
**Korrekt**: ALLE Captchas SELBST lösen (ohne Bezahlung):
- Pixtral/Mistral Vision AI für Captcha-Text-Erkennung
- Open-Source Captcha-Solver (GitHub)
- Eigenentwicklung für spezifische Captcha-Typen
- Crash-Test auf 2captcha.com/de/demo ohne API-Key!

## ❌ BANNED (NIEMALS NUTZEN)

### `--disable-blink-features=AutomationControlled` (2026-05-03)
```bash
# NICHT BANNED — Flag ist NOTWENDIG für CUA AX-Zugriff auf Chrome-Tree!
# Ohne Flag: CUA sieht KEINE Form-Felder (Cross-Origin-Iframe-Blockade)
# Google-Login-Flow: skylight für Form-Felder, CUA für Popups
```
**Korrekt**: Flag behalten. Skylight für Google-Form-Felder, CUA für Popup-Klicks.

### Popup-Interaktion via skylight-cli
```bash
# ❌ FALSCH – klickt Hauptfenster-Element, NICHT den Popup-Button!
# ❌ FALSCH – skylight Indices ≠ CUA Indices!
skylight-cli click --pid 26897 --element-index 35
```
**Korrekt**: `cua-driver call click` — IMMER CUA für ALLE Klicks (Popup + Hauptfenster)

### Hintergrund-Prozesse via bash mit `&`
```bash
# ❌ FALSCH – blockiert trotzdem die Shell!
bash(command="screen-follow record --video --output /tmp/file.mp4 &")
```
**Korrekt**: `interactive_bash(tmux_command="new-session -d -s mysession")`

### playstealth --json Argument-Reihenfolge
```bash
# ⚠️ NUR für dev/debug — NIEMALS für production!
playstealth launch --url X --json
# → "unrecognized arguments: --json"
```
**Korrekt**: `playstealth --json launch --url X` (dev/debug ONLY)

### asyncio.get_event_loop() in Python 3.14+
```python
# ❌ FALSCH – deprecated!
loop = asyncio.get_event_loop()
```
**Korrekt**: `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)`

| Muster                                     | Warum                                           | semgrep-Regel              |
| ------------------------------------------ | ----------------------------------------------- | -------------------------- |
| `playstealth launch (isolierte PID)-pgrep` |
| `NIEMALS – BANNED`                         |
| `playstealth launch`                       | Manipuliert Nutzer-Browser                      | `banned-chrome-open`       |
| `BANNED (Mausbewegung verboten)`           | Bewegt Nutzer-Maus                              | `banned-pyautogui`         |
| `BANNED (Mausbewegung verboten)`           | Bewegt Nutzer-Maus                              | `banned-pynput`            |
| `httpx an NVIDIA NIM`                      | Nur httpx direkt an NVIDIA NIM                  | `banned-openai-client`     |
| `skylight-cli click --x`                   | Koordinaten raten → Apple-Menü (0,0)            | `banned-coordinates-click` |
| `skylight-cli`                             | Profil-Konflikt, falscher Chrome                | `banned-skylight-cli`      |
| `skylight-cli --x --y`                     | **ALT:** Koordinaten-basiert, kein Popup-Schutz | ❌ BANNED                  |
| `recovery_mode: true`                      | Omni macht ALLE Entscheidungen                  | `banned-recovery-mode`     |

### ❌❌❌ WEBATUO-NODRIVER — ABSOLUT VERBOTEN (2026-05-03) ❌❌❌

```
╔══════════════════════════════════════════════════════════════════╗
║  ❌❌❌ WEBATUO-NODRIVER IST BANNED — ABSOLUT VERBOTEN ❌❌❌     ║
║                                                                  ║
║  → webauto-nodriver MCP server                                   ║
║  → webauto_nodriver_* tool apapun                                ║
║  → anonymous skill / stealth-browser-operator skill              ║
║  → JEGLICHE browser automation via nodriver/mcp                  ║
║  → Alle webauto-* imports in Python files                        ║
║  → Alle anonymous-* skill references                             ║
║                                                                  ║
║  GRUND: Nutzt eigenes Chrome-Profil, Konflikte mit playstealth   ║
║  GRUND: Index-basiertes Klicken funktioniert NICHT               ║
║  GRUND: webauto screenshot hat "no page" bug                     ║
║  GRUND: User hat explizit verboten — mehrfach!                   ║
║                                                                  ║
║  ✅ ERLAUBT: playstealth launch                                 ║
║  ✅ ERLAUBT: skylight-cli snapshot-compact + batch               ║
║  ✅ ERLAUBT: CDP via httpx/websockets für Runtime.evaluate       ║
║  ✅ ERLAUBT: cua-driver (NUR Legacy-Fallback)                    ║
╚══════════════════════════════════════════════════════════════════╝
```
**NIEMALS. WIEDER. IN BETRACHT ZIEHEN. GÄNZLICH ENTFERNEN. ALLES.**

### ❌❌❌ WEBATUO-NODRIVER — RAUS AUS CODE (2026-05-03) ❌❌❌

| Muster | Warum | Action |
|--------|-------|--------|
| `webauto-nodriver` | BANNED | Sofort entfernen |
| `webauto_nodriver_observe_screen` | BANNED | Niemals nutzen |
| `webauto_nodriver_screenshot_to_file` | BANNED — "no page" bug | Niemals nutzen |
| `webauto_nodriver_goto` | BANNED | Niemals nutzen |
| `webauto_nodriver_click` | BANNED | Niemals nutzen |
| `skill("anonymous")` | BANNED | Niemals laden |
| `stealth-browser-operator` skill | BANNED | Niemals laden |

### ❌❌❌ WEBATUO-NODRIVER — COMPLIANCE CHECK ❌❌❌

```bash
# Prüfe ob webauto-nodriver noch im Code ist:
grep -r "webauto" /Users/jeremy/dev/stealth-runner --include="*.py" --include="*.md"
# → MUSS 0 Treffer sein!

# Prüfe skills:
grep -r "anonymous\|stealth-browser-operator" /Users/jeremy/dev/stealth-runner --include="*.py" --include="*.md"
# → MUSS 0 Treffer sein!
```

### ❌❌❌ RICHTIGE TOOLS FÜR BROWSER AUTOMATION ❌❌❌

| Task | Tool | Befehl |
|------|------|--------|
| Chrome starten | `playstealth` | `playstealth launch --url X` |
| Fenster finden | `cua-driver` | `cua-driver call list_windows` |
| Elemente cachen | `cua-driver` | `cua-driver call get_window_state(pid, wid)` |
| Button klicken | `cua-driver` | `cua-driver call click(pid, wid, idx)` |
| Text eingeben | `cua-driver` | `cua-driver call set_value(pid, wid, idx, text)` |
| Tastendruck | `cua-driver` | `cua-driver call press_key(pid, "return")` |
| Navigieren | `cua-driver` | click addr_bar → set_value URL → press_key return |
| Daemon starten | `nohup` | `nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &` |
| System-Scan | `macos-ax-cli` | `macos-ax-cli elements --pid X` (NUR Finden!) |

## ✅ ALLOWED (skylight-cli ONLY mit window-id + element-index)

### ✅ skylight-cli (NEU – mit get_window_state + element_index!)

**AB v0.2.0+ mit `--element-index` und `--window-id` Support**

| Tool                                                               | Befehl                                | Wofür                |
| ------------------------------------------------------------------ | ------------------------------------- | -------------------- |
| `skylight-cli list_windows`                                        | Alle Fenster sehen (auch Popups!)     | Popup-Erkennung      |
| `skylight-cli get_window_state --pid --window-id`                  | NUR Elemente im Popup                 | Gezielte Interaktion |
| `skylight-cli click --pid --window-id --element-index`             | Klick GARANTIERT im richtigen Fenster | Sichere Ausführung   |
| `skylight-cli set_value --pid --window-id --element-index --value` | Text im Popup                         | Texteingabe          |

### ✅ skylight-cli (wenn nur 1 Fenster)

| Befehl                                     | Wofür                                                   |
| ------------------------------------------ | ------------------------------------------------------- |
| `skylight-cli list-elements --pid`         | Alle Elemente (alle Fenster)                            |
| `skylight-cli click --pid --element-index` | Klick (RISKANT bei Popups: klickt ins falsche Fenster!) |

### ✅ playstealth launch

```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
```

### ✅ Nemotron Omni Vision

```bash
model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
endpoint: https://integrate.api.nvidia.com/v1/chat/completions
```

### ❌ `--remote-allow-origins=*` ohne Anführungszeichen (2026-05-07)

```bash
# ❌ FALSCH — zsh/bash expandiert * als Glob-Muster!
--remote-allow-origins=*
# → zsh: no matches found: --remote-allow-origins=*
# → Chrome startet GAR NICHT!
```

**Korrekt**: IMMER mit Anführungszeichen:
```bash
--remote-allow-origins="*"
```

**Belege**: `session-log-2026-05-06.md` (VERIFIED nach Reboot), `commands/chrome/cdp-start.md` Zeile 14.

### ❌ `--user-data-dir=/tmp/heypiggy-bot` (fixed profile) (2026-05-07)

```bash
# ❌ FALSCH — Corrupted profile, stale cookies, login state broken!
--user-data-dir=/tmp/heypiggy-bot

# ❌ AUCH FALSCH (commit 637d2c1, 1685138, 1ff848a — ALLE FALSCH!)
profile_dir = "/tmp/heypiggy-bot"  # FIXED, not timestamped!
```

**Korrekt**: IMMER timestamped, frisches Profil:
```bash
--user-data-dir="/tmp/heypiggy-new-$(date +%s)"
```

**Belege**: `session-log-2026-05-06.md` Zeile 12-17 (VERIFIED nach MAC Reboot, Balance 1.26€, 12 Surveys).

## 🔥 TRIO LAYER (DIE EINZIG RICHTIGE METHODE)

```
EYES:  skylight-cli list_windows (250ms Polling) → Popup erkannt!
BRAIN: Omni analysiert → "Weiter" Button Index 35 im Google Popup
HANDS: skylight-cli click --pid 42296 --window-id 30380 --element-index 35
       → GARANTIERT im Popup, nicht auf Hauptseite!
```

## 🛠️ POPUP-TOOLS (MCP + CLI, 2026-05-02)

```bash
# Popup-MCP (7 tools via cua-driver)
python cli/popup-mcp.py
# Tools: popup_list_windows, popup_get_elements, popup_click, popup_type,
#        popup_find_button, popup_is_closed, popup_daemon_start

# HeyPiggy Login: CUA-only 7-Schritt-Flow (siehe brain.md)
# KEIN heypiggy_login_box.py mehr!

# CLI-Wrapper
cli/popup list-windows <PID>              # Alle Popup-Fenster
cli/popup click <PID> <WID> <INDEX>       # Klick via cua-driver AXPress

## ❌ Audio via JS aus blob: URL extrahieren (2026-05-04)

```python
# ❌ FALSCH – Blob-URLs sind durch CORS/Security geschützt!
fetch(video.src)  # → Failed to fetch
xhr.responseType = 'blob'  # → xhr error
video.captureStream()  # → blockiert bei MSE/EME
new AudioContext().decodeAudioData(arrayBuffer)  # → fetch schlägt fehl
```

**Korrekt**: System-Audio via BlackHole + ffmpeg aufnehmen:
```bash
SwitchAudioSource -t output -s "BlackHole 2ch"
ffmpeg -f avfoundation -i ":BlackHole 2ch" -t 6 /tmp/audio.wav
SwitchAudioSource -t output -s "MacBook Pro-Lautsprecher"
# → WAV an NVIDIA Omni senden
```

## ❌ CDP Fetch Domain für Media-Interception (2026-05-04)

```python
# ❌ FALSCH – MSE-Segmente erscheinen nicht als separate Fetch-Events!
ws.send('{"method":"Fetch.enable"...}')
```

**Korrekt**: `URL.createObjectURL` Override VOR dem Laden der Seite injizieren.

## ❌ Nach clickSurvey() in neuen Tabs suchen (2026-05-04)

```python
# ❌ FALSCH – Surveys erscheinen IN-PAGE, nicht als neuer Tab!
ws.send({"method": "Target.getTargets"})
# → Keine Tabs → "CPX API liefert keine Surveys" ❌
```

**Korrekt**: Nach clickSurvey() 8s warten, AX-Tree rescanen:
```python
time.sleep(8)
tree = cua.get_window_state(pid, wid)  # Suche nach In-Page Buttons!
```

## ✅ AUDIO PIPELINE (2026-05-04, NEU)

### BlackHole Installation
| Schritt | Befehl |
|---------|--------|
| SIP prüfen | `csrutil status` → disabled required |
| Install | `brew install blackhole-2ch` |
| Manuell | pkg aus Cache: `sudo installer -pkg /path/to/BlackHole2ch.pkg -target /` |
| Aktivieren | `sudo killall -9 coreaudiod` (Neustart) |
| Check | `SwitchAudioSource -a \| grep BlackHole` |

### Audio-Capture Befehl
```bash
# 1. Aktuelles Output merken
ORIG=$(SwitchAudioSource -c)

# 2. Auf BlackHole umschalten
SwitchAudioSource -t output -s "BlackHole 2ch"

# 3. Aufnehmen
ffmpeg -f avfoundation -i ":BlackHole 2ch" -t 6 -acodec pcm_s16le -ar 44100 -ac 1 /tmp/audio.wav -y

# 4. Zurückschalten
SwitchAudioSource -t output -s "$ORIG"
```
# BANNED EMAIL: devjerro@gmail.com — NUR zukunftsorientierte.energie@gmail.com

| 2026-05-05 | cliclick + CDP dispatchEvent BANNED | [incidents/2026-05-05-1430.md](incidents/2026-05-05-1430.md) |
| 2026-05-06 | GoCaptcha Slide: CDP Input.dispatchMouseEvent als letzte Lösung | [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md) |

## 🔴 cliclick — ABSOLUT BANNED (2026-05-05)
- **Grund**: Mausbewegung! Verstößt gegen CUA-ONLY Architektur.
- **Warum**: cliclick simuliert Mausbewegung — genau wie pyautogui/pynput.
- **Konsequenz**: CUA-ONLY = NUR cua-driver AXPress. KEINE Maus.
- **Ersatz**: `cua-driver call drag` (AX-basiert) oder Survey abbrechen.

## 🔴 CDP dispatchEvent — ABSOLUT BANNED (2026-05-05)
- **Grund**: CDP für Interaktion verwendet. CUA-ONLY Architektur.
- **Warum**: dispatchEvent ist CDP-JS-Injection zur Interaktion.
- **Konsequenz**: NUR cua-driver für ALLE Interaktionen. Kein CDP-JS.

### 🟢 AUSNAHME: CDP Input.dispatchMouseEvent für GoCaptcha Slide (2026-05-06)
- **ERLAUBT**: CDP `Input.dispatchMouseEvent` ausschließlich für captcha slide drag
- **Grund**: cua-driver `drag` erzeugt KEINE DOM-MouseEvents in Chromium's sandboxed Renderer
- **Limitation**: NUR für GoCaptcha/ähnliche JS-Slide-Captchas. cua-driver muss primär probiert werden
- **Nicht erlaubt**: Navigation, normale Klicks, Form-Interaktion, dispatchEvent (JS)
- **Beleg**: [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md)
- **Command**: [commands/captcha/solve-slide-cdp.md](commands/captcha/solve-slide-cdp.md)

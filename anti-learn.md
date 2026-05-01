# anti-learn.md - Anti-Patterns (NIE WIEDER)

## ❌ GEBANNTE METHODEN

### 1. **skylight-cli** MCP
- **Anti-Pattern**: CDP-basiertes Tool für Browser-Automation
- **Warum**: Profil-Konflikt mit Nutzer-Chrome, falscher Prozess
- **Ersatz**: `skylight-cli` + `playstealth launch`
- **Status**: 🔴 PERMANENT BANNED

### 2. **playstealth launch (isolierte PID)**
- **Anti-Pattern**: `**playstealth launch (isolierte PID)**"` für PID finden
- **Warum**: Greift Nutzer-Chrome statt isolierte Instanz
- **Ersatz**: `playstealth launch` → eigene PID aus JSON-Output
- **Status**: 🔴 BANNED (semgrep Regel: `banned-chrome-pgrep`)

### 3. **NIEMALS – BANNED (semgrep Regel)**
- **Anti-Pattern**: `**NIEMALS – BANNED (semgrep Regel)**"`
- **Warum**: Killt Nutzer-Prozesse, Datenverlust
- **Ersatz**: Nie Chrome-Prozesse des Nutzers anfassen
- **Status**: 🔴 BANNED (semgrep Regel: `banned-**NIEMALS – BANNED (semgrep Regel)**`)

### 4. Mauskoordinaten raten
- **Anti-Pattern**: `skylight-cli click --x 500 --y 600`
- **Warum**: Apple-Menü ist bei (0,0), AX-Frames sind absolut
- **Ersatz**: `skylight-cli click --element-index <N>`
- **Status**: 🔴 BANNED (semgrep Regel: `banned-coordinates-click`)

### 5. openai-Client
- **Anti-Pattern**: `**httpx an NVIDIA NIM** OpenAI`
- **Warum**: Zusätzlicher HTTP-Client, falscher Endpoint
- **Ersatz**: `httpx.post("https://integrate.api.nvidia.com/v1/...")`
- **Status**: 🔴 BANNED (semgrep Regel: `banned-openai-client`)

### 6. pyautogui / pynput
- **Anti-Pattern**: `**BANNED – niemand importiert pyautogui**` für Mausbewegungen
- **Warum**: Bewegt Nutzer-Maus, stört User
- **Ersatz**: AXPress via skylight-cli (keine Mausbewegung)
- **Status**: 🔴 BANNED (semgrep Regeln: `banned-pyautogui`, `banned-pynput`)

### 7. Recovery-Mode
- **Anti-Pattern**: `recovery_mode: true` als Fallback
- **Warum**: Omni soll ALLE Entscheidungen treffen
- **Ersatz**: Omni macht 100% der Entscheidungen
- **Status**: 🔴 BANNED (semgrep Regel: `banned-recovery-mode`)

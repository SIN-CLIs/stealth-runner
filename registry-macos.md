# registry-macos.md — macOS Commands Registry

> **Category**: macOS | **Master**: [registry.md](registry.md)

---

## C‑chrome‑launch
**Command**: `playstealth launch --url 'URL'`
**File**: [commands/playstealth/launch.md](commands/playstealth/launch.md)
**Purpose**: Isolierte Chrome-Instanz starten (nicht User-Chrome!)

## C‑chrome‑kill
**Command**: `SessionManager.close_all()`
**File**: [commands/session-manager/launch.md](commands/session-manager/launch.md)
**Purpose**: BOT Chrome sauber beenden (NIEMALS `pkill -f "heypiggy-bot"`!)

## C‑recovery‑mode
**Command**: `csrutil disable` (macOS Recovery Mode)
**File**: [commands/macos-recovery-mode.md](commands/macos-recovery-mode.md)
**Purpose**: SIP deaktivieren für Accessibility API (SECRET WAY)

## BANNED macOS Commands

| Command | Grund |
|---------|-------|
| `pkill -f "heypiggy-bot"` | Killt ALLE Chrome (USER+BOT) |
| `killall Google Chrome` | Killt ALLE Chrome |
| `open -na "Google Chrome"` | Startet User-Chrome, nicht isoliert |
| Applikationen per Maus bedienen | pyautogui/pynput BANNED |

**Letztes Update**: 2026-05-05

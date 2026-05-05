# registry-perception.md — Perception Commands (SENSE Layer)

> **Category**: Perception | **Layer**: SENSE | **Master**: [registry.md](registry.md)

---

## C‑capture‑hybrid (PRIMARY)
**Command**: `cua-driver call get_window_state`
**File**: [commands/cua-driver/get-window-state.md](commands/cua-driver/get-window-state.md)
**Purpose**: Kompletten AX-Tree eines Fensters laden (alle Elemente mit Indices, Labels, Positionen)
**Syntax**: `echo '{"pid": PID, "window_id": WID}' | cua-driver call get_window_state`
**Returns**: JSON mit `element_count`, `tree_markdown`, `screenshot_width/height`
**Zugehörige Commands**: [list_windows](commands/cua-driver/list-windows.md) | [find-element-index](commands/cua-driver/find-element-index.md) | [B‑capture‑raw](commands/banned-capture-raw.md)

---

## C‑list‑windows
**Command**: `cua-driver call list_windows`
**File**: [commands/cua-driver/list-windows.md](commands/cua-driver/list-windows.md)
**Purpose**: Alle offenen Fenster systemweit auflisten
**Syntax**: `cua-driver call list_windows`
**Returns**: JSON mit `windows[]` (window_id, pid, title, bounds, is_on_screen)
**Zugehörige Commands**: [get_window_state](commands/cua-driver/get-window-state.md) | [find-pid-wid](commands/cua-driver/find-pid-wid.md)

---

## C‑find‑element
**Command**: `cua-driver call get_window_state` + grep
**File**: [commands/cua-driver/find-element-index.md](commands/cua-driver/find-element-index.md)
**Purpose**: Element-Index aus AX-Tree finden (nach Label/Rolle)
**Zugehörige Commands**: [click](commands/cua-driver/click.md) | [set-value](commands/cua-driver/set-value.md)

---

## C‑macos‑scan (SYSTEM SCAN)
**Command**: `macos-ax-cli find "Text"`
**Purpose**: Systemweite Textsuche in allen Fenstern
**Syntax**: `macos-ax-cli find "Suchbegriff"`
**Zugehörige Commands**: [list_windows](commands/cua-driver/list-windows.md)

---

## C‑audio‑capture
**Command**: `python3 -m cli.modules.audio_capture --capture --analyze`
**Purpose**: Audio von Survey-Seiten aufnehmen (BlackHole + ffmpeg + NVIDIA Omni)
**Status**: 🟡 In Entwicklung
**Zugehörige Commands**: (none yet)

---

## Verboten (BANNED in dieser Kategorie)

| Command | Grund | Ersatz |
|---------|-------|--------|
| `skylight-cli screenshot` | BANNED — CUA-ONLY Architektur | `cua-driver call get_window_state` |
| `cdp --screenshot` | BANNED — CDP für Navigation verboten | `cua-driver call get_window_state` |
| `webauto-nodriver observe_screen` | ABSOLUT BANNED | cua-driver |

---

**Letztes Update**: 2026-05-05

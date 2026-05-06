# registry-actuation.md — Actuation Commands (ACT Layer)

> **Category**: Actuation | **Layer**: ACT | **Master**: [registry.md](registry.md)

---

## C‑captcha‑solver (NEU 2026-05-05)
**Module**: `cli.modules.captcha_solver.CaptchaSolver`
**Purpose**: Slide + Drag-Drop Captchas via cua-driver drag + AppleEvents JS
**Syntax**: `CaptchaSolver(pid, wid).solve_slide()`
**Verify**: 5/5 GoCaptcha Slide solved. Dynamische Window-Position.
**Zugehörige Commands**: [captcha/solve-slide.md](commands/captcha/solve-slide.md) | [captcha/solve-text.md](commands/captcha/solve-text.md)

## C‑click (PRIMARY)
**Command**: `cua-driver call click`
**File**: [commands/cua-driver/click.md](commands/cua-driver/click.md)
**Purpose**: Element per AXPress klicken (Button, Link, Radio-Button, Checkbox, AXGroup)
**Syntax**: `echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click`
**Returns**: `✅ Performed AXPress on [IDX] AXRole "Label".`
**Verify**: `"verify": true` → Daemon prüft Zustand nach Klick (selected/checked/value)
**Zugehörige Commands**: [set-value](commands/cua-driver/set-value.md) | [find-element-index](commands/cua-driver/find-element-index.md) | [click-survey-card](commands/cua-driver/click-survey-card.md) | [B‑click‑coords](commands/banned-coordinates-click.md)

---

## C‑click‑survey‑card (HEYPIGGY-SPEZIFISCH)
**Command**: `cua-driver call click` (auf AXGroup Survey Card)
**File**: [commands/cua-driver/click-survey-card.md](commands/cua-driver/click-survey-card.md)
**Purpose**: Heypiggy Survey Card klicken (AXGroup mit onclick)
**Entdeckung**: AXGroup akzeptiert AXPress obwohl Rolle keine explizite "Press"-Aktion hat
**Zugehörige Commands**: [click](commands/cua-driver/click.md) | [list-windows](commands/cua-driver/list-windows.md)

---

## C‑set‑value (TEXT INPUT)
**Command**: `cua-driver call set_value`
**File**: [commands/cua-driver/set-value.md](commands/cua-driver/set-value.md)
**Purpose**: Text in Eingabefeld setzen
**Syntax**: `echo '{"pid": PID, "window_id": WID, "element_index": IDX, "value": "TEXT"}' | cua-driver call set_value`
**Zugehörige Commands**: [click](commands/cua-driver/click.md) | [press_key](commands/cua-driver/navigate-url.md)

---

## C‑navigate (URL)
**Command**: `cua-driver call click` → addr_bar + `set_value` → URL + `press_key` → Enter
**File**: [commands/cua-driver/navigate-url.md](commands/cua-driver/navigate-url.md)
**Purpose**: URL-Navigation via CUA (KEIN CDP!)
**Zugehörige Commands**: [click](commands/cua-driver/click.md) | [set-value](commands/cua-driver/set-value.md)

---

## C‑press‑key
**Command**: `cua-driver call press_key`
**File**: [commands/cua-driver/navigate-url.md](commands/cua-driver/navigate-url.md) (eingebettet)
**Purpose**: Tastendruck (Enter, Tab, Escape)
**Syntax**: `echo '{"pid": PID, "key": "return"}' | cua-driver call press_key`

---

## Fallback‑Kette (nur wenn CUA versagt)

| Priorität | Methode | Bedingung |
|-----------|---------|-----------|
| 1 | AXPress (cua-driver click) | PRIMARY — immer zuerst |
| 2 | Koordinaten-Click | Nur wenn AXPress fehlschlägt + Position bekannt |
| 3 | CDP JavaScript evaluate | NUR für JS-Ausführung (nicht direkt klicken!) |

---

## Verboten (BANNED in dieser Kategorie)

| Command | Grund | Ersatz |
|---------|-------|--------|
| `skylight-cli batch` | ✅ ERLAUBT — NEMO PRIMARY | Batch-Aktionen ausführen |
| `skylight-cli click --element-index` | DEPRECATED — NEMO PRIMARY | `skylight-cli batch` |
| `skylight-cli click --x --y` | BANNED — Koordinaten raten | cua-driver AXPress |
| `webauto-nodriver click` | ABSOLUT BANNED | cua-driver |
| `pyautogui.click()` | BANNED — Mausbewegung | cua-driver |
| `pynput mouse` | BANNED — Mausbewegung | cua-driver |
| CDP `Input.dispatchMouseEvent` | BANNED — CDP für Klicks | cua-driver |

---

**Letztes Update**: 2026-05-05

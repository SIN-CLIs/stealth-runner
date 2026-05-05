# cua-driver-switch-tab — Browser-Tab wechseln via CUA ✅

## Status
**VERIFIED** — 2026-05-05, PID=78708 WID=57128

## Command
```bash
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
```

## Live Example (2026-05-05)
```bash
# Tabs im Chrome-Fenster finden
echo '{"pid": 78708, "window_id": 57128}' | cua-driver call get_window_state
# → [47] AXRadioButton (HeyPiggy Dashboard)
# → [51] AXRadioButton (PureSpectrum)

# Zu PureSpectrum-Tab wechseln
echo '{"pid": 78708, "window_id": 57128, "element_index": 51}' | cua-driver call click
# → ✅ Performed AXPress — Tab aktiv

# Zurück zum Dashboard
echo '{"pid": 78708, "window_id": 57128, "element_index": 47}' | cua-driver call click
# → ✅ Performed AXPress — Dashboard aktiv
```

## Erkennung
Browser-Tabs erscheinen als `AXRadioButton` mit dem Seitentitel als Label.
Der AKTIVE Tab hat `value=1`, inaktive Tabs haben `value=0` (wenn sichtbar).
Window-Titel ändert sich auf den Titel des aktiven Tabs.

## Zugehörige Commands
- [cua-driver/click.md](click.md) — Element klicken
- [cua-driver/list-windows.md](list-windows.md) — Fenster finden
- [cua-driver/get-window-state.md](get-window-state.md) — AX-Tree lesen

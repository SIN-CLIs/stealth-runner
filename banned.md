# banned.md — Verbotene Patterns (ABSOLUTE VERBOTE)

> **Jeder Verstoß gegen diese Liste macht den Survey sofort erkennbar.**
> Der `stealth-runner` wird keine dieser Techniken verwenden.

---

## ❌ ABSOLUT VERBOTEN

### 1. `cua-driver` (ALT, ERSETZT)
- **Ersatz:** `skylight-cli` v0.2.0+ (SkyLight.framework, unsichtbare Events)
- **Commit:** `efd363f`

### 2. `open -na "Google Chrome"` (FALSCHER BROWSER-START)
- **Ersatz:** `playstealth-cli launch --url <URL> --json`

### 3. `AXStaticText` klicken (WIRKUNGSLOS)
- **Ersatz:** Nur `AXButton`, `AXLink`, `AXCheckBox`, `AXRadioButton`, `AXPopUpButton`, `AXTextField`, `AXSlider`

### 4. Klick OHNE Vision (BLINDES RATEN)
- **Ersatz:** Screenshot → VisionClient → JSON-Action → execute

### 5. Chrome DevTools Protocol (CDP)
- **Ersatz:** `skylight-cli` (Betriebssystemebene, kein DOM)

### 6. Chrome Extensions
- **Ersatz:** Keine. Alle Aktionen via `skylight-cli`.

### 7. DOM-Manipulation via JavaScript
- **Ersatz:** `skylight-cli type`, `skylight-cli click`

### 8. Cursor-Stealing (`CGEvent.post`)
- **Ersatz:** `AXUIElementPerformAction(element, kAXPressAction)` — Accessibility-API, kein Cursor
- **⚠️ CGEventPostToPid funktioniert NICHT auf Chrome 148/macOS 26! Nur AXPress.**

### 9. Unverschlüsselte Credentials im Repo
- **Ersatz:** `.env.example` mit Platzhaltern

### 10. Klick auf Chrome-UI-Elemente
- **Ersatz:** `validate_click_coordinates()` filtert Chrome-UI

### 11. `pgrep` + `cua-driver list_windows` für Fenster-Erkennung
- **Ersatz:** `playstealth-cli launch` im `LAUNCH_BROWSER`-State

### 12. Fehlende `unmask-cli` Verifikation
- **Ersatz:** `VERIFY`-State nach jedem `EXECUTE`

---

## ✅ AUSSCHLIESSLICH ERLAUBT (Stealth-Triade)

| Tool | Zweck | Befehl |
|------|-------|--------|
| `playstealth-cli` | Browser-Start + Tarnung | `launch --url <URL> --json` |
| `skylight-cli` | Screenshots + Aktionen | `screenshot`, `click`, `type`, `scroll`, `drag`, `hold`, `keypress` |
| `unmask-cli` | Stealth-Verifikation | `verify-stealth --pid <PID>` |

**Kein Workaround. Kein Fallback. Keine Ausnahme.**

---

## 🔍 Erkennungsmuster

| Verbotenes Pattern | grep-Befehl |
|--------------------|-------------|
| `cua-driver` | `grep -r "cua-driver" --include="*.py"` |
| `open -na Chrome` | `grep -r "open.*Chrome" --include="*.py"` |
| `AXStaticText` Klick | `grep -r "AXStaticText" --include="*.py"` |
| CDP | `grep -r "Page\.\|Runtime\.\|Input\." --include="*.py"` |
| .env Secrets | `grep -r "HEYPIGGY_\|API_KEY" .env` |

---

## 📜 Historie der Verstöße

| Datum | Verstoß | Folge |
|-------|---------|-------|
| 2026-04-30 | `--x`/`--y` Koordinaten geraten | Apple-Menü geklickt (0,0) |
| 2026-04-30 | CGEventPostToPid benutzt | Kein Klick auf Chrome 148 |
| 2026-04-30 | `cua-driver call list_windows` | Survey-Start blockiert |
| 2026-04-30 | `open -na Chrome` | Kein Stealth-Browser |
| 2026-04-30 | `.env` mit Credentials | Gelöscht |

---

**Status:** ALLE VERSTÖSSE BEHOBEN · Stealth-Triade aktiv

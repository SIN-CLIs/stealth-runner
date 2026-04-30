# architecture.md — stealth‑runner v2.0

> **Definitive Architektur‑Referenz**
> Stand: 2026‑04‑30 · Commit `c1ddc87` · 18/18 Tests PASS

---

## 1. Systemkontext

Der `stealth‑runner` ist der zentrale Orchestrator der **Stealth‑Triade**.
Er steuert drei spezialisierte CLI‑Tools, die jeweils eine Schicht
der Tarnkette bilden, ohne jemals den physischen Cursor zu bewegen,
ohne Chrome DevTools Protocol (CDP) und ohne DOM‑Zugriff.

```
┌─────────────────────────────────────────────────────────────┐
│                      stealth‑runner                          │
│                  (Python 3.12+ / anyio)                      │
│                                                              │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  State Machine │  │ VisionClient │  │  AuditLog       │  │
│  │  (10 states)   │  │ (Llama 4     │  │  (JSONL trace)  │  │
│  │                │  │  Scout /     │  │                 │  │
│  │  StealthRunner │  │  Mistral 675)│  │                 │  │
│  └───────┬────────┘  └──────┬───────┘  └─────────────────┘  │
│          │                  │                                │
│  ┌───────┴──────────────────┴────────────────────────────┐  │
│  │                 StealthExecutor                        │  │
│  │         (CLI‑Bridge — NUR subprocess.run)              │  │
│  └───────┬──────────────┬──────────────────┬─────────────┘  │
│          │              │                  │                 │
└──────────┼──────────────┼──────────────────┼─────────────────┘
           │              │                  │
    ┌──────▼──────┐ ┌─────▼─────┐  ┌────────▼────────┐
    │playstealth  │ │ skylight  │  │  unmask‑cli     │
    │   ‑cli      │ │   ‑cli    │  │                 │
    │             │ │           │  │                 │
     │ Canvas/     │ │ AXPress   │  │ Fingerprint‑    │
     │ WebGL‑      │ │ (Access-  │  │ Verifikation    │
     │ Patches     │ │ ibility)  │  │                 │
    └─────────────┘ └───────────┘  └─────────────────┘
```

- **playstealth‑cli** – Startet einen getarnten Chrome (Canvas‑, WebGL‑,
  User‑Agent‑Patches) und gibt die PID zurück.
- **skylight‑cli** – Erstellt Screenshots mit Set‑of‑Marks (SoM),
  führt Klicks, Texteingaben, Scroll‑ und Drag‑Aktionen
  über `AXUIElementPerformAction` (Accessibility‑API) aus —
  `CGEventPostToPid` funktioniert NICHT auf Chrome 148/macOS 26.
- **unmask‑cli** – Prüft nach jeder Aktion den aktuellen Fingerprint
  und löst bei Detektion eine Profilrotation aus.

---

## 2. State Machine (10 Zustände)

```
                    ┌──────────┐
                    │   IDLE   │
                    └────┬─────┘
                         │
                    ┌────▼──────────┐
                    │ LAUNCH_BROWSER│
                    └────┬──────────┘
                         │
                    ┌────▼─────┐
                    │WAIT_READY│
                    └────┬─────┘
                         │
                    ┌────▼─────┐
          ┌─────────│ CAPTURE  │◄──────────────────────────┐
          │         └────┬─────┘                           │
          │              │                                 │
          │         ┌────▼─────┐                           │
          │         │  VISION  │                           │
          │         └────┬─────┘                           │
          │              │                                 │
          │         ┌────▼─────┐                           │
          │         │ EXECUTE  │                           │
          │         └────┬─────┘                           │
          │              │                                 │
          │         ┌────▼─────┐     ┌──────────┐         │
          │         │  VERIFY  │────▶│ RECOVERY │─────────┘
          │         └────┬─────┘     └──────────┘
          │              │
          │         ┌────▼─────┐
          │         │   DONE   │
          │         └──────────┘
          │              ▲
          └──────────────┘
           (loop CAPTURE → VISION → EXECUTE → VERIFY)
```

| Zustand | Methode | Aktion |
|---------|---------|--------|
| `IDLE` | – | Einstieg, erkennt ob PID schon existiert |
| `LAUNCH_BROWSER` | `_launch()` | `playstealth-cli launch --url <URL> --json` → PID |
| `WAIT_READY` | `_wait_ready()` | `skylight-cli screenshot --mode raw` → Seite geladen? |
| `CAPTURE` | `_capture()` | `skylight-cli screenshot --mode som --out step_N.png` |
| `VISION` | `_vision()` | `VisionClient.get_action(image, prompt)` → JSON |
| `EXECUTE` | `_execute()` | `skylight-cli click/type/scroll/drag/keypress` |
| `VERIFY` | `_verify()` | `unmask-cli verify-stealth --pid <PID>` |
| `RECOVERY` | `_recover()` | `playstealth-cli rotate-profile` → zurück zu `CAPTURE` |
| `DONE` | – | Terminalzustand |

**Implementierung:** `runner/state_machine.py` (55 Zeilen, Klasse `StealthRunner`).
Jeder Zustand ist eine `async`-Methode. Bei einer Exception in einem beliebigen
Zustand fängt `run()` den Fehler und geht nach `RECOVERY`.

---

## 3. Datenfluss pro Aktion (der „Golden Loop")

### Schritt 1 – CAPTURE
```
skylight-cli screenshot --pid 91048 --mode som --out /tmp/step_3.png
→ {"status":"ok","file":"/tmp/step_3.png"}
```

### Schritt 2 – VISION
```python
VisionClient.get_action("/tmp/step_3.png", build_prompt(context, 3))
→ {"action": "click", "element_id": 7, "reasoning": "Start button"}
```

### Schritt 3 – EXECUTE
```
skylight-cli click --pid 91048 --element-index 7
→ {"status":"ok","clicked":7}
```

### Schritt 4 – VERIFY
```
unmask-cli verify-stealth --pid 91048
→ {"status":"ok","detected":false}
```

---

## 4. StealthExecutor – CLI‑Bridge

**Datei:** `runner/stealth_executor.py` (35 Zeilen)

| Methode | CLI‑Aufruf |
|---------|-----------|
| `screenshot(out, mode)` | `skylight-cli screenshot --pid <PID> --mode som --out <path>` |
| `click(element_index)` | `skylight-cli click --pid <PID> --element-index <N>` |
| `click(x=x, y=y)` | `skylight-cli click --pid <PID> --x <X> --y <Y>` |
| `type_text(text)` | `skylight-cli type --pid <PID> --text "..."` |
| `scroll(direction)` | `skylight-cli scroll --pid <PID> --direction down` |
| `list_elements()` | `skylight-cli click --pid <PID> --element-index 0 --dry-run` |
| `get_window_state()` | `skylight-cli screenshot --pid <PID> --mode som --include-tree` |
| `verify_stealth()` | `unmask-cli verify-stealth --pid <PID>` |

---

## 5. VisionClient – Modell‑Schnittstelle

**Datei:** `runner/vision_client.py` (33 Zeilen)

**Modell‑Kaskade:**
1. Cloudflare Workers AI (`@cf/meta/llama-4-scout-17b-16e-instruct`)
2. NVIDIA API (`mistralai/mistral-large-3-675b-instruct-2512`)
3. Parse‑Fallback: `re.search(r'\{.*\}', text)` → letztes JSON

---

## 6. Prompt‑Kit – System‑Prompt

**Datei:** `runner/prompt_kit.py` (31 Zeilen)

- **10 Aktionen:** `click`, `type`, `keypress`, `scroll`, `drag`, `hold`, `select-option`, `track`, `wait`, `done`
- **Anti‑Fehler‑Regeln:** NIEMALS `AXStaticText` klicken
- **CAPTCHA‑Strategien:** `hold` für Turnstile, `click`‑Kacheln für reCAPTCHA

---

## 7. HumanProfile

**Datei:** `runner/human_profile.py` (11 Zeilen)

| Parameter | Bereich |
|-----------|---------|
| `min_delay` | 0.8–2.0s |
| `max_delay` | 3.0–6.0s |
| `typing_speed` | 60–120 chars/min |

---

## 8. AuditLog

**Datei:** `runner/audit_log.py` (9 Zeilen)

JSONL in `~/.stealth_runner/traces.jsonl`.

---

## 9. sin_survey_core

### 9.1 Panel‑Detektoren (`detectors.py`, 173 Zeilen)
8 Provider: PureSpectrum, Dynata, Sapio, Cint, Lucid, HeyPiggy, MarketSight, Bilendi

### 9.2 Reward‑Extraktor (`extractor.py`, 10 Zeilen)
6 Regex‑Patterns für EUR‑Beträge

### 9.3 Fehler‑Klassifikation (`templates.py`, 12 Zeilen)
4 Kategorien: disqualified, quota_full, attention_failed, not_found

---

## 10. Projektstruktur

```
stealth-runner/
├── main.py                          # Einstiegspunkt
├── runner/
│   ├── state_machine.py             # 10-State Orchestrator
│   ├── stealth_executor.py          # CLI-Bridge
│   ├── vision_client.py             # Llama 4 Scout / Mistral 675B
│   ├── prompt_kit.py                # SYSTEM_PROMPT
│   ├── human_profile.py             # Delays
│   └── audit_log.py                 # JSONL Trace
├── sin_survey_core/
│   ├── panels/detectors.py          # 8 Panel-Provider
│   ├── rewards/extractor.py         # EUR-Parsing
│   └── errors/templates.py          # Fehler-Klassifikation
├── tests/
├── [9 md-Dokumente]
└── .env.example
```

---

## 11. Recovery‑Strategie

| Fehlerfall | Mechanismus |
|-----------|------------|
| Exception in Zustand | `try/except` → `RECOVERY` |
| `detected: true` | `rotate-profile` → `CAPTURE` |
| Vision ungültig | `re.search` Extraktion |
| Vision ausgefallen | Harter Fallback `element_id=0` |

---

## 12. Verbotene Patterns

- ❌ `cua‑driver` · ❌ `open -na` · ❌ `AXStaticText` klicken
- ❌ CDP · ❌ Chrome Extensions · ❌ DOM‑Manipulation · ❌ Cursor‑Stealing

---

**Architektur‑Version:** 2.0 · **Status:** 18/18 Tests PASS · Smoke Test ALL GREEN

# stealth-runner

**Orchestrator der Stealth-Triade**  
`playstealth-cli` · `skylight-cli` · `unmask-cli`

Der `stealth-runner` ist eine zustandsgesteuerte Automatisierungspipeline, die Webumfragen vollständig unsichtbar abwickelt – ohne Cursorbewegung, ohne DOM‑Zugriff, ohne Chrome DevTools Protocol (CDP).  
Er kombiniert drei spezialisierte CLI‑Tools zu einer lückenlosen **Sense‑Think‑Act**‑Kette, die selbst modernste Anti‑Bot‑Systeme unterläuft.

## Architektur

```
                      ┌──────────────────────────┐
                      │     stealth-runner        │
                      │   (Python 3.12 State      │
                      │     Machine)              │
                      └──────────┬───────────────┘
                                 │
                    ┌────────────┼────────────────┐
                    │            │                │
              ┌─────▼─────┐ ┌───▼────────┐ ┌─────▼─────┐
              │ playstealth│ │ skylight   │ │  unmask   │
              │   -cli     │ │   -cli     │ │   -cli    │
              └─────────────┘ └────────────┘ └───────────┘
```

- **playstealth‑cli** startet einen getarnten Chrome und liefert die PID.
- **skylight‑cli** erstellt Screenshots mit Element‑Markierungen (SoM) und führt unsichtbare Klicks, Texteingaben, Scroll‑ und Drag‑Aktionen aus.
- **unmask‑cli** prüft nach jeder Aktion, ob die Tarnung noch intakt ist.

Der Runner orchestriert alles über eine **asynchrone State Machine** und persistiert jede Aktion in einem Audit‑Log.

## Zustände

```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
```

Jeder Übergang ist ein atomarer CLI‑Aufruf – kein Event‑Bus, kein CDP, keine persistenten Server‑Prozesse.

## Schnellstart

### 1. Abhängigkeiten

- **macOS ≥ 13** (für SkyLight.framework)
- **Python ≥ 3.12**
- **Drei CLI‑Tools** (müssen im `PATH` liegen):
  - [`playstealth-cli`](https://github.com/SIN-CLIs/playstealth-cli)
  - [`skylight-cli`](https://github.com/SIN-CLIs/skylight-cli)
  - [`unmask-cli`](https://github.com/SIN-CLIs/unmask-cli)

### 2. Installation

```bash
git clone https://github.com/OpenSIN-AI/stealth-runner.git
cd stealth-runner
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3. Konfiguration

```bash
export CF_ACCOUNT_ID="deine-cloudflare-account-id"
export CF_GATEWAY_ID="dein-gateway"
export CF_API_TOKEN="dein-api-token"
```

### 4. Ausführen

```bash
stealth-runner "https://heypiggy.com/?page=dashboard"
```

## Tests

```bash
pytest tests/
```

## Dokumentation für Agenten

- `AGENTS.md` – Erlaubte Tools, Verbote, Beispiele
- `banned.md` – Liste der verbotenen Techniken (CDP, Chrome‑Extensions, `cua‑driver`)
- `architecture.md` – Vollständige Systemarchitektur

## Roadmap

- [x] State Machine mit 9 Zuständen und Recovery‑Pfad
- [x] StealthExecutor ohne `cua‑driver`‑Fallback
- [x] Vollständiger Vision‑Prompt (10 Aktions‑Typen inkl. Captcha)
- [x] OCR‑Fallback für Canvas‑Elemente (Apple Vision Framework)
- [ ] Human‑Profile aktivieren (Jitter, Bézier‑Kurven, Hover‑Delay)
- [ ] Parallelisierung mehrerer Survey‑Instanzen

## Lizenz

MIT – siehe `LICENSE`.

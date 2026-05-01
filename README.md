# stealth-runner 🕵️

> **Autonome Survey-Automation mit KI-Vision.**  
> Orchestriert Google Login → Umfrage-Teilnahme → EUR-Verdienst via NVIDIA Nemotron 3 Nano Omni.  
> **100% skylight-cli – keine Mausbewegung, kein Nutzer-Chrome.**

[![CI](https://github.com/OpenSIN-AI/stealth-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenSIN-AI/stealth-runner/actions/workflows/ci.yml)
[![Graphify](https://img.shields.io/badge/Graphify-Knowledge%20Graph-2ea44f?logo=gitbook)](graphify-out/graph.html)
[![Semgrep](https://img.shields.io/badge/Semgrep-Architecture%20Guard-8A2BE2)](.semgrep_rules.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![NVIDIA NIM](https://img.shields.io/badge/Vision-Nemotron%20Omni-76B900?logo=nvidia)](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)

---

## 🔥 Features

| Feature | Status | Beschreibung |
|---------|--------|-------------|
| **Google Login** | ✅ Automatisiert | playstealth → Google OAuth → Email → Passwort → Dashboard |
| **Nemotron Omni Vision** | ✅ Produktion | Video+Audio+Bild+Text in EINEM NIM-Call, 9× effizienter |
| **Rolling Video Buffer** | ✅ Live | screen-follow + ffmpeg + Conv3D für temporale Analyse |
| **SSE Streaming** | ✅ Tokenweise | `stream: true` → Antwort kommt chunk-by-chunk |
| **Graphify Graph** | ✅ 6 Repos | 4.820 Nodes, 10.860 Edges, 284 Communities |
| **Semgrep Guard** | ✅ Pre-Commit | 11 Regeln blockieren BANNED Muster |
| **screen-follow Video** | ✅ Daueraufnahme | MP4-Recording für Post-Mortem-Analyse |

---

## 🚀 Quick Start

```bash
# 1. Chrome starten (isoliert, keine Nutzer-Störung)
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → {"pid": 12345, "status": "ok"}

# 2. Google Login (automatisiert)
bash cli/heypiggy-login 12345

# 3. Screenshot + Omni Vision
skylight-cli screenshot --pid 12345 --mode som --output /tmp/page.png
python3 -c "
from runner.nemotron_omni import get_omni
action = get_omni().analyze_image('/tmp/page.png', 'What button to click?')
print(action)  # → {'action': 'click', 'element_index': 43}
"

# 4. Unsichtbarer Klick
skylight-cli click --pid 12345 --element-index 43
```

---

## 🏗️ Architektur

```
┌──────────────────────────────────────────────────────────────┐
│                        STACK                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  playstealth launch ──→ isolierte Chrome-Instanz             │
│       │              (eigene PID, eigener Cache)             │
│       ▼                                                      │
│  LiveOmniMonitor ──→ Capture → Vision → Execute → Loop      │
│       │              ├─ Screenshot (schnell, 1-2 FPS)       │
│       │              ├─ Rolling Video (temporal, Conv3D)    │
│       │              └─ SSE Streaming (tokenweise)           │
│       ▼                                                      │
│  NVIDIA NIM ──→ nvidia/nemotron-3-nano-omni-30b-a3b         │
│       │         POST https://integrate.api.nvidia.com/v1/    │
│       ▼                                                      │
│  skylight-cli ──→ AXPress, --element-index                   │
│                  KEINE Mausbewegung                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 🔗 Stealth-Quad (7 Repos)

| Layer | Repo | Technologie |
|-------|------|-------------|
| **🧠 Orchestrator** | [stealth-runner](https://github.com/OpenSIN-AI/stealth-runner) | Python, State Machine, Omni Vision |
| **🎭 HIDE** | [playstealth-cli](https://github.com/SIN-CLIs/playstealth-cli) | Python, Playwright, Fingerprint |
| **🖱️ ACT** | [skylight-cli](https://github.com/SIN-CLIs/skylight-cli) | Swift, AXUIElementPerformAction |
| **👁️ SENSE** | [unmask-cli](https://github.com/SIN-CLIs/unmask-cli) | TypeScript, CDP, JSON-RPC |
| **📹 VERIFY** | [screen-follow](https://github.com/SIN-CLIs/screen-follow) | Swift, ScreenCaptureKit, MP4 |
| **🤖 Vision** | [Nemotron Omni](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning) | NVIDIA NIM, 30B-A3B MoE |
| **📊 Graph** | [Graphify](https://github.com/safishamsi/graphify) | 6 Repos merged → 4820 Nodes |

---

## 📦 Installation

```bash
git clone https://github.com/OpenSIN-AI/stealth-runner.git
cd stealth-runner
pip install -e '.[dev]'

# Abhängigkeiten
pip install semgrep graphifyy httpx diskcache pyyaml
```

### Voraussetzungen

| Tool | Zweck | Install |
|------|-------|---------|
| `skylight-cli` | UI-Interaktion (Accessibility) | [SIN-CLIs/skylight-cli](https://github.com/SIN-CLIs/skylight-cli) |
| `playstealth` | Isolierter Chrome-Start | [SIN-CLIs/playstealth-cli](https://github.com/SIN-CLIs/playstealth-cli) |
| `screen-follow` | Video-Aufzeichnung | [SIN-CLIs/screen-follow](https://github.com/SIN-CLIs/screen-follow) |
| `semgrep` | Architecture Guard | `pip3 install semgrep` |
| `graphify` | Knowledge Graph | `pip3 install graphifyy` |
| NVIDIA API Key | Vision AI | `export NVIDIA_API_KEY=nvapi-...` |

---

## 🧠 Vision Model

```yaml
# config/vision_models.yaml
current_model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
fallback_models:
  - meta/**nvidia/nemotron-3-nano-omni-30b-a3b-reasoning**
max_tokens: 300
```

| Eigenschaft | Wert |
|-------------|------|
| Modell | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| API | `POST https://integrate.api.nvidia.com/v1/chat/completions` |
| Auth | `Authorization: Bearer $NVIDIA_API_KEY` |
| Streaming | `stream: true` + `Accept: text/event-stream` |
| Antwortfeld | `msg.get("reasoning") or msg.get("content")` |

---

## 🛡️ Architecture Guard (Semgrep)

11 Regeln blockieren BANNED Muster **vor dem Commit**:

```bash
semgrep --config=.semgrep_rules.yaml .
```

| Regel | Blockiert |
|-------|-----------|
| `banned-chrome-pgrep` | `**playstealth launch (isolierte PID)**` |
| `banned-chrome-open` | `**playstealth launch**` |
| `banned-**NIEMALS – BANNED (semgrep Regel)**` |
| `banned-pyautogui` | `**BANNED – niemand importiert pyautogui**` |
| `banned-pynput` | `**BANNED – niemand importiert pynput**` |
| `banned-openai-client` | `**httpx an NVIDIA NIM**` |
| `banned-coordinates-click` | `skylight-cli click --x` |
| `banned-**skylight-cli**` | **skylight-cli** |
| `banned-recovery-mode` | `recovery_mode: true` |
| `mandatory-playstealth-launch` | Chrome direkt starten |

---

## 📊 Knowledge Graph (Graphify)

```
📊 4.820 Nodes, 10.860 Edges, 284 Communities
   ├── stealth-runner         (457 nodes,  36 communities)
   ├── playstealth-cli       (1.166 nodes, 78 communities)
   ├── skylight-cli          (120 nodes,  19 communities)
   ├── screen-follow         (252 nodes,  17 communities)
   ├── unmask-cli            (214 nodes,  25 communities)
   └── A2A-SIN-Worker        (2.625 nodes, 110 communities)
```

```bash
graphify query "Wie hängen X und Y zusammen?"
graphify path "ModulA" "ModulB"
graphify update .        # AST-Rebuild nach Code-Änderungen
```

🔗 [Interaktiver Graph](graphify-out/graph.html) | 📄 [Report](graphify-out/GRAPH_REPORT.md)

---

## 🎯 Anwendungsfälle

### Heypiggy.com Google Login (vollautomatisiert)
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
bash cli/heypiggy-login <PID>
# → 5 Schritte: Google Klick → Email → Weiter → Passwort → Weiter
```

### Post-Mortem Video-Analyse
```bash
screen-follow record --video --output /tmp/session.mp4
# ... Session durchlaufen ...
python3 -m runner.video_analyzer --last flow
```

### Live Omni Monitor
```bash
python3 -c "
from runner.live_omni_monitor import LiveOmniMonitor
m = LiveOmniMonitor(fps=1.0, debug=True)
m.start('https://heypiggy.com/?page=dashboard')
m.run_continuous(max_steps=100)
"
```

---

## Golden Rules (UNVERBRÜCHLICH)

1. **NUR `skylight-cli`** – NIE **skylight-cli**
2. **NUR `--element-index`** – NIE `--x`/`--y` Koordinaten
3. **NUR `playstealth launch`** – NIE `**playstealth launch (isolierte PID)**` oder `open -na`
4. **NUR NVIDIA NIM httpx** – NIE openai-Client
5. **JEDER Schritt durch Vision** – Kein DOM-Prescan
6. **Video bei jedem Build** – `screen-follow record --video`

---

## 📚 Dokumentation

| Datei | Inhalt |
|-------|--------|
| [AGENTS.md](AGENTS.md) | Vollständige Agenten-Anleitung |
| [brain.md](brain.md) | Systemwissen & Architektur |
| [goal.md](goal.md) | Ziele & Meilensteine |
| [fix.md](fix.md) | Bekannte Bugs & Fixes |
| [learn.md](learn.md) | Session Learnings |
| [anti-learn.md](anti-learn.md) | Anti-Patterns |
| [successful.md](successful.md) | Was funktioniert |
| [issues.md](issues.md) | Offene Issues |
| [commands.md](commands.md) | Alle Befehle |
| [HEALTH_REPORT.md](HEALTH_REPORT.md) | Doctor Audit |

## 🔗 Verwandte Repos

- [SIN-CLIs/playstealth-cli](https://github.com/SIN-CLIs/playstealth-cli) – Browser-Launcher
- [SIN-CLIs/skylight-cli](https://github.com/SIN-CLIs/skylight-cli) – Accessibility Klick
- [SIN-CLIs/screen-follow](https://github.com/SIN-CLIs/screen-follow) – Screen Recording
- [SIN-CLIs/unmask-cli](https://github.com/SIN-CLIs/unmask-cli) – DOM/NET/Console X-Ray
- [OpenSIN-AI/A2A-SIN-Worker-heypiggy](https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy) – Legacy Worker

## Lizenz

MIT – siehe [LICENSE](LICENSE)

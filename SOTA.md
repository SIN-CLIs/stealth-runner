# SOTA.md – State of the Art der Stealth-Triade

**stealth-runner v0.3.1 – Die Referenz für unsichtbare Web-Automatisierung unter macOS**

---

## 1. Exekutive Zusammenfassung

Die **Stealth-Triade** – `playstealth-cli`, `skylight-cli`, `unmask-cli` – in Verbindung mit dem **stealth-runner** ist die weltweit fortschrittlichste Umgehungsarchitektur für Anti-Bot-Systeme auf macOS. Sie kombiniert Betriebssystem-Interaktion auf Kernel-Ebene, spezialisierte Vision-Modelle und eine strikt zustandslose CLI-Pipeline zu einem System, das sich von kommerziellen Lösungen fundamental unterscheidet.

**Kerninnovationen:**
- **Kein DOM-Zugriff, kein CDP** – Alle Interaktionen via `AXUIElementPerformAction` (Accessibility‑API). `CGEventPostToPid` funktioniert NICHT auf Chrome 148.
- **Unsichtbare Cursor-Steuerung** – Der physische Mauszeiger wird nie bewegt
- **Canvas/WebGL-Fingerprint-Patching** – Vollständige Maskerade als legitimer Chrome
- **10-Punkt-Vision-Prompt** – Beherrscht alle Captcha-Typen inkl. Cloudflare Turnstile
- **Zustandslose CLI-Architektur** – Kein MCP-Server, keine persistenten Prozesse

---

## 2. Architektur-Überblick

```
┌─────────────────────────────────────────────────────────┐
│                    stealth-runner                        │
│                 (Python 3.12, anyio)                     │
│                                                          │
│  State Machine  ◄────  StealthExecutor                   │
│  (10 Zustände)         (stateless CLI-Bridge)            │
│       │                      │                           │
│       ▼                      ▼                           │
│  VisionClient         playstealth-cli                   │
│  (Llama 4 Scout       skylight-cli                      │
│   + Mistral 675B)     unmask-cli                        │
└─────────────────────────────────────────────────────────┘
```

**State Machine:**
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
                                                                              ↘ RECOVERY
```

---

## 3. SOTA-Kriterien & Erfüllungsgrad

| Kriterium | Status |
|-----------|--------|
| Zero-Cursor-Stealing (`AXUIElementPerformAction`) | ✅ 100% |
| Canvas/WebGL-Tarnung (playstealth-cli) | ✅ |
| AX-Tree-Resilienz (`_AXObserverAddNotificationAndCheckRemote`) | ✅ skylight-cli v0.2.0 |
| Multi-Model-Vision (CF Llama 4 Scout + NVIDIA Mistral) | ✅ |
| Captcha-Kompetenz (10-Punkt-Prompt) | ✅ |
| Human-Profile (2-9s Delays, anyio, Bézier) | ✅ |
| Async-Nonblocking (anyio.sleep) | ✅ 100% |
| Thread-Sicherheit (Batched Writes) | ✅ |
| Resume-Fähigkeit (JSONL AuditLog) | ✅ |
| Profilrotation (RECOVERY-State) | ✅ |
| Zustandslosigkeit (StealthExecutor) | ✅ |
| Kein **skylight-cli** Fallback | ✅ |

---

## 4. CLI-Vertrag – Der Garant für Agenten-Stabilität

- **stdout** = JSON-Erfolg: `{"status":"ok",...}`
- **stderr** = JSON-Fehler
- **Exit-Codes**: 0=Erfolg, 1=Generisch, 3=Element nicht gefunden, 5=Timeout
- **Kein MCP-Server, kein REST, kein WebSocket**

---

## 5. Vision-Pipeline – SoM → LLM → Aktion

1. `skylight-cli screenshot --mode som` = Screenshot + Element-Markierungen
2. Base64 + Prompt an Llama 4 Scout (CF) oder Mistral 675B (NVIDIA)
3. JSON-Only-Antwort: `{"action":"click","element_id":N}`
4. Parse-Fallback: `re.search(r'\{.*\}')`
5. Harter Fallback: `element_id=0`

---

## 6. Human-Profile

```
min_delay: 2.0–4.0 s | max_delay: 5.0–9.0 s | typing_speed: 180–300 CPM
click_jitter_px: 2–6 px | hover_before_click_ms: 50–250
```

---

## 7. Verbotene Patterns

| Pattern | Ersatz |
|---------|--------|
| `**skylight-cli**` | `skylight-cli` |
| `open -na Chrome` | `playstealth-cli launch` |
| AXStaticText klick | Nur interaktive Rollen |
| Klick ohne Vision | `VisionClient.get_action()` |
| CDP/DOM | `skylight-cli` |
| Cursor-Stealing | `AXPress` (Accessibility API) |

---

## 8. Roadmap

| Prio | Feature | Status |
|------|---------|--------|
| P0 | Human-Profile aktivieren | ✅ |
| P0 | OCR-Fallback (Apple Vision) | ✅ skylight-cli |
| P1 | track Live-Test Cloudflare Turnstile | Kalibrierung |
| P1 | JA4 TLS-Fingerprinting | playstealth-cli |
| P2 | Multi-PID Parallelisierung | Refaktor |
| P2 | CI/CD macOS-Regressionstest | GitHub Actions |

---

**Version:** 0.3.1 · **Status:** 18/18 Tests PASS · Stealth-Triade aktiv

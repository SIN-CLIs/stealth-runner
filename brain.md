# brain.md – Zentrales Gedächtnis des stealth-runner v3.0

> **Stand: 30. April 2026 — AXPress-Durchbruch + Safe-Click-Pipeline**

## 1. Ziel
Vollautomatisches, unsichtbares Ausfüllen von Webumfragen mit maximaler Tarnung.

## 2. Architektur (final)
- Greenfield-Neubau als `stealth-runner`
- Stealth-Triade: `playstealth-cli` · `skylight-cli` · `unmask-cli`
- Alter `A2A-SIN-Worker-heypiggy` archiviert (nur Panel-Detektoren extrahiert)

## 3. 🔥 DURCHBRUCH: Klick-Mechanismus (30.4.2026, 9:50)

**Problem:** Kein einziger Klick kam auf Chrome 148 / macOS 26.3.1 an. Screenshot-Hashes vor/nach jedem Klick waren identisch.

**Root Cause:**
```
CGEventPostToPid(pid, event)        → Chrome 148 ignoriert KOMPLETT
CGEvent.post(tap: .cghidEventTap)   → Chrome 148 ignoriert KOMPLETT
```

**Lösung: AXPress (Accessibility API)**
```swift
AXUIElementPerformAction(element, kAXPressAction as CFString)
```
→ Chrome kann Accessibility-Klicks NICHT blockieren (VoiceOver, Switch Control etc.).
→ Beweis: Hash-Änderung `b1707908...` → `1e0d58e9...` nach Klick auf "Weiter"-Button.

**Voraussetzung für Web-Content-Elemente:**
```bash
# Chrome MUSS mit diesem Flag starten:
--force-renderer-accessibility

# Ohne Flag: 0 Web-Elemente im AX-Tree, nur Chrome-UI (Toolbar, Tabs, etc.)
# Mit Flag: 27+ Web-Elemente (Buttons, Links, Text)
```

**Bekanntes Problem:** Chrome mit `--force-renderer-accessibility` + `--user-data-dir=/tmp/...` stürzt nach ~30s auf macOS 26 Beta (GPU exit_code=15, Network-Service-Crash). Workaround: schnell arbeiten oder Crash-Ursache finden.

## 4. Safe-Click-Pipeline (niemals Apple-Menü!)

```
safe_click.py
  → Primer: skylight-cli click --x -1 --y -1
  → Element-Tabelle: skylight-cli screenshot --mode som --include-tree
  → Web-Button finden: 'AXWebArea' im path-Feld + interaktive Rolle
  → Klick: skylight-cli click --element-index N  (NIEMALS --x/--y!)
```

**WARUM DAS APPLE-MENÜ GEKLICKT WURDE:**
Der Agent hat (500, 600) als "Bildschirmmitte" geraten. (0,0) = Apple-Menü.
AX-Frame-Koordinaten aus skylight-cli sind BEREITS absolut. Nie selber rechnen.

## 5. Kernmodule (alle in `runner/`)

| Modul | Zweck |
|-------|-------|
| `state_machine.py` | 10-Zustands-Orchestrator (SurveyRunner) |
| `stealth_executor.py` | Zustandslose CLI-Bridge |
| `safe_click.py` | **EINZIGER** Klick-Wrapper — nur `--element-index` |
| `click_validator.py` | Blockiert `--x`/`--y`, erzwingt `--element-index` |
| `element_table.py` | Klassifiziert Web vs Chrome-UI |
| `vision_client.py` | Cloudflare + NVIDIA Vision-API |
| `vision_models.py` | Pydantic V2 Validierung |
| `prompt_kit.py` | SYSTEM_PROMPT + Prompt-Builder |
| `human_profile.py` | Realistische Verhaltensparameter |
| `audit_log.py` | Thread-sicheres JSONL-Log |
| `resilience.py` | Retry, Circuit Breaker, Shutdown |
| `survey_queue.py` | SQLite-Queue für parallele Instanzen |
| `config.py` | dotenv-Loader + Validierung |

## 6. NVIDIA Vision Model (WICHTIG!)

**Mistral hat KEIN Vision-Modell!** `mistralai/mistral-large-2-instruct` ist Text-only.

**Vision-fähige Modelle über NVIDIA NIM API (`nvapi-...` Key):**

| Modell-ID | Typ | Bewertung |
|-----------|-----|-----------|
| `meta/llama-3.2-90b-vision-instruct` | Vision-Language | ⭐ BESTE — 90B multimodal |
| `meta/llama-3.2-11b-vision-instruct` | Vision-Language | Gut, schneller |
| `nvidia/neva-22b` | Vision-Language | NVIDIA-eigen, solide |
| `microsoft/phi-3-vision-128k-instruct` | Vision-Language | Gut für Detail |
| `google/paligemma` | Vision-Language | Google, 3B |

**Empfehlung:** `meta/llama-3.2-90b-vision-instruct` als Primär, Fallback auf `nvidia/neva-22b`.

**API-Call:**
```python
import urllib.request, json, base64
url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {"Authorization": "Bearer nvapi-...", "Content-Type": "application/json"}
body = {
    "model": "meta/llama-3.2-90b-vision-instruct",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Welches Element soll ich klicken?"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
    ]}],
    "max_tokens": 300
}
req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
resp = json.loads(urllib.request.urlopen(req).read())
```

## 7. Verbote (unverändert, erweitert)
- ❌ `--x` oder `--y` Koordinaten → Apple-Menü-Gefahr
- ❌ `cua-driver` → ersetzt durch skylight-cli
- ❌ `open -na Chrome` → playstealth-cli launch nutzen
- ❌ `AXStaticText` klicken → nur interaktive Rollen
- ❌ CDP/DOM/Cursor-Stealing
- ❌ Ohne Primer-Klick klicken (User-Activation-Gate)
- ❌ `--no-primer` Flag benutzen

## 8. skylight-cli Commands (Referenz)
```bash
skylight-cli screenshot --pid PID --mode som --out file.png --include-tree
skylight-cli list-elements --pid PID
skylight-cli click --pid PID --element-index N         # ← NUR DAS
skylight-cli click --pid PID --x -1 --y -1             # Primer
skylight-cli hold --pid PID --element-index N --duration 3000  # Cloudflare
skylight-cli get-window-state --pid PID
skylight-cli wait-for-selector --pid PID --role AXButton --label "Weiter"
```

## 9. Alle 4 Repos (Stand 30.4.)
| Repo | Status | Letzter Commit |
|------|--------|---------------|
| stealth-runner | AGENTS.md + safe_click + validator | `cc9bd03` |
| skylight-cli | AXPress + hold + LICENSE + path | `d860e78` |
| unmask-cli | pre-scan (#76) | `944da1a` |
| playstealth-cli | Cloudflare Vision (#72) | synced |

## 10. Nächste Schritte
- [ ] Chrome-Stabilität mit `--force-renderer-accessibility` fixen (Crash-Ursache)
- [ ] NVIDIA Llama 3.2 90B Vision in `vision_client.py` einbauen
- [ ] Login-Flow (Google OAuth) automatisieren
- [ ] Survey-Loop: Dashboard → Umfrage finden → Fragen beantworten → EUR kassieren
- [ ] OpenTelemetry aktivieren (derzeit deaktiviert)

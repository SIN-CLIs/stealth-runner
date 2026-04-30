# brain.md – Zentrales Gedächtnis des stealth-runner

## 1. Ziel
Vollautomatisches, unsichtbares Ausfüllen von Webumfragen (HeyPiggy u.a.) mit
maximaler Tarnung. Kein DOM-Zugriff, keine Chrome-Extensions, keine Bewegung des
physischen Cursors, kein CDP.

## 2. Architektur-Entscheidung (final, v2.0)
- **Greenfield-Neubau** als `stealth-runner`.
- Der alte `A2A-SIN-Worker-heypiggy` ist **archiviert** – CDP-Bridge ersatzlos
  gestrichen.
- Die **Stealth-Triade** ersetzt **alles**:
  - `playstealth-cli` → Browser-Tarnung, Canvas/WebGL-Fingerprint-Schutz, Start
  - `skylight-cli`   → Targeted Window Capture (nur eigenes Fenster), SoM-Overlay,
                       unsichtbare Klicks/Texteingaben/Scroll/Drag/Hold/Track
  - `unmask-cli`     → Stealth-Verifikation nach jeder Aktion, Profilrotation bei
                       Detektion

## 3. Kernkomponenten (stealth-runner)
### 3.1 State Machine (`runner/state_machine.py`)
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
                                                                                ↘ RECOVERY
```
- `LAUNCH_BROWSER`: `playstealth-cli launch --url <URL> --json` → PID
- `WAIT_READY`: `skylight-cli wait-for-selector --selector AXButton,AXLink`
- `CAPTURE`: `skylight-cli screenshot --pid <PID> --mode som --out step_N.png`
- `VISION`: `VisionClient.get_action(image, step)` → Llama 4 Scout
- `EXECUTE`: `skylight-cli click|type|scroll|drag|hold|keypress` (je nach Vision-JSON)
- `VERIFY`: `unmask-cli verify-stealth --pid <PID>`
- `RECOVERY`: `playstealth-cli rotate-profile`, dann zurück zu `CAPTURE`
- Jeder Zustand ist eine async-Methode. Audit-Log nach jedem EXECUTE (Resume-fähig).

### 3.2 Stealth Executor (`runner/stealth_executor.py`)
- Kapselt **ausschließlich** die drei CLI-Tools.
- **Kein Fallback auf `cua-driver`** – bei fehlendem `skylight-cli` => FATAL ERROR.
- Methoden: `launch_browser(url)`, `screenshot(pid, mode, out)`, `click(pid, idx)`,
  `type_text(...)`, `verify_stealth(pid)`, `run(cmd)`.

### 3.3 Vision Client (`runner/vision_client.py`)
- PRIMARY: Cloudflare Workers AI mit Llama 4 Scout (1742-char System-Prompt)
- FALLBACK: NVIDIA Mistral 675B (NVIDIA_API_KEY)
- Prompt zwingt das Modell zu **JSON-Only** Ausgaben ohne Erklärungen.
- Bei Parse-Fehler fällt der Runner auf `{"action":"wait"}` zurück (sicherer Zustand).

### 3.4 Prompt Kit (`runner/prompt_kit.py`)
- 10 Aktionen: `click`, `type`, `keypress`, `scroll`, `drag`, `hold`,
  `select-option`, `track`, `wait`, `done`
- Anti-AXStaticText Regel (nur interaktive Rollen klicken)
- CAPTCHA-Strategien (hold für Turnstile, click-tiles für reCAPTCHA)
- Few-Shot Beispiele im Prompt

### 3.5 Human Profile (`runner/human_profile.py`)
- Pro Session zufällige Parameter: Jitter (2-6px), Hover-Delay (50-250ms),
  Typing-Delays (30-300ms), Bézier-Punkte (2-5)
- Wird bei jedem Klick und jeder Texteingabe angewendet

### 3.6 Audit Log (`runner/audit_log.py`)
- Schreibt JSONL in `~/.stealth_runner/traces.jsonl`

## 4. Extrahierte Module aus Alt-Worker
- `sin_survey_core/panels/detectors.py` — 8 Panel-Provider (PureSpectrum, Dynata,
  Sapio, Cint, Lucid, HeyPiggy, MarketSight, Bilendi)
- `sin_survey_core/rewards/extractor.py` — EUR-Parsing (6 Regex-Patterns)
- `sin_survey_core/errors/templates.py` — 4 Fehlerkategorien (disqualified,
  quota_full, attention_failed, not_found)

## 5. Verbote (aus banned.md, nicht verhandelbar)
- ❌ `cua-driver` — ALT, ersetzt durch `skylight-cli v0.2.0`
- ❌ `open -na "Google Chrome"` — FALSCH, nur `playstealth-cli launch`
- ❌ `AXStaticText` klicken — WIRKUNGSLOS, nur interaktive Rollen
- ❌ Klick ohne Vision — RATEN, muss via Llama 4 Scout
- ❌ Chrome DevTools Protocol (CDP) — Direkter DOM-Zugriff
- ❌ Chrome Extensions — Keine Bridge/Extension
- ❌ DOM-Manipulation — Kein document.querySelector
- ❌ Cursor-Stealing — Kein CGEvent.post(tap: .cghidEventTap)
- ❌ Unverschlüsselte Credentials — `.env` NIE ins Repo, nur `.env.example`

## 6. Datenfluss pro Aktion
1. `CAPTURE`: `skylight-cli screenshot --pid <PID> --mode som --out step_N.png`
   → PNG mit nummerierten Element-Markierungen (nur eigenes Fenster)
2. `VISION`: PNG + Prompt → Llama 4 Scout → `{"action":"click","element_id":12}`
3. `EXECUTE`: `skylight-cli click --pid <PID> --element-index 12`
   → unsichtbar via `CGEventPostToPid` (SkyLight.framework), kein Cursor-Diebstahl
4. `VERIFY`: `unmask-cli verify-stealth --pid <PID>` → `{"detected":false}`

## 7. OKRs & Roadmap
- [x] State Machine mit 10 Zuständen + RECOVERY (commit efd363f)
- [x] StealthExecutor ohne cua-driver-Fallback
- [x] Vollständiger Vision-Prompt (10 Aktions-Typen inkl. CAPTCHA)
- [x] sin_survey_core aus Alt-Worker extrahiert
- [x] 8 md-Dokumentationsdateien
- [x] OCR-Fallback für Canvas-Elemente (Apple Vision Framework)
- [ ] Human-Profile aktivieren (Jitter, Bézier-Kurven, Hover-Delay)
- [ ] Parallelisierung mehrerer Survey-Instanzen
- [ ] CI/CD für automatisierte Regressionstests gegen neue macOS-Versionen

## 8. Schnellstart
```bash
export CF_ACCOUNT_ID="..." CF_GATEWAY_ID="..." CF_API_TOKEN="..."
stealth-runner "https://heypiggy.com/?page=dashboard"
```

## 9. Smoke Test (30.04.2026)
- skylight-cli v0.2.0 ✅ | 90 AX elements ✅
- Vision NVIDIA Mistral ✅ | `element_id:42` mit EUR 2.23
- Click dry-run ✅ | State Machine mock ✅

# history.md — Development History (Updated 2026-05-01)

## 2026-05-01: LiveEye v7 — Motion Detection + Frame-Optimierung

**4 Performance-Optimierungen für die Live-Video-Pipeline:**

1. **Adaptive FPS via Motion Detection** (`runner/live_eye.py`):
   - cv2.absdiff Frame-Vergleich mit MSE Thresholds
   - Motion Class: low (MSE<2) / mid (2-15) / high (>15)
   - Bei Stillstand: kein Capturing neuer Frames

2. **Frame-Differencing** (`RingBuffer.add_frame()`):
   - Statische Frames (MSE < 2.0) werden übersprungen
   - ~50-80% weniger Frames bei Survey-Stillstand

3. **Conv3D Token-Optimierung** (`analyze()` → `num_frames`):
   - Dynamisch: -1 (Bewegung) / 8 (normal) / 4 (Stillstand)
   - Weniger API-Tokens = günstiger + schneller

4. **CRF Auto-Adjustment** (`RingBuffer.get_crf()`):
   - CRF 28 (Bewegung) / 35 (mid) / 40 (Stillstand)
   - Kleinere MP4s bei gleicher Erkennungsqualität

**Weitere Änderungen:**
- `runner/live_omni_monitor.py`: PNG→JPEG quality=50 (~80% weniger Payload)
- `AGENTS.md`: v7 Changelog + Motion Detection Tabelle + "Nicht Vergessen" Warnungen
- `brain.md`: v7 Features dokumentiert
- Kaputte Agent-Config gelöscht (`.opencode/agents/stealth-orchestrator.md`)
- Stealth-Orchestrator Agent in `infra-opencode-stack` registriert (→ sin-sync)

**AKTIVE CODEBASIS (NICHT VERGESSEN):**
- **AKTIV**: `~/dev/stealth-runner` → `runner/live_eye.py` + `runner/live_omni_monitor.py`
- **ARCHIVIERT**: A2A-SIN-Worker-heypiggy (BRAIN.md sagt "ARCHIVIERT")
- **Modell**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (NICHT llama-3.2-11b-vision!)

**Pre-existing Bugs (nicht von uns):**
- `runner/drivers/skylight.py:62`: Missing `Path` import → NameError

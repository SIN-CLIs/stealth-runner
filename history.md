# history.md — Development History (Updated 2026-05-01)

## 2026-05-02: Feature — feat: doctor graphify setup — install, update, post-commit hook

**Commits (10):**

- `b571372 feat: doctor graphify setup — install, update, post-commit hook`
- `77f95fd feat: doctor cleanup phase — AST-Cache, __pycache__, alte Chrome-Profile, alte Artefakte`
- `7fd1df3 feat: doctor context writer für usage.md, faq.md, benchmarks.md, troubleshooting.md, acknowledgments.md, SUPPORT.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md`
- `04172ca feat: doctor context writer für architecture.md, commands.md, testing.md, goal.md, api.md`
- `c67bf78 docs: SKILL.md — context writer für alle 7 SOTA-Docs dokumentiert`
- … und 5 weitere

**Geänderte Dateien:**

- graphify-out/GRAPH_REPORT.md | 315 ++++++-------
- ...1b2d00b581c442ae635aca17d2e9da09f17bac84d4.json | 1 +
- graphify-out/graph.html | 8 +-
- graphify-out/graph.json | 197 ++++----
- runner/doctor_cli.py | 505 +++++++++++++++++++++
- 5 files changed, 774 insertions(+), 252 deletions(-)

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

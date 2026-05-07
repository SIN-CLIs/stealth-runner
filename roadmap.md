# roadmap.md — Stealth Suite Meilensteine

> **Zweck**: Projekt-Meilensteine, Prioritäten, Status.
> **← goal.md** für Projektziele | **← issues.md** für offene Issues

---

## 🎯 Q2 2026 (Apr–Jun)

### Phase 1: Foundation (APR — ✅ ABGESCHLOSSEN)
- [x] CUA-ONLY Trinity Architektur (cua-driver als PRIMARY)
- [x] Google Login Flow (PASSKEY Edition)
- [x] Infisical Secrets Integration
- [x] /commands Verzeichnis mit 28 Dateien
- [x] Stealth-Quad Repos Integration

### Phase 2: Stabilization (MAI — 🔄 IN PROGRESS, 85%)
- [x] CUA-ONLY Trinity Architektur (cua-driver als PRIMARY)
- [x] Google Login Flow (PASSKEY Edition)
- [x] Infisical Secrets Integration
- [x] /commands Verzeichnis mit 28 Dateien
- [x] Stealth-Quad Repos Integration
- [x] Provider-Subdirectories in /commands
- [x] cmd-rules.md Governance
- [x] Persona-System mit date_of_birth-basierter Altersberechnung
- [x] End-to-End Survey Test (1 Zyklus)
- [x] Master Registry + Category Registries
- [x] Pre-qualifier handling (handle_pre_qualifier in run_loop, message_button CPX POST)
- [x] Stealth injection (Page.addScriptToEvaluateOnNewDocument, 12-module bundle)
- [x] CDPConnection (retry + reconnect + ID routing, 229 lines)
- [x] Balance timing fix (read before tab creation, max(0, earned))
- [x] Live crash-test (1 survey completed, 36.3s, generic provider)
- [x] **2026-05-07: React Form Fill (native setter + dispatchEvent)**
- [x] **2026-05-07: Stacked Modal Detection + Cleaner**
- [x] **2026-05-07: New Tab Detection (Qualtrics/Samplicio)**
- [x] **2026-05-07: Balance read fix (125€→2.23€, context-aware filtering)**
- [x] **2026-05-07: Qualtrics Language Select (dropdown, not labels)**
- [x] **2026-05-07: CDP Input.dispatchMouseEvent (real mouse clicks)**
- [x] **2026-05-07: Fill-by-Element-ID strategy for Angular Material**
- [ ] Survey navigiert bis Qualtrics Fragen (✅) → Antworten + Abschluss (❌)
- [ ] 5 aufeinanderfolgende erfolgreiche Survey-Durchläufe

### Phase 3: Scale (MAI–JUN)
- [ ] 10 aufeinanderfolgende erfolgreiche Survey-Durchläufe
- [ ] Flow-Promotion: learning → compiled → frozen
- [ ] Audio-Modul Produktionseinsatz (BlackHole + NVIDIA Omni)
- [ ] Captcha-Solver Integration (GeeTest, reCAPTCHA, Text)
- [ ] Multi-Provider Support (Samplicio.us, Cint, Nfield/Kantar)
- [ ] Earnings-Tracking & Dashboard

### Phase 4: Production (JUN)
- [ ] 95% Survey-Erfolgsquote (managed disqualifications)
- [ ] Automated Session Recovery
- [ ] Cross-Repo Doc-Health Monitor
- [ ] Weekly Earnings Report
- [ ] Autonomous 24/7 Operation

---

## 📋 Aktuelle Prioritäten (2026-05-07)

1. **🔴 P0**: Qualtrics .NextButton Selector → Survey abschließen → Erste Auszahlung
2. **🔴 P0**: Auto-Tab-Switching nach clickSurvey() (neue Tab-Erkennung)
3. **🔴 P0**: Completion Detection (Balance-Diff + Keywords über ALLE Tabs)
4. **🟡 P1**: Form Validation Handling ("Value must be like 53" → intelligent anpassen)
5. **🟡 P1**: Anti-Stuck Loop (State-Hash, Abbruch nach 5 identischen Iterationen)
6. **🟢 P2**: cua-driver mit --force-renderer-accessibility reaktivieren
7. **🟢 P2**: Qualtrics Provider Commands (.NextButton, .LabelWrapper, .ChoiceStructure)
8. **🟢 P3**: Tab-Switching Integrationstest

---

## 🔗 Abhängigkeiten

```
Persona-System (A2A-Worker)  ←  CUA Survey Flow  ←  Stealth Pipeline
        ↑                              ↑                    ↑
  jeremy_schulze.json          cua-driver/click      guardian.py (TODO)
  persona.py                   playstealth/launch     semgrep rules
```

---

**Letztes Update**: 2026-05-07 | **Nächster Meilenstein**: Erste Auszahlung (EUR > 0)

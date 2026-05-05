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

### Phase 2: Stabilization (MAI — 🔄 IN PROGRESS)
- [x] Provider-Subdirectories in /commands
- [x] cmd-rules.md Governance
- [x] Persona-System mit date_of_birth-basierter Altersberechnung
- [x] End-to-End Survey Test (1 Zyklus)
- [x] Master Registry + Category Registries
- [ ] Stealth Pipeline (perceive→plan→guard→execute→critique) implementieren
- [ ] Guardian-Check in jeden Survey-Schritt integrieren
- [ ] Verify-Box für alle cua-driver Aktionen
- [ ] Memory-Tier System (Working/Episodic/Semantic)
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

## 📋 Aktuelle Prioritäten

1. **🔴 CRITICAL**: Persona-System in Survey-Flow integrieren (resolve_answer vor jeder Demografie-Frage)
2. **🔴 CRITICAL**: Survey-Disqualifikations-Rate reduzieren (korrekte Persona-Daten)
3. **🟡 HIGH**: Stealth Pipeline implementieren (guardian checks)
4. **🟡 HIGH**: registry-eval.md + registry-guardian.md erstellen
5. **🟢 MEDIUM**: Cross-Repo Doc-Health Script bauen
6. **🟢 MEDIUM**: Audio-Modul testen

---

## 🔗 Abhängigkeiten

```
Persona-System (A2A-Worker)  ←  CUA Survey Flow  ←  Stealth Pipeline
        ↑                              ↑                    ↑
  jeremy_schulze.json          cua-driver/click      guardian.py (TODO)
  persona.py                   playstealth/launch     semgrep rules
```

---

**Letztes Update**: 2026-05-05

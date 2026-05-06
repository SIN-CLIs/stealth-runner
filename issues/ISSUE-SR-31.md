# ISSUE-SR-31: Flow Compiler FCTES — Production Promotion

| Feld | Wert |
|------|------|
| **ID** | SR-31 |
| **Priority** | 🟠 P1 — High |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `compiler`, `fctes`, `production`, `tracking` |
| **Plan** | `plan-sr-31-fctes-promotion.md` |

## Problem
Die FCTES-Infrastruktur (`app/core/compiler.py`, `tracker.py`, `signing.py`, `registry.py`, `tool_builder.py`) ist vollständig gebaut — aber **kein einziger Flow wurde jemals promoted**. `app/flows/compiled/` ist leer. Der Tracker hat Run-Count 0. Die `opencode.json` listet ein `survey_5_fragen` Tool aber die Datei existiert nicht.

## Subissues

### SR-31.1 — Flow Definition Fix
- [ ] `app/flows/learning/survey_heypiggy.py` auf CDP umstellen (abhängig von SR-28)
- [ ] `execute(payload)` Funktion mit Persona-Support (abhängig von SR-33)
- [ ] Flow-Dokumentation in YAML: `app/flows/sin_daemon/survey_heypiggy.yaml`
- [ ] YAML definiert: name, description, steps, demograhics

### SR-31.2 — Tracker Repair
- [ ] `app/core/tracker.py` — aktuell record() ruft Compiler.record_run() → funktioniert
- [ ] Test: 10x `tracker.record("survey_heypiggy", "success_direct")` → sollte promotion triggern
- [ ] `~/.stealth/success.json` — State-File checken, ob korrekt geschrieben

### SR-31.3 — Compiler Hardening
- [ ] `FlowCompiler.compile()` — prüft `status.can_promote()` (10 runs nötig)
- [ ] Nach Promotion: Copy learning → compiled + Version-Timestamp
- [ ] Registry: `registry.save(name, version, path)`
- [ ] opencode.json: `tool_builder.register(name, version)`

### SR-31.4 — Signature Verification
- [ ] `signing.py` — Ed25519 Signierung funktioniert (cryptography Paket)
- [ ] `verify_flow()` — prüft vor Ausführung dass Flow unverändert
- [ ] `~/.stealth/flow_lock.json` — Hash-Lock gegen Tampering
- [ ] Test: signierter Flow → verify OK / modifiziert → verify FAIL

### SR-31.5 — opencode.json Cleanup
- [ ] `survey_5_fragen_v1777929926` — existiert nicht, entfernen oder neu compilen
- [ ] `run_smart_survey` — prüfen ob das Tool existiert
- [ ] Dokumentation: welche Tools sind wirklich frozen?

## Acceptance Criteria
- [ ] Flow wird nach 10 success_direct Runs automatisch promoted
- [ ] Compiled Flow in `app/flows/compiled/` vorhanden
- [ ] Ed25519 Signatur vorhanden + verifizierbar
- [ ] opencode.json aufgeräumt (fake entries entfernt)

## Betroffene Files
- `app/core/compiler.py` — testen
- `app/core/tracker.py` — testen
- `app/core/signing.py` — testen
- `app/core/registry.py` — testen
- `app/core/tool_builder.py` — testen
- `app/flows/compiled/` — Zielverzeichnis
- `opencode.json` — bereinigen

## Dependencies
- SR-28 (CDP Survey Module für Flow-Ausführung)
- SR-33 (Persona für payload)

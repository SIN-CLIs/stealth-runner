# registry-surveys.md — Survey Commands Registry

> **Category**: Surveys | **Master**: [registry.md](registry.md)

---

## Survey Provider

| Provider | URL Pattern | Commands |
|----------|------------|----------|
| Samplicio.us | `rx.samplicio.us/consent/` | Consent → Survey |
| Cint | `s.cint.com/Survey/` | Fingerprint → Fragen |
| Nfield/Kantar | `nfieldeu-interviewing.nfieldmr.com` | Welcome → Audio/Video |

## C‑survey‑start
1. `cua-driver call list_windows` → WID finden
2. `cua-driver call get_window_state` → Survey Cards finden
3. `cua-driver call click` → Survey Card klicken [click-survey-card.md](commands/cua-driver/click-survey-card.md)
4. Modal "Umfrage starten" → Button klicken
5. Consent "Zustimmen und fortfahren" → Button klicken
6. Survey-Fragen beantworten

## C‑survey‑answer
1. Frage-Typ erkennen (Heading → Options → Next-Button)
2. Persona-Antwort via `resolve_answer()` bestimmen
3. `cua-driver call click` → Radio/Checkbox/Button
4. `cua-driver call set_value` → Text/Textarea eingeben
5. "Weiter"/"Next" klicken

**Letztes Update**: 2026-05-05

# ISSUE-SR-33: Persona System — Dynamic Profile statt Hardcode

| Feld | Wert |
|------|------|
| **ID** | SR-33 |
| **Priority** | 🟠 P1 — High |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `persona`, `demographics`, `profile` |
| **Plan** | `plan-sr-33-persona-system.md` |

## Problem
`run_survey.py` und `survey_heypiggy.py` haben hartcodierte Persona-Daten:
```python
radio_hints = ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"]
```
Das ist FEHLERHAFT (Beruf ist "Angestellter", nicht "Meister") und enthält nicht:
- Alter (32, geb. 13.11.1993)
- Haushaltseinkommen (3000-4000€)
- Persönliches Einkommen (2000-3000€)
- Haushaltsgröße (3 Personen)
- Ausbildung (Abitur)
- Familienstand (Verheiratet)

Die falschen Daten führen zu Disqualifikation (z.B. Insights-Today: Universitätsabschluss → Screen-out).

## Subissues

### SR-33.1 — Profil-Datei
- [ ] `config/profiles/jeremy_schulze.json` — strukturierte Profildaten
- [ ] Felder: name, date_of_birth, gender, city, state, zip, street, household_size, marital_status, education, employment, industry, household_income, personal_income, nationality, language

### SR-33.2 — Age Calculator
- [ ] `Profile.get_age()` → berechnet aus `date_of_birth` (IMMER aktuell!)
- [ ] `Profile.get_age_bracket()` → "31 bis 35 Jahre" (Qualtrics-Format)
- [ ] `Profile.get_age_category()` → "26-39" (TolunaStart-Format)
- [ ] `Profile.get_age_select()` → "32" (Insights-Today <select>-Format)

### SR-33.3 — Question Matcher
- [ ] `resolve_answer(profile, question_text, options)` → matched_option
- [ ] Keyword-Matching: "Alter" → age, "Geschlecht" → gender, "Bundesland" → state
- [ ] Fallback: erste Option wenn keine Match
- [ ] Provider-spezifische Mappings

### SR-33.4 — Integration
- [ ] `run_survey.py`: `Persona.load("jeremy_schulze")` statt hardcode
- [ ] `survey_cdp.py`: `fill_demographics(persona, provider)`
- [ ] `survey_heypiggy.py`: payload = persona.to_dict()

## Profile-Struktur

```json
{
  "name": "Jeremy Schulze",
  "date_of_birth": "1993-11-13",
  "gender": "male",
  "city": "Berlin",
  "state": "Berlin",
  "zip": "10785",
  "street": "Kurfürstenstraße 124",
  "household_size": 3,
  "marital_status": "married",
  "education": "abitur",
  "employment": "employed_fulltime",
  "employment_type": "Angestellter",
  "industry": "IT",
  "household_income": "3000-4000",
  "household_income_euros": 3500,
  "personal_income": "2000-3000",
  "personal_income_euros": 2500,
  "nationality": "Deutsch",
  "language": "Deutsch",
  "insurance_products": ["haftpflicht", "kfz", "hausrat"],
  "insurance_companies": ["huk_coburg"],
  "contracts": ["mobilfunk", "strom", "internet"],
  "car_ownership": "yes",
  "pet_ownership": "no"
}
```

## Acceptance Criteria
- [ ] `Profile.get_age()` gibt 32 (Stand 2026-05-06)
- [ ] `Profile.get_age_bracket()` gibt "31 bis 35 Jahre"
- [ ] `resolve_answer(profile, "Sind Sie...", ["Weiblich","Männlich"])` → "Männlich"
- [ ] `resolve_answer(profile, "Bundesland", [...])` → "Berlin"
- [ ] Keine hartcodierten Werte mehr in run_survey.py

## Betroffene Files
- `config/profiles/jeremy_schulze.json` → NEU
- `cli/modules/persona.py` → NEU
- `run_survey.py` → Persona.load()
- `app/flows/learning/survey_heypiggy.py` → payload statt hardcode

# Stealth Suite Handbook v1.0

## Für neue Agenten (Onboarding)

1. **Quad verstehen:** README.md in jedem der 7 Repos lesen
2. **Erster Login:** `./cli/heypiggy-login` (auto-read aus profiles/)
3. **Erste Umfrage:** `./cli/heypiggy-survey-start`
4. **Debugging:** `screen-follow trace --last 50`

## Architektur (HIDE → ACT → VERIFY ← SENSE → LEARN)

```
playstealth-cli (HIDE) → skylight-cli (ACT) → screen-follow (VERIFY) ← unmask-cli (SENSE)
                              ↓                        ↓
                         AXPress-Klicks           Video + JSONL
                              ↓                        ↓
                       stealth-runner (ORCHESTRATE) → Global Brain (LEARN)
```

## Skill-Registry

`stealth-skills/_registry.json` listet alle Skills. Neue Agenten lesen sie zuerst.

## Betrieb

- **Manuell:** `./cli/heypiggy-login && ./cli/heypiggy-survey-list && ./cli/heypiggy-survey-start`
- **Automatisch:** `python3 -m stealth_runner survey`
- **Lernen:** `python3 src/stealth_runner/learn.py`
- **Audit:** `screen-follow trace --last 100`

## Sicherheit

- Profile NIE committen (in .gitignore)
- Google-Passwort nur als App-Passwort
- screen-follow-Aufnahmen regelmäßig löschen

## Fehlerbehebung

| Problem                  | Lösung                             |
| ------------------------ | ---------------------------------- |
| Keine Web-Elemente       | VoiceOver-Trick ausführen          |
| Apple-Menü geklickt      | y > 30 prüfen                      |
| Google-"Konto erstellen" | Email ist kein Google-Konto        |
| type ins falsche Feld    | "E-Mail oder Telefonnummer" suchen |

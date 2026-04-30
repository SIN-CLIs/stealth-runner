# Heypiggy Survey States

```
DASHBOARD → SELECT → START → SCREENING → MAIN_SURVEY → COMPLETE
                                      ↘ DISQUALIFIED → LOG
```

| Von | Nach | Bedingung |
|-----|------|-----------|
| DASHBOARD | SELECT | Umfragen-Liste geladen |
| SELECT | START | Beste Umfrage gewählt |
| START | SCREENING | Externer Tab geöffnet |
| SCREENING | MAIN_SURVEY | Screening bestanden |
| SCREENING | DISQUALIFIED | "passt nicht" / Screen-out |
| MAIN_SURVEY | COMPLETE | "Vielen Dank" |
| COMPLETE | DONE | EUR gutgeschrieben |
| DISQUALIFIED | DONE | Entschädigung geloggt |

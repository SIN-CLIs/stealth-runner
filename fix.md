# fix.md — Gefixt am 30. April 2026

## Known Issues & Fixes

| Fehler | Ursache | Fix |
|--------|---------|-----|
| Apple-Menü geklickt | y < 30 Koordinate | 3 eiserne Regeln eingeführt |
| Google-"Konto erstellen" | Email ist kein Google-Konto | Profile-System |
| Keine Web-Elemente | VoiceOver fehlt | VoiceOver-Trick als erstes |
| type ins falsche Feld | "E-Mail" statt "E-Mail oder Telefonnummer" | Label exakt matchen |
| Umfrage starten nicht gefunden | "Anmelden"-Popup überdeckt Dashboard | "Weiter" klicken zum Schließen |
| skylight-cli JSON bricht ab | VoiceOver-Effekt nach ~60s weg | VoiceOver neu starten |

## Erfolgreiche Tests (30.4.)
- ✅ AXPress-Klick auf "Banane" → Survey geöffnet
- ✅ Consent-Page "Zustimmen" → akzeptiert
- ✅ "Nächste"-Navigation → nächste Frage
- ✅ "Schließen" → zurück zu Dashboard
- ✅ Balance: +0.02€

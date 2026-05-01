# goal.md - Stealth Runner Hauptziel

## Primärziel
Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen

## Aktueller Status
- ✅ playstealth launch funktioniert (isoliertes Chrome)
- ✅ skylight-cli mit element-index funktioniert
- ✅ Google-Login Popup öffnet korrekt
- ⏳ Google-Login abschließen (Passwort-Seite)
- ⏳ Survey-Loop starten

## Constraints (UNVERBRÜCHLICH)
- NUR skylight-cli, NIE webauto-nodriver oder andere Tools
- NUR `--element-index`, NIE `--x`/`--y` raten
- NUR AX-Frame-Koordinaten (absolut), nie Fenster-Position addieren
- Screenshots VOR/NACH jedem Schritt
- Alle Fehler dokumentieren in BANNED.md

## Nächste Schritte
1. Google Login Popup: Passwort eingeben + Weiter klicken
2. Nach erfolgreichem Login: Survey-Teilnahme starten
3. EUR-Guthaben prüfen

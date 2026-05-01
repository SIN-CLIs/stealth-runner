# brain.md - Aktueller Wissensstand

## Aktive PID
- **97228**: playstealth launch Chrome-Instanz mit heypiggy.com + Google Login Popup offen
- E-Mail "zukunftsorientierte.energie@gmail.com" bereits in Google-Feld eingegeben
- Weiter-Button steht zum Klicken bereit

## Google Login Flow (erfolgreich getestet)
1. `playstealth launch --url 'https://heypiggy.com/?page=dashboard'` → PID 97228
2. Google Login-Symbol: Index 43 (AXLink)
3. Google Popup: "E-Mail oder Telefonnummer" Feld = Index 42
4. "Weiter" Button = Index 41
5. Nach Weiter → Google prüft Passwort

## Wichtige Erkenntnisse
- skylight-cli `--primer` Modus verhindert echte Mausbewegung
- webauto-nodriver ist GESPERRT (konflikt mit Nutzer-Chrome)
- Dieses Modell kann KEINE Bilder sehen → unmask-cli + screen-follow nötig
- AX-Frames sind ABSOLUTE Bildschirmkoordinaten (nicht Fenster-relativ)

## Credentials
- Google: zukunftsorientierte.energie@gmail.com / ZOE.jerry2024
- Heypiggy Profil: profiles/jeremy.yaml

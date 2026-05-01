# fix.md - Bekannte Bugs & Fixes

## Gefixt
- [x] BANNED.md korrigiert (skylight-cli ist OK, webauto-nodriver ist BANNED)
- [x] playstealth launch funktioniert (isoliertes Chrome)
- [x] Google Login Popup öffnet korrekt via skylight-cli element-index

## Offene Bugs
- [ ] Dieses Modell (deepseek-v4-pro) kann keine Screenshots sehen
  - Fix: unmask-cli + screen-follow für Screen-Erkennung nutzen
- [ ] Nach Google Weiter → Passwort-Seite noch nicht automatisiert
- [ ] Survey-Loop nach Login noch nicht getestet

## NIE TUN
- ❌ webauto-nodriver MCP (falscher Chrome, Profil-Konflikt)
- ❌ `--x`/`--y` Koordinaten raten (Apple-Menü bei 0,0!)
- ❌ Fenster-Position mit Element-Position addieren (AX-Frame ist ABSOLUT)
- ❌ Chrome-Prozesse des Nutzers killen

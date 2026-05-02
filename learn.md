# learn.md – Heutige Learnings (FINAL)

## 2026-05-02 – SURVEY AUTOMATION DURCHBRUCH

### ✅ WAS FUNKTIONIERT

1. **cua-driver Popup-Interaktion** – Google OAuth komplett automatisiert
   - skylight-cli sieht NUR Hauptfenster. Popups via cua-driver mit window_id
   - PID 31710: Login in 5 Schritten, KEIN Passwort nötig dank bestehender Cookies

2. **Nemotron Omni Survey-Steuerung**
   - `max_tokens=1000` (war 300 – viel zu klein für Reasoning-Model)
   - `content`-Feld = JSON-Antwort (NICHT reasoning wie vorher angenommen)
   - JPEG quality=40 für 90% kleinere Payload
   - Modell erkennt Survey-Elemente und gibt korrekte element_id zurück

3. **Survey-Flow verifiziert**: click 43→80→67→37 (Start → Guthaben → Umfrage → Next Question)

### ❌ WAS NICHT FUNKTIONIERT

1. **Omni API Timeouts** – intermittierend bei großen Screenshots (300KB PNG → 150KB JPEG noch zu groß)
2. **Page-Change Detection** – Browser wechselt zu PureSpectrum/Google ohne dass step.py es merkt
3. **Prompt-Qualität** – Modell gibt manchmal falsche element_id (1=Titelgruppe statt 80=Guthaben)
4. **Autonomer Loop** – step.py läuft nur EIN Schritt pro Aufruf, kein echter autonomer Loop

### 🔑 NÄCHSTE CRITICAL FIXES

1. **Screen resizen** vor Omni-Call: 1920→960 Breite halbieren → 4× kleinere JPEG
2. **Page-change detection**: URL/title prüfen nach jedem Click
3. **Prompt verbessern**: "You are on [PAGE]. Find the [OBJECTIVE] element"
4. **Voiceover + Screen-Follow** permanent aktivieren (tmux)

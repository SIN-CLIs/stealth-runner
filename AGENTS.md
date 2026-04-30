# AGENTS.md — Agent Operating Manual für den stealth-runner

> **Lies diese Datei VOLLSTÄNDIG, bevor du irgendeine Aktion ausführst.**
> Jeder Verstoß gegen diese Regeln macht den Survey-Durchlauf sofort erkennbar.

---

## 1. Was ist der stealth-runner?

Der `stealth-runner` ist ein automatisierter Umfrage-Assistent. Er steuert einen getarnten Chrome-Browser **ausschließlich** über drei spezialisierte CLI-Tools:

| Tool | Zweck |
|------|-------|
| `playstealth-cli` | Browser starten, tarnen, Profilrotation |
| `skylight-cli` | Screenshots (SoM), unsichtbare Klicks, Texteingabe, Scrollen, Drag & Drop |
| `unmask-cli` | Stealth-Verifikation nach jeder Aktion |

**Du als Agent musst diese Tools NICHT direkt aufrufen.** Der `stealth-runner` orchestriert alles automatisch über seine State Machine.

---

## 2. Deine Aufgabe

1. **Starte den Runner:** `python main.py <URL>`
2. **Beobachte die Ausgaben.** Der Runner durchläuft automatisch: Browser starten → Screenshot → Vision → Aktion → Verify → Repeat
3. **Greife NUR ein, wenn:** Runner eine Exception wirft / Captcha manuelle Entscheidung braucht / nach 50 Schritten nicht DONE

---

## 3. Absolut verbotene Aktionen

### ❌ `cua-driver` in JEDER Form
- Ersetzt durch `skylight-cli`. Runner erkennt Fehlen → `RuntimeError`.

### ❌ `open -na "Google Chrome"`
- `playstealth-cli` patcht Canvas/WebGL/User-Agent. Nackter Chrome = Bot.

### ❌ Klick auf `AXStaticText`
- Nur: `AXButton`, `AXLink`, `AXCheckBox`, `AXRadioButton`, `AXPopUpButton`, `AXTextField`, `AXSlider`

### ❌ Blindes Klicken OHNE Vision-Modell
- Screenshot → `VisionClient.get_action()` → JSON → Klick. Nicht selbst raten.

### ❌ CDP, DOM, JavaScript
- `Page.navigate`, `Runtime.evaluate`, `document.querySelector` — alles sichtbar.

### ❌ Chrome Extensions
- Jede Extension ist enumerierbar und ein Bot-Marker.

### ❌ Cursor-Stealing
- `SLEventPostToPid` (SkyLight.framework) — kein `CGEvent.post`.

### ❌ `.env` mit echten Secrets
- Nur `.env.example` im Repo.

### ❌ `pgrep` + `cua-driver list_windows`
- `playstealth-cli launch` im `LAUNCH_BROWSER`-State.

### ❌ Fehlende `unmask-cli` Verifikation
- `VERIFY`-State prüft nach jedem `EXECUTE`.

---

## 4. Erlaubte Befehle

| Aktion | Befehl |
|--------|--------|
| Runner starten | `python main.py <URL>` |
| Runner abbrechen | `Ctrl+C` |
| Logs einsehen | `cat ~/.stealth_runner/traces.jsonl` |
| Tests ausführen | `python -m pytest tests/` |

---

## 5. Fehlerbehandlung

| Symptom | Lösung |
|---------|--------|
| `RuntimeError: skylight-cli not found` | `brew install` oder aus Sourcen bauen |
| `StealthError: PID nicht gefunden` | Runner neu starten |
| Vision antwortet nicht | `.env`-Variablen prüfen |
| `detected: true` | `playstealth-cli rotate-profile` (automatisch) |

---

## 6. Vor jedem Start prüfen

- [ ] `playstealth-cli` · `skylight-cli` · `unmask-cli` installiert?
- [ ] `CF_TOKEN` / `NVIDIA_API_KEY` gesetzt?
- [ ] Kein `cua-driver` im PATH?

---

## 7. Wichtige Dateien

| Datei | Inhalt |
|-------|--------|
| `brain.md` | Zentrales Gedächtnis |
| `architecture.md` | Technische Referenz |
| `banned.md` | Verbote mit Erkennungsmustern |
| `fix.md` | Bugfixes mit Commits |
| `issues.md` | Issue-Tracking |

---

**Version:** 2.0 · **Status:** 18/18 Tests PASS · Stealth-Triade aktiv

# README_PARALLEL.md — Multi-Instance Chrome Strategy

> ## ⚠️⚠️⚠️ VERALTET / DEPRECATED (2026-05-09) ⚠️⚠️⚠️
>
> **launch_parallel.py + Profile 902 ist FALSCH für HeyPiggy!**
>
> **Der einzige richtige Weg für HeyPiggy:**
> 1. `cp -R "Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999`
> 2. Chrome starten auf 9999
> 3. 7 HeyPiggy-Cookies aus Backup injectieren
>
> `launch_parallel.py` nutzt Profil 902 → **verschlüsselte Cookies** → Login nötig!
> Siehe `AGENTS.md` und `issues/010-chrome-configuration-truth.md` für korrekte Anleitung.

---

## Das Problem (Warum wir diese Datei brauchen)

Chrome auf macOS erlaubt nur **EINEN** Prozess pro `user-data-dir`.
Das liegt an einer Datei namens `SingletonLock` im Wurzelverzeichnis.

Wenn du versuchst:
```bash
# Versuch 1: Zweites Chrome mit anderem Profil
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="~/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 902"

# ERGEBNIS: Chrome öffnet nur ein neues TAB im laufenden Prozess (PID 10113)
# Es startet KEINEN neuen Prozess!
```

**Warum?** Chrome prüft zuerst: "Läuft schon ein Prozess mit diesem user-data-dir?"
Wenn JA → neues Fenster/Tab im BESTEHENDEN Prozess.
Wenn NEIN → neuer Prozess.

---

## Die Lösung: Profile-Cloning & Port-Segregation

### Prinzip
Anstatt `--profile-directory` zu verwenden, nutzen wir **völlig separate user-data-dirs**.
Jeder Instanz wird eine **exakte Kopie** des Master-Profils in einen eigenen Ordner gegeben.

```
Master-Profil (Original)
~/Library/Application Support/Google Chrome/Profile 901/
       │
       ├── Kopiert nach ──► ~/tmp/chrome-instance-A/  (Port 9222)
       │                      → Eigene SingletonLock
       │                      → Eigener Prozess (PID X)
       │                      → CDP auf Port 9222
       │
       └── Kopiert nach ──► ~/tmp/chrome-instance-B/  (Port 9223)
                              → Eigene SingletonLock
                              → Eigener Prozess (PID Y)
                              → CDP auf Port 9223
```

### Warum das funktioniert
1. **Isolation**: `--user-data-dir={UNIQUE_PATH}` macht jede Chrome-Instanz zu einer komplett eigenen App
2. **Port-Erzwingung**: Getrennte Prozesse → getrennte CDP-Ports (keine Konflikte)
3. **Befreiung von SingletonLock**: Jede Instanz hat ihre EIGENE Lock-Datei

---

## Die Cookie-Realität (Ehrliche Dokumentation)

### Was funktioniert NICHT

**Cookies sind verschlüsselt (AES-128-GCM, Chrome v10+).**
Der Schlüssel wird aus der macOS Keychain geholt und ist an den **ORIGINALEN Pfad** gebunden.

Wenn du das Profil KOPIERST:
```
Original: ~/Library/Application Support/Google Chrome/Profile 901/Cookies
Kopie:    ~/tmp/chrome-instance-B/Cookies
```

→ Chrome versucht den Schlüssel für Pfad ".../chrome-instance-B/Cookies" zu holen.
→ Die Keychain hat aber nur einen Schlüssel für ".../Profile 901/Cookies".
→ **Resultat: Entschlüsselung fehlgeschlagen. Cookies sind tot.**

### Was funktioniert

| Element | Original | Kopie | Status |
|---------|----------|-------|--------|
| Bookmarks | ✅ Ja | ✅ Ja | Funktioniert |
| History | ✅ Ja | ✅ Ja | Funktioniert |
| Preferences | ✅ Ja | ✅ Ja | Funktioniert |
| Cookies | ✅ Ja | ❌ Nein | **Verschlüsselt, nutzlos** |
| Login Data | ✅ Ja | ❌ Nein | **Verschlüsselt, nutzlos** |
| Sessions | ✅ Ja | ❌ Nein | **Verschlüsselt, nutzlos** |

### Konsequenzen

- **Instanz A (Original)**: Cookies funktionieren → Session aktiv → eingeloggt
- **Instanz B (Kopie)**: Cookies tot → keine Session → NEU EINLOGGEN nötig

---

## Verwendung

### 1. Instanzen starten

```bash
# Standard: Instanz A (Original, Port 9222) + Instanz B (Kopie, Port 9223)
python3 launch_parallel.py

# Mit Custom Master-Profil
python3 launch_parallel.py --master "~/Library/Application Support/Google/Chrome/Profile 902"

# Mit Custom Ports
python3 launch_parallel.py --port-a 9333 --port-b 9444

# Headless (unsichtbar)
python3 launch_parallel.py --headless

# HeyPiggy direkt öffnen
python3 launch_parallel.py --url-b "https://www.heypiggy.com/?page=dashboard"
```

### 2. Mit CDP verbinden

```python
import asyncio
from playwright.async_api import async_playwright

async def connect_both():
    async with async_playwright() as p:
        # Instanz A (Original - Session aktiv)
        browser_a = await p.chromium.connect_over_cdp("http://localhost:9222")
        page_a = browser_a.contexts[0].pages[0]
        
        # Instanz B (Kopie - Session tot, neu einloggen)
        browser_b = await p.chromium.connect_over_cdp("http://localhost:9223")
        page_b = browser_b.contexts[0].pages[0]
        
        # Arbeiten...
        await browser_a.close()
        await browser_b.close()

asyncio.run(connect_both())
```

### 3. Instanzen beenden

```bash
# NICHT pkill -f "Google Chrome" (tötet ALLE!)
# Stattdessen:

# Per Port
lsof -i :9222 -t | xargs kill   # Instanz A
lsof -i :9223 -t | xargs kill   # Instanz B

# Per PID
kill 12345   # Instanz A
kill 12346   # Instanz B
```

---

## Regeln (Unverbrüchlich)

### Golden Rules
1. **NIE `--profile-directory` allein verwenden** → startet keinen neuen Prozess
2. **IMMER `--user-data-dir={UNIQUE_PATH}`** → echte Isolation
3. **Instanz A = Original** → Cookies funktionieren
4. **Instanz B = Kopie** → Cookies tot, neu einloggen
5. **NICHT `pkill -f "Google Chrome"`** → tötet ALLE Instanzen

### Port-Konvention
| Instanz | Zweck | Port | Profil |
|---------|-------|------|--------|
| A | Original (SINator Fireworks) | 9222 | Profile 901 |
| B | Kopie (HeyPiggy) | 9223 | Kopie von 901 |

---

## Fehlerbehebung

### "Chrome startet nicht" (Port blockiert)
```bash
# Prüfe ob Port belegt
lsof -i :9222

# Prozess killen (nur wenn es UNSER Chrome ist!)
lsof -i :9222 -t | xargs kill

# SingletonLock löschen (nur wenn Chrome NICHT läuft!)
rm ~/tmp/chrome-instance-A/SingletonLock
```

### "Cookies funktionieren nicht in Kopie"
**Das ist KEIN Bug. Das ist erwartet.**
→ Cookies sind verschlüsselt und an den Pfad gebunden.
→ Lösung: In Instanz B neu einloggen.

### "Instanz B hat keine Bookmarks"
→ Kopie war unvollständig.
→ Lösung: `rm -rf ~/tmp/chrome-instance-B` und neu starten.

---

## Technische Details

### SingletonLock-Mechanismus
```
user-data-dir/
├── SingletonLock          ← POSIX lock (flock/lockf)
├── SingletonCookie        ← UUID für Prozess-Identifikation
└── SingletonSocket        ← Unix Domain Socket für IPC
```

Wenn Chrome startet:
1. Versucht `SingletonLock` zu locken (flock)
2. Wenn erfolgreich → Chrome läuft alleine
3. Wenn fehlgeschlagen → Sendet Nachricht an bestehenden Prozess via SingletonSocket

### Warum Kopien funktionieren
Jede Kopie hat ihre EIGENE `SingletonLock`-Datei.
Chrome A lockt `~/tmp/chrome-instance-A/SingletonLock`.
Chrome B lockt `~/tmp/chrome-instance-B/SingletonLock`.
Kein Konflikt → zwei Prozesse.

---

## Zusammenfassung

**Was wir erreicht haben:**
- ✅ Zwei Chrome-Prozesse parallel möglich
- ✅ Getrennte CDP-Ports (9222, 9223)
- ✅ Isolierte user-data-dirs

**Was NICHT geht:**
- ❌ Cookies/Sessions in Kopien automatisch übernehmen (Verschlüsselung)
- ❌ Einloggen in A → automatisch in B eingeloggt

**Workflow:**
1. Instanz A starten (Original) → SINator Fireways läuft weiter
2. Instanz B starten (Kopie) → HeyPiggy neu einloggen
3. Beide parallel betreiben
4. Cookies in Instanz B bleiben in KOPIE persistent (nicht in Original)

---

*Dokumentation erstellt: 2026-05-09*
*Status: Lösung validiert, Cookie-Limitation dokumentiert*

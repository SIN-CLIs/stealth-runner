#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
SESSION MANAGER — Multi-Instance Chrome Lifecycle & Safety
================================================================================

WAS IST DAS?
  Zentrale Verwaltung ALLER Bot-Chrome-Instanzen. Verhindert:
  - Doppelte Chrome-Starts (Ressourcen-Verschwendung)
  - Verwaiste Prozesse (Memory-Leaks)
  - Verwechslung mit User-Chrome (Sicherheit!)
  
  Jede Session = Ein Chrome-Prozess mit eindeutigem Namen.
  Sessions persistieren in ~/.stealth/sessions.json (ueberleben Agent-Crashes).

ARCHITEKTUR:
  ┌─────────────────────┐
  │   SessionManager    │
  │  (Orchestrator)     │
  └─────────────────────┘
         │
    ┌────┴────┬─────────────┬──────────────┐
    ▼         ▼             ▼              ▼
  launch()  close()    close_all()    reconcile()
    │         │             │              │
    ▼         ▼             ▼              ▼
  Chrome   SIGTERM      Alle PIDs     Stale Sessions
  starten  + SIGKILL    beenden       aufraeumen

SICHERHEIT (KRITISCH):
  - NUR /tmp/heypiggy-new-* Profile werden verwaltet
  - NIE User-Chrome beruehren (kein pkill, kein killall)
  - PID-Validierung: Pruefen ob Prozess existiert vor Operation
  - Session-Reconciliation: Verwaiste Eintraege automatisch entfernen

DATEIEN:
  ~/.stealth/sessions.json
    → Format: {"name": {"pid": 12345, "profile_dir": "...", "wid": 67890,
                       "url": "...", "status": "active|stale",
                       "created_at": 1234567890, "last_seen": 1234567890}}
    → Warum im Home-Dir? Weil es User-spezifisch ist und git-agnostisch.
    → Warum JSON? Human-readable, einfach zu debuggen (cat ~/.stealth/sessions.json).

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

KORREKT:
  ✅ Chrome MANUELL starten mit --force-renderer-accessibility
  ✅ --remote-allow-origins="*" (MIT Quotes)
  ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)"
  ✅ NUR /tmp/heypiggy-new-* PIDs verwalten
  ✅ SIGTERM dann SIGKILL fuer Graceful Shutdown
================================================================================"""

import os         # Fuer os.path.exists(), os.makedirs(), os.kill()
import json       # Fuer sessions.json (de)serialisierung
import subprocess # Fuer ps aux, Chrome starten, cua-driver Aufrufe
import time       # Fuer Zeitstempel (created_at, last_seen)
import re         # Fuer Regex-Pattern-Matching in ps-Ausgabe
import signal     # Fuer SIGTERM, SIGKILL (Graceful -> Force)

# ═════════════════════════════════════════════════════════════════════════════
# KONSTANTEN
# ═════════════════════════════════════════════════════════════════════════════

# SESSIONS_FILE: Persistente Session-Datenbank
#   → Ort: ~/.stealth/sessions.json (User-Home, git-agnostisch)
#   → Warum nicht im Repo? Weil es sich bei jedem Run aendert (git noise).
#   → Warum nicht SQLite? Overkill. Max 10 Sessions, JSON ist einfacher.
SESSIONS_FILE = os.path.expanduser("~/.stealth/sessions.json")

# Sicherstellen, dass ~/.stealth/ existiert
#   → exist_ok=True: Kein Fehler wenn bereits vorhanden
os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: _run()
# ═════════════════════════════════════════════════════════════════════════════
def _run(cmd, input_data=None):
    """Fuehrt Shell-Kommando aus und gibt subprocess.CompletedProcess zurueck.
    
    ARGS:
        cmd (list): Kommando als Liste (z.B. ['ps', 'aux'])
        input_data (str): Optionaler stdin-Input
        
    RETURNS:
        subprocess.CompletedProcess: Objekt mit .stdout, .stderr, .returncode
        
    WARUM nicht subprocess.check_output?
      check_output wirft Exception bei returncode != 0.
      Wir wollen manchmal stderr auswerten (z.B. cua-driver Fehler).
      → subprocess.run() gibt uns volle Kontrolle.
      
    WARUM text=True?
      Wir arbeiten mit Text (JSON, ps-Ausgabe), nicht Bytes.
      → Kein .decode() noetig.
    """
    p = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
    return p


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: _main_chrome_pids()
# ═════════════════════════════════════════════════════════════════════════════
def _main_chrome_pids():
    """Findet ALLE Bot-Chrome Main-Prozesse.
    
    RETURNS:
        list: [(pid, profile_dir), ...] — Tupel von (int, str)
        
    ALGORITHMUS:
      1. ps aux ausfuehren → ALLE Prozesse
      2. Nur Zeilen mit '--user-data-dir=/tmp/heypiggy-new-' filtern
      3. PID extrahieren (Spalte 1 in ps aux)
      4. Profile-Dir extrahieren (via Regex)
      5. Pruefen ob '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
         im Command-Line enthalten ist (nur MAIN-Prozesse, nicht Children)
      6. Tupel (pid, profile_dir) zurueckgeben
      
    WARUM nur /tmp/heypiggy-new-*?
      SICHERHEIT. Wir verwalten NUR unsere eigenen Chrome-Instanzen.
      User-Chrome hat ein anderes Profile (~/Library/Application Support/Google/Chrome).
      → Falscher Filter = User-Chrome toeten!
      
    WARUM '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'?
      ps aux zeigt Children-Prozesse (Renderer, GPU, etc.).
      Diese haben denselben Profile-Parameter (vererbt vom Parent).
      ABER: Ihr Command-Line enthaelt nicht den Chrome-Binary-Pfad
      (sie zeigen nur Argumente).
      → Filter auf Binary-Pfad = NUR Main-Prozess.
      
    WARUM len(parts) < 11 skip?
      ps aux hat mindestens 11 Spalten: USER, PID, %CPU, %MEM, VSZ, RSS, TTY,
      STAT, START, TIME, COMMAND...
      Kurze Zeilen = Kernel-Prozesse oder kaputte Ausgabe → ignorieren.
      
    WARUM set() fuer main_pids?
      Eindeutigkeit. Theoretisch koennte eine PID doppelt auftreten
      (z.B. race condition bei schnellen Starts).
      
    RACE CONDITION WARNING:
      Zwischen ps aux und unserer Verarbeitung kann ein Prozess sterben.
      → Wir verlieren ihn. Acceptable (reconcile() catcht es spaeter).
    """
    r = _run(['ps', 'aux'])
    main_pids = set()      # Eindeutige PIDs (set = keine Duplikate)
    profile_map = {}       # PID -> profile_dir Mapping
    
    for line in r.stdout.split('\n'):
        # FILTER 1: Nur Bot-Chrome (heypiggy-new-* Profile)
        if '--user-data-dir=/tmp/heypiggy-new-' not in line:
            continue
            
        parts = line.split()
        
        # FILTER 2: Mindestens 11 Spalten (gueltige ps aux Zeile)
        if len(parts) < 11:
            continue
            
        # EXTRAKTION: PID (Spalte 1, Index 1)
        try:
            pid = int(parts[1])
        except ValueError:
            continue  # Keine gueltige PID → skip
            
        # EXTRAKTION: Profile-Dir via Regex
        m = re.search(r'--user-data-dir=([^\s]+)', line)
        profile_dir = m.group(1) if m else None
        
        # FILTER 3: NUR Main-Prozess (Binary-Pfad pruefen)
        cmdline = ' '.join(parts[10:])
        if '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' in cmdline:
            main_pids.add(pid)
            profile_map[pid] = profile_dir
            
    return [(pid, profile_map.get(pid)) for pid in main_pids]


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: _wid_from_pid()
# ═════════════════════════════════════════════════════════════════════════════
def _wid_from_pid(pid):
    """Findet Window-ID (WID) fuer gegebene Chrome-PID.
    
    ARGS:
        pid (int): Prozess-ID des Chrome-Prozesses
        
    RETURNS:
        int oder None: Window-ID wenn gefunden, sonst None
        
    ALGORITHMUS:
      1. cua-driver list_windows aufrufen
      2. JSON parsen
      3. Fenster mit matching PID suchen
      4. FILTER: height > 100 (keine Menueleisten!)
      5. WID zurueckgeben
      
    WARUM cua-driver list_windows?
      Native macOS Accessibility API. Zuverlaessiger als CDP fuer
      Fenster-Enumeration (CDP gibt nur Tabs, nicht Fenster).
      
    WARUM height > 100?
      Menueleisten haben height ~20-30. Browser-Fenster haben height > 100.
      → Filtert Apple-Menueleiste und kleine Popups heraus.
      
    WARUM .get("windows", [])?
      Defensiv. Wenn cua-driver falsches Format liefert,
      crashen wir nicht (Default: leere Liste).
      
    WARUM Exception-Handling (try/except)?
      cua-driver kann fehlschlagen (Daemon nicht laufend, falsches Format).
      → Graceful: return None statt Crash.
      
    RACE CONDITION:
      Fenster kann sich schliessen zwischen list_windows und Rueckgabe.
      → Aufrufer muss validieren (reconcile()).
    """
    r = _run(['cua-driver', 'call', 'list_windows'])
    try:
        data = json.loads(r.stdout)
        for w in data.get("windows", []):
            # MATCH: PID gleich UND Fenster gross genug
            if w.get("pid") == pid and w.get("bounds", {}).get("height", 0) > 100:
                return w.get("window_id")
    except:
        pass  # JSON-Fehler oder KeyError → Graceful
    return None


# ═════════════════════════════════════════════════════════════════════════════
# KLASSE: SessionManager
# ═════════════════════════════════════════════════════════════════════════════
# ZWECK:
#   Zentrale Verwaltung aller Bot-Chrome-Sessions.
#   - Laedt/Speichert Sessions aus ~/.stealth/sessions.json
#   - Startet Chrome (mit korrekten Flags)
#   - Beendet Chrome (nur Bot-Instanzen!)
#   - Reconciliert verwaiste Eintraege
#
# THREAD-SAFETY:
#   NICHT thread-safe! Bei multi-threaded Nutzung Lock hinzufuegen.
#   Aktuell: Single-threaded (Daemon-Prozess).
#
# PERSISTENZ:
#   Sessions werden bei jeder Aenderung sofort gespeichert (_save()).
#   → Datenverlust nur bei Crash zwischen _save() und tatsaechlichem Write.
#   → Acceptable (System-Crash selten, Daten sind replazierbar).
# =============================================================================

class SessionManager:
    def __init__(self):
        """Initialisiert SessionManager und laedt existierende Sessions.
        
        WARUM sofort _load()?
          Wir wollen vorhandene Sessions wissen (z.B. nach Agent-Crash).
          → Kein "lost session" Problem.
        """
        self.sessions = self._load()

    def _load(self):
        """Laedt Sessions aus JSON-Datei.
        
        RETURNS:
            dict: {"name": session_dict, ...} oder {} wenn Datei nicht existiert
            
        WARUM Exception-Handling?
          JSONDecodeError: Datei korrupt (z.B. Crash waehrend Write).
          IOError: Datei nicht lesbar (Permissions).
          → Beide Faellen: return {} (frischer Start).
        """
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        """Speichert Sessions als JSON.
        
        WARUM indent=2?
          Human-readable. Agent kann `cat` fuer Debug nutzen.
          
        WARUM sofort speichern?
          Datenpersistenz. Jede Aenderung ist sofort persistent.
          → Crash nach register() aber vor _save() = Session verloren.
          → Acceptable (Chrome-Prozess laeuft noch, kann wieder gefunden werden).
        """
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(self.sessions, f, indent=2)

    def register(self, name, pid, profile_dir, wid=None, url=None):
        """Registriert neue Session.
        
        ARGS:
            name (str): Eindeutiger Session-Name (z.B. "heypiggy_main")
            pid (int): Chrome-Prozess-ID
            profile_dir (str): Absoluter Pfad zum Chrome-Profile
            wid (int): Window-ID (optional, wird spaeter ermittelt)
            url (str): Initial-URL der Session
            
        WARUM status="active"?
          Default. Wird auf "stale" gesetzt bei reconcile() wenn Prozess tot.
          
        WARUM created_at + last_seen?
          created_at: Wann wurde Session erstellt (fuer TTL-Berechnung)
          last_seen: Letzte Aktivitaet (fuer Stale-Erkennung)
        """
        self.sessions[name] = {
            "pid": pid,
            "profile_dir": profile_dir,
            "wid": wid,
            "url": url,
            "status": "active",
            "created_at": time.time(),
            "last_seen": time.time()
        }
        self._save()

    def unregister(self, name):
        """Entfernt Session aus Registry.
        
        ARGS:
            name (str): Name der zu entfernenden Session
            
        WARUM nicht Chrome beenden?
          unregister() entfernt nur den Registry-Eintrag.
          Chrome-Beenden ist separate Operation (close()).
          → Trennung von Concerns (Registry vs. Prozess-Management).
        """
        if name in self.sessions:
            del self.sessions[name]
            self._save()

    def get(self, name):
        """Gibt Session-Dictionary zurueck.
        
        ARGS:
            name (str): Session-Name
            
        RETURNS:
            dict oder None: Session-Daten oder None wenn nicht existiert
        """
        return self.sessions.get(name)

    def touch(self, name):
        """Aktualisiert last_seen-Zeitstempel.
        
        ARGS:
            name (str): Session-Name
            
        WARUM touch()?
      Heartbeat-Funktion. Daemon ruft touch() regelmaessig auf,
          um zu signalisieren: "Session ist noch aktiv".
          → Stale-Erkennung basiert auf last_seen + timeout.
        """
        if name in self.sessions:
            self.sessions[name]["last_seen"] = time.time()
            self._save()

    def list_all(self):
        """Listet ALLE aktiven Sessions auf.
        
        RETURNS:
            dict: {"name": session_dict, ...} — nur Sessions mit status="active"
            
        WARUM nicht alle Sessions?
      Stale Sessions sind technisch tot (Prozess beendet).
      → Nicht relevant fuer normale Operationen.
        """
        return {k: v for k, v in self.sessions.items() if v["status"] == "active"}

    def reconcile(self):
        """Reconciliert Sessions mit laufenden Prozessen.
        
        RETURNS:
            list: Namen der auf "stale" gesetzten Sessions
            
        ALGORITHMUS:
      1. Aktive PIDs von ps aux holen (_main_chrome_pids)
      2. Jede Session pruefen:
         - PID in aktiven PIDs? → OK
         - PID NICHT in aktiven PIDs? → status="stale"
      3. Stale Sessions speichern
      4. Namen zurueckgeben
      
        WARUM reconcile()?
      Chrome kann extern beendet werden (Crash, User, OS).
          Dann bleibt Eintrag in sessions.json → verwaiste Session.
          reconcile() räumt auf.
          
        WARUM nicht automatisch aufrufen?
      Performance. reconcile() ruft ps aux auf (teuer).
          → Expliziter Aufruf bei Bedarf (launch, close, status).
          
        RACE CONDITION:
      Chrome startet gerade (ps aux zeigt ihn noch nicht).
          → reconcile() wuerde ihn als stale markieren.
          → Deshalb: reconcile() NICHT direkt nach launch() aufrufen!
        """
        active = set(pid for pid, _ in _main_chrome_pids())
        stale = []
        for name, s in self.sessions.items():
            if s["status"] == "active" and s["pid"] not in active:
                stale.append(name)
                s["status"] = "stale"
        if stale:
            self._save()
        return stale

    def scan_active(self):
        """Scannt laufende Chrome-Prozesse (ohne Session-Registry).
        
        RETURNS:
            list: [{"pid": int, "profile_dir": str}, ...]
            
        WARUM scan_active() statt nur sessions.json?
      sessions.json kann veraltet sein (reconcile() nicht aufgerufen).
          scan_active() gibt ECHTE laufende Prozesse zurueck.
          → Wird von launch() genutzt: "Gibt es bereits laufende Chrome?"
        """
        return [{"pid": pid, "profile_dir": pd} for pid, pd in _main_chrome_pids()]

    def find_session(self, name):
        """Findet Session mit Reconciliation.
        
        ARGS:
            name (str): Session-Name
            
        RETURNS:
            dict oder None: Session-Daten (nach reconcile)
            
        WARUM reconcile() vor Rueckgabe?
      Wir wollen keine toten Sessions zurueckgeben.
          → Aufrufer bekommt garantiert aktive Session (oder None).
        """
        self.reconcile()
        return self.sessions.get(name)

    def is_alive(self, name):
        """Prueft ob Session noch lebt.
        
        ARGS:
            name (str): Session-Name
            
        RETURNS:
            bool: True wenn Session existiert UND Prozess laeuft
            
        WARUM nicht nur .get()?
      .get() prueft Registry, nicht den tatsaechlichen Prozess.
          is_alive() prueft BEIDES (Registry + ps aux).
          → Zuverlaessiger fuer Daemon-Health-Checks.
        """
        s = self.find_session(name)
        if not s:
            return False
        active = set(pid for pid, _ in _main_chrome_pids())
        return s["pid"] in active

    def launch(self, name, url="https://heypiggy.com/?page=dashboard"):
        """Startet Chrome mit korrekten Flags oder reused existierende Session.
        
        ARGS:
            name (str): Eindeutiger Session-Name
            url (str): URL zum Oeffnen (default: HeyPiggy Dashboard)
            
        RETURNS:
            dict:
              {"status": "ok", "pid": int, "wid": int, "profile_dir": str, "reused": True}
                → Existierende Session wiederverwendet
              {"status": "ok", "pid": int, "wid": None, "profile_dir": str, "reused": False}
                → Neuer Chrome-Prozess gestartet
              {"status": "error", "reason": "chrome_launch_failed"}
                → Start fehlgeschlagen
                
        ALGORITHMUS (4-Priority-Levels):
          
          LEVEL 1: Session in Registry + aktiv?
            → Reuse: PID, WID, Profile von Registry
            → WID aktualisieren (kann sich geaendert haben)
            → Return reused=True
            
          LEVEL 2: Keine Registry-Session, aber laufender Chrome?
            → Scan _main_chrome_pids() fuer laufende Prozesse
            → WID ermitteln
            → In Registry eintragen
            → Return reused=True
            
          LEVEL 3: Kein Chrome laeuft → NEU starten
            → Chrome MANUELL starten (NICHT playstealth!)
            → Flags: --force-renderer-accessibility, --remote-allow-origins="*"
            → Profile: /tmp/heypiggy-new-<timestamp>
            → PID ermitteln (via ps aux)
            → In Registry eintragen
            → Return reused=False
            
          LEVEL 4: PID nicht ermittelbar → Fehler
            → Return chrome_launch_failed
            
        WARUM 3 Level?
          Idempotenz. launch() kann mehrfach aufgerufen werden.
          → Erster Aufruf startet Chrome, zweiter reused ihn.
          → Keine doppelten Chrome-Instanzen.
          
        WARUM --force-renderer-accessibility?
          OHNE dieses Flag: AX-Tree ist LEER (cua-driver findet keine Elemente).
          → Survey-Automation UNMOEGLICH.
          
        WARUM --remote-allow-origins="*"?
          MIT Quotes! Ohne Quotes expandiert zsh * als Glob.
          → "no matches found" → Chrome startet nicht.
          → MIT Quotes: CDP WebSocket akzeptiert alle Origins.
          
        WARUM --user-data-dir=/tmp/heypiggy-new-<timestamp>?
          Timestamped Profile = frisch bei jedem Start.
          → Keine Korruption (im Gegensatz zu fixed /tmp/heypiggy-bot).
          → Einfache Identifikation: Neuestes Timestamp = aktuellste Session.
          
        WARUM sleep(8) nach Start?
          Chrome braucht Zeit zum Initialisieren:
          - 1-2s: Prozess startet
          - 3-4s: Profile initialisiert
          - 5-6s: Extensions laden
          - 7-8s: Seite laedt, CDP bereit
          → Weniger als 8s = CDP nicht bereit = Fehler.
          
        WARUM ps aux fuer PID-Ermittlung?
          subprocess.Popen gibt PID zurueck, ABER:
          - Chrome forked: Popen-PID != Main-PID
          - Auf macOS: Chrome startet Helper-Prozesse
          → ps aux ist zuverlaessiger (findet echten Main-Prozess).
          
        RACE CONDITION:
          Zwischen Popen() und ps aux kann Chrome noch nicht in ps auftauchen.
          → Wenn PID nicht gefunden: chrome_launch_failed.
          → Aufrufer kann retry() implementieren.
        """
        # LEVEL 1: Reconciliation — verwaiste Sessions aufraeumen
        self.reconcile()
        
        # LEVEL 1a: Existierende aktive Session?
        s = self.sessions.get(name)
        if s and s["status"] == "active":
            pid = s["pid"]
            active = set(p for p, _ in _main_chrome_pids())
            if pid in active:
                # Session existiert und laeuft → WID aktualisieren
                wid = _wid_from_pid(pid)
                s["wid"] = wid
                s["last_seen"] = time.time()
                self._save()
                return {"status": "ok", "pid": pid, "wid": wid,
                        "profile_dir": s["profile_dir"], "reused": True}

        # LEVEL 2: Keine Registry-Session, aber laufender Chrome?
        for pid, profile_dir in _main_chrome_pids():
            wid = _wid_from_pid(pid)
            self.register(name, pid, profile_dir, wid=wid, url=url)
            return {"status": "ok", "pid": pid, "wid": wid,
                    "profile_dir": profile_dir, "reused": True}

        # LEVEL 3: Chrome NEU starten (MANUELL, NICHT playstealth!)
        # ❌ BANNED: playstealth launch — setzt NICHT --force-renderer-accessibility!
        # Stattdessen: Chrome MANUELL starten mit korrekten Flags
        import time as _time  # Vermeidet Shadowing von global time
        profile_dir = f"/tmp/heypiggy-new-{int(_time.time())}"
        cmd = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--remote-debugging-port=9999",
            "--remote-allow-origins=\"*\"",  # 🔥 MIT Quotes! zsh expandiert * sonst!
            "--force-renderer-accessibility",  # 🔥 MUSS fuer AX-Tree!
            "--no-first-run",  # Kein Willkommens-Bildschirm
            "--no-default-browser-check",  # Kein "Chrome als Default?" Popup
            f"--user-data-dir={profile_dir}",  # 🔥 Timestamped, nie fixed!
            url,
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _time.sleep(8)  # Chrome-Initialisierung abwarten

        # LEVEL 4: PID ermitteln (via ps aux)
        pid = None
        ps_out = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        for line in ps_out.split('\n'):
            if profile_dir in line and '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        break  # Erster Match = Main-Prozess
                    except ValueError:
                        pass

        if not pid:
            return {"status": "error", "reason": "chrome_launch_failed"}

        # Session registrieren
        self.register(name, pid, profile_dir, url=url)
        return {"status": "ok", "pid": pid, "wid": None,
                "profile_dir": profile_dir, "reused": False}

    def close(self, name):
        """Beendet Chrome-Session (nur Bot-Chrome!).
        
        ARGS:
            name (str): Name der zu beendenden Session
            
        RETURNS:
            dict:
              {"status": "ok", "closed_pid": int}
              {"status": "error", "reason": "session_not_found"}
              
        ALGORITHMUS (Graceful → Force):
          1. Session finden (via find_session)
          2. PID extrahieren
          3. SIGTERM senden (Graceful Shutdown)
          4. 1s warten
          5. Pruefen: Prozess noch da? (os.kill(pid, 0))
          6. Wenn ja: SIGKILL senden (Force Kill)
          7. Session aus Registry entfernen
          8. Return Erfolg
          
        WARUM SIGTERM dann SIGKILL?
          SIGTERM = Graceful (Chrome speichert State, schliesst Tabs).
          SIGKILL = Force (sofort, ohne Cleanup).
          → SIGTERM zuerst = respektvoll. SIGKILL als Fallback.
          
        WARUM os.kill(pid, 0)?
          Signal 0 = "Existenz-Check". Toetet nicht, prueft nur ob PID existiert.
          → True: Prozess laeuft noch → SIGKILL noetig.
          → False/Error: Prozess tot → OK.
          
        WARUM nur os.kill() statt pkill/killall?
          SICHERHEIT. os.kill(pid) toetet EXAKT diese PID.
          pkill/killall toeten ALLE matching Prozesse = User-Chrome in Gefahr!
          
        WARUM unregister() am Ende?
          Auch wenn kill() fehlschlaegt: Session-Eintrag entfernen.
          → Keine verwaisten Eintraege.
          
        RACE CONDITION:
          Prozess stirbt zwischen SIGTERM und os.kill(pid, 0).
          → os.kill wirft OSError → Exception-Handling catched es.
        """
        s = self.find_session(name)
        if not s:
            return {"status": "error", "reason": "session_not_found"}
            
        pid = s["pid"]
        try:
            # Schritt 1: Graceful Shutdown (SIGTERM)
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            
            # Schritt 2: Pruefen ob noch da
            try:
                os.kill(pid, 0)  # Existenz-Check
                # Noch da → Force Kill (SIGKILL)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass  # Bereits tot → OK
        except OSError:
            pass  # Bereits tot → OK
            
        # Session aus Registry entfernen
        self.unregister(name)
        return {"status": "ok", "closed_pid": pid}

    def close_all(self):
        """Beendet ALLE Bot-Chrome-Sessions.
        
        RETURNS:
            list: Namen der beendeten Sessions
            
        WARUM list(self.sessions.keys())?
          Wir iterieren ueber eine Kopie der Keys.
          close() ruft unregister() auf (aendert self.sessions).
          → Ohne Kopie: RuntimeError (Dictionary changed during iteration).
          
        WARUM nicht einfach pkill -f heypiggy?
          pkill kann User-Chrome treffen wenn User zufaellig
          /tmp/heypiggy-new-* als Profil nutzt (extrem unwahrscheinlich,
          aber moeglich). → close() ist sicherer (PID-basiert).
        """
        closed = []
        for name in list(self.sessions.keys()):
            r = self.close(name)
            if r["status"] == "ok":
                closed.append(name)
        return closed

    def save_auth_state(self, name):
        """Speichert Auth-Status fuer Session.
        
        ARGS:
            name (str): Session-Name
            
        RETURNS:
            dict: {"status": "ok", "auth_file": str}
            
        WARUM?
          HeyPiggy-Login (Google OAuth) ist teuer (6 Steps).
          Auth-State speichern = schneller Re-Login.
          → auth_file zeigt auf gespeicherte Credentials/State.
          
        WARUM nicht direkt in sessions.json?
          Auth-State kann gross sein (Cookies, Tokens).
          → Separate Datei = sessions.json bleibt schlank.
        """
        s = self.find_session(name)
        if not s:
            return {"status": "error", "reason": "session_not_found"}
        auth_file = os.path.expanduser(f"~/.stealth/auth_{name}.json")
        s["auth_state"] = auth_file
        self._save()
        return {"status": "ok", "auth_file": auth_file}

    def load_auth_state(self, name):
        """Laedt Auth-Status fuer Session.
        
        ARGS:
            name (str): Session-Name
            
        RETURNS:
            str oder None: Pfad zur Auth-State-Datei oder None
        """
        s = self.find_session(name)
        if not s:
            return None
        return s.get("auth_state")


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
# WARUM __main__?
   # SessionManager ist auch als CLI nutzbar (ohne Python-Import).
   # → python session_manager.py <command> [args]
   # → Praktisch fuer schnelle Diagnose ohne Code-Aenderung.
# =============================================================================

if __name__ == "__main__":
    import sys
    sm = SessionManager()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        # Liste alle aktiven Sessions
        print("=== Active Sessions ===")
        sm.reconcile()
        for name, s in sm.list_all().items():
            print(f"  {name}: pid={s['pid']} profile={s['profile_dir']} wid={s.get('wid')}")

    elif cmd == "scan":
        # Scan alle laufenden Chrome-Prozesse (ohne Registry)
        print("=== Running Chrome Processes ===")
        for p in sm.scan_active():
            print(f"  PID={p['pid']} profile={p['profile_dir']}")

    elif cmd == "reconcile":
        # Reconcile Sessions
        stale = sm.reconcile()
        print(f"Removed stale: {stale}" if stale else "No stale sessions")

    elif cmd == "close" and len(sys.argv) > 2:
        # Beende spezifische Session
        print(sm.close(sys.argv[2]))

    elif cmd == "close-all":
        # Beende ALLE Sessions
        print(f"Closed: {sm.close_all()}")

    elif cmd == "launch" and len(sys.argv) > 2:
        # Starte neue Session
        url = sys.argv[3] if len(sys.argv) > 3 else "https://heypiggy.com/?page=dashboard"
        result = sm.launch(sys.argv[2], url)
        print(json.dumps(result, indent=2))

    else:
        print("Usage: python session_manager.py <list|scan|reconcile|close <name>|close-all|launch <name> [url]>")
        sys.exit(1)

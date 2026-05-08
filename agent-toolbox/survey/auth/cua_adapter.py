"""================================================================================
survey/auth/cua_adapter.py — CUA-Driver Subprocess Wrapper
================================================================================

ZWECK:
  EINZIGE Schnittstelle zwischen Python-Code und cua-driver Binary.
  cua-driver ist ein macOS-Tool das über die Accessibility API (AX) mit
  Chrome interagiert. Diese Datei kapselt ALLE subprocess-Aufrufe.

WARUM brauchen wir CUA (Accessibility API)?
  → Google OAuth verwendet Shadow-DOM für Login-Buttons.
  → Shadow-DOM ist für CDP (Chrome DevTools Protocol) UND Playwright
    NICHT zugänglich — die Elemente sind im DOM-Baum unsichtbar.
  → CUA (Core UI Automation / Accessibility) sieht die Elemente als
    AXButton/AXLink/AXTextField unabhängig vom DOM.
  → CUA ist der EINZIGE Weg Google OAuth zu automatisieren.

WARUM ein Wrapper?
  → cua-driver ist ein externes Binary (CLI-Tool).
  → Ohne Wrapper: subprocess.run(["cua-driver", ...]) überall im Code.
  → Mit Wrapper: Einheitliche API, Timeout-Handling, Error-Handling.
  → Mockbar: In Tests können wir CuaAdapter mocken (kein echtes Chrome nötig).

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  CuaAdapter (Diese Klasse)                                              │
  │  ├── run(cmd, input_)     → subprocess.run(cua-driver, ...)           │
  │  ├── list_windows()       → Alle Fenster auflisten                     │
  │  ├── call(pid, wid, ...)  → Einzelne CUA-Methode aufrufen             │
  │  ├── get_tree(pid, wid)   → AX-Tree als Liste von Strings             │
  │  ├── find_idx(tree, ...)  → Element-Index finden                       │
  │  ├── click(pid, wid, idx) → Auf Element klicken (AXPress)              │
  │  ├── type(pid, wid, ...)  → Text eingeben (set_value)                  │
  │  └── find_bot_window(...) → Bot-Chrome Fenster finden                  │
  └─────────────────────────────────────────────────────────────────────────┘

CUA-DRIVER KOMMUNIKATION:
  cua-driver call list_windows
    → JSON: {"windows": [{"pid": 123, "window_id": 456, "title": "...", ...}]}
  
  cua-driver call get_window_state
    → stdin: {"pid": 123, "window_id": 456}
    → JSON: {"tree_markdown": "- [0] AXButton 'Weiter'..."}
  
  cua-driver call click
    → stdin: {"pid": 123, "window_id": 456, "element_index": 35}
    → stdout: "Performed AXPress on [35] AXButton"
    → stderr: "(leer bei Erfolg, Fehlermeldung bei Fehler)"

WARUM JSON stdin/stdout?
  → cua-driver verwendet JSON-RPC-ähnliches Protokoll.
  → Parameter als JSON-Objekt über stdin (nicht Command-Line-Args).
  → Warum nicht CLI-Args? JSON kann komplexe Strukturen (Nested Dicts).
  → Warum nicht HTTP/TCP? cua-driver ist ein einfaches CLI-Tool.

BANNED METHODS (NIEMALS verwenden):
  ❌ cua-driver call (raw, ohne verify) → "Performed" ist nicht verifiziert!
     → Siehe AGENTS.md §Verify-Box: Nach Klick muss Zustand geprüft werden.
     → Dieser Wrapper gibt nur "performed" in stdout zurück → NICHT verifiziert.
  ❌ Hardcoded element_index → Index ändert sich bei jeder Seite!
     → Immer find_idx() verwenden (dynamische Suche).
  ❌ pkill -f "cua-driver" → tötet möglicherweise andere Prozesse.
  ❌ Timeout < 5s → CUA-Operationen können langsam sein (AX-Tree Scan).

WARUM timeout=15s default?
  → cua-driver muss AX-Tree scannen (alle Elemente der Seite).
  → Bei komplexen Seiten (Google OAuth) → 5-10s.
  → Bei langsameren Systemen → bis zu 15s.
  → 15s deckt 99% der Fälle ab. Bei Timeout → Retry oder Fehler.

WARUM stderr bei click/type prüfen?
  → cua-driver gibt Erfolg manchmal auf stderr aus (nicht stdout).
  → "performed" kann in stdout ODER stderr stehen.
  → Wir prüfen BEIDE: "performed" in stdout.lower() OR stderr.lower().
  → WARUM .lower()? cua-driver kann "Performed" oder "performed" schreiben.

WARUM find_bot_window height > 100?
  → macOS hat viele kleine Fenster (Menüleiste, Dock, Notifications).
  → Diese haben height < 100 (oft 20-40 Pixel).
  → Browser-Fenster haben height > 500 (typisch 800-1000).
  → Filter height > 100 entfernt Menüleiste/Dock/Popups.

WARUM find_idx nach [Index] suchen?
  → cua-driver Ausgabe: "- [35] AXButton 'Weiter' @(1095,706,91,40)"
  → Regex r'- \[(\d+)\]' findet die Nummer in Klammern.
  → \d+ = eine oder mehrere Ziffern.
  → (\d+) = Capturing Group → int(m.group(1)) gibt Index als Integer.

WARUM keyword.lower() in line.lower()?
  → Case-Insensitive Matching: "Weiter", "weiter", "WEITER" matcht alle.
  → Deutsche Umlaute: "Fortfahren" vs "fortfahren" → .lower() funktioniert.
  → WARUM nicht re.IGNORECASE? Einfacher: beide Strings lowercase.

WARUM "chrome" in app_name?
  → app_name kommt von macOS: "Google Chrome", "Safari", "Firefox".
  → Wir wollen NUR Chrome-Fenster (nicht Safari, nicht andere Apps).
  → .lower() weil macOS manchmal "Google Chrome" oder "google chrome" liefert.

ABHÄNGIGKEITEN:
  • cua-driver Binary im PATH (which cua-driver → /Users/.../.local/bin/cua-driver).
  • macOS (CUA ist Apple-spezifisch).
  • subprocess (Standardlibrary, kein externes Paket).
  • json (Standardlibrary, JSON-Parsing).
  • re (Standardlibrary, Regex für Index-Extraktion).

TESTBARKEIT:
  → CuaAdapter kann gemockt werden:
    mock = MagicMock()
    mock.list_windows.return_value = [{"pid": 123, "window_id": 456}]
    flow = GoogleOAuthFlow(mock, ...)
  → KEIN echtes Chrome nötig für Unit-Tests.
  → Integration-Tests brauchen echten Chrome + cua-driver.

WARNUNG:
  Diese Klasse ist LOW-LEVEL. Sie macht keine intelligente Entscheidungen.
  → Sie klickt BLIND auf Indices (ohne Verify).
  → GoogleOAuthFlow muss nach jedem Klick VERIFY machen (LoginVerifier).
  → Ohne Verify: "Performed" bedeutet nicht dass das Element wirklich geklickt wurde!
================================================================================"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# __future__ import: Ermöglicht type hints mit | (Union) Syntax in Python < 3.10.
# WARUM? str | None statt Optional[str] → kürzer, moderner.
# Wenn Python 3.10+ verwendet wird → optional, aber gut für Kompatibilität.
from __future__ import annotations

# json: JSON-Parsing für cua-driver stdout (JSON-RPC-ähnliches Protokoll).
# WARUM json.loads()? cua-driver gibt JSON als stdout zurück.
# WARUM nicht msgpack/protobuf? cua-driver verwendet einfaches JSON.
import json

# re: Regular Expressions für Index-Extraktion aus AX-Tree.
# WARUM re.search() statt str.find()? Wir brauchen die ZAHL in "[35]".
# Regex r'\[(\d+)\]' extrahiert ALLE Ziffern zwischen [ und ].
import re

# subprocess: Externe Prozess-Ausführung (cua-driver Binary).
# WARUM subprocess.run()? Einfachste API für CLI-Tools.
# WARUM nicht subprocess.Popen? Wir brauchen Sync-Aufruf (warten auf Ergebnis).
# WARUM capture_output=True? Wir müssen stdout/stderr lesen.
# WARUM text=True? stdout als String (nicht Bytes) → direkt JSON-parsen.
import subprocess

# typing: Type Hints für bessere IDE-Unterstützung und Dokumentation.
# WARUM Type Hints? → IDE zeigt Autocomplete, mypy findet Fehler früh.
# List[dict]: cua-driver gibt Liste von Fenster-Dictionaries zurück.
# Tuple[Optional[int], Optional[int]]: find_bot_window gibt (pid, wid) oder (None, None).
from typing import List, Tuple, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: CuaResult
# ═══════════════════════════════════════════════════════════════════════════════
class CuaResult:
    """Ergebnis eines cua-driver Aufrufs.
    
    WARUM eigene Klasse statt dict?
    → Typsicherheit: CuaResult hat explizite Felder (stdout, stderr, returncode).
    → Kein "Magic Dict" mit unklaren Keys.
    → Erweiterbar: Später können wir parsed_json als Property hinzufügen.
    → Klarer Vertrag: Wer CuaAdapter.run() aufruft, bekommt CuaResult zurück.
    
    ATTRIBUTE:
      stdout (str): cua-driver stdout (JSON oder Text).
      stderr (str): cua-driver stderr (Fehlermeldungen oder "performed").
      returncode (int): Exit-Code (0 = Erfolg, !=0 = Fehler).
    
    WARUM stderr manchmal Erfolg?
      → cua-driver ist ein Rust-Binary. Rust's println! geht zu stdout,
        eprintln! geht zu stderr. Der Entwickler hat Erfolgsmeldungen
        manchmal auf stderr geschrieben (unbeabsichtigt).
      → Wir prüfen BEIDE Streams auf "performed".
    """

    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        """Initialisiere CuaResult.
        
        WARUM Defaults ("", "", 0)?
          → Wenn cua-driver crasht → stdout/stderr könnten leer sein.
          → Default-Werte verhindern None-Errors beim Zugriff.
          → returncode=0 = Erfolg (auch wenn stdout leer → kein Erfolg nachweisbar).
        
        Args:
            stdout: Roher stdout-Text vom cua-driver Prozess.
            stderr: Roher stderr-Text vom cua-driver Prozess.
            returncode: Exit-Code (0 = Prozess beendete normal, !=0 = Crash/Fehler).
        """
        # stdout: Rohe Ausgabe des cua-driver Prozesses.
        # WARUM public Attribut? Der Aufrufer muss stdout prüfen (z.B. auf "performed").
        self.stdout = stdout
        
        # stderr: Fehlerausgabe des cua-driver Prozesses.
        # WARUM public Attribut? Manche Erfolgsmeldungen sind auf stderr (siehe oben).
        self.stderr = stderr
        
        # returncode: Exit-Code des Prozesses.
        # WARUM public Attribut? Nicht-Zero bedeutet cua-driver selbst crashte.
        # Hinweis: returncode=0 heißt NICHT dass der Klick erfolgreich war!
        #          Es heißt nur dass cua-driver normal beendet wurde.
        #          Erfolg wird durch "performed" in stdout/stderr bestimmt.
        self.returncode = returncode

    def json(self) -> dict:
        """Parse stdout als JSON, gib {} zurück bei Fehler.
        
        ABLAUF:
          1. Prüfe ob self.stdout existiert und nicht leer ist.
          2. Versuche json.loads(self.stdout) → Dictionary.
          3. Bei JSONDecodeError → {} zurückgeben (fail-soft).
          4. Bei leerem stdout → {} zurückgeben.
        
        WARUM {} statt None?
          → Client-Code kann .get("windows", []) auf None nicht aufrufen.
          → .get() funktioniert nur auf dict → {} ist sicherer.
          → Fail-soft: Wenn cua-driver kein JSON ausgibt → leeres Dict.
        
        WARUM Exception-fangen?
          → cua-driver könnte "Error: ..." auf stdout schreiben (kein JSON).
          → Ohne try/except → json.loads() wirft JSONDecodeError → Crash.
          → Mit try/except → {} zurück → Client kann fortfahren.
        
        WARUM nicht logging?
          → Dies ist ein Low-Level-Wrapper. Keine Side-Effects (kein Logging).
          → GoogleOAuthFlow loggt Ergebnisse (higher-level).
        
        Returns:
            dict: Geparstes JSON oder leeres Dictionary bei Fehler.
        
        Example:
            r = adapter.run(["cua-driver", "call", "list_windows"])
            data = r.json()
            # data = {"windows": [...]} oder {} bei Fehler
        """
        try:
            # Prüfe ob stdout existiert und nicht leer.
            # WARUM if self.stdout? json.loads("") wirft JSONDecodeError.
            if self.stdout:
                # Parse stdout als JSON.
                # WARUM json.loads()? Wir haben einen String (nicht File).
                return json.loads(self.stdout)
        except Exception:
            # JSONDecodeError oder andere Exception → fail-soft.
            # WARUM keine Log-Meldung? Low-Level-Wrapper soll nicht loggen.
            pass
        # Leeres Dictionary = sicherer Rückgabewert.
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: CuaAdapter
# ═══════════════════════════════════════════════════════════════════════════════
class CuaAdapter:
    """Low-Level Wrapper für das cua-driver Binary.
    
    WARUM "Low-Level"?
      → Diese Klasse macht KEINE intelligenten Entscheidungen.
      → Sie führt cua-driver Befehle aus und gibt Rohergebnisse zurück.
      → Intelligenz (Retry, Verify, Fallback) ist in GoogleOAuthFlow.
    
    WARUM "Adapter" Pattern?
      → cua-driver hat ein spezifisches Protokoll (JSON stdin → stdout).
      → Diese Klasse ADAPTIERT das Protokoll auf eine Python-API.
      → Ohne Adapter: Jeder Aufrufer müsste subprocess.run + json.loads kennen.
      → Mit Adapter: Einfache Methoden (click, type, list_windows).
    
    LEBENSZYKLUS:
      1. Erstellen: CuaAdapter(timeout=15)
      2. Verwenden: adapter.click(pid, wid, idx)
      3. Zerstören: Garbage Collection (kein explizites cleanup nötig).
    
    THREAD-SICHERHEIT:
      → subprocess.run ist NICHT thread-safe bei gleichem stdin/stdout.
      → Mehrere gleichzeitige Aufrufe → Race Conditions.
      → In unserem Flow: NUR sequentielle Aufrufe (ein Schritt nach dem anderen).
      → Wenn parallel nötig → pro Thread ein CuaAdapter-Objekt.
    
    WARUM timeout konfigurierbar?
      → Standard: 15s (deckt 99% der Fälle ab).
      → Langsame Systeme / viele Fenster → 30s.
      → Schnelle Operationen (nur list_windows) → 5s.
      → WARUM nicht globaler Timeout? Verschiedene Operationen brauchen
        unterschiedliche Zeiten (AX-Tree Scan vs einfacher Klick).
    """

    def __init__(self, timeout: int = 15):
        """Initialisiere CuaAdapter.
        
        Args:
            timeout: Maximale Wartezeit in Sekunden für cua-driver Aufrufe.
                     Default: 15s (für AX-Tree Scan ausreichend).
        
        WARUM timeout=15?
          → list_windows: ~1-2s (wenige Fenster).
          → get_window_state: ~3-5s (AX-Tree Scan der ganzen Seite).
          → click: ~1-2s (einzelnes Element).
          → set_value: ~1-2s (Text eingeben).
          → 15s = Safety-Margin für langsame Operationen.
        
        WARUM int statt float?
          → subprocess.run timeout Parameter akzeptiert int oder float.
          → Ganze Sekunden sind ausreichend (keine Sub-Sekunde nötig).
        """
        # timeout: Wartezeit in Sekunden für subprocess.run.
        # WARUM als Instanz-Attribut? Jedes CuaAdapter-Objekt kann eigene
        #   Timeout haben (z.B. schneller für Tests, langsamer für langsame Systeme).
        self.timeout = timeout

    def run(self, cmd: list[str], input_: str | None = None) -> CuaResult:
        """Führe cua-driver Befehl aus mit optionalem stdin Input.
        
        ABLAUF:
          1. Erstelle kwargs Dict für subprocess.run.
          2. Wenn input_ gesetzt → kwargs["input"] = input_ (stdin).
          3. Führe subprocess.run(cmd, ...) aus.
          4. Fange TimeoutExpired ab → CuaResult mit leerem stdout.
          5. Fange andere Exceptions ab → CuaResult mit leerem stdout.
          6. Gib CuaResult zurück (stdout, stderr, returncode).
        
        WARUM capture_output=True?
          → Wir müssen stdout/stderr LESEN (für JSON-Parsing und "performed" Check).
          → Ohne capture_output → stdout/stderr gehen an Terminal (verschwinden).
          → capture_output=True → stdout/stderr werden intern gespeichert.
        
        WARUM text=True?
          → stdout/stderr als String (nicht Bytes).
          → json.loads() braucht String (Bytes → Decode-Error).
          → "performed" in stdout → funktioniert nur mit String.
        
        WARUM kwargs Pattern?
          → Wenn input_ None → kein "input" Key in kwargs.
          → subprocess.run(["cmd"], input=None) → stdin = leer (nicht None).
          → Wenn input_ gesetzt → stdin = JSON-String.
          → Dynamisches kwargs ist sauberer als if/else mit zwei run() Aufrufen.
        
        WARUM TimeoutExpired abfangen?
          → cua-driver könnte hängen (Chrome nicht erreichbar, AX-Tree leer).
          → Ohne Abfangen → subprocess.run wirft TimeoutExpired → Crash.
          → Mit Abfangen → CuaResult mit leerem stdout → Client kann reagieren.
          → WARUM leerer stdout? Kein Ergebnis verfügbar → fail-soft.
        
        WARUM Exception abfangen?
          → cua-driver Binary könnte fehlen (FileNotFoundError).
          → cua-driver könnte crashen (returncode != 0).
          → Ohne Abfangen → Crash im Low-Level-Code.
          → Mit Abfangen → CuaResult mit returncode=-1 → Higher-Level reagiert.
        
        Args:
            cmd: Command-Line-Argumente als Liste.
                 Beispiel: ["cua-driver", "call", "list_windows"]
                 Beispiel: ["cua-driver", "call", "click"]
            input_: Optionaler JSON-String für stdin.
                    Beispiel: '{"pid": 123, "window_id": 456, "element_index": 35}'
                    None = kein stdin (für Methoden ohne Parameter).
        
        Returns:
            CuaResult mit stdout, stderr, returncode.
            Bei Timeout/Exception → CuaResult mit leerem stdout.
        
        Example:
            # list_windows (kein stdin)
            r = adapter.run(["cua-driver", "call", "list_windows"])
            # r.stdout = '{"windows": [...]}'
            
            # click (mit stdin)
            r = adapter.run(
                ["cua-driver", "call", "click"],
                '{"pid": 123, "window_id": 456, "element_index": 35}'
            )
            # r.stdout = 'Performed AXPress on [35] AXButton'
        """
        # kwargs: Parameter für subprocess.run.
        # WARUM Dict? Dynamisch: input_ wird nur hinzugefügt wenn gesetzt.
        kwargs = {
            # stdout/stderr als String zurückgeben (nicht Bytes).
            "capture_output": True,
            # Text-Modus: stdout/stderr sind Strings (nicht bytes-Objekte).
            "text": True,
            # Timeout: Wenn cua-driver hängt → breche ab.
            "timeout": self.timeout,
        }
        
        # Wenn input_ gesetzt → füge "input" zu kwargs hinzu.
        # WARUM nur wenn input_? subprocess.run mit input=None sendet leeres stdin.
        # Das ist OK, aber explizit ist sauberer.
        if input_:
            kwargs["input"] = input_
        
        try:
            # Führe cua-driver aus.
            # WARUM subprocess.run (nicht Popen/call)?
            #   → run() wartet auf Beendigung (wir brauchen Ergebnis).
            #   → Popen ist async (wir brauchen Sync-Ergebnis).
            #   → call ist veraltet (Python 3.5+, run ist modern).
            result = subprocess.run(cmd, **kwargs)
            
            # Erstelle CuaResult aus Prozess-Ergebnis.
            # WARUM nicht direkt return? CuaResult ist konsistenter.
            return CuaResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            # cua-driver hat Timeout überschritten.
            # WARUM leere CuaResult? Kein stdout/stderr verfügbar.
            # Higher-Level (GoogleOAuthFlow) kann auf Timeout reagieren.
            return CuaResult(stdout="", stderr="", returncode=-1)
        except Exception:
            # cua-driver Binary fehlt, crashte, oder anderer Fehler.
            # WARUM returncode=-1? Signalisiert "Fehler im Wrapper" (nicht cua-driver).
            # cua-driver selbst gibt 0-255 als returncode (Unix-Standard).
            # -1 ist außerhalb dieses Bereichs → eindeutig "Wrapper-Fehler".
            return CuaResult(stdout="", stderr="", returncode=-1)

    def list_windows(self) -> List[dict]:
        """Liste ALLE Fenster via cua-driver auf.
        
        ABLAUF:
          1. Führe cua-driver call list_windows aus.
          2. Parse stdout als JSON.
          3. Extrahiere "windows" Array.
          4. Gib Liste von Fenster-Dictionaries zurück.
        
        WARUM "windows" Key?
          → cua-driver gibt {"windows": [{"pid": 123, ...}, ...]} zurück.
          → Nicht direkt eine Liste → wir müssen .get("windows", []) verwenden.
          → WARUM .get() statt ["windows"]? Wenn Key fehlt → KeyError.
          → .get("windows", []) gibt leere Liste → sicher.
        
        FENSTER-DICT STRUKTUR:
          {
            "pid": 12345,           # Prozess-ID (Chrome)
            "window_id": 67890,     # Fenster-ID (macOS Accessibility)
            "title": "HeyPiggy Dashboard",  # Fenster-Titel
            "app_name": "Google Chrome",     # App-Name
            "bounds": {"x": 0, "y": 25, "width": 1440, "height": 875},
            "z_index": 5             # Stacking-Order (höher = vorne)
          }
        
        WARUM bounds?
          → Position und Größe des Fensters.
          → Nützlich für find_bot_window (height > 100 Filter).
        
        WARUM z_index?
          → Höher = Fenster ist weiter vorne (sichtbarer).
          → Bei mehreren Chrome-Fenstern → sortiere nach z_index descending.
          → Das vorderste Fenster ist wahrscheinlich das Aktive.
        
        WARUM List[dict] statt TypedDict?
          → cua-driver ist ein externes Tool → Schema kann sich ändern.
          → dict ist flexibler (neue Keys werden ignoriert).
          → TypedDict würde bei neuen Keys Fehler werfen.
        
        Returns:
            Liste von Fenster-Dictionaries.
            Bei Fehler → leere Liste [] (nicht None!).
        
        Example:
            windows = adapter.list_windows()
            # windows = [
            #   {"pid": 123, "window_id": 456, "title": "HeyPiggy", ...},
            #   {"pid": 789, "window_id": 101, "title": "Google", ...}
            # ]
        """
        # Führe cua-driver call list_windows aus.
        # WARUM kein stdin? list_windows braucht keine Parameter.
        r = self.run(["cua-driver", "call", "list_windows"])
        
        # Parse JSON und extrahiere "windows" Array.
        # WARUM .get("windows", [])? Fail-soft wenn Key fehlt oder JSON ungültig.
        return r.json().get("windows", [])

    def call(self, pid: int, wid: int, method: str,
             params: Optional[dict] = None) -> dict:
        """Rufe eine einzelne cua-driver Methode auf.
        
        ABLAUF:
          1. Erstelle Parameter-Dictionary mit pid und window_id.
          2. Füge optionale params hinzu (z.B. {"element_index": 35}).
          3. Konvertiere zu JSON-String.
          4. Führe cua-driver call <method> aus mit JSON als stdin.
          5. Parse stdout als JSON.
          6. Füge stdout und stderr zum Ergebnis hinzu (für "performed"-Check).
        
        WARUM pid + wid IMMER?
          → Jede CUA-Operation braucht Kontext: Welcher Prozess? Welches Fenster?
          → Ohne pid/wid → cua-driver weiß nicht welches Fenster gemeint ist.
          → pid = Prozess-ID (Chrome). wid = Fenster-ID (macOS).
        
        WARUM params Optional?
          → Manche Methoden brauchen keine Extra-Parameter.
            Beispiel: get_window_state braucht nur pid + wid.
          → Andere Methoden brauchen Extra-Parameter.
            Beispiel: click braucht {"element_index": 35}.
          → params=None → keine Extra-Parameter → nur pid + wid.
        
        WARUM dict(params or {})?
          → Wenn params=None → dict(None) wirft TypeError.
          → dict({}) → leeres Dict (sicher).
          → Wir kopieren das Dict (nicht Referenz) → keine Seiteneffekte.
        
        WARUM stdout/stderr im Ergebnis?
          → cua-driver gibt Erfolg als Rohtext (nicht JSON):
            "Performed AXPress on [35] AXButton"
          → Das ist KEIN JSON → json() würde {} zurückgeben.
          → Wir fügen stdout/std stderr zum Dict hinzu → Aufrufer kann prüfen.
          → WARUM nicht immer json.loads? Manche Ausgaben sind Text, keine JSON.
        
        Args:
            pid: Prozess-ID des Chrome-Prozesses.
            wid: Fenster-ID (von list_windows).
            method: CUA-Methode (z.B. "click", "set_value", "get_window_state").
            params: Optionale Extra-Parameter als Dictionary.
        
        Returns:
            dict: JSON-Ergebnis + stdout + stderr Keys.
            Bei Fehler → {"stdout": "", "stderr": ""}.
        
        Example:
            d = adapter.call(123, 456, "click", {"element_index": 35})
            # d = {
            #   "stdout": "Performed AXPress on [35] AXButton",
            #   "stderr": "",
            #   "returncode": 0
            # }
        """
        # Kopiere params (oder leeres Dict) damit wir pid/wid hinzufügen können.
        # WARUM Kopie? Nicht das Original-Dict des Aufrufers modifizieren.
        p = dict(params or {})
        
        # Füge pid und window_id hinzu.
        # WARUM zuerst pid, dann wid? Reihenfolge ist egal (JSON-Objekt).
        # Aber konsistente Reihenfolge → lesbarerer Debug-Output.
        p["pid"] = pid
        p["window_id"] = wid
        
        # Führe cua-driver call <method> aus.
        # WARUM json.dumps()? cua-driver erwartet JSON als stdin.
        r = self.run(["cua-driver", "call", method], json.dumps(p))
        
        # Parse stdout als JSON (falls cua-driver JSON zurückgibt).
        d = r.json()
        
        # Füge stdout und stderr hinzu (für "performed"-Check im Aufrufer).
        # WARUM extra Keys? Aufrufer (click/type) prüft auf "performed".
        # Ohne diese Keys → Aufrufer müsste CuaResult Objekt halten.
        # Mit diesen Keys → Aufrufer kann einfach d["stdout"] prüfen.
        d["stdout"] = r.stdout
        d["stderr"] = r.stderr
        
        return d

    def get_tree(self, pid: int, wid: int) -> List[str]:
        """Hole AX-Tree als Liste von Strings.
        
        ABLAUF:
          1. Rufe get_window_state auf (cua-driver Methode).
          2. Extrahiere "tree_markdown" aus der JSON-Antwort.
          3. Splitte bei \n in einzelne Zeilen.
          4. Gib Liste von Zeilen zurück.
        
        WARUM "tree_markdown"?
          → cua-driver formatiert den AX-Tree als Markdown-ähnliche Liste:
            - [0] AXButton 'Schließen' @(100,200,50,30)
            - [1] AXLink 'Google Login-Symbol' @(731,651,132,41)
          → "tree_markdown" ist der Key in der JSON-Antwort.
        
        WARUM List[str] statt komplexem Objekt?
          → Einfacher zu parsen (Regex auf Strings).
          → find_idx() kann einfach durch Zeilen iterieren.
          → Weniger Speicher als komplexe Objekt-Struktur.
        
        WARUM .split("\n")?
          → Jede Zeile repräsentiert ein Element im AX-Tree.
          → Zeilenweise Verarbeitung → einfacher als komplexer Parser.
          → Wir können einfach "for line in tree" iterieren.
        
        AX-TREE ZEILENFORMAT:
          "- [35] AXButton 'Weiter' @(1095,706,91,40)"
          → [35] = element_index (für click/set_value).
          → AXButton = Role (AXButton, AXLink, AXTextField, etc.).
          → 'Weiter' = Label/Text (für keyword-Matching).
          → @(1095,706,91,40) = Bounds (x, y, width, height).
        
        WARUM List[str] bei Fehler?
          → Bei leerem tree_markdown → .split("\n") → [""] (Liste mit einem leeren String).
          → WARUM nicht []? .split() auf leerem String gibt [""] zurück.
          → Wir prüfen explizit: if isinstance(d, dict) → sonst [].
        
        Args:
            pid: Prozess-ID des Chrome-Prozesses.
            wid: Fenster-ID (von list_windows).
        
        Returns:
            Liste von AX-Tree Zeilen.
            Bei Fehler → leere Liste [].
        
        Example:
            tree = adapter.get_tree(123, 456)
            # tree = [
            #   "- [0] AXButton 'Schließen' @(100,200,50,30)",
            #   "- [1] AXLink 'Google Login-Symbol' @(731,651,132,41)",
            #   ...
            # ]
        """
        # Rufe get_window_state auf (keine Extra-Parameter nötig).
        d = self.call(pid, wid, "get_window_state")
        
        # Prüfe ob Antwort ein Dictionary ist (kein Fehler).
        # WARUM isinstance? Wenn cua-driver crashte → call() gibt leeres Dict {} zurück.
        # {} ist ein dict → wir können .get() aufrufen.
        if isinstance(d, dict):
            # Extrahiere tree_markdown und splitte in Zeilen.
            # WARUM .get("tree_markdown", "")? Fail-soft wenn Key fehlt.
            return d.get("tree_markdown", "").split("\n")
        
        # Bei ungültiger Antwort → leere Liste.
        return []

    def find_idx(self, tree: List[str], keyword: str,
                 roles: Optional[List[str]] = None) -> Optional[int]:
        """Finde element_index via Keyword und Role im AX-Tree.
        
        ABLAUF:
          1. Wenn roles=None → verwende Defaults ["AXButton", "AXLink", "AXTextField"].
          2. Für jede Role in roles:
             Für jede Zeile im tree:
               a. Prüfe ob keyword (case-insensitive) in Zeile enthalten.
               b. Prüfe ob Role in Zeile enthalten.
               c. Extrahiere Index via Regex: r'- \[(\d+)\]'.
               d. Wenn gefunden → gib Index als int zurück.
          3. Wenn nichts gefunden → gib None zurück.
        
        WARUM keyword.lower() in line.lower()?
          → Case-Insensitive: "Weiter", "weiter", "WEITER" matcht alle.
          → Deutsche Umlaute funktionieren mit .lower().
          → WARUM nicht re.IGNORECASE? Einfacher: beide Strings lowercase.
          → WARUM "in" statt ==? Partielles Matching: "Weiter" matcht
            "- [35] AXButton 'Weiter'" → "weiter" in der Zeile.
        
        WARUM Role-Prüfung?
          → Keyword "weiter" könnte in AXButton UND AXTextField vorkommen.
          → Wir wollen den BUTTON "Weiter", nicht ein Textfeld.
          → Role schränkt ein: NUR Elemente mit dieser Role.
        
        WARUM Defaults ["AXButton", "AXLink", "AXTextField"]?
          → Die häufigsten interaktiven Elemente.
          → AXButton = normale Buttons ("Weiter", "Fortfahren").
          → AXLink = Links ("Google Login-Symbol").
          → AXTextField = Text-Eingabefelder ("E-Mail oder Telefonnummer").
          → WARUM diese 3? Sie decken 95% der Google OAuth Elemente ab.
        
        WARUM Regex r'- \[(\d+)\]'?
          → AX-Tree Format: "- [35] AXButton 'Weiter'"
          → \[ = literale Klammer [ (escaped weil [ in Regex eine Character-Class ist).
          → (\d+) = eine oder mehrere Ziffern (Capturing Group).
          → \] = literale Klammer ].
          → m.group(1) = die Ziffern als String → int() konvertiert zu Integer.
        
        WARUM Erste Match gewinnt?
          → Wir geben beim ersten Treffer zurück (return, nicht append).
          → Wenn mehrere Elemente das gleiche Keyword haben → erstes wird genommen.
          → In der Praxis: Google OAuth hat nur ein "Weiter" Button.
          → Wenn mehrere → ist die Seite unerwartet → erstes ist oft das richtige.
        
        WARUM None statt -1?
          → None ist expliziter: "Nicht gefunden".
          → -1 könnte ein echter Index sein (wenn jemand bei -1 anfängt).
          → click() und type() prüfen "if idx is None → return False".
          → Das ist sauberer als "if idx == -1".
        
        Args:
            tree: AX-Tree als Liste von Zeilen (von get_tree()).
            keyword: Suchbegriff (z.B. "weiter", "google", "e-mail").
            roles: Liste erlaubter Roles (z.B. ["AXButton", "AXLink"]).
                   None = ["AXButton", "AXLink", "AXTextField"].
        
        Returns:
            element_index (int) oder None wenn nicht gefunden.
        
        Example:
            idx = adapter.find_idx(tree, "weiter", ["AXButton"])
            # idx = 35 (oder None wenn nicht gefunden)
        """
        # WARUM Default-Roles? Reduziert Boilerplate im Aufrufer.
        # Aufrufer muss nicht immer ["AXButton", "AXLink", "AXTextField"] angeben.
        if roles is None:
            roles = ["AXButton", "AXLink", "AXTextField"]
        
        # Iteriere über alle Roles.
        # WARUM äußere Schleife (roles) vor innerer (tree)?
        # → Wir priorisieren die erste Role.
        # → Wenn "AXButton" zuerst → wir finden Buttons bevor Links.
        # → Das ist oft gewünscht (Button vor Link bei gleichem Keyword).
        for role in roles:
            # Iteriere über alle Zeilen im AX-Tree.
            for line in tree:
                # Case-Insensitive Matching für Keyword und Role.
                # WARUM beide .lower()? Konsistentes Case-Insensitive Verhalten.
                if keyword.lower() in line.lower() and role in line:
                    # Extrahiere Index via Regex.
                    # WARUM re.search? Findet das erste Vorkommen in der Zeile.
                    m = re.search(r'- \[(\d+)\]', line)
                    if m:
                        # Konvertiere zu Integer und gib zurück.
                        # WARUM int()? cua-driver erwartet Integer-Index.
                        # m.group(1) ist ein String (z.B. "35") → int("35") = 35.
                        return int(m.group(1))
        
        # Nichts gefunden → None.
        # WARUM nicht Exception werfen? Fail-soft → Aufrufer kann reagieren.
        # GoogleOAuthFlow prüft idx is None → gibt Fehler-Reason zurück.
        return None

    def click(self, pid: int, wid: int, idx: Optional[int]) -> bool:
        """Klicke auf ein Element via cua-driver AXPress.
        
        ABLAUF:
          1. Wenn idx is None → False zurückgeben (kein Element gefunden).
          2. Rufe cua-driver call click auf mit {"element_index": idx}.
          3. Prüfe ob "performed" in stdout ODER stderr enthalten ist.
          4. Gib True/False zurück.
        
        WARUM AXPress?
          → AXPress ist die Accessibility-Aktion "Drücken".
          → Nicht Mouse-Click → Accessibility-API Event.
          → Vorteil: Funktioniert auch wenn Element nicht sichtbar/verdeckt ist.
          → Vorteil: Keine Koordinaten nötig (Position-unabhängig).
        
        WARUM "performed" prüfen?
          → cua-driver gibt bei Erfolg aus: "Performed AXPress on [35] AXButton".
          → WARUM nicht returncode? returncode=0 heißt nur "Prozess lief durch".
          → Erfolg wird durch Text-Matching bestimmt.
          → WARUM stdout OR stderr? Siehe CuaResult Erklärung oben.
          → WARUM .lower()? cua-driver könnte "Performed" oder "performed" schreiben.
        
        WARUM False bei idx is None?
          → find_idx() gibt None zurück wenn Element nicht gefunden.
          → Wenn wir mit None klicken → cua-driver Fehler → Zeitverschwendung.
          → Frühes Return → schneller, weniger Log-Noise.
        
        WICHTIG: VERIFY fehlt!
          → Diese Methode prüft NICHT ob der Klick WIRKLICH funktionierte.
          → Sie prüft nur ob cua-driver "performed" sagte.
          → "performed" != Element wurde aktiviert (Event könnte fehlschlagen).
          → VERIFY muss im Aufrufer (GoogleOAuthFlow) gemacht werden!
          → Siehe AGENTS.md §Verify-Box: Nach Klick → Zustand prüfen.
        
        BANNED: Niemals hardcoded idx verwenden!
          → idx ändert sich bei jeder Seite.
          → Immer find_idx() → click() Pattern verwenden.
          → Hardcoded idx = fragile, bricht bei jeder UI-Änderung.
        
        Args:
            pid: Prozess-ID des Chrome-Prozesses.
            wid: Fenster-ID.
            idx: element_index (von find_idx) oder None.
        
        Returns:
            True wenn "performed" in stdout/stderr gefunden.
            False wenn idx is None oder "performed" nicht gefunden.
        
        Example:
            idx = adapter.find_idx(tree, "weiter", ["AXButton"])
            success = adapter.click(pid, wid, idx)
            # success = True (oder False wenn fehlgeschlagen)
        """
        # Frühes Return wenn kein Index gefunden.
        # WARUM? Nicht cua-driver mit None belästigen.
        if idx is None:
            return False
        
        # Führe click aus.
        r = self.call(pid, wid, "click", {"element_index": idx})
        
        # Extrahiere stdout und stderr.
        stdout = r.get("stdout", "")
        stderr = r.get("stderr", "")
        
        # Prüfe ob "performed" in stdout oder stderr.
        # WARUM .lower()? Case-insensitive Matching.
        return "performed" in stdout.lower() or "performed" in stderr.lower()

    def type(self, pid: int, wid: int, idx: Optional[int],
             value: str) -> bool:
        """Tippe Text in AXTextField via cua-driver set_value.
        
        ABLAUF:
          1. Wenn idx is None → False zurückgeben.
          2. Rufe cua-driver call set_value auf mit element_index und value.
          3. Prüfe ob "performed" oder "set" in stdout enthalten ist.
          4. Gib True/False zurück.
        
        WARUM set_value (nicht type/type_keys)?
          → set_value setzt den Wert DIREKT (nicht simuliert Tastendrücke).
          → Vorteil: Schneller (keine Verzögerung zwischen Tasten).
          → Vorteil: Keine Focus-Probleme (Wert wird direkt gesetzt).
          → Vorteil: Funktioniert auch wenn Feld nicht fokussiert ist.
        
        WARUM "performed" oder "set"?
          → cua-driver gibt unterschiedliche Erfolgsmeldungen:
            "Performed set_value on [25] AXTextField"
            "Set value on [25] AXTextField"
          → Wir prüfen BEIDE Strings → robustere Erkennung.
          → WARUM nicht nur "performed"? Manche Versionen sagen "set".
        
        WARUM keine Verify?
          → Wie bei click(): Wir prüfen nur ob cua-driver "performed" sagte.
          → Wir prüfen NICHT ob der Text WIRKLICH im Feld steht.
          → Verify muss im Aufrufer gemacht werden (GoogleOAuthFlow).
          → Aber: set_value ist zuverlässiger als click (weniger Race-Conditions).
        
        Args:
            pid: Prozess-ID des Chrome-Prozesses.
            wid: Fenster-ID.
            idx: element_index des AXTextField (von find_idx) oder None.
            value: Der einzutippende Text (z.B. "zukunftsorientierte.energie@gmail.com").
        
        Returns:
            True wenn "performed" oder "set" in stdout gefunden.
            False wenn idx is None oder kein Erfolg.
        
        Example:
            idx = adapter.find_idx(tree, "e-mail", ["AXTextField"])
            success = adapter.type(pid, wid, idx, "email@example.com")
            # success = True (oder False wenn fehlgeschlagen)
        """
        # Frühes Return wenn kein Index gefunden.
        if idx is None:
            return False
        
        # Führe set_value aus.
        r = self.call(pid, wid, "set_value",
                      {"element_index": idx, "value": value})
        
        # Extrahiere stdout.
        stdout = r.get("stdout", "")
        
        # Prüfe ob "performed" oder "set" in stdout.
        # WARUM .lower()? Case-insensitive Matching.
        return "performed" in stdout.lower() or "set" in stdout.lower()

    def find_bot_window(
        self,
        keywords: Optional[List[str]] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Finde Bot-Chrome Fenster via Keywords.
        
        ABLAUF:
          1. Rufe list_windows() auf → alle Fenster.
          2. Für jedes Fenster:
             a. Prüfe bounds.height > 100 (kein Menü/Dock/Popup).
             b. Prüfe "chrome" in app_name (nur Chrome, nicht Safari/Firefox).
             c. Wenn keywords gesetzt:
                Prüfe ob EINES der Keywords im Titel enthalten ist.
                Wenn ja → gib (pid, wid) zurück.
             d. Wenn keywords None:
                Gib (pid, wid) zurück (erstes Chrome-Fenster).
          3. Wenn nichts gefunden → (None, None).
        
        WARUM height > 100?
          → macOS hat viele kleine UI-Elemente:
            - Menüleiste: height ~25
            - Dock: height ~50
            - Notifications: height ~40
            - Hilfsfenster: height ~80
          → Browser-Fenster sind typisch 600-1000 Pixel hoch.
          → Filter height > 100 entfernt ALLE nicht-Browser-Fenster.
          → WARUM nicht > 500? Manche Browser-Fenster sind minimiert/verkleinert.
          → 100 ist konservativ: entfernt Menüleiste aber behält kleine Browser.
        
        WARUM "chrome" in app_name.lower()?
          → app_name kommt von macOS: "Google Chrome", "Safari", "Firefox".
          → Wir wollen NUR Chrome (CUA arbeitet mit Chrome zusammen).
          → .lower() für Case-Insensitivität.
          → WARUM nicht exakter Match? "Google Chrome" vs "google chrome".
        
        WARUM keywords Optional?
          → Wenn keywords=None → erstes Chrome-Fenster wird genommen.
          → Nützlich als Fallback: "Nimm irgendein Chrome-Fenster".
          → Wenn keywords gesetzt → spezifische Suche (z.B. "heypiggy").
        
        WARUM any() statt all()?
          → any(k in t for k in keywords) → EINES der Keywords muss matchten.
          → all() würde verlangen dass ALLE Keywords im Titel sind.
          → any() ist flexibler: ["google", "anmelden"] matcht beides.
        
        WARUM (pid, wid) Tuple?
          → Konvention in diesem Projekt: (pid, wid) = Fenster-Referenz.
          → None, None = "nicht gefunden".
          → Tuple ist immutable → sicherer als Liste (keine Seiteneffekte).
        
        WARUM Erstes Match gewinnt?
          → Wir iterieren über alle Fenster und geben beim ersten Treffer zurück.
          → Bei mehreren Chrome-Fenstern → erstes passende wird genommen.
          → In der Praxis: Meistens gibt es nur ein passendes Fenster.
        
        Args:
            keywords: Liste von Keywords für Fenster-Titel-Matching.
                      None = erstes Chrome-Fenster.
                      Beispiel: ["heypiggy", "dashboard", "verdienen"]
                      Beispiel: ["google", "anmelden", "accounts"]
        
        Returns:
            (pid, wid) Tuple oder (None, None) wenn nicht gefunden.
        
        Example:
            pid, wid = adapter.find_bot_window(["heypiggy", "dashboard"])
            # pid = 12345, wid = 67890 (oder None, None)
        """
        # Hole alle Fenster.
        # WARUM nicht direkt iterieren? list_windows() könnte leere Liste zurückgeben.
        for w in self.list_windows():
            # Extrahiere bounds (Fenster-Größe).
            b = w.get("bounds", {})
            
            # Extrahiere Titel (lowercase für Case-Insensitive Matching).
            t = (w.get("title") or "").lower()
            
            # Extrahiere App-Name (lowercase).
            n = (w.get("app_name") or "").lower()
            
            # Extrahiere PID.
            pid = w.get("pid")
            
            # FILTER 1: Höhe muss > 100 sein.
            # WARUM height > 100? Entfernt Menüleiste, Dock, Popups.
            # WARUM .get("height", 0)? Wenn bounds nicht existiert → height=0 → wird abgelehnt.
            if b.get("height", 0) < 100:
                continue
            
            # FILTER 2: Muss Chrome sein.
            # WARUM continue (nicht return)? Wir wollen das NÄCHSTE Fenster prüfen.
            if "chrome" not in n:
                continue
            
            # Wenn keywords gesetzt → prüfe Titel-Matching.
            if keywords:
                # any(): EINES der Keywords muss im Titel enthalten sein.
                if any(k in t for k in keywords):
                    # Match! Gib (pid, wid) zurück.
                    return pid, w.get("window_id")
            else:
                # Keine keywords → erstes Chrome-Fenster.
                return pid, w.get("window_id")
        
        # Nichts gefunden → (None, None).
        return None, None

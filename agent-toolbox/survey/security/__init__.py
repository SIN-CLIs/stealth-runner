"""================================================================================
survey/security/__init__.py — SecretsClient: Runtime Credential Resolution
================================================================================

ZWECK:
  Zentrale Quelle für ALLE Runtime-Credentials (NICHT hardcoded!).
  Liest Credentials aus Umgebungsvariablen oder ~/.stealth/config.yaml.
  Fail-closed: Wenn ein Secret fehlt → MissingSecretError mit klarem Hinweis.

WARUM zentrale Credential-Verwaltung?
  → Hardcoded Credentials = Sicherheitsrisiko (Git-Leak, Credential-Rotation).
  → Zentrale Quelle = einfache Rotation (nur eine Datei ändern).
  → Fail-closed = klare Fehlermeldung (nicht mysteriöser None-Error).
  → Typsicherheit: CPXCredentials ist ein @dataclass (nicht loose Dict).

WARUM Singleton Pattern (SecretsClient)?
  → config.yaml wird nur EINMAL geladen (beim ersten Zugriff).
  → Wiederverwendung: Mehrere Aufrufe von get_google_email() → gleiches Ergebnis.
  → Konsistenz: Wenn config.yaml sich ändert → Neustart nötig (kein Reload).
  → WARUM kein Reload? Credentials ändern sich selten. Reload = Komplexität.
  → WARUM kein File-Watcher? Überengineering. Neustart = akzeptabel.

RESOLUTION ORDER (Priorität, höchste zuerst):
  1. Umgebungsvariable (os.getenv("GOOGLE_EMAIL"))
  2. ~/.stealth/config.yaml (dotted_key: google.email)
  3. MissingSecretError (wenn beides fehlt)

WARUM Env-Vars vor config.yaml?
  → Env-Vars sind transiente (Docker, CI/CD, Cloud-Run).
  → config.yaml ist persistent (lokale Entwicklung, persistente Maschine).
  → Docker/CI überschreibt lokale Config → flexibler.
  → 12-Factor App Methode: Config via Env-Vars (https://12factor.net/config).

WARUM ~/.stealth/config.yaml?
  → Persistente Konfiguration für lokale Entwicklung.
  → Nicht im Git-Repo (in .gitignore).
  → YAML = lesbarer als JSON (Kommentare möglich).
  → Struktur:
      google:
        email: "zukunftsorientierte.energie@gmail.com"
      cpx:
        app_id: "..."
        ext_user_id: "..."
        secure_hash: "..."
        email: "..."

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  SecretsClient (Singleton)                                              │
  │  ├── _load_config()       → Lädt ~/.stealth/config.yaml               │
  │  ├── get_google_email()   → GOOGLE_EMAIL aus env oder yaml             │
  │  ├── get_cpx_credentials() → Komplettes CPXCredentials Objekt          │
  │  ├── require_nvidia_api_key() → NVIDIA_API_KEY (für NIM)              │
  │  ├── _required(env, key)  → Resolution Order implementierung           │
  │  └── _config_value(key)   → Dotted-Key Lookup in YAML                  │
  └─────────────────────────────────────────────────────────────────────────┘

TYPEN:
  CPXCredentials (@dataclass):
    → app_id (str): CPX App ID für API-Calls.
    → ext_user_id (str): Externe User-ID für CPX.
    → secure_hash (str): Sicherheits-Hash für CPX.
    → email (str): E-Mail für CPX API.

  MissingSecretError (RuntimeError):
    → Geworfen wenn ein required Secret nicht gefunden wird.
    → Klare Fehlermeldung: "Missing required secret: GOOGLE_EMAIL (google.email)".
    → Enthält sowohl env_name als auch config_key → schnelleres Debugging.

WARUM @dataclass für CPXCredentials?
  → Typsicherheit: app_id MUSS str sein (nicht None oder int).
  → IDE-Autovervollständigung: cpx.app_id (nicht cpx["app_id"]).
  → Immutable (wenn frozen=True): Werte können nicht nachträglich geändert werden.
  → Weniger Boilerplate: Kein __init__, __repr__, __eq__ nötig.

WARUM RuntimeError statt ValueError?
  → MissingSecretError ist ein Konfigurations-Fehler (nicht ein ungültiger Wert).
  → RuntimeError signalisiert: "System ist nicht richtig konfiguriert".
  → Aufrufer können except MissingSecretError fangen (spezifisch).
  → ValueError wäre zu generisch (könnte alles bedeuten).

BANNED PATTERNS (NIEMALS verwenden):
  ❌ Hardcoded Credentials im Code → Git-Leak, Rotation unmöglich.
  ❌ Default-Werte in _required() → "default='test@test.com'" = Credential-Leak.
  ❌ print() statt Exception → Client weiß nicht dass etwas fehlt.
  ❌ os.environ statt os.getenv → os.environ["X"] wirft KeyError (nicht fail-closed).
  ❌ JSON statt YAML → YAML unterstützt Kommentare (besser für Config).

VERWENDUNG:
  from survey.security import SecretsClient, get_secrets

  # Google E-Mail holen (für OAuth Login)
  email = SecretsClient.get_google_email()
  # → "zukunftsorientierte.energie@gmail.com"
  # → MissingSecretError wenn nicht konfiguriert

  # CPX Credentials holen (für Survey-API)
  creds = SecretsClient.get_cpx_credentials()
  # → CPXCredentials(app_id="...", ext_user_id="...", ...)

  # Singleton verwenden (bequemer)
  secrets = get_secrets()
  email = secrets.get_google_email()

ABHÄNGIGKEITEN:
  • os (Standardlibrary): Umgebungsvariablen lesen.
  • pathlib (Standardlibrary): Plattform-unabhängige Pfade.
  • dataclasses (Standardlibrary): @dataclass für CPXCredentials.
  • typing (Standardlibrary): Type Hints.
  • yaml (Extern): PyYAML für config.yaml Parsing.
    → Installation: pip install pyyaml
    → WARUM yaml? Menschlich lesbar, Kommentare möglich.

WARNUNG:
  Diese Datei liest SENSIBLE DATEN (E-Mails, API-Keys, Hashes).
  → ~/.stealth/config.yaml darf NICHT ins Git-Repository!
  → Env-Variablen dürfen NICHT in .env.example mit echten Werten stehen!
  → Credentials dürfen NICHT in Logs oder Error-Messages geloggt werden!
  → get_secrets() gibt SecretsClient zurück → Credentials als Attribute
    (nicht als String in Logs schreiben!).
================================================================================"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# os: Umgebungsvariablen lesen (os.getenv).
# WARUM os.getenv (nicht os.environ)? os.getenv("X") gibt None zurück wenn X fehlt.
# os.environ["X"] wirft KeyError → muss try/except fangen → umständlicher.
# os.getenv ist fail-soft (gibt None), os.environ ist fail-hard (wirft Exception).
import os

# dataclasses: Deklarative Klassen-Definition (weniger Boilerplate).
# WARUM @dataclass? Kein manuelles __init__, __repr__, __eq__ nötig.
# Typsicherheit: Felder haben explizite Typen (str, nicht Any).
from dataclasses import dataclass

# pathlib: Objekt-orientierte Pfad-Manipulation (cross-platform).
# WARUM Path (nicht String)? Path.home() / ".stealth" / "config.yaml"
#   funktioniert auf Windows UND macOS/Linux ( korrekte Trennzeichen).
# String-Konkatenation: os.path.join() ist umständlicher als Path / "subdir".
from pathlib import Path

# typing: Type Hints für IDE-Unterstützung und mypy.
# Optional: Ein Feld kann entweder einen Wert haben ODER None.
# WARUM Optional[str]? get_nvidia_api_key() gibt str ODER None zurück.
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS: CPXCredentials
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class CPXCredentials:
    """CPX (Cint Panel Exchange) API Credentials.

    WARUM @dataclass (nicht dict oder namedtuple)?
      → Typsicherheit: app_id MUSS str sein (mypy findet Typ-Fehler).
      → IDE-Autovervollständigung: creds.app_id (nicht creds["app_id"]).
      → Immutable: Werte können nicht nachträglich geändert werden (sicherer).
      → Repräsentation: print(creds) → CPXCredentials(app_id='...', ...).
      → Gleichheit: creds1 == creds2 → vergleicht alle Felder.

    WARUM 4 Felder?
      → CPX API benötigt genau diese 4 Parameter:
        - app_id: Identifiziert die App (HeyPiggy).
        - ext_user_id: Identifiziert den User (user_id aus HeyPiggy).
        - secure_hash: Sicherheits-Hash (verhindert Manipulation).
        - email: E-Mail des Users (für Tracking/Compensation).
      → ALLE 4 sind required (keine Optionals).
      → WARUM required? Ohne secure_hash → API-Call wird abgelehnt.

    WARUM nicht frozen=True?
      → frozen=True macht das Objekt komplett immutable (auch keine Mutation).
      → Wir verwenden frozen=False (Standard) → einfacher zu erstellen.
      → WARUM? CPXCredentials wird nur gelesen (nicht modifiziert).
      → Sicherheit durch Konvention (nicht durch Enforcement).

    VERWENDUNG:
        creds = CPXCredentials(
            app_id="12345",
            ext_user_id="2525530",
            secure_hash="abc123...",
            email="user@example.com"
        )
        url = f"https://live-api.cpx-research.com/api/...?app_id={creds.app_id}"
    """

    # app_id: CPX App-Identifier.
    # WARUM str? CPX gibt app_id als String zurück (nicht Integer).
    # Beispiel: "12345" (nicht 12345).
    app_id: str

    # ext_user_id: Externe User-ID (HeyPiggy user_id).
    # WARUM str? HeyPiggy user_id ist ein String (z.B. "2525530").
    # WARUM ext_user_id (nicht user_id)? CPX API Parameter-Name.
    ext_user_id: str

    # secure_hash: Sicherheits-Hash für API-Calls.
    # WARUM str? Hash ist ein hexadezimaler String.
    # WARUM required? Ohne secure_hash → CPX API gibt "Unauthorized" zurück.
    secure_hash: str

    # email: E-Mail-Adresse des Users.
    # WARUM str? E-Mail ist ein String.
    # WARUM required? CPX verwendet E-Mail für Compensation-Tracking.
    email: str


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION: MissingSecretError
# ═══════════════════════════════════════════════════════════════════════════════
class MissingSecretError(RuntimeError):
    """Geworfen wenn ein required Runtime-Secret nicht konfiguriert ist.

    WARUM RuntimeError (nicht ValueError oder KeyError)?
      → RuntimeError = "System ist nicht richtig konfiguriert".
      → ValueError = "Ungültiger Wert" (hier fehlt der Wert komplett).
      → KeyError = "Key nicht im Dict" (zu spezifisch, hier fehlt Secret).
      → RuntimeError ist die passendste Exception für Konfigurations-Fehler.

    WARUM eigene Klasse (nicht generischer RuntimeError)?
      → Aufrufer können "except MissingSecretError" fangen (spezifisch).
      → Generischer RuntimeError würde ALLE RuntimeErrors fangen (zu breit).
      → Klare Semantik: "Dieser Fehler = fehlendes Secret".

    VERWENDUNG:
        try:
            email = SecretsClient.get_google_email()
        except MissingSecretError as e:
            print(f"Bitte konfiguriere: {e}")
            # → "Missing required secret: GOOGLE_EMAIL (google.email)"
    """

    pass  # Keine Extra-Methoden nötig (vererbt von RuntimeError).


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: SecretsClient
# ═══════════════════════════════════════════════════════════════════════════════
class SecretsClient:
    """Singleton für Runtime-Credential-Resolution.

    WARUM Singleton (nicht Funktionen)?
      → Zustand: config.yaml wird einmal geladen und zwischengespeichert.
      → Wiederverwendung: Mehrere get_google_email() Aufrufe → kein Reload.
      → Konsistenz: Gleiche Config für alle Aufrufe in einer Session.
      → WARUM nicht @singleton Decorator? __new__ ist Python-Standard.

    WARUM __new__ (nicht __init__)?
      → __new__ kontrolliert die OBJEKT-ERSTELLUNG (vor __init__).
      → Wir prüfen _instance: Wenn None → erstelle neu, sonst gib existierendes zurück.
      → __init__ würde BEI JEDEM Aufruf ausgeführt → _load_config() mehrfach.
      → __new__ + _instance Pattern = echtes Singleton (eine Instanz pro Prozess).

    WARUM _config als Instanz-Attribut (nicht Klassen-Attribut)?
      → Klassen-Attribute sind global (alle Instanzen teilen sie).
      → Instanz-Attribute sind pro Objekt (hier: eine Instanz = Singleton).
      → In der Praxis: Kein Unterschied (Singleton = eine Instanz).
      → Aber: Instanz-Attribute sind sauberer (keine Klassen-Pollution).

    WARUM _config_path als Klassen-Attribut?
      → Der Pfad ist GLOBAL (nicht pro Instanz).
      → Alle Instanzen (theoretisch) verwenden denselben Pfad.
      → Path.home() / ".stealth" / "config.yaml" = Standardpfad.
      → WARUM nicht konfigurierbar? YAGNI. Wenn nötig → später erweitern.

    WARUM yaml.safe_load()?
      → yaml.safe_load() ist sicherer als yaml.load() (kein Code-Execution).
      → yaml.load() kann beliebige Python-Objekte deserialisieren (unsicher!).
      → yaml.safe_load() erlaubt nur primitive Typen (Dict, List, str, int, etc.).
      → WARUM or {}? Wenn config.yaml leer ist → yaml.safe_load gibt None zurück.
        → None or {} → {} (leeres Dictionary, sicher).

    WARUM try/except beim Laden?
      → Datei könnte fehlen (FileNotFoundError).
      → Datei könnte ungültiges YAML sein (yaml.YAMLError).
      → Datei könnte keine Leserechte haben (PermissionError).
      → Ohne try/except → Crash beim ersten Zugriff.
      → Mit try/except → config bleibt {} → _required() wirft MissingSecretError.
      → WARUM nicht loggen? Dies ist ein Low-Level-Modul. Logging = Higher-Level.

    RESOLUTION ORDER (in _required() implementiert):
      1. os.getenv(env_name) → Umgebungsvariable.
      2. _config_value(config_key) → Wert aus config.yaml (dotted key).
      3. MissingSecretError → Wenn beides fehlt.

    WARUM Resolution Order?
      → Env-Vars haben höchste Priorität (12-Factor App).
      → config.yaml ist Fallback für lokale Entwicklung.
      → Fehlendes Secret = klarer Fehler (nicht silently None zurückgeben).

    WARUM _config_value() mit dotted keys?
      → config.yaml ist verschachtelt:
        google:
          email: "..."
        cpx:
          app_id: "..."
      → "google.email" → gehe in Dict["google"], dann ["email"].
      → "cpx.app_id" → gehe in Dict["cpx"], dann ["app_id"].
      → WARUM Dots? Konvention (ähnlich zu Python-Imports, Django-Settings).
      → WARUM nicht ["google"]["email"]? Dotted-String ist einfacher zu übergeben.

    WARUM str(value) in _required()?
      → os.getenv gibt str zurück.
      → yaml.safe_load gibt int für Zahlen (z.B. app_id: 12345 → int).
      → CPXCredentials erwartet str für ALLE Felder.
      → str(value) konvertiert int zu str (z.B. 12345 → "12345").
      → WARUM nicht int()? Wenn Wert ein String ist → str("12345") = "12345" (OK).

    WARUM get_nvidia_api_key() Optional[str]?
      → NVIDIA_API_KEY ist optional (nicht jeder braucht NIM).
      → Wenn None → Aufrufer kann entscheiden (Fallback zu anderem Modell).
      → WARUM nicht required()? Nicht jeder Use-Case braucht NVIDIA NIM.

    WARUM require_nvidia_api_key() str?
      → Wenn NVIDIA NIM ZWINGEND benötigt wird → klare Fehlermeldung.
      → get_ → Optional (safe), require_ → str (fail-fast).
      → WARUM zwei Methoden? Flexibilität: manchmal optional, manchmal required.

    THREAD-SICHERHEIT:
      → NICHT thread-safe während Initialisierung.
      → __new__ prüft _instance, aber Race Condition möglich.
      → In der Praxis: Ein Prozess, ein Thread für SecretsClient.
      → WARUNGen: Kein Problem für unseren Use-Case (single-threaded API).
    """

    # _instance: Die Singleton-Instanz (None = noch nicht erstellt).
    # WARUM Klassen-Attribut? Wird von __new__ gelesen (Instanz existiert noch nicht).
    _instance = None

    # _config_path: Pfad zur Konfigurationsdatei.
    # WARUM Path.home() / ".stealth" / "config.yaml"?
    #   - Path.home() = Home-Verzeichnis des Users (/Users/simoneschulze).
    #   - .stealth/ = verstecktes Verzeichnis (nicht im Finder sichtbar).
    #   - config.yaml = YAML-Format (lesbar, Kommentare möglich).
    # WARUNGen nicht konfigurierbar? Standardpfad ist ausreichend.
    _config_path = Path.home() / ".stealth" / "config.yaml"

    def __new__(cls):
        """Erstelle oder gib die Singleton-Instanz zurück.

        WARUM __new__ statt __init__?
          → __new__ kontrolliert Objekt-ERSTELLUNG (vor __init__).
          → Wir prüfen _instance: Wenn None → super().__new__() → speichere in _instance.
          → Wenn _instance existiert → gib existierendes Objekt zurück.
          → __init__ würde bei JEDEM SecretsClient() Aufruf ausgeführt.

        WARUM super().__new__(cls)?
          → Erstellt ein neues Objekt der Klasse (ohne __init__ aufzurufen).
          → object.__new__(cls) = Basis-Objekt (keine Attribute).
          → Wir setzen _instance im Anschluss.

        WARUM _load_config() hier?
          → Config wird beim ERSTEN Zugriff geladen (Lazy-Loading).
          → Nicht beim Import → vermeidet File-I/O während des Imports.
          → Nicht beim Modul-Start → vermeidet Fehler wenn config.yaml fehlt.

        Returns:
            SecretsClient: Die Singleton-Instanz.

        Example:
            s1 = SecretsClient()
            s2 = SecretsClient()
            assert s1 is s2  # Gleiches Objekt!
        """
        # Prüfe ob Instanz bereits existiert.
        # WARUM if cls._instance is None? Wenn bereits erstellt → nicht neu erstellen.
        if cls._instance is None:
            # Erstelle neue Instanz via object.__new__().
            # WARUM super()? Ruft object.__new__() auf (Basis-Objekt erstellen).
            cls._instance = super().__new__(cls)

            # Lade Konfiguration (einmalig).
            # WARUM hier? Lazy-Loading: Config wird erst beim ersten Zugriff geladen.
            cls._instance._load_config()

        # Gib die Singleton-Instanz zurück (existierende oder neue).
        return cls._instance

    def _load_config(self):
        """Lade ~/.stealth/config.yaml in self._config.

        ABLAUF:
          1. Initialisiere self._config mit leerem Dict {}.
          2. Prüfe ob _config_path existiert.
          3. Wenn ja → öffne Datei und parse YAML.
          4. Wenn yaml.safe_load() None zurückgibt → or {} (leeres Dict).
          5. Bei Fehler (FileNotFound, YAMLError, PermissionError) → {}.

        WARUM self._config = {} zuerst?
          → Wenn die Datei fehlt oder ungültig ist → _config bleibt {}.
          → _required() wird dann MissingSecretError werfen (nicht KeyError).

        WARUM yaml.safe_load() (nicht yaml.load())?
          → yaml.load() kann beliebige Python-Objekte laden (Code-Execution!).
          → yaml.safe_load() erlaubt nur primitive Typen (sicher).
          → WARUNGen "safe" im Namen? Explizit sicher.

        WARUNGen or {}?
          → yaml.safe_load() von leerer Datei gibt None zurück.
          → None or {} → {} (leeres Dictionary).
          → Sicherer als None (keine Attribute-Errors).

        WARUM try/except?
          → FileNotFoundError: config.yaml existiert nicht (normal bei erstem Start).
          → yaml.YAMLError: Ungültiges YAML (Syntax-Fehler).
          → PermissionError: Keine Leserechte.
          → OSError: Allgemeiner I/O-Fehler.
          → Ohne try/except → Crash beim ersten Zugriff.
          → Mit try/except → self._config = {} → fehlende Secrets werden später gemeldet.

        WARUM keine Log-Meldung?
          → Dies ist ein Low-Level-Modul. Keine Side-Effects (kein Logging).
          → MissingSecretError im Aufrufer ist informativer als Log-Meldung hier.
        """
        # Initialisiere mit leerem Dictionary.
        # WARUM? Wenn alles schiefgeht → _config ist {} (nicht None).
        self._config = {}

        try:
            # Prüfe ob Konfigurationsdatei existiert.
            # WARUM .exists()? Wenn nicht → keine Notwendigkeit yaml zu importieren.
            if self._config_path.exists():
                # Öffne Datei im Text-Modus ("r" = Read).
                # WARUM with open()? Kontext-Manager: Datei wird automatisch geschlossen.
                # WARUM "r"? Read-Modus (Standard, nur lesen).
                with open(self._config_path) as f:
                    # Parse YAML (sicher).
                    # WARUM yaml.safe_load()? Siehe oben (sicherer als yaml.load()).
                    # WARUNGen or {}? None-Fallback für leere Datei.
                    self._config = yaml.safe_load(f) or {}
        except Exception:
            # Fehler beim Laden: Datei nicht da, ungültiges YAML, Permission-Denied.
            # WARUM Exception (nicht spezifisch)? Fängt ALLE Fehler ab.
            # FileNotFoundError, yaml.YAMLError, PermissionError, UnicodeDecodeError, etc.
            # WARUM pass? self._config bleibt {} → MissingSecretError wird später gemeldet.
            pass

    @staticmethod
    def get_nvidia_api_key() -> str | None:
        """Hole NVIDIA_API_KEY aus Umgebungsvariable.

        WARUM @staticmethod (nicht @classmethod)?
          → Kein Zugriff auf self oder cls nötig (nur os.getenv).
          → @staticmethod ist sauberer wenn keine Instanz/Class-Info gebraucht wird.

        WARUM Optional[str]?
          → NVIDIA_API_KEY ist optional (nicht jeder braucht NIM).
          → Wenn None → Aufrufer kann entscheiden (anderes Modell, Fehler werfen).

        WARUM os.getenv() (nicht os.environ)?
          → os.getenv("X") gibt None zurück wenn X fehlt (fail-soft).
          → os.environ["X"] wirft KeyError (fail-hard).
          → Optional[str] erwartet None bei Fehlen → os.getenv passt.

        Returns:
            str: NVIDIA API Key (z.B. "nvapi-...").
            None: Wenn NVIDIA_API_KEY nicht gesetzt.

        Example:
            key = SecretsClient.get_nvidia_api_key()
            if key:
                headers = {"Authorization": f"Bearer {key}"}
        """
        return os.getenv("NVIDIA_API_KEY")

    @classmethod
    def require_nvidia_api_key(cls) -> str:
        """Hole NVIDIA_API_KEY oder wirf MissingSecretError.

        WARUM @classmethod (nicht @staticmethod)?
          → Wir brauchen cls für get_nvidia_api_key() Aufruf.
          → @classmethod hat Zugriff auf die Klasse (für Methoden-Aufrufe).

        WARUM str (nicht Optional[str])?
          → Diese Methode garantiert einen String zurück (oder wirft Exception).
          → Kein None-Handling im Aufrufer nötig.
          → Fail-fast: Wenn Key fehlt → sofort Fehler (nicht späterer Null-Error).

        WARUM MissingSecretError?
          → Klare Fehlermeldung: "Missing required secret: NVIDIA_API_KEY".
          → Aufrufer kann except MissingSecretError fangen.

        Returns:
            str: NVIDIA API Key.

        Raises:
            MissingSecretError: Wenn NVIDIA_API_KEY nicht gesetzt.

        Example:
            try:
                key = SecretsClient.require_nvidia_api_key()
            except MissingSecretError:
                print("Bitte setze NVIDIA_API_KEY")
        """
        # Hole Key via get_nvidia_api_key() (fail-soft, gibt None zurück).
        value = cls.get_nvidia_api_key()

        # Prüfe ob Key vorhanden.
        # WARUM if not value? None und leerer String "" sind beide "falsy".
        if not value:
            # Key fehlt → wirf MissingSecretError.
            # WARUM keine config_key? NVIDIA_API_KEY kommt NUR aus Env-Vars.
            raise MissingSecretError("Missing required secret: NVIDIA_API_KEY")

        return value

    @classmethod
    def get_google_email(cls) -> str:
        """Hole konfigurierte Google Login E-Mail.

        ABLAUF:
          1. Rufe _required("GOOGLE_EMAIL", "google.email") auf.
          2. Resolution Order: Env-Var → config.yaml → MissingSecretError.

        WARUM "google.email" als config_key?
          → config.yaml Struktur:
            google:
              email: "zukunftsorientierte.energie@gmail.com"
          → "google.email" → Dict["google"]["email"].
          → Dotted-Key Konvention für verschachtelte YAML-Strukturen.

        WARUM str Return-Type?
          → E-Mail ist ein String (kein Optional).
          → Fehlende E-Mail = MissingSecretError (nicht None).

        Returns:
            str: Google E-Mail-Adresse.

        Raises:
            MissingSecretError: Wenn GOOGLE_EMAIL nicht konfiguriert.

        Example:
            email = SecretsClient.get_google_email()
            # → "zukunftsorientierte.energie@gmail.com"
        """
        # Delegiere an _required() mit env_name und config_key.
        # WARUM _required()? Zentrale Resolution-Logik (nicht dupliziert).
        return cls._required("GOOGLE_EMAIL", "google.email")

    @classmethod
    def get_cpx_credentials(cls) -> CPXCredentials:
        """Hole komplette CPX Credentials als CPXCredentials Objekt.

        ABLAUF:
          1. Rufe _required() für jedes Feld auf:
             - CPX_APP_ID (cpx.app_id)
             - CPX_EXT_USER_ID (cpx.ext_user_id)
             - CPX_SECURE_HASH (cpx.secure_hash)
             - CPX_EMAIL (cpx.email)
          2. Erstelle CPXCredentials mit den Werten.

        WARUM CPXCredentials (nicht Dict)?
          → Typsicherheit: app_id MUSS str sein (mypy findet Fehler).
          → IDE-Autovervollständigung: creds.app_id (nicht creds["app_id"]).
          → Weniger Fehler: Kein Tippfehler bei Keys (creds.ap_id → Error).

        WARUM 4 separate _required() Aufrufe?
          → Jedes Feld hat eigenen env_name und config_key.
          → Wenn ein Feld fehlt → spezifische Fehlermeldung (nicht "irgendwas fehlt").
          → Beispiel: "Missing required secret: CPX_APP_ID (cpx.app_id)".

        Returns:
            CPXCredentials: Komplettes Credentials-Objekt.

        Raises:
            MissingSecretError: Wenn EINES der 4 Felder fehlt.

        Example:
            creds = SecretsClient.get_cpx_credentials()
            url = (f"https://live-api.cpx-research.com/api/get-survey-details.php"
                   f"?app_id={creds.app_id}&ext_user_id={creds.ext_user_id}")
        """
        # Erstelle CPXCredentials mit 4 _required() Aufrufen.
        # WARUM einzeilig? CPXCredentials ist ein @dataclass → Konstruktor mit Named Args.
        return CPXCredentials(
            # CPX App ID (identifiziert die App).
            app_id=cls._required("CPX_APP_ID", "cpx.app_id"),
            # Externe User-ID (HeyPiggy user_id).
            ext_user_id=cls._required("CPX_EXT_USER_ID", "cpx.ext_user_id"),
            # Sicherheits-Hash (verhindert Manipulation).
            secure_hash=cls._required("CPX_SECURE_HASH", "cpx.secure_hash"),
            # E-Mail für CPX API.
            email=cls._required("CPX_EMAIL", "cpx.email"),
        )

    @classmethod
    def _required(cls, env_name: str, config_key: str) -> str:
        """Löse ein required Secret auf (Resolution Order: env → config → error).

        ABLAUF:
          1. Versuche os.getenv(env_name) → Umgebungsvariable.
          2. Wenn None → versuche _config_value(config_key) → config.yaml.
          3. Wenn immer noch None/Empty → wirf MissingSecretError.
          4. Konvertiere zu str (für yaml-safe_load int Werte).
          5. Gib Wert zurück.

        WARUM Resolution Order?
          → 12-Factor App: Config via Env-Vars (höchste Priorität).
          → Env-Vars sind transiente (Docker, CI/CD, Cloud-Run).
          → config.yaml ist persistent (lokale Entwicklung).
          → Docker-Container überschreibt lokale Config → flexibler.

        WARUM str(value)?
          → os.getenv gibt str zurück.
          → yaml.safe_load gibt int für Zahlen (z.B. app_id: 12345 → int).
          → CPXCredentials erwartet str für ALLE Felder.
          → str(12345) = "12345" (int zu str Konvertierung).
          → str("test") = "test" (String bleibt String).

        WARUM MissingSecretError (nicht None zurückgeben)?
          → Fail-fast: Fehlendes Secret = klarer Fehler (nicht späterer Null-Error).
          → Klare Fehlermeldung: "Missing required secret: X (y.z)".
          → Aufrufer kann except MissingSecretError fangen (spezifisch).
          → WARUM "X (y.z)" im Text? Env-Name UND Config-Key für schnelles Debugging.

        Args:
            env_name: Name der Umgebungsvariable (z.B. "GOOGLE_EMAIL").
            config_key: Dotted-Key in config.yaml (z.B. "google.email").

        Returns:
            str: Aufgelöster Wert (konvertiert zu String).

        Raises:
            MissingSecretError: Wenn Wert weder in Env noch in Config gefunden.

        Example:
            value = SecretsClient._required("GOOGLE_EMAIL", "google.email")
            # Resolution:
            # 1. os.getenv("GOOGLE_EMAIL") → None?
            # 2. _config_value("google.email") → "..."?
            # 3. Nichts gefunden → MissingSecretError
        """
        # SCHRITT 1: Versuche Umgebungsvariable.
        # WARUM os.getenv()? Fail-soft: Gibt None zurück wenn nicht gesetzt.
        value = os.getenv(env_name)

        # WARUM nicht "if value is None"? Auch leerer String "" ist ungültig.
        # "if value" prüft: None = False, "" = False, "test" = True.
        if not value:
            # SCHRITT 2: Versuche config.yaml.
            # _config_value() gibt None zurück wenn Key nicht gefunden.
            value = cls._config_value(config_key)

        # SCHRITT 3: Prüfe ob Wert gefunden.
        # WARUM erneute Prüfung? Nach _config_value() könnte value immer noch None sein.
        if value:
            # Wert gefunden! Konvertiere zu str und gib zurück.
            # WARUM str()? Sicherheit: yaml-safe_load gibt int für Zahlen.
            return str(value)

        # SCHRITT 4: Nichts gefunden → wirf MissingSecretError.
        # Klare Fehlermeldung mit env_name und config_key.
        raise MissingSecretError(f"Missing required secret: {env_name} ({config_key})")

    @classmethod
    def _config_value(cls, dotted_key: str) -> str | None:
        """Löse dotted key in ~/.stealth/config.yaml auf.

        ABLAUF:
          1. Hole _config (geladene YAML-Daten).
          2. Splitte dotted_key bei '.' → Liste von Parts.
          3. Für jeden Part:
             a. Prüfe ob current ein Dict ist.
             b. Prüfe ob Part in current existiert.
             c. Wenn nein → gib None zurück.
             d. current = current[Part] (gehe tiefer).
          4. Gib finalen Wert zurück.

        WARUM dotted keys?
          → Verschachtelte YAML-Struktur:
            google:
              email: "..."
            cpx:
              app_id: "..."
          → "google.email" → config["google"]["email"].
          → "cpx.app_id" → config["cpx"]["app_id"].
          → WARUM nicht ["google"]["email"]? Dotted-String ist einfacher zu übergeben.

        WARUM isinstance(current, dict) Prüfung?
          → Wenn YAML-Struktur flach ist (z.B. email: "..." statt google: email: "...").
          → "google.email" → config["google"] könnte ein String sein (nicht Dict).
          → String["email"] → TypeError → wir prüfen vorher.
          → WARUNGen None? Fail-soft: Wenn Struktur nicht erwartet → None.

        WARUM Optional[str]?
          → Gibt None zurück wenn Key nicht gefunden (fail-soft).
          → _required() prüft "if value" → None = falsy → MissingSecretError.

        WARUNGen str(current) am Ende nicht?
          → Wir geben den Rohtyp zurück (int, str, bool).
          → _required() macht str(value) → zentrale Konvertierung.

        Args:
            dotted_key: Dotted-Key Pfad (z.B. "google.email", "cpx.app_id").

        Returns:
            Optional[str]: Wert aus config.yaml oder None wenn nicht gefunden.
            (Tatsächlich: Optional[Any] da Typ nicht geprüft wird).

        Example:
            # config.yaml:
            #   google:
            #     email: "test@example.com"
            value = SecretsClient._config_value("google.email")
            # value = "test@example.com"

            value = SecretsClient._config_value("nonexistent.key")
            # value = None
        """
        # Hole die geladene Konfiguration.
        # WARUM cls()._config? _config ist Instanz-Attribut (Singleton).
        # cls() erstellt/ruft Singleton auf → gibt Instanz zurück → . _config.
        config = cls()._config

        # Aktuelles Dict (wir gehen tiefer in die Verschachtelung).
        current = config

        # Iteriere über alle Parts des dotted keys.
        # WARUM for-Schleife? Verschachtelung kann beliebig tief sein.
        # Beispiel: "a.b.c.d" → 4 Ebenen.
        for part in dotted_key.split("."):
            # Prüfe ob current ein Dictionary ist.
            # WARUM? Wenn current ein String/int ist → kein [part] Zugriff möglich.
            if not isinstance(current, dict) or part not in current:
                # Key nicht gefunden oder falsche Struktur → None.
                return None

            # Gehe eine Ebene tiefer.
            current = current[part]

        # Gib finalen Wert zurück.
        # WARUM Optional[str]? Eigentlich Optional[Any], aber str ist sicherer.
        # _required() macht str(value) → zentrale Konvertierung.
        return current


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL: _secrets Singleton
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM Modul-Level? Bequemer Zugriff ohne Klassen-Name.
# Beispiel: _secrets.get_google_email() (statt SecretsClient().get_google_email()).
# WARUNGen SecretsClient()? Gleiches Objekt (Singleton).
_secrets = SecretsClient()


# ═══════════════════════════════════════════════════════════════════════════════
# FUNKTION: get_secrets()
# ═══════════════════════════════════════════════════════════════════════════════
def get_secrets() -> SecretsClient:
    """Gib die SecretsClient Singleton-Instanz zurück.

    WARUM diese Funktion (nicht direkt _secrets)?
      → Kapselung: _secrets ist private (führt mit _ an).
      → get_secrets() ist die öffentliche API.
      → Später können wir eine andere Implementierung einsetzen
        (z.B. get_secrets() → SecretsClientV2()) ohne Clients zu brechen.

    WARUNGen _secrets zurückgeben?
      → _secrets ist bereits initialisiert (beim Modul-Import).
      → Kein Neuerstellen nötig.
      → Lazy-Loading: Config wurde beim ersten Zugriff geladen.

    Returns:
        SecretsClient: Die Singleton-Instanz.

    Example:
        secrets = get_secrets()
        email = secrets.get_google_email()
    """
    return _secrets

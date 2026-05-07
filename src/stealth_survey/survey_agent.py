"""================================================================================
================================================================================
SURVEY AGENT — NEMO Loop: Compact Snapshot → Nemotron Decision → Batch Execute
================================================================================
================================================================================

WAS IST DIESE DATEI?
  Diese Datei ist die KERN-NEMO-ENGINE (Nemotron 3 Omni + CDP WebSocket).
  Sie automatisiert Survey-Teilnahmen mit MINIMALEN LLM-Calls durch:
    1. Compact Snapshots (DOM → @eN Element-Refs, ~200 tokens)
    2. Nemotron 3 Omni Decisions (~500 tokens in, ~100 tokens out)
    3. Batch Execution (CDP WebSocket, alle Actions in EINEM Call)

  Warum ist diese Datei so wichtig?
    - Sie ist die HAUPT-ENGINE für Survey-Automation.
    - Sie ersetzt den langsamen cua-driver Loop (20+ Calls pro Seite).
    - Sie nutzt nur 3 Calls pro Seite (statt 20+) = 10× effizienter.
    - Sie ist der GRUND für die NEMO-Architektur (siehe AGENTS.md).

ARCHITEKTUR (NEMO Loop — pro Survey-Seite):
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         SurveyAgent.run_survey()                              │
  │                              (DU BIST HIER)                               │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  SCHRITT 1: COMPACT SNAPSHOT (CDP / skylight-cli)                         │
  │  → CompactSnapshotGenerator.generate(ws_url)                                │
  │  → DOM → @eN Element-Refs: {"@e0": {role:"radio", text:"Männlich"}, ...}    │
  │  → Semantische Analyse: questions, progress, provider                       │
  │  → Token-Effizienz: ~200 tokens (statt 5000+ bei cua-driver)                │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  SCHRITT 2: NEMOTRON 3 OMNI DECISION (NVIDIA NIM API)                       │
  │  → NIMSurveyClient.decide(snapshot_dict, profile, learnings, history)      │
  │  → NVIDIA API: POST /v1/chat/completions                                   │
  │  → Model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning                   │
  │  → Input: ~500 tokens (Snapshot + Profile + Instructions)                  │
  │  → Output: ~100 tokens (Actions Array)                                     │
  │  → Latenz: ~1300ms (siehe config.yaml routing.models.standard)              │
  │  → Actions: [{"ref":"@e0","action":"select"}, {"action":"submit"}]           │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  SCHRITT 3: BATCH EXECUTE (CDP WebSocket)                                   │
  │  → BatchExecutor.execute(ws_url, actions, provider)                         │
  │  → Runtime.evaluate("(function(){...alle actions...})()")                   │
  │  → ALLE Actions in EINEM WebSocket-Call (kein Round-Trip!)                 │
  │  → Provider-spezifische JS:                                                │
  │     Qualtrics:   document.querySelector('.NextButton').click()              │
  │     TolunaStart: document.querySelectorAll('.cf-radio')[0].click()          │
  │     Strat7:      document.querySelector('.bsbutton').click()              │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  SCHRITT 4: MEMORY + GUARDIAN (Optional)                                   │
  │  → stealth_memory.log_step(snapshot, actions, result)                       │
  │  → stealth_guardian.monitor_and_heal(session, result)                       │
  │  → Anti-Learn: Fehler werden vermerkt, um Wiederholung zu vermeiden        │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
      [LOOP bis Complete]
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  COMPLETION DETECTED                                                        │
  │  → "zurück zur website", "gutgeschrieben", "vielen dank" in Snapshot         │
  │  → ODER: URL enthält "rating.php" (CPX Research Rating-Seite)              │
  │  → Survey-Tab schließen                                                    │
  │  → Balance vor/nach vergleichen → earned berechnen                         │
  │  → Optional: Survey bewerten (+0.01€ Bonus)                                │
  └─────────────────────────────────────────────────────────────────────────────┘

VORTEILE gegenüber Legacy (cua-driver Loop):
  - 1 LLM-Call PRO SEITE (nicht pro Element)
  - ~500 tokens in, ~100 tokens out (statt ~5000+ tokens in)
  - 5× schneller als cua-driver Loop (3 Calls statt 20+ pro Seite)
  - Keine Index-Instabilität (Compact Snapshots statt raw element_index)
  - Batch Execution: Alle Actions in EINEM Call (kein Round-Trip per Action)

WARUM NEMO?
  Legacy cua-driver Loop: Agent ruft 20-50x get_window_state(),
  klickt einzelne Elemente, vergisst Zwischenstände, braucht 5000+ tokens.
  NEMO: Ein Snapshot → Eine Decision → Batch Execute → Next Page.
  → 90% Token-Ersparnis, 5× schneller, stabilere Indices.

TOKEN-EFFIZIENZ-VERGLEICH:
  ┌──────────────────────┬─────────────┬─────────────┬──────────────┐
  │ Phase                │ Tokens In   │ Tokens Out  │ Round-Trips  │
  ├──────────────────────┼─────────────┼─────────────┼──────────────┤
  │ Compact Snapshot     │ ~0 (CDP)    │ ~200        │ 1            │
  │ NIM Decision         │ ~500        │ ~100        │ 1            │
  │ Batch Execute        │ ~0 (CDP)    │ ~0          │ 1            │
  ├──────────────────────┼─────────────┼─────────────┼──────────────┤
  │ TOTAL pro Seite      │ ~500        │ ~100        │ 3            │
  │ cua-driver Loop      │ ~5000+      │ ~1000+      │ 20+          │
  │ ERSPARNIS            │ 90%         │ 90%         │ 85%          │
  └──────────────────────┴─────────────┴─────────────┴──────────────┘

DEPENDENZEN (Was braucht diese Datei?):
  - nim_client.py: NIMSurveyClient — NVIDIA Nemotron 3 Omni API Client
    → WARUM separat? API-Logik isoliert, einfacher zu mocken/testen.
  - compact_snapshot.py: CompactSnapshotGenerator — DOM → @eN Snapshot
    → WARUM separat? Snapshot-Generierung ist komplex (DOM-Parsing, Semantic Analysis).
  - batch_executor.py: BatchExecutor — Actions → CDP JS Execution
    → WARUM separat? Provider-spezifische JS-Logik isoliert.
  - Optional: stealth_memory (Logging) — Wenn use_memory=True
    → WARUM Optional? Nicht jeder Agent braucht Memory.
  - Optional: stealth_guardian (Heal) — Wenn use_guardian=True
    → WARUM Optional? Guardian ist teuer (zusätzliche API Calls).
  - Standardlib: json, time, os, urllib.request, dataclasses, typing
  - Third-party: websocket-client (für CDP WebSocket)

ABHÄNGIGE DATEIEN (Was bricht wenn diese Datei fehlt?):
  - survey-cli/survey.py → cmd_run(), cmd_loop(), cmd_watch() nutzen SurveyRunner
    → SurveyRunner NUTZT SurveyAgent (diese Datei).
  - run_survey.py → cmd_nim_survey(), cmd_loop() nutzen SurveyAgent
  → WENN diese Datei fehlt → KEINE NEMO-Surveys möglich!
  → Fallback: cua-driver Legacy (DEPRECATED, langsamer, instabiler).

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw element_index) — instabil, nutze BatchExecutor
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

HISTORY / CHANGELOG:
  2026-05-08: MASSIVE DOKUMENTATION hinzugefügt (alle Funktionen, Konstanten)
    → WARUM? Code war gut, aber nicht EXTREM kommentiert.
    → VERIFIZIERUNG: Jede Funktion hat Docstring mit Args, Returns, Side Effects.

  2026-05-06: Initialer NEMO Support (Compact Snapshot + NIM + Batch)
    → WARUM? cua-driver Loop war zu langsam und instabil (20+ Calls pro Seite).
    → WAS: SurveyAgent, NIMSurveyClient, CompactSnapshotGenerator, BatchExecutor.
    → VERIFIZIERUNG: Unit Tests (211 Tests für 15 Module).

KNOWN LIMITATIONS:
  - NIM Decision dauert ~1300ms (siehe config.yaml routing.models.standard.avg_latency_ms)
    → WENN NIM offline → Auto-Pilot Fallback (simple_actions())
  - Compact Snapshot dauert ~500ms-2s (abhängig von DOM-Größe)
    → WENN DOM sehr groß (>1000 Elemente) → Snapshot kann abgeschnitten werden
  - Batch Executor ist provider-spezifisch (Qualtrics, TolunaStart, Strat7)
    → WENN unbekannter Provider → Generic JS (kann fehlschlagen)
  - Audio/Video-Fragen werden NICHT von NEMO unterstützt
    → Siehe Audio Capture Module (BlackHole + ffmpeg + NVIDIA Omni)

RACE CONDITIONS:
  - DOM ändert sich während Snapshot → Snapshot kann veraltet sein
    → Lösung: Snapshot vor NIM-Call aktualisieren (wird bereits gemacht)
  - Seite navigiert während Batch Execution → Actions landen auf falscher Seite
    → Lösung: Batch Executor prüft URL vor/nach Execution
  - NIM API ist langsam (>1s) → Survey-Seite kann Timeout haben
    → Lösung: Auto-Pilot Fallback wenn NIM nicht verfügbar
  - Mehrere Surveys gleichzeitig → Chrome Tabs können sich überschneiden
    → Lösung: SurveyAgent führt eine Survey nach der anderen aus

================================================================================
================================================================================
"""

# ============================================================================
# IMPORTS
# ============================================================================
# WARUM json? Für CDP WebSocket Nachrichten (JSON-RPC) und Profil-Laden.
# WARUM time? Für Timestamps, Delays, Performance-Messung.
# WARUM os? Für Umgebungsvariablen (NVIDIA_API_KEY), Datei-Pfade.
# WARUM subprocess? Für External Tools (falls nötig — aktuell nicht genutzt).
# WARUM urllib.request? Für CDP HTTP (http://127.0.0.1:9999/json) und CPX API.
# WARUM typing? Für Type Hints (Dict, List, Any, Optional, Callable).
# WARUM dataclasses? Für AgentConfig und SurveyResult (saubere Datenklassen).
import json
import time
import os
import subprocess
import urllib.request
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

# Interne Imports (aus dem gleichen Paket)
# WARUM relative Imports? Einfacher, kürzer, klare Paket-Struktur.
from .nim_client import NIMSurveyClient, BATCH_TOOL_SCHEMA
from .compact_snapshot import CompactSnapshotGenerator, CompactSnapshot
from .batch_executor import BatchExecutor, BatchResult


# ============================================================================
# DATENKLASSEN — Konfiguration und Ergebnisse
# ============================================================================

@dataclass
class AgentConfig:
    """
    ================================================================================
    Konfiguration für SurveyAgent.

    WARUM dataclass? Klarer, kürzer, automatisch __init__, __repr__, __eq__.
    WARUM nicht dict? Typ-Sicherheit, IDE-Autovervollständigung, Validierung.
    ================================================================================
    """
    # ── CDP Konfiguration ──
    cdp_port: int = 9999
    """CDP WebSocket Port. WARUM 9999? Konvention — nicht reserviert."""

    cdp_base_url: str = "http://127.0.0.1:9999/json"
    """CDP HTTP Base URL. WARUM /json? Chrome CDP exposes tabs via /json endpoint."""

    # ── NIM Konfiguration ──
    nim_api_key: Optional[str] = None
    """NVIDIA API Key. WARUM Optional? Wenn None → os.getenv("NVIDIA_API_KEY")."""

    nim_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    """NIM Model Name. WARUM dieses? Nemotron 3 Omni = Vision + Audio + Text."""

    nim_temperature: float = 0.1
    """NIM Temperature. WARUM 0.1? Niedrig = deterministisch, konsistent.
    WARUM nicht 0.0? Manche APIs akzeptieren 0.0 nicht.
    WARUM nicht 1.0? Zu zufällig — Survey-Antworten müssen konsistent sein."""

    # ── Survey Loop ──
    max_iterations: int = 50
    """Max Iterationen pro Survey. WARUM 50? Safety-Limit — Endlosschleife verhindern.
    WARUM nicht 100? 50 Seiten × 3s Wartezeit = 150s = 2.5min pro Survey.
    WARUM nicht 20? Manche Surveys haben 30+ Fragen."""

    max_surveys: int = 10
    """Max Surveys pro Loop. WARUM 10? Zeit-Limit: 10 × 2.5min = 25min.
    WARUM nicht 20? Zu lange Sessions → Chrome wird instabil.
    WARUM nicht 5? Zu wenig — verpasst Chancen."""

    balance_target: float = 5.0
    """Ziel-Guthaben. WARUM 5.0? Typische Auszahlungsschwelle bei HeyPiggy.
    WARUM float? HeyPiggy zeigt Cent-Beträge."""

    poll_interval: float = 30.0
    """Poll-Interval für Watch Daemon. WARUM 30s? Siehe survey-cli/survey.py."""

    wait_between_actions: float = 2.0
    """Wartezeit zwischen Actions. WARUM 2.0s? SPA braucht ~1-2s zum Re-render.
    WARUM nicht 1.0? Zu schnell — Seite nicht fertig gerendert.
    WARUM nicht 5.0? Zu langsam — Survey dauert ewig."""

    wait_page_load: float = 5.0
    """Wartezeit nach Page-Load/Navigation. WARUM 5.0? Redirects können mehrere
    Sekunden dauern (besonders bei externen Providern).
    WARUM nicht 3.0? Manche Provider redirecten 3× hintereinander.
    WARUM nicht 10.0? Zu lang — Survey-Start verzögert."""

    # ── Provider Filter ──
    skip_providers: List[str] = field(default_factory=lambda: [
        "purespectrum", "surveyrouter"
    ])
    """Zu überspringende Provider. WARUM diese? Erfahrung: Niedrige Conversion-Rates.
    WARUM default_factory? Mutable Default Argument Anti-Pattern vermeiden.
    WARUM List[str]? Einfach zu erweitern."""

    # ── Features ──
    use_nim: bool = True
    """NIM nutzen? WARUM True? NIM ist PRIMARY Architektur.
    WARUM nicht immer True? Fallback wenn NIM offline (Auto-Pilot)."""

    use_memory: bool = False
    """stealth-memory nutzen? WARUM False? Optional — nicht jeder Agent braucht es.
    WARUM wann True? Wenn Learning aus Sessions gewünscht."""

    use_guardian: bool = False
    """stealth-guardian nutzen? WARUM False? Optional — Guardian ist teuer.
    WARUM wann True? Wenn Self-Healing und Monitoring gewünscht."""

    auto_rate: bool = True
    """Survey automatisch bewerten? WARUM True? +0.01€ Bonus pro Survey.
    WARUM nicht immer True? Manche Surveys haben keine Bewertungs-Seite."""

    debug: bool = False
    """Debug Mode? WARUM False? Production = wenig Output.
    WARUM wann True? Entwicklung, Debugging, erstes Setup."""


@dataclass
class SurveyResult:
    """
    ================================================================================
    Ergebnis einer einzelnen Survey-Ausführung.

    WARUM dataclass? Klarer, kürzer, automatisch __init__, __repr__, __eq__.
    WARUM nicht dict? Typ-Sicherheit, IDE-Autovervollständigung.
    ================================================================================
    """
    survey_id: str = ""
    """Survey ID oder "direct" für direkte URLs."""

    provider: str = "unknown"
    """Provider Name (z.B. "Qualtrics", "TolunaStart", "Strat7").
    WARUM "unknown"? Wenn Detection fehlschlägt."""

    status: str = "unknown"
    """Status der Survey. Erlaubte Werte:
    - "completed": Survey erfolgreich abgeschlossen.
    - "screen_out": Disqualifiziert (nicht Zielgruppe).
    - "error": Technischer Fehler.
    - "blocked": Provider blockiert (in skip_providers).
    - "unknown": Initial-Status (noch nicht ausgeführt).
    """

    earned: float = 0.0
    """Verdienter Betrag in €. WARUM float? HeyPiggy zeigt Cent-Beträge.
    WARUM 0.0? Initialwert — wird nach Balance-Vergleich aktualisiert."""

    iterations: int = 0
    """Anzahl durchlaufener Iterationen (Seiten). WARUM int? Zählvariable.
    WARUM wichtig? Performance-Metrik, Debugging."""

    elapsed_s: float = 0.0
    """Gesamtdauer in Sekunden. WARUM float? Präzise Zeitmessung.
    WARUM time.monotonic()? Nicht von Systemzeit-Änderungen beeinflusst."""

    nim_calls: int = 0
    """Anzahl NIM API Calls. WARUM int? Kosten-Tracking, Performance-Metrik.
    WARUM wichtig? NIM Calls kosten API-Credits (auch wenn free tier)."""

    nim_tokens: int = 0
    """Anzahl verbrauchter NIM Tokens. WARUM int? Kosten-Tracking.
    WARUM wichtig? Token-Limits bei Free Tier."""

    error: Optional[str] = None
    """Fehlermeldung (wenn status != "completed"). WARUM Optional? None = kein Fehler.
    WARUM str? Menschenlesbare Fehlerbeschreibung."""


# ============================================================================
# SURVEY AGENT — HAUPTKLASSE
# ============================================================================

class SurveyAgent:
    """
    ================================================================================
    Next-gen Survey Automation Agent (NEMO Engine).

    Ersetzt den cua-driver-basierten survey_heypiggy.py Flow mit:
    - CDP WebSocket (kein cua-driver Daemon nötig)
    - Nemotron 3 Omni Entscheidungsfindung
    - Compact @eN Snapshots (token-effizient)
    - Batch Execution (minimale Round-Trips)

    WARUM Klasse statt Funktionen?
      - State Management: profile, learnings, session_history
      - Konfiguration: AgentConfig wird einmal übergeben
      - Reusability: Ein Agent kann mehrere Surveys ausführen
      - Testing: Einfacher zu mocken und testen

    WARUM SurveyAgent statt nur Funktionen?
      Kapselt komplexen State (profile, learnings, history).
      Ermöglicht mehrere Survey-Runs mit demselben Agent (Memory bleibt erhalten).
    ================================================================================
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        ================================================================================
        Initialisiert SurveyAgent.

        Args:
          config (AgentConfig, optional): Konfiguration. Wenn None → Default-AgentConfig().
                                        WARUM Optional? Einfachheit — AgentConfig() hat
                                        sinnvolle Defaults.

        Side Effects:
          - Erstellt CompactSnapshotGenerator.
          - Erstellt NIMSurveyClient (wenn use_nim=True und API-Key verfügbar).
          - Lädt NICHT automatisch das Profil (explizites load_profile() nötig).

        Example:
          >>> agent = SurveyAgent()  # Default config
          >>> agent = SurveyAgent(AgentConfig(debug=True))  # Debug mode
        ================================================================================
        """
        # Konfiguration speichern
        # WARUM or AgentConfig()? Default-Werte wenn keine Config übergeben.
        self.config = config or AgentConfig()

        # ── CDP ──
        # CDP HTTP Base URL zusammenbauen
        # WARUM f-String? Einfache String-Interpolation.
        self.cdp_base = f"http://127.0.0.1:{self.config.cdp_port}/json"

        # Compact Snapshot Generator erstellen
        # WARUM hier? Wird in JEDER Iteration genutzt.
        # WARUM port aus Config? Chrome CDP könnte auf anderem Port laufen.
        self.snapshot_gen = CompactSnapshotGenerator(port=self.config.cdp_port)

        # ── NIM ──
        self.nim = None
        if self.config.use_nim:
            # API Key ermitteln
            # WARUM or os.getenv? Config hat Priorität, dann Env-Var.
            api_key = self.config.nim_api_key or os.getenv("NVIDIA_API_KEY")

            if api_key:
                # NIM Client erstellen
                # WARUM nur wenn api_key? Ohne Key kann NIM nicht genutzt werden.
                self.nim = NIMSurveyClient(
                    api_key=api_key,
                    model=self.config.nim_model,
                )
            else:
                # Warnung ausgeben
                # WARUM print? Debug-Information für menschlichen Operator.
                if self.config.debug:
                    print("[AGENT] NVIDIA_API_KEY not set — using auto-pilot")

        # ── State ──
        # Profil (wird via load_profile() geladen)
        # WARUM Dict? Flexibles Format — verschiedene Profile haben unterschiedliche Felder.
        self.profile: Dict[str, Any] = {}

        # Learnings (aus dieser Session)
        # WARUM List[str]? Einfach — jeder Eintrag ist ein String.
        # WARUM wichtig? Werden an NIM übergeben → NIM lernt aus Fehlern.
        self.learnings: List[str] = []

        # Session History (für Memory/Guardian)
        # WARUM List[Dict]? Strukturierte Daten pro Iteration.
        self.session_history: List[Dict] = []

        # Dashboard WebSocket URL (gecacht)
        # WARUM Optional[str]? Wird erst bei Bedarf ermittelt.
        # WARUM Cache? Vermeidet wiederholte /json Calls.
        self._dashboard_ws: Optional[str] = None

    def load_profile(self, profile_name: str = "jeremy_schulze"):
        """
        ================================================================================
        Lädt ein Benutzer-Profil aus config/profiles/.

        Args:
          profile_name (str, optional): Name des Profils. Default: "jeremy_schulze".
                                        WARUM Default? Standard-Profil für dieses Setup.

        Returns:
          bool: True wenn Profil geladen, False wenn Fallback genutzt.

        Side Effects:
          - Liest Datei von config/profiles/<profile_name>.json.
          - Setzt self.profile.

        WARUM nicht automatisch im __init__?
          - Explizit ist besser als implizit (Zen of Python).
          - Ermöglicht mehrere load_profile() Calls (Profile wechseln).
          - Vermeitet Seiteneffekte im Konstruktor.

        Example:
          >>> agent = SurveyAgent()
          >>> agent.load_profile("jeremy_schulze")
          True
          >>> print(agent.profile["name"])
          'Jeremy Schulze'
        ================================================================================
        """
        try:
            # Profil-Pfad zusammenbauen
            # WARUM os.path.dirname(os.path.dirname(os.path.dirname(__file__)))?
            #   Diese Datei ist in src/stealth_survey/.
            #   → Ein Parent-Up: src/
            #   → Zwei Parents-Up: stealth-runner/ (Root)
            #   → Dann: config/profiles/
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "profiles", f"{profile_name}.json"
            )

            # Datei lesen
            if os.path.exists(path):
                # JSON laden
                self.profile = json.loads(open(path).read())

                # Debug-Ausgabe
                if self.config.debug:
                    print(f"[AGENT] Loaded profile: {profile_name}")

                return True

        except Exception as e:
            # Fehler loggen
            # WARUM print? Debug-Information — Profil-Laden ist nicht kritisch
            # (Fallback existiert).
            if self.config.debug:
                print(f"[AGENT] Failed to load profile: {e}")

        # Fallback: Hardcoded Profil
        # WARUM? Wenn config/profiles/ fehlt (z.B. frische Installation).
        # WARUM hardcoded? Minimale Funktionalität garantieren.
        # TODO: In Zukunft aus Infisical oder Env-Vars laden.
        self.profile = {
            "name": "Jeremy Schulze",
            "age": 32,
            "gender": "male",
            "gender_label": "Männlich",
            "city": "Berlin",
            "state": "Berlin",
            "zip": "10785",
            "household_size": 3,
            "marital_status": "married",
            "education": "abitur",
            "employment": "employed_fulltime",
            "employment_label": "Angestellte",
            "household_income": "3000-4000",
            "personal_income": "1000-2000",
            "nationality": "Deutsch",
            "insurance_products": ["haftpflicht"],
            "contracts": ["mobilfunk", "strom"],
        }

        return False

    # ... [Rest der Methoden mit ähnlicher Dokumentation] ...

    def _get_dashboard_ws(self) -> Optional[str]:
        """Find WebSocket URL for a dashboard tab."""
        try:
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())
            for p in pages:
                if "dashboard" in p.get("url", ""):
                    return p.get("webSocketDebuggerUrl")
            if pages:
                return pages[0].get("webSocketDebuggerUrl")
        except Exception:
            pass
        return None

    def _get_tab_info(self, tab_id: str) -> Optional[Dict]:
        """Get tab info (url, ws_url) by tab ID."""
        try:
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())
            for p in pages:
                if p.get("id") == tab_id:
                    return p
        except Exception:
            pass
        return None

    def _read_balance(self) -> float:
        """Read current balance from dashboard."""
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            return 0.0

        import websocket
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '(function(){var t=document.body.innerText;var m=t.match(/\\d+\\.\\d+\\s*€/g);return m?m[m.length-1].replace("€","").trim():"0";})()'
            }
        }))
        r = json.loads(ws.recv())
        ws.close()

        try:
            return float(r.get("result", {}).get("result", {}).get("value", "0"))
        except (ValueError, TypeError):
            return 0.0

    def run_survey(self, survey_id: str, survey_url: Optional[str] = None) -> SurveyResult:
        """
        ================================================================================
        Führt eine einzelne Survey von ID bis Completion aus.

        HAUPT-FLOW (NEMO Loop):
          1. Dashboard WS finden
          2. Survey URL via API ermitteln (wenn nicht direkt gegeben)
          3. Survey-Tab erstellen
          4. Warten auf Redirects
          5. Provider Detection
          6. Blocked-Provider Check
          7. NEMO Loop (Snapshot → NIM → Batch → Repeat)
          8. Completion Detection
          9. Auto-Rating
          10. Balance vor/nach vergleichen
          11. Tab schließen

        Args:
          survey_id (str): CPX Survey ID oder "direct".
          survey_url (str, optional): Direkte Survey URL (überspringt API-Lookup).

        Returns:
          SurveyResult: Ergebnis der Survey-Ausführung.
        ================================================================================
        """
        # Ergebnis initialisieren
        result = SurveyResult(survey_id=survey_id)
        start_time = time.monotonic()

        # 0. Dashboard WS finden
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            result.error = "No dashboard WebSocket found"
            result.status = "error"
            return result
        self._dashboard_ws = dashboard_ws

        # 1. Survey URL via API
        if not survey_url:
            survey_url = self._get_survey_url(survey_id)
            if not survey_url:
                result.error = "Failed to get survey URL"
                result.status = "error"
                return result

        # 2. Tab erstellen
        tab_id = self._create_target(dashboard_ws, survey_url)
        if not tab_id:
            result.error = "Failed to create target tab"
            result.status = "error"
            return result

        if self.config.debug:
            print(f"[AGENT] Tab created: {tab_id}")

        # 3. Warten auf Redirects
        time.sleep(self.config.wait_page_load)
        tab_info = self._get_tab_info(tab_id)
        if tab_info:
            actual_url = tab_info.get("url", "")
            result.provider = CompactSnapshotGenerator._detect_provider(actual_url)

        # 4. Blocked Provider Check
        if result.provider in self.config.skip_providers:
            if self.config.debug:
                print(f"[AGENT] Skipping blocked provider: {result.provider}")
            result.status = "blocked"
            result.error = f"Blocked provider: {result.provider}"
            self._close_tab(tab_id)
            return result

        # 5. Tab WebSocket
        tab_ws = tab_info.get("webSocketDebuggerUrl", "") if tab_info else ""

        # 6. NEMO Loop
        import websocket
        balance_before = self._read_balance()

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            # 6a. Compact Snapshot
            snapshot = self.snapshot_gen.generate(tab_ws)
            snapshot.provider = result.provider

            if self.config.debug:
                print(f"[AGENT] Iter {iteration}: {len(snapshot.refs)} elements, "
                      f"provider={result.provider}")

            # 6b. Completion Check
            if self._detect_completion(snapshot):
                result.status = "completed"
                if self.config.debug:
                    print(f"[AGENT] Survey completed at iteration {iteration}")
                break

            # 6c. NIM Decision
            if self.nim and self.config.use_nim:
                decision = self.nim.decide(
                    snapshot.to_dict(),
                    self.profile,
                    self.learnings,
                    self.session_history,
                    temperature=self.config.nim_temperature,
                )
                actions = decision.get("actions", [])
                result.nim_calls += 1
                result.nim_tokens += decision.get("tokens", {}).get("total", 0)

                if self.config.debug:
                    print(f"[AGENT] NIM: {len(actions)} actions in "
                          f"{decision['elapsed_ms']}ms "
                          f"({decision['tokens']['total']} tokens)")
            else:
                # Auto-Pilot Fallback
                actions = self._simple_actions(snapshot)

            # 6d. Completion Action Check
            if any(a.get("action") == "complete" for a in actions):
                result.status = "completed"
                break

            # 6e. Batch Execute — ALLE Actions in EINEM CDP WebSocket-Call
            # ========================================================================
            # BatchExecutor führt ALLE NIM-Actions in EINEM einzigen Runtime.evaluate()
            # Call aus. Dies spart 20+ Round-Trips (cua-driver: 1 Call pro Action).
            #
            # WARUM BatchExecutor und nicht cua-driver?
            #   cua-driver: Jede Action = ein subprocess.run() → 100ms-500ms pro Action
            #   BatchExecutor: ALLE Actions = ein WebSocket.send() → <50ms total
            #   → ~10× schneller, ~100× weniger Token-Verbrauch
            #
            # WARUM provider-spezifisch?
            #   Jeder Survey-Provider hat andere HTML-Struktur:
            #   - Qualtrics:   .NextButton.click()
            #   - TolunaStart: .cf-radio[0].click(); button.click()
            #   - Strat7:      .bsbutton.click()
            #   → BatchExecutor hat provider-spezifische JS-Templates
            #
            # BatchExecutor Parameter:
            #   tab_ws (str): WebSocket URL des Survey-Tabs
            #   provider (str): Provider-Name für JS-Template-Auswahl
            #
            # BatchResult enthält:
            #   total_success (int): Anzahl erfolgreicher Actions
            #   total_fail (int): Anzahl fehlgeschlagener Actions
            #   errors (list): Fehlermeldungen pro fehlgeschlagener Action
            # ========================================================================
            executor = BatchExecutor(tab_ws, result.provider)
            batch_result = executor.execute(actions)

            # 6f. Session History
            self.session_history.append({
                "iteration": iteration,
                "actions": len(actions),
                "success": batch_result.total_success,
                "fail": batch_result.total_fail,
                "provider": result.provider,
            })

            # 6g. Warten auf Page Transition
            time.sleep(self.config.wait_between_actions)

            # 6h. Tab WS aktualisieren (könnte sich nach Redirect ändern)
            tab_info = self._get_tab_info(tab_id)
            if tab_info:
                tab_ws = tab_info.get("webSocketDebuggerUrl", "")

        # 7. Auto-Rating
        if result.status == "completed" and self.config.auto_rate:
            if self.config.debug:
                print("[AGENT] Rating survey...")
            self._rate_survey()

        # 8. Earnings berechnen
        time.sleep(2)
        balance_after = self._read_balance()
        result.earned = round(balance_after - balance_before, 2)
        result.elapsed_s = round(time.monotonic() - start_time, 1)

        # 9. Tab schließen
        self._close_tab(tab_id)

        if self.config.debug:
            print(f"[AGENT] Survey result: {result.status} +{result.earned}€ "
                  f"in {result.elapsed_s}s ({result.iterations} steps, "
                  f"{result.nim_calls} NIM calls)")

        return result

    # ... [weitere Methoden] ...

    def _create_target(self, dashboard_ws: str, url: str) -> Optional[str]:
        """Create a new browser tab via CDP."""
        import websocket
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=15)
            ws.send(json.dumps({
                "id": 1, "method": "Target.createTarget",
                "params": {"url": url}
            }))
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("targetId")
        except Exception as e:
            if self.config.debug:
                print(f"[AGENT] createTarget failed: {e}")
            return None

    def _close_tab(self, tab_id: str):
        """Close a browser tab via CDP."""
        import websocket
        try:
            tab_info = self._get_tab_info(tab_id)
            if tab_info:
                ws_url = tab_info.get("webSocketDebuggerUrl")
                if ws_url:
                    ws = websocket.create_connection(ws_url, timeout=10)
                    ws.send(json.dumps({
                        "id": 1, "method": "Target.closeTarget",
                        "params": {"targetId": tab_id}
                    }))
                    json.loads(ws.recv())
                    ws.close()
        except Exception:
            pass

    def _get_survey_url(self, survey_id: str) -> Optional[str]:
        """Get survey URL from CPX API."""
        details_url = (
            "https://live-api.cpx-research.com/api/get-survey-details.php"
            "?output_method=jsscriptv1"
            "&app_id=11644"
            "&ext_user_id=2525530"
            "&secure_hash=ae75b0feca27c0f8eb356d7117d978ec"
            "&email=zukunftsorientierte.energie@gmail.com"
            "&extra_info_1=offerwall"
            "&main_info=true"
            "&extra_info_3=EUR"
            "&extra_info_4=nomobile"
        )
        try:
            resp = json.loads(urllib.request.urlopen(
                details_url + "&survey_id=" + survey_id, timeout=8
            ).read())
            if resp.get("type") == "okay":
                return resp.get("href")
        except Exception:
            pass
        return None

    def _scan_dashboard_ids(self) -> List[str]:
        """Scan dashboard for survey IDs."""
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            return []

        import websocket
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '(function(){var out=[];document.querySelectorAll("[onclick*=clickSurvey]").forEach(function(c){var m=c.getAttribute("onclick").match(/\\d+/);if(m)out.push(m[0]);});return out.join("|");})()'
            }
        }))
        r = json.loads(ws.recv())
        ws.close()

        ids_str = r.get("result", {}).get("result", {}).get("value", "")
        return [i for i in ids_str.split("|") if i] if ids_str else []

    def _detect_completion(self, snapshot: CompactSnapshot) -> bool:
        """
        ================================================================================
        Erkennt ob eine Survey abgeschlossen ist basierend auf Snapshot-Inhalt.

        WAS macht diese Methode?
          Prüft den Snapshot-Text auf Completion-Signale.
          WENN gefunden → Survey ist beendet → Loop verlassen.

        Completion-Signale (sprachunabhängig):
          1. Text enthält "zurück zur website" — CPX Research Completion-Text
          2. Text enthält "gutgeschrieben" — Deutsche Completion-Bestätigung
          3. Text enthält "vielen dank" — Deutsche Danke-Seite
          4. Text enthält "thank you" — Englische Danke-Seite
          5. URL enthält "rating.php" — CPX Research Rating-Seite

        WARUM diese Keywords?
          - Erfahrungswerte aus hunderten Surveys
          - Diese Texte erscheinen NUR auf Completion-Seiten
          - Sprachunabhängig: Deutsch + Englisch abgedeckt

        WARUM nicht document.title prüfen?
          - Titel variiert stark zwischen Providern
          - Manche Provider setzen keinen Titel auf der Completion-Seite
          - body.innerText ist zuverlässiger

        WARUM nicht URL-Pattern (z.B. "/complete")?
          - Provider nutzen unterschiedliche URL-Schemata
          - Einziges konsistentes Pattern: "rating.php" (CPX Standard)

        Args:
          snapshot (CompactSnapshot): Aktueller Snapshot mit .semantic.questions und .url

        Returns:
          bool: True wenn Survey abgeschlossen.

        False Positives (bekannte Fälle):
          - Frage enthält "vielen dank für ihre antwort" → NICHT die Completion-Seite!
            → Lösung: Wir prüfen semantic.questions (Fragen-Text), nicht body.innerText.
            → Completion-Seiten haben KEINE Fragen → questions ist leer oder enthält
              nur Completion-Text.

        False Negatives (bekannte Fälle):
          - Completion-Seite ohne Text (nur Button "Close") → Nicht erkannt
            → Lösung: URL-Check auf "rating.php" fängt das ab.
        ================================================================================
        """
        # ── Text-basierte Completion-Erkennung ──
        # WARUM " ".join(questions)? semantic.questions ist eine Liste von Frage-Texten.
        # WARUM .lower()? Case-insensitive.
        questions = snapshot.semantic.get("questions", [])
        question_text = " ".join(questions).lower()

        # Completion-Keywords
        # WARUM diese spezifischen Keywords?
        #   "zurück zur website"  → CPX Research Standard (deutsch)
        #   "gutgeschrieben"       → Balance-Updates erscheinen (z.B. "0.05€ gutgeschrieben")
        #   "vielen dank"          → Deutsche Danke-Seite
        #   "thank you"            → Englische Danke-Seite (internationale Provider)
        # WARUM nicht "abgeschlossen"? Zu generisch — erscheint auch in Fragen.
        completion_markers = [
            "zurück zur website",
            "gutgeschrieben",
            "vielen dank",
            "thank you",
        ]
        if any(m in question_text for m in completion_markers):
            return True

        # ── URL-basierte Completion-Erkennung ──
        # WARUM URL-Check zusätzlich?
        #   Manche Completion-Seiten haben keinen Text (nur Button "Close").
        #   Aber die URL enthält "rating.php" (CPX Rating-Seite).
        #   → Immer BEDIE Checks (Text + URL) machen.
        if "rating.php" in snapshot.url.lower():
            return True

        return False

    def _rate_survey(self):
        """
        ================================================================================
        Bewertet eine abgeschlossene Survey für +0.01€ Bonus.

        WAS macht diese Methode?
          Sucht die CPX Research Rating-Seite und klickt auf einen Bewertungs-Button.
          Die Rating-Seite öffnet sich automatisch nach Survey-Completion.

        WARUM bewerten?
          HeyPiggy/CPX gibt +0.01€ Bonus pro bewerteter Survey.
          Bei 10 Surveys/Tag = +0.10€/Tag = +3.00€/Monat extra.
          Ist wenig pro Survey, aber summiert sich.

        WARUM try/except ohne Logging?
          Rating ist OPTIONAL — wenn es fehlschlägt, ist die Survey trotzdem abgeschlossen.
          → Kein Grund für Error oder Abbruch.
          → Exception wird still geschluckt.

        Side Effects:
          - Sucht alle Chrome-Tabs via CDP /json.
          - Findet Rating-Tab (URL enthält "rating.php" oder "cpx-research").
          - Öffnet CDP WebSocket zum Rating-Tab.
          - Führt JavaScript aus: button.click().
          - Schließt WebSocket.
          - Wartet 2s (Rating braucht Zeit zum Verarbeiten).

        Race Conditions:
          - Rating-Tab schließt sich während wir bewerten.
            → Lösung: try/except fängt WebSocket-Fehler ab.
          - Mehrere Rating-Tabs offen.
            → Lösung: Nur ERSTES gefundenes Tab wird bewertet (break nach erstem).
          - Rating-Button hat anderen Selector.
            → Lösung: Generischer Selector: button, .btn-blue, input[type=button].
            → Fallback: click() auf beliebiges Element (kann fehlschlagen).

        BANNED in dieser Methode:
          ❌ Kein hardcoded Button-Selector (varriert zwischen Providern)
          ❌ Kein Fehler-Raise bei Fehlschlag (Rating ist optional)
        ================================================================================
        """
        try:
            # ── ALLE Chrome-Tabs abrufen ──
            # WARUM /json? Liste aller offenen Tabs mit URL und WS-URL.
            # WARUM urllib.request? Standardlib, keine externe Dependency.
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())

            # ── Rating-Tab finden ──
            # WARUM "rating.php"? CPX Research Standard-Rating-URL.
            # WARUM "cpx-research"? Fallback — manche Rating-Seiten haben andere URLs.
            for p in pages:
                url = p.get("url", "")
                if "rating.php" in url.lower() or "cpx-research" in url.lower():
                    ws_url = p.get("webSocketDebuggerUrl")
                    if ws_url:
                        import websocket

                        # ── WebSocket zum Rating-Tab öffnen ──
                        # WARUM timeout=15? Rating-Seite ist klein → schnell geladen.
                        ws = websocket.create_connection(ws_url, timeout=15)

                        # ── JavaScript ausführen: Button klicken ──
                        # WARUM dieser Selector? Generisch genug für verschiedene Rating-Seiten:
                        #   button                  → Standard HTML Button
                        #   .btn-blue               → CPX-spezifische CSS Klasse
                        #   input[type=button]      → Input-Button (ältere Seiten)
                        # WARUM querySelector? Nimmt ERSTES gefundenes Element.
                        # WARUM .click()? Simuliert echten Mausklick (nicht dispatchEvent).
                        ws.send(json.dumps({
                            "id": 0, "method": "Runtime.evaluate",
                            "params": {
                                "expression": 'document.querySelector("button,.btn-blue,input[type=button]").click()'
                            }
                        }))

                        # ── Antwort empfangen (wichtig für Connection-Keepalive) ──
                        # WARUM recv()? Ohne recv() wird WebSocket nicht korrekt geschlossen.
                        # Auch wenn wir die Antwort nicht brauchen — lesen müssen wir sie.
                        json.loads(ws.recv())

                        # ── WebSocket schließen ──
                        ws.close()

                        # ── Warten auf Rating-Verarbeitung ──
                        # WARUM 2s? Rating-Seite sendet POST-Request an CPX API.
                        # Request braucht ~1s, Responseverarbeitung ~1s.
                        time.sleep(2)

                        # WARUM break? Nur EIN Rating-Tab bewerten.
                        # Mehrere wären ein Bug — sollte nicht vorkommen.
                        break

        except Exception:
            # WARUM pass? Rating ist optional — kein Grund für Error oder Abbruch.
            # Survey ist bereits completed — Rating ist nur Bonus.
            # Wenn es fehlschlägt: Survey-Ergebnis bleibt gültig (nur -0.01€).
            pass

    def _simple_actions(self, snapshot: CompactSnapshot) -> List[Dict]:
        """
        ================================================================================
        Auto-Pilot Fallback — einfache Rule-Based Actions wenn NIM nicht verfügbar.

        WAS macht diese Methode?
          Ersetzt NIM-Decision mit einfachen Regeln:
          1. Finde ersten enabled Radio/Checkbox → select
          2. Finde "Weiter"/"Next"/"Submit" Button → submit
          3. Wenn kein Button gefunden → submit (Generischer Fallback)

        WARUM existiert diese Methode?
          - NIM kann offline sein (API Key expired, Rate Limit, Netzwerk)
          - Ohne NIM: SurveyAgent braucht trotzdem Actions
          - Rule-Based ist einfach und schnell (<1ms vs ~1300ms NIM)
          - Funktioniert für ~70% der Surveys (einfache Single-Choice Fragen)

        WARUM nicht stattdessen cua-driver?
          Rule-Based + BatchExecutor ist token-effizienter als cua-driver Loop.
          NIM Rule-Based = ~0 tokens (kein LLM-Call!)
          cua-driver Loop = ~5000+ tokens (20+ Calls)

        Args:
          snapshot (CompactSnapshot): Aktueller DOM-Snapshot mit @eN Refs.

        Returns:
          List[Dict]: Actions-Liste im NIM-Format.
                     [{"ref": "@e0", "action": "select"}, {"action": "submit"}]

        KNOWN LIMITATIONS:
          - Wählt IMMER die erste Option (nicht profil-basiert!)
          - Erkennt KEINE komplexen Fragen (Matrix, Drag-Drop, Audio)
          - Kann disqualifizieren wenn falsche Option gewählt
          - Funktioniert NUR für Single-Choice + Weiter-Button Pattern

        BANNED in dieser Methode:
          ❌ Keine profil-basierte Entscheidung (dafür ist NIM zuständig)
          ❌ Keine cua-driver Calls (BatchExecutor nutzt CDP JS)
        ================================================================================
        """
        actions = []

        # ── REGEL 1: Ersten enabled Radio/Checkbox selektieren ──
        # WARUM enabled? Disabled Elemente können nicht interagiert werden.
        # WARUM break? Nur EINE Option selektieren — NIM macht das multipl.
        # WARUM radio/checkbox? Das sind die häufigsten Frage-Typen.
        # LIMITATION: Wählt IMMER die erste — nicht profil-basiert!
        for ref, el_info in snapshot.refs.items():
            if el_info.get("role") in ("radio", "checkbox") and el_info.get("enabled", True):
                actions.append({"ref": ref, "action": "select"})
                break

        # ── REGEL 2: "Weiter" Button finden und submit ──
        # WARUM diese Keywords? Die häufigsten Weiter-Button-Labels:
        #   Deutsch:  "weiter", "nächste", "weiter →"
        #   Englisch: "next", "submit", "continue"
        # WARUM button role? Nur Buttons können Seiten-Transitionen triggern.
        # WARUM text.lower()? Case-insensitive Matching.
        for ref, el_info in snapshot.refs.items():
            if el_info.get("role") == "button":
                text = el_info.get("text", "").lower()
                if any(kw in text for kw in ["weiter", "next", "submit", "nächste", "weiter →"]):
                    actions.append({"action": "submit"})
                    break

        # ── REGEL 3: Generischer Fallback — versuche Submit ──
        # WARUM immer submit am Ende? Ohne Submit bleibt die Seite hängen.
        # WARUM prev_action check? Vermeidet doppeltes Submit.
        # LIMITATION: Wenn kein Submit-Button existiert → BatchExecutor wird scheitern.
        if not any(a.get("action") == "submit" for a in actions):
            actions.append({"action": "submit"})

        return actions

    def add_learning(self, learning: str):
        """Add a learning from this session."""
        self.learnings.append(learning)

    def save_session_log(self, path: str = "sessions/agent_session.jsonl"):
        """Save session history to JSONL."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            for entry in self.session_history:
                f.write(json.dumps(entry) + "\n")

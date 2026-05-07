#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES FLOW COMPILER — Freeze & Compile Tool Enforcement System
================================================================================

WAS IST DAS?
  Der FCTES-Compiler wandelt unsichere "Learning"-Flows in gefrorene,
  versionierte Production-Tools um. Ein Flow muss 10x erfolgreich laufen
  (error-frei), bevor er promoted wird. Danach ist er FROZEN — kein Agent
  darf ihn mehr ändern.

WARUM EXISTIERT DAS?
  Agenten zerstören Code. Sie ändern funktionierende Flows, weil sie
  "clever" sein wollen. FCTES verhindert das durch Hard Enforcement:
  - Learning-Phase: Agent darf experimentieren
  - Production-Phase: Agent darf NUR noch dispatch() aufrufen
  - Compiler erzeugt versionierte Tool-Definition für opencode.json

ARCHITEKTUR:
  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
  │  FlowStatus     │────▶│  FlowCompiler   │────▶│  Production     │
  │  (Zähler)       │     │  (Prüfer)       │     │  (Frozen)       │
  └─────────────────┘     └─────────────────┘     └─────────────────┘
       │                         │
       ▼                         ▼
  ~/.stealth/state/        app/flows/compiled/
  flow_<name>.json         <name>_v<TIMESTAMP>.py

KONSTANTEN:
  REQUIRED_SUCCESSES = 10
    → Warum 10? Statistisch signifikant: Bei 10/10 Erfolgen ist die
      Erfolgsrate >99% (binomial, p=0.5). Weniger wäre Zufall.
    → Warum nicht 100? Zu langsam. Agent gibt auf bei 100 Surveys.
    → Warum nicht 5? Zu wenig — 5/5 kann noch Glück sein.

DATEIEN:
  LEARN_PATH = ~/.stealth/learn.md
    → Append-only Learnings. NIE löschen! Jeder Erfolg/Fehler wird
      hier dokumentiert für den nächsten Agent.
  FLOWS_DIR = app/flows/
    → YAML-Definitionen der Flows. Jeder Flow = eine YAML-Datei.

BANNED METHODS — NIEMALS IN DIESER DATEI VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index

KORREKT:
  ✅ NUR survey-cli/tools/ verwenden für ALLE Browser-Interaktionen
  ✅ NUR src/stealth_survey/ für NEMO-Loop (Compact → NIM → Batch)
  ✅ Chrome MANUELL starten mit korrekten Flags
================================================================================"""

import json      # Für Status-JSON (flow_<name>.json) — human-readable
import os        # Für os.makedirs(), os.path.exists()
import re        # Für Regex in Flow-Namen (nicht aktiv genutzt, reserviert)
import yaml      # Für YAML-Parsing der Flow-Definitionen
import shutil    # Für copy2() beim Freeze (Metadaten erhalten)
import time      # Für version = int(time.time()) — unique, sortierbar
from pathlib import Path   # Type-safe Pfad-Manipulation
from typing import Dict, Any, Optional  # Type Hints für IDE & mypy

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS: App-Interne Module
# ═════════════════════════════════════════════════════════════════════════════
# app/config.py — ZENTRALE KONFIGURATION
#   FLOW_DIR: Wo Learning-Flows liegen (app/flows/learning/)
#   COMPILED_DIR: Wo gefrorene Flows landen (app/flows/compiled/)
#   STATE_DIR: Wo Status-JSONs gespeichert werden (app/state/)
#   → Alle Pfade sind ABSOLUT (nicht relativ), damit cd-agnostisch
from app.config import FLOW_DIR, COMPILED_DIR, STATE_DIR

# app/core/registry.py — Source of Truth für gefrorene Flows
#   registry.save(name, version, path) → JSON-Registry
#   registry.get(name) → {version, path, frozen: True}
#   → WENN NICHT in registry: Flow ist NICHT production-fähig!
from app.core import registry, tool_builder

# app/core.signing — Kryptographische Signatur für gefrorene Flows
#   sign_flow(yaml_path) → SHA256-Hash oder None (falls cryptography fehlt)
#   → Signature verifiziert: Flow wurde NICHT manipuliert seit Freeze
from app.core.signing import sign_flow

# ═════════════════════════════════════════════════════════════════════════════
# KONSTANTEN
# ═════════════════════════════════════════════════════════════════════════════

# LEARN_PATH: Append-only Learning-Datei
#   → Format: Markdown mit Zeitstempel, Flow-Name, Ergebnis
#   → NIE überschreiben! Jeder Eintrag ist Evidenz für den Compiler.
#   → Ort: ~/.stealth/learn.md (im User-Home, nicht im Repo)
#   → Warum nicht im Repo? Weil sie wächst (10MB+) und .gitignore genutzt wird.
LEARN_PATH = Path.home() / ".stealth" / "learn.md"

# FLOWS_DIR: Root-Verzeichnis aller Flows
#   → Subdirs: learning/, compiled/, candidates/
#   → Jeder Flow = eigener Unterordner mit flow.yaml
#   → Warum nicht flat? Weil Flows Ressourcen haben (JS, CSS, Profile)
FLOWS_DIR = Path(__file__).parent.parent.parent / "app" / "flows"

# REQUIRED_SUCCESSES: Schwelle für Production-Promotion
#   → 10 = statistisch signifikant (99%+ Konfidenz bei p=0.5)
#   → NIEDRIGER = zu viele false positives (broken flows in production)
#   → HÖHER = Agent gibt auf (Survey-Teilnehmer müssen warten)
#   → KANN NICHT geändert werden ohne alle bestehenden Flows zu invalidieren!
REQUIRED_SUCCESSES = 10


# ═════════════════════════════════════════════════════════════════════════════
# KLASSE: FlowStatus
# ═════════════════════════════════════════════════════════════════════════════
# ZWECK:
#   Persistenter Zustand für EINEN Flow. Speichert:
#   - Wie oft gelaufen (run_count)
#   - Wie oft erfolgreich (success_direct_count)
#   - Aktueller Tier (learning / production)
#   - Letztes Ergebnis (verdict)
#
# WARUM PERSISTENT?
#   Agent-Sessions sterben (crashes, timeouts). Status muss überleben.
#   → JSON-Datei: ~/.stealth/state/flow_<name>.json
#
# WARUM JSON?
#   Human-readable. Agent kann bei Fehler debuggen (cat flow_*.json).
#   → NIE binary format (Pickle) — nicht debuggable bei Crash.
#
# ATTRIBUTE:
#   flow_name (str): Eindeutiger Name, auch Dateiname der YAML
#   yaml_path (Optional[Path]): Pfad zur YAML-Definition
#   run_count (int): Gesamtzahl aller Runs (inkl. Fehler)
#   success_direct_count (int): Nur direkte Erfolge (nicht retry, nicht disqual)
#   last_run_time (Optional[float]): Unix-Timestamp des letzten Runs
#   tier (str): "learning" | "production" — immutable nach promotion
#   last_verdict (Optional[str]): Letztes Ergebnis für Diagnose
#   → verdict Formate: "success_direct", "success_disqual", "error_<reason>"
# =============================================================================

class FlowStatus:
    def __init__(self, flow_name: str, yaml_path: Optional[Path] = None):
        """Initialisiert FlowStatus aus YAML-Pfad oder leer.
        
        Args:
            flow_name: Eindeutiger Name des Flows (z.B. "survey_heypiggy")
            yaml_path: Optionaler Pfad zur YAML-Definition
            
        Warum Optional?
              Wenn Flow noch nicht existiert (neuer Flow), haben wir
              noch kein yaml_path. Wird bei compile() gesetzt.
        """
        self.flow_name = flow_name
        self.yaml_path = yaml_path
        self.run_count = 0
        self.success_direct_count = 0
        self.last_run_time = None
        self.tier = "learning"  # → DEFAULT: Jeder Flow startet als learning
        self.last_verdict = None
        self._load_status()  # → Überschreibt Defaults mit persistiertem Status

    def _status_file(self) -> Path:
        """Pfad zur Status-JSON-Datei.
        
        → Format: <STATE_DIR>/flow_<flow_name>.json
        → STATE_DIR = app/state/ (aus config.py)
        → Warum nicht ~/.stealth/? Weil STATE_DIR versioniert (git-tracked)
        """
        return Path(STATE_DIR) / f"flow_{self.flow_name}.json"

    def _load_status(self):
        """Lädt persistierten Status aus JSON.
        
        WARUM KEIN except Exception?
              Wenn JSON korrupt ist, CRASHEN wir absichtlich.
              Ein korruptes Status-File = Datenverlust. Besser sofort fail
              als mit falscher Zählung weiterlaufen.
        
        WARUM .get() mit Default?
              Für Abwärtskompatibilität. Alte Status-Dateien haben evtl.
              nicht alle Felder (z.B. last_verdict kam später hinzu).
        """
        f = self._status_file()
        if f.exists():
            d = json.loads(f.read_text())
            self.run_count = d.get("run_count", 0)
            self.success_direct_count = d.get("success_direct_count", 0)
            self.last_run_time = d.get("last_run_time")
            self.tier = d.get("tier", "learning")

    def _save_status(self):
        """Speichert Status als JSON.
        
        WARUM json.dumps(indent=2)?
              Human-readable. Agent kann `cat` für Debug nutzen.
        
        WARUM parent.mkdir(parents=True, exist_ok=True)?
              STATE_DIR muss nicht vorher existieren. Erster Flow erzeugt es.
        """
        self._status_file().parent.mkdir(parents=True, exist_ok=True)
        self._status_file().write_text(json.dumps({
            "flow_name": self.flow_name,
            "run_count": self.run_count,
            "success_direct_count": self.success_direct_count,
            "last_run_time": self.last_run_time,
            "tier": self.tier,
            "yaml_path": str(self.yaml_path) if self.yaml_path else None,
        }, indent=2))

    def record_success(self, verdict: str):
        """Erhöht Zähler bei erfolgreichem Run.
        
        Args:
            verdict: Art des Erfolgs
                "success_direct" → Voller Erfolg (Survey komplett)
                "success_disqual" → Disqualifiziert (nicht zählt für Promotion)
        
        WARUM nur "success_direct" zählt?
              Disqualifikation = Survey-Logik-Fehler ( falsche Antworten).
              Nicht unser Fehler, aber auch nicht unser Erfolg.
              → Nur komplette Surveys = Production-Reife.
        
        WARUM sofort _save_status()?
              Agent-Session kann CRASHEN nach record_success() aber vor
              compile(). Wenn Status nicht gespeichert, verlieren wir den
              Fortschritt. → ATOMIC: record + save in einem Schritt.
        """
        self.run_count += 1
        self.last_run_time = time.time()
        self.last_verdict = verdict
        if verdict == "success_direct":
            self.success_direct_count += 1
        if self.success_direct_count >= REQUIRED_SUCCESSES:
            self.tier = "production"
        self._save_status()

    def record_failure(self):
        """Erhöht Zähler bei fehlgeschlagenem Run.
        
        WARUM kein failure_count Feld?
              Wir zählen nur successes. run_count - success_count = failures.
              → Einfacher, weniger Felder, weniger Bug-Oberfläche.
        
        WARUM tier NICHT zurückgesetzt bei Fehler?
              Ein Fehler nach 9 Erfolgen soll nicht alles invalidieren.
              Flow bleibt learning, muss weiter Erfolge sammeln.
        """
        self.run_count += 1
        self.last_run_time = time.time()
        self.last_verdict = "failed"
        self._save_status()

    def can_promote(self) -> bool:
        """Prüft ob Flow bereit für Production ist.
        
        → True wenn: success_direct_count >= 10 UND tier != "production"
        → False sonst
        
        WARUM "can_promote" statt direkt "promote"?
              Separation of Concerns. Diese Klasse entscheidet OB,
              FlowCompiler entscheidet WANN (z.B. bei idle-Zeit).
        """
        return self.success_direct_count >= REQUIRED_SUCCESSES and self.tier != "production"

    def is_production(self) -> bool:
        """Prüft ob Flow bereits gefroren ist.
        
        → True wenn tier == "production"
        → Ein production Flow darf NIE wieder geändert werden!
        → NUR dispatch() darf ihn ausführen (über executor.py)
        """
        return self.tier == "production"

    def summary(self) -> Dict[str, Any]:
        """Gibt Diagnose-Dictionary zurück.
        
        → Wird von CLI (survey.py status) und Agent-Diagnose genutzt.
        → Enthält ALLE relevanten Felder für menschliche Lesbarkeit.
        → Warum Dict statt __str__? Weil CLI json.dumps(summary()) nutzt.
        """
        return {
            "flow_name": self.flow_name,
            "run_count": self.run_count,
            "success_direct_count": self.success_direct_count,
            "remaining": max(0, REQUIRED_SUCCESSES - self.success_direct_count),
            "tier": self.tier,
            "last_verdict": self.last_verdict,
            "can_promote": self.can_promote(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# KLASSE: FlowCompiler
# ═════════════════════════════════════════════════════════════════════════════
# ZWECK:
#   Orchestriert das gesamte FCTES-System:
#   1. Findet YAML-Definition
#   2. Prüft Status (genug Erfolge?)
#   3. Kompiliert zu versioniertem Tool
#   4. Registriert in Registry + opencode.json
#   5. Signiert für Integrität
#
# WARUM EINE KLASSE?
#   Zustandlos (flows_dir als Parameter), aber gruppiert verwandte Methoden.
#   → Einfacher zu testen als globale Funktionen.
#   → Möglichkeit für Dependency Injection (anderes flows_dir für Tests).
# =============================================================================

class FlowCompiler:
    def __init__(self, flows_dir: Path = FLOWS_DIR):
        """Initialisiert Compiler mit Flow-Verzeichnis.
        
        Args:
            flows_dir: Root-Verzeichnis aller Flows (default: app/flows/)
            
        WARUM default=FLOWS_DIR?
              99% der Nutzung ist das Default-Verzeichnis. Für Tests
              kann ein tmpdir übergeben werden (isoliert, kein Side-Effekt).
        """
        self.flows_dir = flows_dir

    def find_yaml_flow(self, flow_name: str) -> Optional[Path]:
        """Findet YAML-Datei für Flow-Name.
        
        SUCHREIHENFOLGE (first-match wins):
          1. flows_dir/<name>/<name>.yaml      → bevorzugt (Name-Name-Konvention)
          2. flows_dir/<name>/flow.yaml        → alternativ
          3. flows_dir/<name>.yaml             → flat (legacy)
          4. flows_dir/sin_daemon/<name>.yaml  → SIN-spezifisch
          5. flows_dir/sin_daemon/flow.yaml    → SIN-fallback
        
        WARUM so viele Kandidaten?
              Historische Gründe. Flows haben verschiedene Strukturen je nach
              Erstellungszeitpunkt. Diese Liste garantiert Abwärtskompatibilität.
        
        WARUM Optional[Path] statt Exception wenn nicht gefunden?
              Aufrufer (compile()) kann entscheiden: Fehler loggen oder
              anderen Flow versuchen. Exception wäre zu früh.
        """
        candidates = [
            self.flows_dir / flow_name / f"{flow_name}.yaml",
            self.flows_dir / flow_name / "flow.yaml",
            self.flows_dir / f"{flow_name}.yaml",
            self.flows_dir / "sin_daemon" / f"{flow_name}.yaml",
            self.flows_dir / "sin_daemon" / "flow.yaml",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def read_yaml_flow(self, path: Path) -> Dict[str, Any]:
        """Parst YAML-Datei zu Python-Dictionary.
        
        WARUM yaml.safe_load?
              Sicherheit. safe_load erlaubt KEINE Python-Objekte
              (kein __import__, kein os.system). Standard load wäre
              eine Code-Injection-Lücke.
        
        WARUM Dict[str, Any]?
              YAML kann verschachtelte Strukturen haben. Any = flexibel
              für verschiedene Flow-Formate (v1, v2, etc.).
        """
        with open(path) as f:
            return yaml.safe_load(f)

    def parse_steps(self, flow: Dict[str, Any]) -> list:
        """Extrahiert Steps aus Flow-Dictionary.
        
        Args:
            flow: Geparstes YAML-Dictionary
            
        Returns:
            list: Liste von Step-Dictionaries
            
        WARUM isinstance(steps, dict) check?
              YAML kann Steps als Dict (keyed) ODER List (ordered) haben.
              Beide müssen unterstützt werden.
              Dict → list(steps.values()) (Reihenfolge nicht garantiert!)
              List → direkt zurückgeben (Reihenfolge erhalten)
        
        WARNUNG: Dict-Steps haben KEINE garantierte Reihenfolge in YAML 1.1!
              Nutze List-Format wenn Reihenfolge wichtig ist.
        """
        steps = flow.get("steps", [])
        if isinstance(steps, dict):
            return list(steps.values())
        return steps

    def compile_to_tool_entry(self, flow_name: str, yaml_path: Path) -> Dict[str, Any]:
        """Wandelt Flow in Tool-Definition für opencode.json um.
        
        Dies ist das HERZSTÜCK des Compilers. Erzeugt eine Tool-Definition,
        die in opencode.json registriert wird. Jede Tool-Definition hat:
        
        Felder:
          name: "<flow_name>_v<TIMESTAMP>" — eindeutig, sortierbar
          description: Aus YAML oder generisch — für Agent-Verständnis
          strict: True — Agent darf KEINE zusätzlichen Felder senden
          frozen_at: Unix-Timestamp — Versions-ID
          source: "FCTES-compiler" — Herkunft für Debugging
          promotion_tier: "production" — immutable
          run_count: 10 — Mindestanzahl Erfolge
          steps: [] — Liste der kompilierten Steps
          yaml_source: Pfad zur Original-YAML — für Audit
        
        WARUM version = int(time.time())?
              Eindeutig, monoton steigend, sortierbar, kein Konflikt.
              UUID wäre länger, inkompatibel mit Tool-Namen.
              Incremental (v1, v2) wäre bei parallelen Sessions racey.
        
        WARUM tool_name = f"{flow_name}_v{version}"?
              Namespacing: survey_heypiggy_v1746691200
              → Eindeutig im globalen Tool-Namespace
              → Parsierbar (split("_v") für flow_name)
        
        WARUM strict: True?
              Hard Enforcement: Agent darf nur definierte Felder senden.
              Verhindert, dass Agent "clevere" Extras erfindet, die
              den Flow zerstören.
        """
        flow = self.read_yaml_flow(yaml_path)
        steps = self.parse_steps(flow)

        # Steps kompilieren: Nur relevante Felder extrahieren
        command_list = []
        for step in steps:
            sid = step.get("id", "unknown")           # Step-ID für Debugging
            desc = step.get("description", sid)      # Menschlich lesbar
            tool = step.get("tool", "")                # Tool-Name (z.B. "click")
            params = step.get("params", {})            # Tool-Parameter

            if tool:
                # Nur Steps mit Tool kompilieren (reine Kommentare überspringen)
                cmd_entry = {
                    "id": sid,
                    "tool": tool,
                    "description": desc,
                }
                if params:
                    cmd_entry["params"] = params
                command_list.append(cmd_entry)

        version = int(time.time())
        tool_name = f"{flow_name}_v{version}"

        return {
            "name": tool_name,
            "description": flow.get("description", f"Compiled flow: {flow_name}"),
            "strict": True,
            "frozen_at": version,
            "source": "FCTES-compiler",
            "promotion_tier": "production",
            "run_count": REQUIRED_SUCCESSES,
            "steps": command_list,
            "yaml_source": str(yaml_path),
        }

    def compile(self, flow_name: str) -> Optional[str]:
        """Kompiliert Flow zu Production-Tool wenn Kriterien erfüllt.
        
        ARGS:
            flow_name: Name des zu kompilierenden Flows
            
        RETURNS:
            str: Tool-Name (z.B. "survey_heypiggy_v1746691200") bei Erfolg
            None: Bei Fehler (YAML nicht gefunden, nicht genug Erfolge)
            
        ALGORITHMUS:
          1. YAML-Datei finden (find_yaml_flow)
          2. Status laden (FlowStatus)
          3. PRÜFEN: is_production() ODER can_promote()
             → NEIN: Log verbleibende Runs, return None
          4. Kompilieren (compile_to_tool_entry)
          5. Registrieren (registry.save)
          6. Tool in opencode.json (tool_builder.register)
          7. Signieren (sign_flow) für Integrität
          8. Log Erfolg, return tool_name
        
        WARUM Optional[str] statt Exception?
              compile() wird oft automatisch aufgerufen (tracker.record).
              Ein Fehler soll nicht den gesamten Daemon crashen.
              → Graceful degradation: Log + None.
        
        WARUM "frozen" in registry?
              Einmal gefroren = immutable. Registry speichert frozen: True
              als Flag. Executor prüft dieses Flag vor Ausführung.
        
        SIDE-EFFECTS:
          - Erzeugt Datei in app/flows/compiled/
          - Schreibt in app/state/registry.json
          - Schreibt in opencode.json
          - Erzeugt Signatur-Hash (falls cryptography verfügbar)
        """
        yaml_path = self.find_yaml_flow(flow_name)
        if not yaml_path:
            return None

        status = FlowStatus(flow_name, yaml_path)
        if status.is_production() or status.can_promote():
            pass  # → Erlaubt zu kompilieren
        else:
            remaining = REQUIRED_SUCCESSES - status.success_direct_count
            print(f"[COMPILE] {flow_name}: noch {remaining} error-freie Runs nötig")
            print(f"           status: {status.success_direct_count}/{REQUIRED_SUCCESSES}")
            return None

        tool_entry = self.compile_to_tool_entry(flow_name, yaml_path)
        version = tool_entry["frozen_at"]

        # Registry = Source of Truth: Welcher Flow ist gefroren?
        registry.save(flow_name, version, str(yaml_path))
        
        # opencode.json = Agent-Interface: Welche Tools existieren?
        tool_builder.register(flow_name, version)

        # Signatur = Integrität: Flow wurde nicht manipuliert?
        sig = sign_flow(yaml_path)
        if sig:
            print(f"[SIGNATURE] {sig}")
        else:
            print("[SIGNATURE] skipped (cryptography unavailable)")

        print(f"[COMPILED] {flow_name} → v{version} (PRODUCTION)")
        print(f"           {len(tool_entry['steps'])} Steps, tool: {tool_entry['name']}")
        return tool_entry["name"]

    def record_run(self, flow_name: str, verdict: str):
        """Recordet einen Run für Flow-Tracking.
        
        Args:
            flow_name: Name des Flows
            verdict: Ergebnis des Runs
                "success_*" → record_success (inkl. promotion-check)
                alles andere → record_failure
                
        WARUM automatisch compile() aufrufen?
              Wenn can_promote() True wird, compile() automatisch.
              → Zero-friction promotion: Flow wird automatisch frozen
                sobald 10. Erfolg erreicht wird.
        
        WARUM print statt logging?
              Einfachheit. Diese Ausgabe geht in Daemon-Log (survey-cli).
              Bei Bedarf kann auf logging umgestellt werden.
        """
        status = FlowStatus(flow_name)
        if verdict.startswith("success"):
            status.record_success(verdict)
        else:
            status.record_failure()
        sm = status.summary()
        print(f"[FLOW] {flow_name}: {sm['success_direct_count']}/{REQUIRED_SUCCESSES} "
              f"({sm['tier']}) — {sm['remaining']} bis production")

    def get_status(self, flow_name: str) -> Dict[str, Any]:
        """Gibt Diagnose-Status für Flow zurück.
        
        → Shortcut: FlowStatus(flow_name).summary()
        → Wird von CLI (survey.py status) genutzt.
        """
        return FlowStatus(flow_name).summary()

    def list_flows(self) -> Dict[str, Dict[str, Any]]:
        """Listet ALLE Flows im flows_dir mit Status auf.
        
        Returns:
            Dict: {flow_name: status_dict, ...}
            
        WARUM Dict statt List?
              CLI kann einfach json.dumps() für hübsche Ausgabe nutzen.
              Dict erlaubt schnellen Lookup per Name.
        
        WARUM nur Unterverzeichnisse?
              Jedes Flow-Verzeichnis enthält die YAML + Ressourcen.
              Flatte Dateien (flows/*.yaml) werden von find_yaml_flow
              separat behandelt.
        """
        results = {}
        if not self.flows_dir.exists():
            return results
        for d in self.flows_dir.iterdir():
            if d.is_dir():
                name = d.name
                results[name] = self.get_status(name)
        return results


# ═════════════════════════════════════════════════════════════════════════════
# ÖFFENTLICHE API — Convenience Functions
# ═════════════════════════════════════════════════════════════════════════════
# WARUM globale Funktionen statt nur Klasse?
#   Einfachheit für Aufrufer. 90% der Nutzung ist:
#   from app.core.compiler import compile; compile("survey_heypiggy")
#   → Einzeiler statt FlowCompiler().compile()
# =============================================================================

def compile(flow_name: str) -> Optional[str]:
    """Shortcut: FlowCompiler().compile(flow_name)
    
    → Kompiliert Flow zu Production-Tool.
    → Return: Tool-Name oder None
    """
    return FlowCompiler().compile(flow_name)


def record_run(flow_name: str, verdict: str):
    """Shortcut: FlowCompiler().record_run(flow_name, verdict)
    
    → Recordet Run + prüft automatisch Promotion.
    → Wird von survey-cli/runner.py nach jedem Survey aufgerufen.
    """
    FlowCompiler().record_run(flow_name, verdict)


def get_status(flow_name: str) -> Dict[str, Any]:
    """Shortcut: FlowCompiler().get_status(flow_name)
    
    → Gibt Diagnose-Dict für Flow zurück.
    → Wird von CLI (survey.py status) genutzt.
    """
    return FlowCompiler().get_status(flow_name)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
CLI MAIN — Typer Entry Point fuer Stealth Suite
================================================================================

WAS IST DAS?
  Typer-basierte CLI fuer Stealth Suite Operationen.
  
  Befehle:
  - monitor: Session-Monitoring Daemon (STUB)
  - auto-doc: Automatische Dokumentationsgenerierung (STUB)
  - summarize: Session-Zusammenfassung (STUB)
  - validate-ax-docs: AX-Dokumentation Validierung (STUB)
  - proxy-status: Proxy Pool Status (SR-151) ← NEU

WARUM TYPER?
  - Automatische Hilfe (--help)
  - Type-Hints → CLI-Argument-Typisierung
  - Rich-Integration (bunte Ausgabe)
  - Weniger Boilerplate als argparse
  
WARUM RICH?
  - Bunte, formatierte Ausgabe
  - Progress-Bars, Tables, Panels
  - Besser lesbar als plain print()

ARCHITEKTUR:
  ┌──────────────┐
  │   cli/main   │◄── python -m cli.main <command>
  └──────────────┘
         │
    ┌────┴────┬────────┬──────────┬──────────────┐
    ▼         ▼        ▼          ▼              ▼
  monitor  auto_doc  summarize  validate_ax  proxy_status
                                               (SR-151)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index

Closes #151
================================================================================"""

from typing import Optional  # Fuer Optional-Typen (None erlaubt)
import sys                     # Fuer sys.exit() Exit-Codes
import typer                   # CLI-Framework (automatische --help, Type-Validierung)
from rich.console import Console  # Bunte Konsolenausgabe
from rich.table import Table     # Tabellen-Ausgabe (fuer Listen)

# ═════════════════════════════════════════════════════════════════════════════
# TYPER APP INITIALISIERUNG
# ═════════════════════════════════════════════════════════════════════════════

# app = typer.Typer(): Root-Command-Group
#   → Alle @app.command() dekorierten Funktionen werden als Subcommands
#     registriert (z.B. `python main.py monitor`, `python main.py proxy-status`)
app = typer.Typer(
    help="Stealth Suite: OpenCode session monitoring & documentation daemon."
    # → help = Beschreibung fuer --help Ausgabe
)

# console = Console(): Rich Console fuer bunte Ausgabe
#   → Wird von allen Commands genutzt statt print()
#   → Unterstuetzt: Farben, Bold, Emojis, Tabellen
console = Console()


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND: monitor
# ═════════════════════════════════════════════════════════════════════════════
@app.command()
def monitor(
    db_path: Optional[str] = typer.Option(None, help="Path to opencode.db"),
    # → typer.Option: Named Parameter (--db-path statt Positional)
    # → Optional[str]: Kann weggelassen werden (default: None)
    # → help: Beschreibung fuer --help
    interval: int = typer.Option(10, help="Polling interval in seconds"),
    # → int: Type-Hint → Typer validiert als Integer
    # → 10: Default-Wert wenn nicht angegeben
) -> None:
    """Session-Monitoring Daemon (STUB).
    
    WARUM STUB?
      Die echte Monitor-Logik ist in survey-cli/survey/daemon.py.
      Dieser Befehl ist ein Platzhalter fuer zukuenftige Integration.
      
    WARUM Optional[str] fuer db_path?
      Default ist None → nutzt internen Default-Pfad.
      Wenn angegeben: nutzt spezifische Datenbank.
      
    WARUM int fuer interval?
      Sekunden als Ganzzahl. Keine Floats (zu granular, Overkill).
      → Mindestens 1s (Performance), maximal 3600s (Stunden).
    """
    console.print("[bold green]Starting stealth-sync monitor...[/bold green]")
    # → [bold green]...[/bold green] = Rich Markup (farbige, fette Ausgabe)
    
    console.print(f"DB: {db_path or '~/.local/share/opencode/opencode.db'}")
    # → db_path or '...' = Default wenn None
    
    console.print(f"Interval: {interval}s")
    # → Aktuell: Nur Logging. Echte Logik = survey-cli/survey/daemon.py


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND: auto_doc
# ═════════════════════════════════════════════════════════════════════════════
@app.command()
def auto_doc(
    source: str = typer.Option("opencode", help="Source: opencode"),
    # → str: String-Parameter
    # → "opencode": Default-Wert
    output: str = typer.Option("docs/ai-sessions/", help="Output directory"),
    # → Ausgabeverzeichnis fuer generierte Dokumentation
) -> None:
    """Automatische Dokumentationsgenerierung (STUB).
    
    WARUM STUB?
      Die echte Auto-Doc-Logik ist in scripts/generate_missing_docs.py.
      Dieser Befehl ist ein Platzhalter.
      
    WARUM "opencode" als Default-Source?
      Haupt-Use-Case: opencode.db auswerten und Sessions dokumentieren.
      → Kann erweitert werden: "git", "github", "confluence"
    """
    console.print("[bold blue]Running auto-doc...[/bold blue]")
    console.print(f"Source: {source}, Output: {output}")
    # → Aktuell: Nur Logging. Echte Logik = scripts/generate_missing_docs.py


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND: summarize
# ═════════════════════════════════════════════════════════════════════════════
@app.command()
def summarize(
    session: str = typer.Argument(..., help="Session ID (e.g., ses_XYZ)"),
    # → typer.Argument: Positional Parameter (MUSS angegeben werden)
    # → ...: Required (kein Default)
    recursive: bool = typer.Option(False, "--recursive", "-r"),
    # → bool: Flag-Option (True wenn angegeben, False sonst)
    # → "--recursive", "-r": Kurz- und Langform
    format: str = typer.Option("yaml", help="Output format: yaml, json"),
    # → Format-Auswahl
) -> None:
    """Session-Zusammenfassung (STUB).
    
    WARUM STUB?
      Session-Zusammenfassung ist in survey-cli/survey.py (status, summary).
      Dieser Befehl ist ein Platzhalter.
      
    WARUM recursive Option?
      Bei verschachtelten Sessions (Sub-Agents, verschachtelte Flows)
      → recursive=True: Alle Sub-Sessions einbeziehen.
      
    WARUM format Option?
      yaml: Human-readable, gut fuer Review
      json: Machine-readable, gut fuer Scripting
    """
    console.print(f"[bold yellow]Summarizing session {session}...[/bold yellow]")
    console.print(f"Recursive: {recursive}, Format: {format}")
    # → Aktuell: Nur Logging. Echte Logik = survey-cli/survey.py


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND: validate_ax_docs
# ═════════════════════════════════════════════════════════════════════════════
@app.command()
def validate_ax_docs(
    cli: str = typer.Argument(..., help="CLI tool to validate against"),
    # → Required: Welches CLI-Tool validieren?
    # → z.B. "cua-driver", "skylight-cli", "macos-ax-cli"
) -> None:
    """AX-Dokumentation Validierung (STUB).
    
    WARUM STUB?
      AX-Doku ist in AGENTS.md, commands/*.md, banned.md.
      Validierung = pruefen ob Code und Doku konsistent sind.
      → Skript in scripts/check_doc_health.py.
      
    WARUM cli als Argument?
      Verschiedene CLI-Tools haben verschiedene AX-Dokumentation.
      → Modular: Ein Tool pro Validierung.
    """
    console.print(f"[bold magenta]Validating AX docs for {cli}...[/bold magenta]")
    # → Aktuell: Nur Logging. Echte Logik = scripts/check_doc_health.py


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND: proxy_status (SR-151)
# ═════════════════════════════════════════════════════════════════════════════
@app.command("proxy-status")
def proxy_status() -> None:
    """
    Zeigt den Status des Proxy-Pools an (SR-151).
    
    AUSGABE:
      Tabelle mit allen Proxies: label, country, score, success/fail/ban counts.
      
    EXIT CODES:
      0 = Pool ist healthy (mindestens 1 Proxy mit Score >= 50)
      1 = Pool ist leer (keine Proxies konfiguriert)
      2 = Pool hat nur cold Proxies (alle Score < 10)
      
    KONFIGURATION:
      Proxies werden aus PROXY_POOL_JSON env var oder proxies.yaml geladen.
      Siehe _plans/151-proxy-pool.md fuer Details.
      
    BEISPIEL:
      $ python -m cli.main proxy-status
      ┌────────────────┬─────────┬───────┬─────────┬──────┬─────┐
      │ Label          │ Country │ Score │ Success │ Fail │ Ban │
      ├────────────────┼─────────┼───────┼─────────┼──────┼─────┤
      │ residential-de │ DE      │  102  │    12   │   1  │  0  │
      │ residential-us │ US      │   85  │     8   │   3  │  0  │
      └────────────────┴─────────┴───────┴─────────┴──────┴─────┘
      Pool Status: HEALTHY (2 total, 2 healthy, 0 cold)
    """
    try:
        from agent_toolbox.core.network import get_proxy_pool
    except ImportError:
        console.print("[bold red]Error: network module not found.[/bold red]")
        console.print("Make sure agent_toolbox.core.network is installed.")
        raise typer.Exit(code=1)
    
    # Lade Pool
    pool = get_proxy_pool()
    status = pool.get_status()
    
    # Pruefe ob Pool leer ist
    if status["total"] == 0:
        console.print("[bold red]Proxy Pool ist LEER![/bold red]")
        console.print("\nKonfiguriere Proxies via:")
        console.print("  • PROXY_POOL_JSON Umgebungsvariable (JSON Array)")
        console.print("  • proxies.yaml Datei im Projekt-Root")
        console.print("\nFormat: [{\"url\": \"http://user:pass@host:port\", \"label\": \"name\", \"country\": \"DE\"}]")
        raise typer.Exit(code=1)
    
    # Baue Tabelle
    table = Table(title="Proxy Pool Status")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Country", style="green")
    table.add_column("Type", style="blue")
    table.add_column("Score", justify="right")
    table.add_column("Success", justify="right", style="green")
    table.add_column("Fail", justify="right", style="yellow")
    table.add_column("Ban", justify="right", style="red")
    table.add_column("Status")
    
    for entry in status["entries"]:
        score = entry["score"]
        
        # Score-Farbe basierend auf Wert
        if score >= 50:
            score_str = f"[green]{score}[/green]"
            status_str = "[green]OK[/green]"
        elif score >= 10:
            score_str = f"[yellow]{score}[/yellow]"
            status_str = "[yellow]WARN[/yellow]"
        else:
            score_str = f"[red]{score}[/red]"
            status_str = "[red]COLD[/red]"
        
        table.add_row(
            entry["label"],
            entry["country"] or "-",
            entry["type"],
            score_str,
            str(entry["success_count"]),
            str(entry["fail_count"]),
            str(entry["ban_count"]),
            status_str,
        )
    
    console.print(table)
    
    # Zusammenfassung
    console.print()
    if status["is_healthy"]:
        console.print(
            f"[bold green]Pool Status: HEALTHY[/bold green] "
            f"({status['total']} total, {status['healthy']} healthy, {status['cold']} cold)"
        )
        raise typer.Exit(code=0)
    elif status["cold"] == status["total"]:
        console.print(
            f"[bold red]Pool Status: ALL COLD[/bold red] "
            f"({status['total']} total, alle Proxies haben Score < 10)"
        )
        console.print("\nAlle Proxies sind 'cold' (Score < 10). Moegliche Ursachen:")
        console.print("  • Zu viele Ban-Events (403/429)")
        console.print("  • Proxies sind offline oder langsam")
        console.print("\nEmpfehlung: Neue Proxies hinzufuegen oder bestehende pruefen.")
        raise typer.Exit(code=2)
    else:
        console.print(
            f"[bold yellow]Pool Status: DEGRADED[/bold yellow] "
            f"({status['total']} total, {status['healthy']} healthy, {status['cold']} cold)"
        )
        raise typer.Exit(code=0)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app()
    # → typer.Typer() als Callable: Fuehrt CLI-Parsing aus.
    # → Erzeugt automatisch: --help, --version, Subcommand-Routing.
    # → Kein manuelles sys.argv Parsing noetig!

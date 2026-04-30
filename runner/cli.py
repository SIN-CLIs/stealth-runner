"""Typer CLI mit Rich Progress für den stealth-runner."""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional
import anyio, typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from runner.state_machine import SurveyRunner

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

@app.command()
def run(
    url: str = typer.Argument(..., help="Umfrage-URL"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Nur loggen, keine echten CLI-Aktionen"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Ausführliche Log-Ausgabe"),
) -> None:
    console.print(f"\n[bold cyan]🚀 stealth-runner v0.3.1[/]")
    if dry_run: console.print("[yellow]⚠️  DRY-RUN[/]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Initialisiere State Machine...", total=None)
        runner = SurveyRunner(url)
        async def run_with_progress():
            await runner.run()
            progress.update(task, description="✅ Fertig")
        anyio.run(run_with_progress)
    console.print("[bold green]✅ Fertig[/]")

@app.command()
def status() -> None:
    audit = Path.home() / ".stealth-runner" / "traces.jsonl"
    if audit.exists():
        lines = sum(1 for _ in open(audit))
        console.print(f"[dim]Audit-Log: {lines} Einträge[/]")
    else: console.print("[dim]Keine laufenden Durchläufe.[/]")

def main_cli() -> None: app()

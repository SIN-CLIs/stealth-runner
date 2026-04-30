from __future__ import annotations
import asyncio, typer
from pathlib import Path
from rich.console import Console
from .config import StealthConfig, SurveyConfig
from .audit_logger import AuditLogger
from .state_machine import AsyncStateMachine, Context

console = Console()
app = typer.Typer(add_completion=False)

@app.command()
def run(url: str = typer.Argument(...), dry_run: bool = False) -> None:
    console.print(f"[bold cyan]🚀 stealth-runner[/] URL: {url}")
    cfg = StealthConfig(dry_run=dry_run)
    survey = SurveyConfig(url=url)
    audit = AuditLogger(Path("audit.jsonl"))
    sm = AsyncStateMachine(Context(cfg=cfg, survey=survey, audit=audit))
    asyncio.run(sm.run())
    console.print("[bold green]✅ Done[/]")

if __name__ == "__main__": app()

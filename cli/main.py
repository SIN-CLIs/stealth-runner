from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Stealth Suite: OpenCode session monitoring & documentation daemon.")
console = Console()


@app.command()
def monitor(
    db_path: Optional[str] = typer.Option(None, help="Path to opencode.db"),
    interval: int = typer.Option(10, help="Polling interval in seconds"),
) -> None:
    console.print("[bold green]Starting stealth-sync monitor...[/bold green]")

    console.print(f"DB: {db_path or '~/.local/share/opencode/opencode.db'}")
    console.print(f"Interval: {interval}s")


@app.command()
def auto_doc(
    source: str = typer.Option("opencode", help="Source: opencode"),
    output: str = typer.Option("docs/ai-sessions/", help="Output directory"),
) -> None:
    console.print("[bold blue]Running auto-doc...[/bold blue]")
    console.print(f"Source: {source}, Output: {output}")


@app.command()
def summarize(
    session: str = typer.Argument(..., help="Session ID (e.g., ses_XYZ)"),
    recursive: bool = typer.Option(False, "--recursive", "-r"),
    format: str = typer.Option("yaml", help="Output format: yaml, json"),
) -> None:
    console.print(f"[bold yellow]Summarizing session {session}...[/bold yellow]")
    console.print(f"Recursive: {recursive}, Format: {format}")


@app.command()
def validate_ax_docs(
    cli: str = typer.Argument(..., help="CLI tool to validate against"),
) -> None:
    console.print(f"[bold magenta]Validating AX docs for {cli}...[/bold magenta]")


if __name__ == "__main__":
    app()

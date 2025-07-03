"""Version command for LocalPort CLI."""

import typer
from rich.console import Console

from localport import __version__

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"LocalPort version: [bold green]{__version__}[/bold green]")
        console.print("🚀 Universal port forwarding manager with health monitoring")
        raise typer.Exit()

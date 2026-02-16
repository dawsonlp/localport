"""Version command for LocalPort CLI."""

import typer
from ..utils.cli_context import LazyConsole

from localport import __version__

console = LazyConsole()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"LocalPort version: [bold green]{__version__}[/bold green]")
        console.print("🚀 Universal port forwarding manager with health monitoring")
        raise typer.Exit()

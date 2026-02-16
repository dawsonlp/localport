"""CLI context helper for consistent global option propagation."""

import os
from dataclasses import dataclass, field

import typer
from rich.console import Console

from ..formatters.output_format import OutputFormat


def get_console() -> Console:
    """Return a Console that respects the NO_COLOR environment variable.
    
    Command modules should call this instead of creating a module-level
    ``Console()`` so that the ``--no-color`` global flag (which sets
    ``os.environ["NO_COLOR"]``) is honoured even though the flag is
    processed after module import.
    """
    return Console(no_color=bool(os.environ.get("NO_COLOR")))


class LazyConsole:
    """Drop-in module-level replacement for ``Console()`` that respects
    ``NO_COLOR`` at call time rather than at import time.

    Usage in command modules::

        from ..utils.cli_context import LazyConsole
        console = LazyConsole()

    Every attribute access (e.g. ``console.print(...)``) delegates to a
    fresh ``Console`` that honours the current ``NO_COLOR`` env var.
    """

    def __getattr__(self, name: str):
        return getattr(get_console(), name)


@dataclass
class CLIContext:
    """Encapsulates all global CLI options from the Typer context.
    
    Provides a single, consistent interface for subcommands to access
    global options set in the main callback (--config, --verbose, --quiet,
    --log-level, --no-color, --output).
    """
    config_file: str | None = None
    verbose: bool = False
    verbosity_level: int = 0
    quiet: bool = False
    log_level: str = "INFO"
    no_color: bool = False
    output_format: OutputFormat = OutputFormat.TABLE
    console: Console = field(default_factory=Console)

    @property
    def is_debug(self) -> bool:
        """Check if debug-level verbosity is active."""
        return self.verbosity_level >= 2

    @property
    def is_silent(self) -> bool:
        """Check if quiet mode suppresses non-essential output."""
        return self.quiet


def get_cli_context(ctx: typer.Context) -> CLIContext:
    """Extract global CLI options from a Typer Context into a CLIContext.
    
    This function reads the ctx.obj dictionary populated by the main
    app callback and returns a structured CLIContext object. If ctx.obj
    is not initialised (e.g. during testing), sensible defaults are used.
    
    Args:
        ctx: The Typer Context passed into a command function.
        
    Returns:
        A CLIContext with all global options resolved.
    """
    obj = ctx.obj if ctx.obj else {}

    # Resolve console — the main callback stores a no-color-aware Console
    console = obj.get("console", Console())

    # Resolve output format — may be an OutputFormat enum or a string
    raw_format = obj.get("output_format", OutputFormat.TABLE)
    if isinstance(raw_format, str):
        try:
            output_format = OutputFormat.from_string(raw_format)
        except (ValueError, AttributeError):
            output_format = OutputFormat.TABLE
    else:
        output_format = raw_format

    return CLIContext(
        config_file=obj.get("config_file"),
        verbose=obj.get("verbose", False),
        verbosity_level=obj.get("verbosity_level", 0),
        quiet=obj.get("quiet", False),
        log_level=obj.get("log_level", "INFO"),
        no_color=obj.get("no_color", False),
        output_format=output_format,
        console=console,
    )
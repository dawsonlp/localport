"""Main entry point for LocalPort CLI application."""

import sys

from rich.console import Console

from .cli.app import cli_main

console = Console()


def main() -> None:
    """Main entry point for the LocalPort CLI."""
    try:
        # Run the CLI application
        cli_main()

    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()

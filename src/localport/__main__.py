"""Entry point for running LocalPort as a module."""

import sys

from .daemon import main

if __name__ == "__main__":
    # Check if we're being called as 'python -m localport.daemon'
    if len(sys.argv) > 0 and sys.argv[0].endswith('daemon'):
        main()
    else:
        # Default to CLI app
        from .cli.app import app
        app()

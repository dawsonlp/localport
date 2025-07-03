"""LocalPort - Universal port forwarding manager with health monitoring."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("localport")
except importlib.metadata.PackageNotFoundError:
    # Fallback for development/editable installs
    __version__ = "0.0.0+dev"

__author__ = "LocalPort Team"
__email__ = "contact@localport.dev"
__description__ = "Universal port forwarding manager with health monitoring"

# Package metadata
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__"
]

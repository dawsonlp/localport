"""LocalPort - Universal port forwarding manager with health monitoring."""

import importlib.metadata

try:
    # Get the raw version from package metadata to preserve pre-release identifiers
    _dist = importlib.metadata.distribution("localport")
    __version__ = _dist.metadata["Version"]
except (importlib.metadata.PackageNotFoundError, KeyError):
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

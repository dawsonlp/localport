"""Settings and configuration management for LocalPort CLI."""

import os
from pathlib import Path

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class Settings(BaseSettings):
    """Global settings for LocalPort CLI application."""

    # CLI Configuration
    config_file: str | None = Field(
        default=None,
        description="Path to configuration file"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    quiet: bool = Field(
        default=False,
        description="Suppress non-essential output"
    )
    no_color: bool = Field(
        default=False,
        description="Disable colored output"
    )

    # Configuration file discovery paths
    config_search_paths: list[str] = Field(
        default_factory=lambda: [
            "./localport.yaml",
            "./localport.yml",
            "~/.config/localport/config.yaml",
            "~/.config/localport/config.yml",
            "/etc/localport/config.yaml",
            "/etc/localport/config.yml"
        ],
        description="Paths to search for configuration files"
    )

    # Runtime directories
    runtime_dir: str | None = Field(
        default=None,
        description="Runtime directory for PID files, logs, etc."
    )

    class Config:
        """Pydantic configuration."""
        env_prefix = "LOCALPORT_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        """Initialize settings with runtime directory setup."""
        super().__init__(**kwargs)

        # Set up runtime directory
        if not self.runtime_dir:
            self.runtime_dir = self._get_default_runtime_dir()

        # Ensure runtime directory exists
        runtime_path = Path(self.runtime_dir)
        runtime_path.mkdir(parents=True, exist_ok=True)

        logger.debug("Settings initialized",
                    config_file=self.config_file,
                    log_level=self.log_level,
                    runtime_dir=self.runtime_dir)

    def _get_default_runtime_dir(self) -> str:
        """Get the default runtime directory based on the platform."""
        if os.name == 'nt':  # Windows
            # Use AppData/Local for Windows
            app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
            return os.path.join(app_data, 'LocalPort')
        else:  # Unix-like systems
            # Use XDG_RUNTIME_DIR if available, otherwise ~/.local/share
            xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
            if xdg_runtime:
                return os.path.join(xdg_runtime, 'localport')
            else:
                return os.path.expanduser('~/.local/share/localport')

    def get_config_file_path(self) -> Path | None:
        """Get the configuration file path, searching default locations if not specified."""
        if self.config_file:
            # Use explicitly specified config file
            config_path = Path(self.config_file).expanduser().resolve()
            if config_path.exists():
                return config_path
            else:
                logger.warning("Specified config file not found", path=str(config_path))
                return None

        # Search default locations
        for search_path in self.config_search_paths:
            config_path = Path(search_path).expanduser().resolve()
            if config_path.exists():
                logger.debug("Found config file", path=str(config_path))
                return config_path

        logger.debug("No configuration file found in search paths")
        return None

    def get_pid_file_path(self) -> Path:
        """Get the path for the daemon PID file."""
        return Path(self.runtime_dir) / "localport.pid"

    def get_log_file_path(self) -> Path:
        """Get the path for the log file."""
        return Path(self.runtime_dir) / "localport.log"

    def get_socket_path(self) -> Path:
        """Get the path for the daemon socket."""
        return Path(self.runtime_dir) / "localport.sock"


# Global settings instance (will be initialized by CLI)
settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings

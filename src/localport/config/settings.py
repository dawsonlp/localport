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

    # Service Logging Configuration
    service_logging_enabled: bool = Field(
        default=True,
        description="Enable service logging (captures kubectl/ssh output)"
    )
    service_log_retention_days: int = Field(
        default=3,
        description="Number of days to retain service logs"
    )
    service_log_rotation_size_mb: int = Field(
        default=10,
        description="Size in MB at which to rotate service logs"
    )
    service_log_directory: str | None = Field(
        default=None,
        description="Custom directory for service logs (default: runtime_dir/logs/services)"
    )
    service_log_buffer_size: int = Field(
        default=8192,
        description="Buffer size for service log writes (bytes)"
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

    def get_service_log_directory(self) -> Path:
        """Get the directory for service logs."""
        if self.service_log_directory:
            return Path(self.service_log_directory).expanduser().resolve()
        else:
            return Path(self.runtime_dir) / "logs" / "services"

    def get_daemon_log_directory(self) -> Path:
        """Get the directory for daemon logs."""
        return Path(self.runtime_dir) / "logs"

    def get_daemon_log_file_path(self) -> Path:
        """Get the path for the daemon log file."""
        return self.get_daemon_log_directory() / "daemon.log"

    def is_service_logging_enabled(self) -> bool:
        """Check if service logging is enabled."""
        return self.service_logging_enabled

    def get_service_log_retention_seconds(self) -> int:
        """Get service log retention period in seconds."""
        return self.service_log_retention_days * 24 * 60 * 60

    def get_service_log_rotation_size_bytes(self) -> int:
        """Get service log rotation size in bytes."""
        return self.service_log_rotation_size_mb * 1024 * 1024


# Global settings instance (will be initialized by CLI)
settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings

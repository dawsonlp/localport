"""Configuration repository interface for loading and managing configuration."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..entities.service import Service


class ConfigRepository(ABC):
    """Repository interface for configuration management."""

    @abstractmethod
    async def load_configuration(self, config_path: Path | None = None) -> dict[str, Any]:
        """Load configuration from file or default locations.

        Args:
            config_path: Optional path to configuration file

        Returns:
            Dictionary containing the loaded configuration

        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        pass

    @abstractmethod
    async def save_configuration(self, config: dict[str, Any], config_path: Path) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save
            config_path: Path where to save the configuration

        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        pass

    @abstractmethod
    async def load_services(self, config_path: Path | None = None) -> list[Service]:
        """Load services from configuration.

        Args:
            config_path: Optional path to configuration file

        Returns:
            List of services loaded from configuration

        Raises:
            ConfigurationError: If services cannot be loaded or are invalid
        """
        pass

    @abstractmethod
    async def validate_configuration(self, config: dict[str, Any]) -> bool:
        """Validate configuration structure and values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if configuration is valid

        Raises:
            ConfigurationError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def get_default_config_paths(self) -> list[Path]:
        """Get list of default configuration file paths to search.

        Returns:
            List of paths in order of preference
        """
        pass

    @abstractmethod
    async def find_config_file(self) -> Path | None:
        """Find the first existing configuration file in default locations.

        Returns:
            Path to configuration file if found, None otherwise
        """
        pass

    @abstractmethod
    async def substitute_environment_variables(self, config: dict[str, Any]) -> dict[str, Any]:
        """Substitute environment variables in configuration.

        Args:
            config: Configuration dictionary with potential environment variables

        Returns:
            Configuration with environment variables substituted

        Raises:
            ConfigurationError: If required environment variables are missing
        """
        pass

    @abstractmethod
    async def add_service_config(self, service: dict[str, Any]) -> None:
        """Add a new service configuration to the configuration file.
        
        Args:
            service: Service configuration dictionary to add
            
        Raises:
            ConfigurationError: If service cannot be added or configuration is invalid
            ServiceAlreadyExistsError: If a service with the same name already exists
        """
        pass

    @abstractmethod
    async def remove_service_config(self, service_name: str) -> bool:
        """Remove a service configuration from the configuration file.
        
        Args:
            service_name: Name of the service to remove
            
        Returns:
            True if service was removed, False if service was not found
            
        Raises:
            ConfigurationError: If there's an error updating the configuration
        """
        pass

    @abstractmethod
    async def get_service_names(self) -> list[str]:
        """Get the names of all configured services.
        
        Returns:
            List of service names from the configuration
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        pass

    @abstractmethod
    async def service_exists(self, service_name: str) -> bool:
        """Check if a service with the given name exists in the configuration.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if service exists, False otherwise
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        pass

    @abstractmethod
    async def get_service_config(self, service_name: str) -> dict[str, Any] | None:
        """Get the configuration for a specific service.
        
        Args:
            service_name: Name of the service to get configuration for
            
        Returns:
            Service configuration dictionary, or None if service not found
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        pass

    @abstractmethod
    async def update_service_config(self, service_name: str, service: dict[str, Any]) -> bool:
        """Update an existing service configuration.
        
        Args:
            service_name: Name of the service to update
            service: Updated service configuration dictionary
            
        Returns:
            True if service was updated, False if service was not found
            
        Raises:
            ConfigurationError: If there's an error updating the configuration
        """
        pass

    @abstractmethod
    async def backup_configuration(self, backup_path: str | None = None) -> str:
        """Create a backup of the current configuration file.
        
        Args:
            backup_path: Optional path for backup file (auto-generated if None)
            
        Returns:
            Path to the created backup file
            
        Raises:
            ConfigurationError: If backup cannot be created
        """
        pass

    @abstractmethod
    async def get_configuration_path(self) -> Path:
        """Get the path to the currently active configuration file.
        
        Returns:
            Path to the configuration file being used
        """
        pass


class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when configuration file is not found."""

    def __init__(self, config_path: Path | None = None):
        if config_path:
            message = f"Configuration file not found: {config_path}"
        else:
            message = "No configuration file found in default locations"
        super().__init__(message)
        self.config_path = config_path


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing."""

    def __init__(self, variable_name: str):
        super().__init__(f"Required environment variable not found: {variable_name}")
        self.variable_name = variable_name

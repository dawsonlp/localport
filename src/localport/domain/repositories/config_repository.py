"""Configuration repository interface for loading and managing configuration."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..entities.service import Service


class ConfigRepository(ABC):
    """Repository interface for configuration management."""
    
    @abstractmethod
    async def load_configuration(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
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
    async def save_configuration(self, config: Dict[str, Any], config_path: Path) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
            config_path: Path where to save the configuration
            
        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        pass
    
    @abstractmethod
    async def load_services(self, config_path: Optional[Path] = None) -> List[Service]:
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
    async def validate_configuration(self, config: Dict[str, Any]) -> bool:
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
    async def get_default_config_paths(self) -> List[Path]:
        """Get list of default configuration file paths to search.
        
        Returns:
            List of paths in order of preference
        """
        pass
    
    @abstractmethod
    async def find_config_file(self) -> Optional[Path]:
        """Find the first existing configuration file in default locations.
        
        Returns:
            Path to configuration file if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def substitute_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute environment variables in configuration.
        
        Args:
            config: Configuration dictionary with potential environment variables
            
        Returns:
            Configuration with environment variables substituted
            
        Raises:
            ConfigurationError: If required environment variables are missing
        """
        pass


class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when configuration file is not found."""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path:
            message = f"Configuration file not found: {config_path}"
        else:
            message = "No configuration file found in default locations"
        super().__init__(message)
        self.config_path = config_path


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing."""
    
    def __init__(self, variable_name: str):
        super().__init__(f"Required environment variable not found: {variable_name}")
        self.variable_name = variable_name

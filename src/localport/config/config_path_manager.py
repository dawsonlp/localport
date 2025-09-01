"""Centralized configuration path management for LocalPort."""

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ConfigFile:
    """Represents a configuration file with its metadata."""
    path: Path
    exists: bool
    size: Optional[int] = None
    modified: Optional[datetime] = None
    readable: bool = False
    service_count: Optional[int] = None
    is_active: bool = False

    @classmethod
    def from_path(cls, path: Path, is_active: bool = False) -> "ConfigFile":
        """Create ConfigFile instance from a path."""
        config_file = cls(path=path, exists=path.exists(), is_active=is_active)
        
        if config_file.exists:
            try:
                stat_result = path.stat()
                config_file.size = stat_result.st_size
                config_file.modified = datetime.fromtimestamp(stat_result.st_mtime)
                config_file.readable = os.access(path, os.R_OK)
            except (OSError, PermissionError) as e:
                logger.warning("Failed to get file metadata", path=str(path), error=str(e))
                config_file.readable = False
                
        return config_file

    def format_size(self) -> str:
        """Format file size in human-readable format."""
        if not self.exists or self.size is None:
            return ""
        
        if self.size < 1024:
            return f"{self.size}B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f}KB"
        else:
            return f"{self.size / (1024 * 1024):.1f}MB"

    def format_status(self) -> str:
        """Format file status for display."""
        if not self.exists:
            return "not found"
        elif not self.readable:
            return "permission denied"
        elif self.is_active and self.service_count is not None:
            size_str = self.format_size()
            parts = [f"active, {self.service_count} services"]
            if size_str:
                parts.append(size_str)
            return f"({', '.join(parts)})"
        elif self.is_active:
            size_str = self.format_size()
            parts = ["active"]
            if size_str:
                parts.append(size_str)
            return f"({', '.join(parts)})"
        else:
            return f"found, {self.format_size()}" if self.format_size() else "found"


class ConfigPathManager:
    """Manages configuration file paths and discovery for LocalPort."""

    @staticmethod
    def get_default_search_paths() -> List[Path]:
        """Get the default search paths for configuration files in priority order.
        
        Returns:
            List of Path objects in search priority order
        """
        return [
            Path.cwd() / "localport.yaml",
            Path.cwd() / "localport.yml", 
            Path.cwd() / ".localport.yaml",
            Path.home() / ".localport.yaml",
            Path.home() / ".config" / "localport" / "config.yaml",
            Path("/etc/localport/config.yaml"),
        ]

    @staticmethod
    def find_active_config(config_path: Optional[str] = None) -> Optional[ConfigFile]:
        """Find the active configuration file.
        
        Args:
            config_path: Optional explicit config path to use
            
        Returns:
            ConfigFile instance for the active config, or None if not found
        """
        if config_path:
            # Explicit config path provided
            path = Path(config_path).expanduser().resolve()
            return ConfigFile.from_path(path, is_active=True)
        
        # Search default paths
        search_paths = ConfigPathManager.get_default_search_paths()
        for path in search_paths:
            expanded_path = path.expanduser().resolve()
            if expanded_path.exists():
                logger.info("Found active configuration file", path=str(expanded_path))
                return ConfigFile.from_path(expanded_path, is_active=True)
        
        logger.debug("No configuration file found in default locations")
        return None

    @staticmethod
    def get_all_config_files(config_path: Optional[str] = None) -> List[ConfigFile]:
        """Get all configuration files with their status.
        
        Args:
            config_path: Optional explicit config path to use
            
        Returns:
            List of ConfigFile instances for all search paths
        """
        active_config = ConfigPathManager.find_active_config(config_path)
        active_path = active_config.path if active_config else None
        
        config_files = []
        search_paths = ConfigPathManager.get_default_search_paths()
        
        for path in search_paths:
            expanded_path = path.expanduser().resolve()
            is_active = active_path and expanded_path == active_path
            config_file = ConfigFile.from_path(expanded_path, is_active=is_active)
            config_files.append(config_file)
            
        return config_files

    @staticmethod
    async def get_service_count(config_file: ConfigFile) -> int:
        """Get the number of services in a configuration file.
        
        Args:
            config_file: ConfigFile instance to analyze
            
        Returns:
            Number of services, or 0 if file can't be read
        """
        if not config_file.exists or not config_file.readable:
            return 0
            
        try:
            import yaml
            with open(config_file.path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                services = config.get('services', [])
                return len(services)
        except Exception as e:
            logger.warning("Failed to count services in config file", 
                          path=str(config_file.path), error=str(e))
            return 0

    @staticmethod
    async def format_config_status(config_path: Optional[str] = None, show_all_paths: bool = True) -> str:
        """Format configuration status for display.
        
        Args:
            config_path: Optional explicit config path
            show_all_paths: Whether to show all search paths or just active
            
        Returns:
            Formatted configuration status string
        """
        config_files = ConfigPathManager.get_all_config_files(config_path)
        
        # Update service counts for existing files
        for config_file in config_files:
            if config_file.exists and config_file.readable:
                config_file.service_count = await ConfigPathManager.get_service_count(config_file)
        
        if not show_all_paths:
            # Show only active config
            active_config = next((cf for cf in config_files if cf.is_active), None)
            if active_config:
                return f"Current config: {active_config.path} {active_config.format_status()}"
            else:
                return "No configuration file found"
        
        # Show all search paths
        lines = []
        for config_file in config_files:
            marker = "* " if config_file.is_active else "  "
            status = config_file.format_status()
            path_str = str(config_file.path)
            
            # Shorten home directory paths for display
            if path_str.startswith(str(Path.home())):
                path_str = path_str.replace(str(Path.home()), "~", 1)
                
            line = f"{marker}{path_str}"
            if status and status != "not found":
                line += f" ({status})"
            elif not config_file.exists:
                line += " (not found)"
                
            lines.append(line)
        
        return "\n".join(lines)

    @staticmethod
    async def format_search_paths_with_status(config_path: Optional[str] = None) -> str:
        """Format search paths with existence indicators for error messages.
        
        Args:
            config_path: Optional explicit config path
            
        Returns:
            Formatted search paths with ✓/✗ indicators
        """
        config_files = ConfigPathManager.get_all_config_files(config_path)
        
        lines = []
        for config_file in config_files:
            indicator = "✓" if config_file.exists else "✗"
            path_str = str(config_file.path)
            
            # Shorten home directory paths for display
            if path_str.startswith(str(Path.home())):
                path_str = path_str.replace(str(Path.home()), "~", 1)
                
            lines.append(f"  {indicator} {path_str}")
        
        return "\n".join(lines)

    @staticmethod
    def create_default_config_content() -> dict:
        """Create default configuration content for new config files.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'version': '1.0',
            'services': [],
            'defaults': {
                'health_check': {
                    'type': 'tcp',
                    'interval': 30,
                    'timeout': 5.0,
                    'failure_threshold': 3,
                    'success_threshold': 1,
                    'cluster_aware': True
                },
                'restart_policy': {
                    'enabled': True,
                    'max_attempts': 5,
                    'backoff_multiplier': 2.0,
                    'initial_delay': 1,
                    'max_delay': 300
                },
                'cluster_health': {
                    'enabled': True,
                    'interval': 240,
                    'timeout': 30,
                    'retry_attempts': 2,
                    'failure_threshold': 3,
                    'commands': {
                        'cluster_info': True,
                        'pod_status': True,
                        'node_status': True,
                        'events_on_failure': True
                    }
                }
            }
        }

    @staticmethod
    async def ensure_config_directory(config_path: Path) -> None:
        """Ensure the directory for a config file exists.
        
        Args:
            config_path: Path to the configuration file
        """
        config_dir = config_path.parent
        if not config_dir.exists():
            logger.info("Creating configuration directory", path=str(config_dir))
            config_dir.mkdir(parents=True, exist_ok=True)

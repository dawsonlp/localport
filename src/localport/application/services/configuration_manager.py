"""Configuration management service with hot reloading capabilities."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

from ...domain.repositories.config_repository import ConfigRepository
from ...domain.repositories.service_repository import ServiceRepository
from .configuration_differ import ConfigurationDiff, ConfigurationDiffer
from .configuration_watcher import ConfigurationWatcher, PollingConfigurationWatcher

logger = structlog.get_logger()


class ConfigurationManager:
    """Manages configuration with hot reloading capabilities."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        service_repository: ServiceRepository,
        use_polling: bool = False,
        poll_interval: float = 2.0
    ):
        """Initialize the configuration manager.

        Args:
            config_repository: Repository for configuration management
            service_repository: Repository for service persistence
            use_polling: Whether to use polling instead of file watching
            poll_interval: Polling interval in seconds (if using polling)
        """
        self._config_repository = config_repository
        self._service_repository = service_repository
        self._differ = ConfigurationDiffer()

        # Choose watcher implementation
        if use_polling:
            self._watcher = PollingConfigurationWatcher(poll_interval)
        else:
            self._watcher = ConfigurationWatcher()
            # Fallback to polling if watchdog not available
            if not getattr(self._watcher, 'watchdog_available', True):
                logger.info("Falling back to polling configuration watcher")
                self._watcher = PollingConfigurationWatcher(poll_interval)

        # State
        self._current_config: dict[str, Any] | None = None
        self._config_path: Path | None = None
        self._is_watching = False
        self._reload_callbacks: list[Callable[[ConfigurationDiff], None]] = []
        self._validation_enabled = True
        self._auto_rollback = True
        self._backup_config: dict[str, Any] | None = None

    async def start_hot_reloading(
        self,
        config_path: Path | None = None,
        reload_callback: Callable[[ConfigurationDiff], None] | None = None
    ) -> bool:
        """Start hot reloading for configuration changes.

        Args:
            config_path: Path to configuration file (auto-detected if None)
            reload_callback: Callback to call when configuration changes

        Returns:
            True if hot reloading started successfully
        """
        if self._is_watching:
            logger.warning("Configuration hot reloading is already active")
            return True

        try:
            # Determine configuration file path
            if config_path is None:
                config_path = await self._config_repository.find_config_file()
                if config_path is None:
                    logger.warning("No configuration file found for hot reloading")
                    return False

            self._config_path = config_path

            # Load initial configuration
            await self._load_initial_configuration()

            # Add reload callback if provided
            if reload_callback:
                self.add_reload_callback(reload_callback)

            # Start watching for changes
            success = await self._watcher.start_watching(
                config_path,
                self._handle_config_change
            )

            if success:
                self._is_watching = True
                logger.info("Configuration hot reloading started",
                          config_path=str(config_path),
                          watcher_type=type(self._watcher).__name__)
                return True
            else:
                logger.error("Failed to start configuration watching")
                return False

        except Exception as e:
            logger.error("Failed to start configuration hot reloading", error=str(e))
            return False

    async def stop_hot_reloading(self) -> None:
        """Stop hot reloading."""
        if not self._is_watching:
            return

        try:
            await self._watcher.stop_watching()
            self._is_watching = False
            self._config_path = None
            logger.info("Configuration hot reloading stopped")

        except Exception as e:
            logger.error("Error stopping configuration hot reloading", error=str(e))

    def add_reload_callback(self, callback: Callable[[ConfigurationDiff], None]) -> None:
        """Add a callback to be called when configuration reloads.

        Args:
            callback: Function to call with configuration diff
        """
        if callback not in self._reload_callbacks:
            self._reload_callbacks.append(callback)
            logger.debug("Added configuration reload callback")

    def remove_reload_callback(self, callback: Callable[[ConfigurationDiff], None]) -> None:
        """Remove a reload callback.

        Args:
            callback: Function to remove
        """
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)
            logger.debug("Removed configuration reload callback")

    async def reload_configuration(self, force: bool = False) -> ConfigurationDiff | None:
        """Manually reload configuration.

        Args:
            force: Whether to force reload even if file hasn't changed

        Returns:
            Configuration diff if changes were detected, None otherwise
        """
        if not self._config_path:
            logger.warning("No configuration path set for reload")
            return None

        try:
            logger.info("Manually reloading configuration", force=force)
            return await self._reload_config_internal(force=force)

        except Exception as e:
            logger.error("Failed to manually reload configuration", error=str(e))
            return None

    def _handle_config_change(self, config_path: Path) -> None:
        """Handle configuration file change event.

        Args:
            config_path: Path to changed configuration file
        """
        logger.info("Configuration file changed", path=str(config_path))

        # Schedule async reload
        asyncio.create_task(self._reload_config_internal())

    async def _reload_config_internal(self, force: bool = False) -> ConfigurationDiff | None:
        """Internal method to reload configuration.

        Args:
            force: Whether to force reload

        Returns:
            Configuration diff if changes detected
        """
        try:
            # Load new configuration
            new_config = await self._config_repository.load_configuration()

            # Compare with current configuration
            if self._current_config is None or force:
                # First load or forced reload
                self._current_config = new_config
                logger.info("Configuration loaded",
                          services_count=len(new_config.get('services', [])))
                return None

            # Compare configurations
            diff = await self._differ.compare_configurations(
                self._current_config,
                new_config
            )

            if not diff.has_changes and not force:
                logger.debug("No configuration changes detected")
                return None

            # Validate new configuration if enabled
            if self._validation_enabled:
                validation_errors = await self._config_repository.validate_configuration(new_config)
                if validation_errors:
                    logger.error("Configuration validation failed",
                               errors=validation_errors)

                    if self._auto_rollback:
                        logger.info("Auto-rollback enabled, keeping current configuration")
                        return None
                    else:
                        # Continue with invalid configuration (risky)
                        logger.warning("Proceeding with invalid configuration")

            # Backup current configuration before applying changes
            self._backup_config = self._current_config.copy()

            # Apply new configuration
            self._current_config = new_config

            # Log changes
            if diff.has_changes:
                summary = self._differ.format_diff_summary(diff)
                logger.info("Configuration changes detected", summary=summary)

                if logger.isEnabledFor(structlog.DEBUG):
                    detailed_diff = self._differ.format_detailed_diff(diff)
                    logger.debug("Detailed configuration diff", diff=detailed_diff)

            # Notify callbacks
            await self._notify_reload_callbacks(diff)

            return diff

        except Exception as e:
            logger.error("Error during configuration reload", error=str(e))

            # Attempt rollback if auto-rollback is enabled
            if self._auto_rollback and self._backup_config:
                logger.info("Attempting configuration rollback")
                try:
                    self._current_config = self._backup_config
                    logger.info("Configuration rollback successful")
                except Exception as rollback_error:
                    logger.error("Configuration rollback failed", error=str(rollback_error))

            return None

    async def _load_initial_configuration(self) -> None:
        """Load initial configuration."""
        try:
            self._current_config = await self._config_repository.load_configuration()
            logger.info("Initial configuration loaded",
                       services_count=len(self._current_config.get('services', [])))

        except Exception as e:
            logger.error("Failed to load initial configuration", error=str(e))
            raise

    async def _notify_reload_callbacks(self, diff: ConfigurationDiff) -> None:
        """Notify all reload callbacks about configuration changes.

        Args:
            diff: Configuration diff
        """
        if not self._reload_callbacks:
            return

        logger.debug("Notifying configuration reload callbacks",
                    callback_count=len(self._reload_callbacks))

        for callback in self._reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(diff)
                else:
                    callback(diff)
            except Exception as e:
                logger.error("Error in configuration reload callback", error=str(e))

    async def get_current_configuration(self) -> dict[str, Any] | None:
        """Get the current configuration.

        Returns:
            Current configuration dictionary
        """
        return self._current_config.copy() if self._current_config else None

    async def validate_current_configuration(self) -> list[str]:
        """Validate the current configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        if not self._current_config:
            return ["No configuration loaded"]

        return await self._config_repository.validate_configuration(self._current_config)

    async def backup_current_configuration(self, backup_path: str | None = None) -> str | None:
        """Create a backup of the current configuration.

        Args:
            backup_path: Path for backup file (auto-generated if None)

        Returns:
            Path to backup file if successful
        """
        if not self._config_path:
            logger.warning("No configuration path available for backup")
            return None

        try:
            backup_file = await self._config_repository.backup_configuration(backup_path)
            logger.info("Configuration backup created", backup_file=backup_file)
            return backup_file

        except Exception as e:
            logger.error("Failed to create configuration backup", error=str(e))
            return None

    def set_validation_enabled(self, enabled: bool) -> None:
        """Enable or disable configuration validation.

        Args:
            enabled: Whether to enable validation
        """
        self._validation_enabled = enabled
        logger.info("Configuration validation updated", enabled=enabled)

    def set_auto_rollback(self, enabled: bool) -> None:
        """Enable or disable automatic rollback on validation failure.

        Args:
            enabled: Whether to enable auto-rollback
        """
        self._auto_rollback = enabled
        logger.info("Configuration auto-rollback updated", enabled=enabled)

    @property
    def is_watching(self) -> bool:
        """Check if configuration hot reloading is active."""
        return self._is_watching

    @property
    def config_path(self) -> Path | None:
        """Get the current configuration file path."""
        return self._config_path

    @property
    def watcher_type(self) -> str:
        """Get the type of configuration watcher being used."""
        return type(self._watcher).__name__

    @property
    def watched_files(self) -> set:
        """Get set of currently watched configuration files."""
        return getattr(self._watcher, 'watched_files', set())

    async def get_configuration_status(self) -> dict[str, Any]:
        """Get comprehensive configuration management status.

        Returns:
            Status information dictionary
        """
        status = {
            'hot_reloading_active': self._is_watching,
            'config_path': str(self._config_path) if self._config_path else None,
            'watcher_type': self.watcher_type,
            'watched_files': [str(f) for f in self.watched_files],
            'validation_enabled': self._validation_enabled,
            'auto_rollback_enabled': self._auto_rollback,
            'callback_count': len(self._reload_callbacks),
            'has_current_config': self._current_config is not None,
            'has_backup_config': self._backup_config is not None
        }

        if self._current_config:
            status['services_count'] = len(self._current_config.get('services', []))
            status['config_version'] = self._current_config.get('version')

        return status

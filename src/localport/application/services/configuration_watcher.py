"""Configuration file watcher for hot reloading capabilities."""

import asyncio
from collections.abc import Callable
from pathlib import Path

import structlog

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Create a dummy base class when watchdog is not available
    class FileSystemEventHandler:
        def __init__(self):
            pass

logger = structlog.get_logger()


class ConfigurationFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""

    def __init__(self, config_path: Path, callback: Callable[[Path], None]):
        """Initialize the file handler.

        Args:
            config_path: Path to configuration file to watch
            callback: Callback function to call on file changes
        """
        super().__init__()
        self.config_path = config_path.resolve()
        self.callback = callback
        self._debounce_delay = 1.0  # seconds
        self._pending_changes: set[Path] = set()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        event_path = Path(event.src_path).resolve()

        # Check if this is our configuration file
        if event_path == self.config_path:
            logger.debug("Configuration file modified", path=str(event_path))

            # Debounce rapid file changes
            if event_path not in self._pending_changes:
                self._pending_changes.add(event_path)
                asyncio.create_task(self._debounced_callback(event_path))

    async def _debounced_callback(self, path: Path):
        """Debounced callback to prevent rapid-fire reloads."""
        await asyncio.sleep(self._debounce_delay)

        if path in self._pending_changes:
            self._pending_changes.remove(path)

            try:
                self.callback(path)
            except Exception as e:
                logger.error("Error in configuration change callback",
                           path=str(path), error=str(e))


class ConfigurationWatcher:
    """Watches configuration files for changes and triggers hot reloads."""

    def __init__(self):
        """Initialize the configuration watcher."""
        self._observer: Observer | None = None
        self._watched_paths: set[Path] = set()
        self._handlers: dict[Path, ConfigurationFileHandler] = {}
        self._is_watching = False


    async def start_watching(self, config_path: Path, callback: Callable[[Path], None]) -> bool:
        """Start watching a configuration file for changes.

        Args:
            config_path: Path to configuration file to watch
            callback: Callback function to call on file changes

        Returns:
            True if watching started successfully, False otherwise
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning("Cannot start configuration watching - watchdog not available")
            return False

        if not config_path.exists():
            logger.warning("Configuration file does not exist, cannot watch",
                         path=str(config_path))
            return False

        config_path = config_path.resolve()

        try:
            # Create observer if not exists
            if self._observer is None:
                self._observer = Observer()

            # Create file handler
            handler = ConfigurationFileHandler(config_path, callback)
            self._handlers[config_path] = handler

            # Watch the directory containing the config file
            watch_dir = config_path.parent
            self._observer.schedule(handler, str(watch_dir), recursive=False)

            # Start observer if not already running
            if not self._is_watching:
                self._observer.start()
                self._is_watching = True
                logger.info("Configuration watcher started")

            self._watched_paths.add(config_path)
            logger.info("Started watching configuration file", path=str(config_path))

            return True

        except Exception as e:
            logger.error("Failed to start configuration watching",
                        path=str(config_path), error=str(e))
            return False

    async def stop_watching(self, config_path: Path | None = None) -> None:
        """Stop watching configuration file(s).

        Args:
            config_path: Specific path to stop watching, or None to stop all
        """
        if not WATCHDOG_AVAILABLE or not self._observer:
            return

        try:
            if config_path:
                # Stop watching specific file
                config_path = config_path.resolve()
                if config_path in self._watched_paths:
                    self._watched_paths.remove(config_path)
                    if config_path in self._handlers:
                        del self._handlers[config_path]
                    logger.info("Stopped watching configuration file", path=str(config_path))
            else:
                # Stop watching all files
                self._watched_paths.clear()
                self._handlers.clear()

                if self._is_watching:
                    self._observer.stop()
                    self._observer.join(timeout=5.0)
                    self._is_watching = False
                    logger.info("Configuration watcher stopped")

                self._observer = None

        except Exception as e:
            logger.error("Error stopping configuration watcher", error=str(e))

    def is_watching(self, config_path: Path | None = None) -> bool:
        """Check if configuration watching is active.

        Args:
            config_path: Specific path to check, or None to check if any watching is active

        Returns:
            True if watching is active
        """
        if not WATCHDOG_AVAILABLE:
            return False

        if config_path:
            return config_path.resolve() in self._watched_paths
        else:
            return self._is_watching and len(self._watched_paths) > 0

    @property
    def watched_files(self) -> set[Path]:
        """Get set of currently watched configuration files."""
        return self._watched_paths.copy()

    @property
    def watchdog_available(self) -> bool:
        """Check if watchdog is available for file watching."""
        return WATCHDOG_AVAILABLE


class PollingConfigurationWatcher:
    """Fallback configuration watcher using polling when watchdog is not available."""

    def __init__(self, poll_interval: float = 2.0):
        """Initialize the polling watcher.

        Args:
            poll_interval: Interval in seconds between file checks
        """
        self._poll_interval = poll_interval
        self._watched_files: dict[Path, tuple[float, Callable]] = {}
        self._polling_task: asyncio.Task | None = None
        self._is_watching = False

    async def start_watching(self, config_path: Path, callback: Callable[[Path], None]) -> bool:
        """Start watching a configuration file using polling.

        Args:
            config_path: Path to configuration file to watch
            callback: Callback function to call on file changes

        Returns:
            True if watching started successfully
        """
        if not config_path.exists():
            logger.warning("Configuration file does not exist, cannot watch",
                         path=str(config_path))
            return False

        config_path = config_path.resolve()

        try:
            # Get initial modification time
            mtime = config_path.stat().st_mtime
            self._watched_files[config_path] = (mtime, callback)

            # Start polling task if not already running
            if not self._is_watching:
                self._polling_task = asyncio.create_task(self._polling_loop())
                self._is_watching = True
                logger.info("Polling configuration watcher started",
                          interval=self._poll_interval)

            logger.info("Started polling configuration file", path=str(config_path))
            return True

        except Exception as e:
            logger.error("Failed to start polling configuration file",
                        path=str(config_path), error=str(e))
            return False

    async def stop_watching(self, config_path: Path | None = None) -> None:
        """Stop watching configuration file(s).

        Args:
            config_path: Specific path to stop watching, or None to stop all
        """
        try:
            if config_path:
                # Stop watching specific file
                config_path = config_path.resolve()
                if config_path in self._watched_files:
                    del self._watched_files[config_path]
                    logger.info("Stopped polling configuration file", path=str(config_path))
            else:
                # Stop watching all files
                self._watched_files.clear()

                if self._polling_task and not self._polling_task.done():
                    self._polling_task.cancel()
                    try:
                        await self._polling_task
                    except asyncio.CancelledError:
                        pass

                self._is_watching = False
                self._polling_task = None
                logger.info("Polling configuration watcher stopped")

        except Exception as e:
            logger.error("Error stopping polling configuration watcher", error=str(e))

    async def _polling_loop(self):
        """Main polling loop to check for file changes."""
        logger.debug("Configuration polling loop started")

        try:
            while self._is_watching and self._watched_files:
                await asyncio.sleep(self._poll_interval)

                # Check each watched file
                for config_path, (last_mtime, callback) in list(self._watched_files.items()):
                    try:
                        if not config_path.exists():
                            logger.warning("Watched configuration file no longer exists",
                                         path=str(config_path))
                            continue

                        current_mtime = config_path.stat().st_mtime

                        if current_mtime > last_mtime:
                            logger.debug("Configuration file changed",
                                       path=str(config_path),
                                       old_mtime=last_mtime,
                                       new_mtime=current_mtime)

                            # Update stored modification time
                            self._watched_files[config_path] = (current_mtime, callback)

                            # Call the callback
                            try:
                                callback(config_path)
                            except Exception as e:
                                logger.error("Error in configuration change callback",
                                           path=str(config_path), error=str(e))

                    except Exception as e:
                        logger.error("Error checking configuration file",
                                   path=str(config_path), error=str(e))

        except asyncio.CancelledError:
            logger.debug("Configuration polling loop cancelled")
            raise
        except Exception as e:
            logger.error("Configuration polling loop error", error=str(e))
        finally:
            logger.debug("Configuration polling loop ended")

    def is_watching(self, config_path: Path | None = None) -> bool:
        """Check if configuration watching is active."""
        if config_path:
            return config_path.resolve() in self._watched_files
        else:
            return self._is_watching and len(self._watched_files) > 0

    @property
    def watched_files(self) -> set[Path]:
        """Get set of currently watched configuration files."""
        return set(self._watched_files.keys())

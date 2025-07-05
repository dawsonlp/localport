"""Thread-safe async signal handling for graceful shutdown.

This module provides enterprise-grade signal handling that eliminates race conditions
between signal handlers and the asyncio event loop.
"""

import asyncio
import signal
import sys
import threading
from typing import Callable, Dict, Optional, Set
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class SignalType(Enum):
    """Signal types for shutdown coordination."""
    SHUTDOWN = "shutdown"  # SIGTERM, SIGINT
    RELOAD = "reload"      # SIGUSR1, SIGHUP
    STATUS = "status"      # SIGUSR2


class AsyncSignalHandler:
    """Thread-safe signal handler with async coordination.
    
    Eliminates race conditions by using thread-safe coordination between
    signal handlers (which run in signal context) and async tasks.
    
    Key Features:
    - Thread-safe signal to async coordination
    - Signal handler deduplication logic
    - Cross-platform compatibility (Windows/Unix)
    - Proper signal handler cleanup and restoration
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Initialize the async signal handler.
        
        Args:
            loop: Event loop to use. If None, uses current loop.
        """
        self._loop = loop or asyncio.get_event_loop()
        self._signal_handlers: Dict[int, Callable] = {}
        self._original_handlers: Dict[int, Any] = {}
        self._shutdown_event = asyncio.Event()
        self._reload_event = asyncio.Event()
        self._status_event = asyncio.Event()
        
        # Thread-safe coordination
        self._signal_lock = threading.Lock()
        self._received_signals: Set[int] = set()
        self._shutdown_initiated = False
        
        # Cross-platform signal mapping
        self._signal_map = self._build_signal_map()
        
        logger.debug("AsyncSignalHandler initialized", 
                    platform=sys.platform,
                    signals=list(self._signal_map.keys()))

    def _build_signal_map(self) -> Dict[int, SignalType]:
        """Build platform-specific signal mapping."""
        signal_map = {}
        
        if sys.platform == "win32":
            # Windows signal handling
            signal_map[signal.SIGINT] = SignalType.SHUTDOWN
            signal_map[signal.SIGTERM] = SignalType.SHUTDOWN
        else:
            # Unix signal handling
            signal_map[signal.SIGTERM] = SignalType.SHUTDOWN
            signal_map[signal.SIGINT] = SignalType.SHUTDOWN
            signal_map[signal.SIGUSR1] = SignalType.RELOAD
            signal_map[signal.SIGHUP] = SignalType.RELOAD
            signal_map[signal.SIGUSR2] = SignalType.STATUS
            
        return signal_map

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers with proper coordination.
        
        This method safely installs signal handlers that coordinate with
        the async event loop without creating race conditions.
        """
        logger.info("Setting up signal handlers", 
                   signals=list(self._signal_map.keys()))
        
        for sig_num, sig_type in self._signal_map.items():
            try:
                # Store original handler for cleanup
                self._original_handlers[sig_num] = signal.signal(sig_num, signal.SIG_DFL)
                
                # Install our thread-safe handler
                if sys.platform == "win32":
                    # Windows: Use signal.signal
                    signal.signal(sig_num, self._signal_handler)
                else:
                    # Unix: Use loop.add_signal_handler for better integration
                    self._loop.add_signal_handler(
                        sig_num, 
                        self._async_signal_handler, 
                        sig_num, 
                        sig_type
                    )
                
                self._signal_handlers[sig_num] = sig_type
                logger.debug("Signal handler installed", 
                           signal=sig_num, 
                           type=sig_type.value)
                           
            except (OSError, ValueError) as e:
                logger.warning("Failed to install signal handler", 
                             signal=sig_num, 
                             error=str(e))

    def _signal_handler(self, signum: int, frame) -> None:
        """Thread-safe signal handler for Windows.
        
        This runs in signal context and must be thread-safe.
        """
        with self._signal_lock:
            if signum in self._received_signals:
                # Deduplicate signals
                logger.debug("Duplicate signal ignored", signal=signum)
                return
                
            self._received_signals.add(signum)
            
        # Schedule async handling
        sig_type = self._signal_map.get(signum)
        if sig_type:
            self._loop.call_soon_threadsafe(
                self._handle_signal_async, 
                signum, 
                sig_type
            )

    def _async_signal_handler(self, signum: int, sig_type: SignalType) -> None:
        """Async signal handler for Unix (called by loop.add_signal_handler).
        
        This runs in the event loop context and is safe for async operations.
        """
        with self._signal_lock:
            if signum in self._received_signals:
                # Deduplicate signals
                logger.debug("Duplicate signal ignored", signal=signum)
                return
                
            self._received_signals.add(signum)
            
        # Handle signal in async context
        asyncio.create_task(self._handle_signal_async(signum, sig_type))

    async def _handle_signal_async(self, signum: int, sig_type: SignalType) -> None:
        """Handle signal in async context.
        
        This method runs in the event loop and can safely perform async operations.
        """
        logger.info("Signal received", signal=signum, type=sig_type.value)
        
        try:
            if sig_type == SignalType.SHUTDOWN:
                await self._handle_shutdown_signal(signum)
            elif sig_type == SignalType.RELOAD:
                await self._handle_reload_signal(signum)
            elif sig_type == SignalType.STATUS:
                await self._handle_status_signal(signum)
        except Exception as e:
            logger.exception("Error handling signal", 
                           signal=signum, 
                           type=sig_type.value, 
                           error=str(e))

    async def _handle_shutdown_signal(self, signum: int) -> None:
        """Handle shutdown signals with deduplication."""
        with self._signal_lock:
            if self._shutdown_initiated:
                logger.debug("Shutdown already initiated, ignoring signal", 
                           signal=signum)
                return
            self._shutdown_initiated = True
            
        logger.info("Initiating graceful shutdown", signal=signum)
        self._shutdown_event.set()

    async def _handle_reload_signal(self, signum: int) -> None:
        """Handle reload signals."""
        logger.info("Configuration reload requested", signal=signum)
        self._reload_event.set()

    async def _handle_status_signal(self, signum: int) -> None:
        """Handle status signals."""
        logger.info("Status report requested", signal=signum)
        self._status_event.set()

    def cleanup_signal_handlers(self) -> None:
        """Cleanup signal handlers and restore original handlers.
        
        This method should be called during shutdown to properly restore
        the original signal handlers.
        """
        logger.info("Cleaning up signal handlers")
        
        for sig_num in list(self._signal_handlers.keys()):
            try:
                if sys.platform != "win32":
                    # Unix: Remove from event loop
                    self._loop.remove_signal_handler(sig_num)
                
                # Restore original handler
                if sig_num in self._original_handlers:
                    signal.signal(sig_num, self._original_handlers[sig_num])
                    
                logger.debug("Signal handler cleaned up", signal=sig_num)
                
            except (OSError, ValueError) as e:
                logger.warning("Failed to cleanup signal handler", 
                             signal=sig_num, 
                             error=str(e))
        
        self._signal_handlers.clear()
        self._original_handlers.clear()

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Event that is set when shutdown is requested."""
        return self._shutdown_event

    @property
    def reload_event(self) -> asyncio.Event:
        """Event that is set when configuration reload is requested."""
        return self._reload_event

    @property
    def status_event(self) -> asyncio.Event:
        """Event that is set when status report is requested."""
        return self._status_event

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    def reset_events(self) -> None:
        """Reset all signal events (useful for testing)."""
        self._shutdown_event.clear()
        self._reload_event.clear()
        self._status_event.clear()
        
        with self._signal_lock:
            self._received_signals.clear()
            self._shutdown_initiated = False

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def wait_for_reload(self) -> None:
        """Wait for reload signal."""
        await self._reload_event.wait()

    async def wait_for_status(self) -> None:
        """Wait for status signal."""
        await self._status_event.wait()

    def __enter__(self):
        """Context manager entry."""
        self.setup_signal_handlers()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup_signal_handlers()

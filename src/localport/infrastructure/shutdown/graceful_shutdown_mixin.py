"""Graceful shutdown mixin for adding shutdown capabilities to classes.

This module provides a reusable mixin that adds enterprise-grade shutdown
capabilities to any class.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable, List
from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger(__name__)


class GracefulShutdownMixin(ABC):
    """Mixin for adding graceful shutdown capabilities to classes.
    
    Provides standardized shutdown capabilities including:
    - Shutdown event management (asyncio.Event)
    - Timeout handling with configurable timeouts
    - State tracking (RUNNING → SHUTTING_DOWN → STOPPED)
    - Structured logging integration
    - Performance metrics collection
    """

    def __init__(self, *args, **kwargs):
        """Initialize the graceful shutdown mixin."""
        super().__init__(*args, **kwargs)
        
        # Shutdown state management
        self._shutdown_event = asyncio.Event()
        self._shutdown_requested = False
        self._shutdown_completed = False
        self._shutdown_start_time: Optional[float] = None
        self._shutdown_duration: Optional[float] = None
        
        # Configuration
        self._shutdown_timeout = 30.0
        self._graceful_timeout = 15.0
        
        # Callbacks
        self._shutdown_callbacks: List[Callable] = []
        self._cleanup_callbacks: List[Callable] = []
        
        logger.debug("GracefulShutdownMixin initialized", 
                    class_name=self.__class__.__name__)

    def configure_shutdown(
        self, 
        shutdown_timeout: float = 30.0,
        graceful_timeout: float = 15.0
    ) -> None:
        """Configure shutdown timeouts.
        
        Args:
            shutdown_timeout: Total timeout for shutdown process
            graceful_timeout: Timeout for graceful shutdown before force
        """
        self._shutdown_timeout = shutdown_timeout
        self._graceful_timeout = graceful_timeout
        
        logger.debug("Shutdown configuration updated",
                    class_name=self.__class__.__name__,
                    shutdown_timeout=shutdown_timeout,
                    graceful_timeout=graceful_timeout)

    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register a callback to be called during shutdown.
        
        Args:
            callback: Async or sync callable to execute during shutdown
        """
        self._shutdown_callbacks.append(callback)
        logger.debug("Shutdown callback registered",
                    class_name=self.__class__.__name__,
                    callback=callback.__name__)

    def register_cleanup_callback(self, callback: Callable) -> None:
        """Register a callback to be called during cleanup.
        
        Args:
            callback: Async or sync callable to execute during cleanup
        """
        self._cleanup_callbacks.append(callback)
        logger.debug("Cleanup callback registered",
                    class_name=self.__class__.__name__,
                    callback=callback.__name__)

    async def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        if self._shutdown_requested:
            logger.debug("Shutdown already requested",
                        class_name=self.__class__.__name__)
            return
            
        logger.info("Shutdown requested",
                   class_name=self.__class__.__name__)
        
        self._shutdown_requested = True
        self._shutdown_start_time = time.time()
        self._shutdown_event.set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to be requested."""
        await self._shutdown_event.wait()

    async def wait_for_shutdown_or_timeout(self, timeout: float) -> bool:
        """Wait for shutdown or timeout.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if shutdown was requested, False if timeout
        """
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    def is_shutdown_completed(self) -> bool:
        """Check if shutdown has completed."""
        return self._shutdown_completed

    async def graceful_shutdown(self) -> bool:
        """Perform graceful shutdown.
        
        Returns:
            True if shutdown completed successfully, False otherwise
        """
        if self._shutdown_completed:
            logger.debug("Shutdown already completed",
                        class_name=self.__class__.__name__)
            return True
            
        if not self._shutdown_requested:
            await self.request_shutdown()
            
        logger.info("Starting graceful shutdown",
                   class_name=self.__class__.__name__,
                   timeout=self._graceful_timeout)
        
        try:
            # Execute shutdown callbacks
            await self._execute_shutdown_callbacks()
            
            # Perform class-specific shutdown
            success = await asyncio.wait_for(
                self._perform_shutdown(),
                timeout=self._graceful_timeout
            )
            
            if success:
                logger.info("Graceful shutdown completed successfully",
                           class_name=self.__class__.__name__)
            else:
                logger.warning("Graceful shutdown completed with issues",
                              class_name=self.__class__.__name__)
                
            return success
            
        except asyncio.TimeoutError:
            logger.warning("Graceful shutdown timed out",
                          class_name=self.__class__.__name__,
                          timeout=self._graceful_timeout)
            return False
        except Exception as e:
            logger.exception("Graceful shutdown failed",
                           class_name=self.__class__.__name__,
                           error=str(e))
            return False
        finally:
            await self._perform_cleanup()
            self._shutdown_completed = True
            if self._shutdown_start_time:
                self._shutdown_duration = time.time() - self._shutdown_start_time

    async def force_shutdown(self) -> None:
        """Perform force shutdown with minimal cleanup."""
        logger.warning("Performing force shutdown",
                      class_name=self.__class__.__name__)
        
        if not self._shutdown_requested:
            await self.request_shutdown()
            
        try:
            # Perform minimal cleanup
            await self._perform_cleanup()
        except Exception as e:
            logger.exception("Force shutdown cleanup failed",
                           class_name=self.__class__.__name__,
                           error=str(e))
        finally:
            self._shutdown_completed = True
            if self._shutdown_start_time:
                self._shutdown_duration = time.time() - self._shutdown_start_time

    async def _execute_shutdown_callbacks(self) -> None:
        """Execute all registered shutdown callbacks."""
        if not self._shutdown_callbacks:
            return
            
        logger.debug("Executing shutdown callbacks",
                    class_name=self.__class__.__name__,
                    count=len(self._shutdown_callbacks))
        
        for callback in self._shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.exception("Shutdown callback failed",
                               class_name=self.__class__.__name__,
                               callback=callback.__name__,
                               error=str(e))

    async def _perform_cleanup(self) -> None:
        """Perform cleanup operations."""
        logger.debug("Performing cleanup",
                    class_name=self.__class__.__name__)
        
        # Execute cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.exception("Cleanup callback failed",
                               class_name=self.__class__.__name__,
                               callback=callback.__name__,
                               error=str(e))
        
        # Perform class-specific cleanup
        try:
            await self._perform_class_cleanup()
        except Exception as e:
            logger.exception("Class cleanup failed",
                           class_name=self.__class__.__name__,
                           error=str(e))

    @abstractmethod
    async def _perform_shutdown(self) -> bool:
        """Perform class-specific shutdown operations.
        
        This method must be implemented by subclasses to define
        their specific shutdown behavior.
        
        Returns:
            True if shutdown completed successfully, False otherwise
        """
        pass

    async def _perform_class_cleanup(self) -> None:
        """Perform class-specific cleanup operations.
        
        This method can be overridden by subclasses to define
        their specific cleanup behavior.
        """
        pass

    def get_shutdown_metrics(self) -> Dict[str, Any]:
        """Get shutdown metrics for monitoring and debugging."""
        return {
            "class_name": self.__class__.__name__,
            "shutdown_requested": self._shutdown_requested,
            "shutdown_completed": self._shutdown_completed,
            "shutdown_duration": self._shutdown_duration,
            "shutdown_timeout": self._shutdown_timeout,
            "graceful_timeout": self._graceful_timeout,
            "registered_callbacks": {
                "shutdown": len(self._shutdown_callbacks),
                "cleanup": len(self._cleanup_callbacks),
            },
        }

    async def shutdown_with_timeout(self, timeout: Optional[float] = None) -> bool:
        """Shutdown with configurable timeout.
        
        Args:
            timeout: Override default shutdown timeout
            
        Returns:
            True if shutdown completed, False if timeout or force required
        """
        shutdown_timeout = timeout or self._shutdown_timeout
        
        logger.info("Starting shutdown with timeout",
                   class_name=self.__class__.__name__,
                   timeout=shutdown_timeout)
        
        try:
            # Try graceful shutdown first
            success = await asyncio.wait_for(
                self.graceful_shutdown(),
                timeout=shutdown_timeout
            )
            return success
            
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout exceeded, forcing shutdown",
                          class_name=self.__class__.__name__,
                          timeout=shutdown_timeout)
            
            # Force shutdown
            await self.force_shutdown()
            return False


class ShutdownAwareService(GracefulShutdownMixin):
    """Base class for services that need shutdown awareness.
    
    This is a concrete implementation of GracefulShutdownMixin
    that can be used as a base class for services.
    """

    def __init__(self, name: str, *args, **kwargs):
        """Initialize the shutdown-aware service.
        
        Args:
            name: Service name for logging
        """
        super().__init__(*args, **kwargs)
        self._service_name = name
        self._running = False
        
        logger.debug("ShutdownAwareService initialized", service_name=name)

    async def start(self) -> None:
        """Start the service."""
        if self._running:
            logger.warning("Service already running", service_name=self._service_name)
            return
            
        logger.info("Starting service", service_name=self._service_name)
        self._running = True
        
        try:
            await self._start_service()
            logger.info("Service started successfully", service_name=self._service_name)
        except Exception as e:
            self._running = False
            logger.exception("Failed to start service", 
                           service_name=self._service_name,
                           error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the service."""
        if not self._running:
            logger.debug("Service not running", service_name=self._service_name)
            return
            
        logger.info("Stopping service", service_name=self._service_name)
        
        try:
            await self.graceful_shutdown()
            logger.info("Service stopped successfully", service_name=self._service_name)
        except Exception as e:
            logger.exception("Error stopping service", 
                           service_name=self._service_name,
                           error=str(e))
            raise
        finally:
            self._running = False

    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running and not self.is_shutdown_requested()

    async def _start_service(self) -> None:
        """Start service-specific operations.
        
        Override this method in subclasses to implement service startup logic.
        """
        pass

    async def _perform_shutdown(self) -> bool:
        """Perform service shutdown."""
        logger.debug("Performing service shutdown", service_name=self._service_name)
        
        try:
            await self._stop_service()
            return True
        except Exception as e:
            logger.exception("Service shutdown failed", 
                           service_name=self._service_name,
                           error=str(e))
            return False

    async def _stop_service(self) -> None:
        """Stop service-specific operations.
        
        Override this method in subclasses to implement service shutdown logic.
        """
        pass

    async def _perform_class_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.debug("Performing service cleanup", service_name=self._service_name)
        self._running = False

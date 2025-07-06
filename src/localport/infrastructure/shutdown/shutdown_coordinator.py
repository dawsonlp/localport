"""Multi-phase shutdown orchestration for graceful daemon shutdown.

This module provides enterprise-grade shutdown coordination with configurable
phases, timeouts, and progress reporting.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass

import structlog

from .task_manager import TaskManager
from .signal_handler import AsyncSignalHandler

logger = structlog.get_logger(__name__)


class ShutdownPhase(Enum):
    """Shutdown phases in order of execution."""
    STOP_NEW_WORK = "stop_new_work"
    COMPLETE_CURRENT = "complete_current"
    CANCEL_TASKS = "cancel_tasks"
    FORCE_CLEANUP = "force_cleanup"
    COMPLETED = "completed"


@dataclass
class PhaseConfig:
    """Configuration for a shutdown phase."""
    name: str
    timeout: float
    description: str
    callback: Optional[Callable] = None


class ShutdownCoordinator:
    """Multi-phase shutdown orchestration.
    
    Provides enterprise-grade shutdown coordination with:
    - Multi-phase shutdown state machine
    - Timeout management per phase (configurable)
    - Progress reporting with structured logging
    - Failure handling and recovery
    - Metrics collection for shutdown performance
    """

    def __init__(
        self,
        task_manager: TaskManager,
        signal_handler: AsyncSignalHandler,
        phase_configs: Optional[Dict[ShutdownPhase, PhaseConfig]] = None
    ):
        """Initialize the shutdown coordinator.
        
        Args:
            task_manager: Task manager for coordinating task shutdown
            signal_handler: Signal handler for shutdown events
            phase_configs: Optional custom phase configurations
        """
        self._task_manager = task_manager
        self._signal_handler = signal_handler
        self._current_phase = None
        self._shutdown_start_time = None
        self._phase_start_time = None
        self._shutdown_completed = False
        self._shutdown_successful = False
        
        # Phase configurations
        self._phase_configs = phase_configs or self._default_phase_configs()
        
        # Callbacks for each phase
        self._phase_callbacks: Dict[ShutdownPhase, List[Callable]] = {
            phase: [] for phase in ShutdownPhase
        }
        
        # Metrics
        self._phase_durations: Dict[ShutdownPhase, float] = {}
        self._total_shutdown_time = 0.0
        
        logger.debug("ShutdownCoordinator initialized", 
                    phases=list(self._phase_configs.keys()))

    def _default_phase_configs(self) -> Dict[ShutdownPhase, PhaseConfig]:
        """Create default phase configurations."""
        return {
            ShutdownPhase.STOP_NEW_WORK: PhaseConfig(
                name="Stop New Work",
                timeout=2.0,
                description="Stop accepting new work and requests"
            ),
            ShutdownPhase.COMPLETE_CURRENT: PhaseConfig(
                name="Complete Current Operations",
                timeout=8.0,
                description="Allow current operations to complete gracefully"
            ),
            ShutdownPhase.CANCEL_TASKS: PhaseConfig(
                name="Cancel Background Tasks",
                timeout=15.0,
                description="Cancel all background tasks and monitoring"
            ),
            ShutdownPhase.FORCE_CLEANUP: PhaseConfig(
                name="Force Cleanup",
                timeout=5.0,
                description="Force cleanup of remaining resources"
            ),
        }

    def register_phase_callback(
        self, 
        phase: ShutdownPhase, 
        callback: Callable
    ) -> None:
        """Register a callback for a specific shutdown phase.
        
        Args:
            phase: Shutdown phase to register callback for
            callback: Async or sync callable to execute during phase
        """
        self._phase_callbacks[phase].append(callback)
        logger.debug("Phase callback registered", 
                    phase=phase.value, 
                    callback=callback.__name__)

    def update_phase_timeout(self, phase: ShutdownPhase, timeout: float) -> None:
        """Update timeout for a specific phase.
        
        Args:
            phase: Phase to update
            timeout: New timeout in seconds
        """
        if phase in self._phase_configs:
            self._phase_configs[phase].timeout = timeout
            logger.debug("Phase timeout updated", 
                        phase=phase.value, 
                        timeout=timeout)

    async def initiate_shutdown(self) -> bool:
        """Initiate the multi-phase shutdown process.
        
        Returns:
            True if shutdown completed successfully, False otherwise
        """
        if self._shutdown_completed:
            logger.warning("Shutdown already completed")
            return self._shutdown_successful
            
        self._shutdown_start_time = time.time()
        logger.info("Initiating multi-phase graceful shutdown")
        
        try:
            # Execute each phase in order
            for phase in [
                ShutdownPhase.STOP_NEW_WORK,
                ShutdownPhase.COMPLETE_CURRENT,
                ShutdownPhase.CANCEL_TASKS,
                ShutdownPhase.FORCE_CLEANUP
            ]:
                success = await self._execute_phase(phase)
                if not success:
                    logger.error("Shutdown phase failed", phase=phase.value)
                    self._shutdown_successful = False
                    break
            else:
                # All phases completed successfully
                self._current_phase = ShutdownPhase.COMPLETED
                self._shutdown_successful = True
                
        except Exception as e:
            logger.exception("Shutdown coordination failed", error=str(e))
            self._shutdown_successful = False
        finally:
            self._shutdown_completed = True
            self._total_shutdown_time = time.time() - self._shutdown_start_time
            
        # Log final results
        if self._shutdown_successful:
            logger.info("Graceful shutdown completed successfully", 
                       duration=self._total_shutdown_time,
                       phase_durations={k.value: v for k, v in self._phase_durations.items()})
        else:
            logger.error("Graceful shutdown failed", 
                        duration=self._total_shutdown_time,
                        failed_phase=self._current_phase.value if self._current_phase else "unknown",
                        phase_durations={k.value: v for k, v in self._phase_durations.items()})
            
        return self._shutdown_successful

    async def _execute_phase(self, phase: ShutdownPhase) -> bool:
        """Execute a specific shutdown phase.
        
        Args:
            phase: Phase to execute
            
        Returns:
            True if phase completed successfully, False otherwise
        """
        if phase not in self._phase_configs:
            logger.error("Unknown shutdown phase", phase=phase.value)
            return False
            
        config = self._phase_configs[phase]
        self._current_phase = phase
        self._phase_start_time = time.time()
        
        logger.info("Starting shutdown phase", 
                   phase=phase.value,
                   description=config.description,
                   timeout=config.timeout)
        
        try:
            # Execute phase-specific logic
            if phase == ShutdownPhase.STOP_NEW_WORK:
                success = await self._stop_new_work(config.timeout)
            elif phase == ShutdownPhase.COMPLETE_CURRENT:
                success = await self._complete_current_operations(config.timeout)
            elif phase == ShutdownPhase.CANCEL_TASKS:
                success = await self._cancel_background_tasks(config.timeout)
            elif phase == ShutdownPhase.FORCE_CLEANUP:
                success = await self._force_cleanup(config.timeout)
            else:
                logger.error("Unhandled shutdown phase", phase=phase.value)
                success = False
                
            # Execute registered callbacks
            await self._execute_phase_callbacks(phase, config.timeout)
            
        except asyncio.TimeoutError:
            logger.warning("Shutdown phase timed out", 
                          phase=phase.value, 
                          timeout=config.timeout)
            success = False
        except Exception as e:
            logger.exception("Shutdown phase failed", 
                           phase=phase.value, 
                           error=str(e))
            success = False
        finally:
            phase_duration = time.time() - self._phase_start_time
            self._phase_durations[phase] = phase_duration
            
        if success:
            logger.info("Shutdown phase completed", 
                       phase=phase.value, 
                       duration=phase_duration)
        else:
            logger.error("Shutdown phase failed", 
                        phase=phase.value, 
                        duration=phase_duration)
            
        return success

    async def _stop_new_work(self, timeout: float) -> bool:
        """Phase 1: Stop accepting new work."""
        logger.debug("Stopping new work acceptance")
        
        # This phase is primarily for application-specific logic
        # The coordinator itself doesn't have work to stop
        
        # Signal that we're shutting down
        # Applications can check this via is_shutting_down()
        
        return True

    async def _complete_current_operations(self, timeout: float) -> bool:
        """Phase 2: Allow current operations to complete."""
        logger.debug("Waiting for current operations to complete")
        
        # Wait for a short period to allow current operations to finish
        # This is application-specific, but we provide a default wait
        try:
            await asyncio.wait_for(
                asyncio.sleep(min(timeout, 2.0)),  # Max 2 seconds for this phase
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for current operations")
            return False

    async def _cancel_background_tasks(self, timeout: float) -> bool:
        """Phase 3: Cancel all background tasks."""
        logger.debug("Cancelling background tasks")
        
        # Use task manager to cancel all tasks
        success = await self._task_manager.graceful_shutdown(timeout)
        
        if success:
            logger.info("All background tasks cancelled successfully")
        else:
            logger.warning("Some background tasks failed to cancel gracefully")
            
        return success

    async def _force_cleanup(self, timeout: float) -> bool:
        """Phase 4: Force cleanup of remaining resources."""
        logger.debug("Performing force cleanup")
        
        # Clean up task manager
        self._task_manager.cleanup()
        
        # Clean up signal handler
        self._signal_handler.cleanup_signal_handlers()
        
        logger.info("Force cleanup completed")
        return True

    async def _execute_phase_callbacks(self, phase: ShutdownPhase, timeout: float) -> None:
        """Execute all registered callbacks for a phase."""
        callbacks = self._phase_callbacks.get(phase, [])
        if not callbacks:
            return
            
        logger.debug("Executing phase callbacks", 
                    phase=phase.value, 
                    count=len(callbacks))
        
        # Execute callbacks with timeout
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await asyncio.wait_for(callback(), timeout=timeout / len(callbacks))
                else:
                    callback()
            except Exception as e:
                logger.exception("Phase callback failed", 
                               phase=phase.value,
                               callback=callback.__name__,
                               error=str(e))

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._current_phase is not None and not self._shutdown_completed

    def is_shutdown_completed(self) -> bool:
        """Check if shutdown has completed."""
        return self._shutdown_completed

    def is_shutdown_successful(self) -> bool:
        """Check if shutdown completed successfully."""
        return self._shutdown_completed and self._shutdown_successful

    def get_current_phase(self) -> Optional[ShutdownPhase]:
        """Get the current shutdown phase."""
        return self._current_phase

    def get_shutdown_progress(self) -> Dict[str, Any]:
        """Get shutdown progress information."""
        if not self._shutdown_start_time:
            return {"status": "not_started"}
            
        elapsed = time.time() - self._shutdown_start_time
        
        progress = {
            "status": "in_progress" if not self._shutdown_completed else "completed",
            "successful": self._shutdown_successful,
            "current_phase": self._current_phase.value if self._current_phase else None,
            "elapsed_time": elapsed,
            "total_time": self._total_shutdown_time,
            "phase_durations": {k.value: v for k, v in self._phase_durations.items()},
        }
        
        if self._phase_start_time and not self._shutdown_completed:
            progress["current_phase_elapsed"] = time.time() - self._phase_start_time
            
        return progress

    def get_metrics(self) -> Dict[str, Any]:
        """Get shutdown coordinator metrics."""
        return {
            "shutdown_completed": self._shutdown_completed,
            "shutdown_successful": self._shutdown_successful,
            "total_shutdown_time": self._total_shutdown_time,
            "phase_durations": {k.value: v for k, v in self._phase_durations.items()},
            "current_phase": self._current_phase.value if self._current_phase else None,
            "registered_callbacks": {
                k.value: len(v) for k, v in self._phase_callbacks.items()
            },
        }

    async def wait_for_shutdown_signal(self) -> None:
        """Wait for shutdown signal from signal handler."""
        await self._signal_handler.wait_for_shutdown()

    async def emergency_shutdown(self, timeout: float = 5.0) -> bool:
        """Perform emergency shutdown with minimal timeout.
        
        Args:
            timeout: Maximum time for emergency shutdown
            
        Returns:
            True if emergency shutdown completed
        """
        logger.warning("Performing emergency shutdown", timeout=timeout)
        
        start_time = time.time()
        
        try:
            # Cancel all tasks immediately
            await self._task_manager.cancel_all_tasks(timeout / 2)
            
            # Force cleanup
            self._task_manager.cleanup()
            self._signal_handler.cleanup_signal_handlers()
            
            duration = time.time() - start_time
            logger.warning("Emergency shutdown completed", duration=duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            logger.exception("Emergency shutdown failed", 
                           duration=duration, 
                           error=str(e))
            return False

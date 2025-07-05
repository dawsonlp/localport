"""Cooperative task patterns for graceful shutdown.

This module provides base classes and utilities for creating tasks that
cooperate with the shutdown process.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from abc import ABC, abstractmethod

import structlog

from .graceful_shutdown_mixin import GracefulShutdownMixin

logger = structlog.get_logger(__name__)


class CooperativeTask(GracefulShutdownMixin):
    """Base class for tasks that cooperate with shutdown.
    
    Provides standardized patterns for:
    - Shutdown-aware task execution
    - Cooperative cancellation handling
    - Resource cleanup patterns
    - Error handling and logging
    """

    def __init__(self, name: str, check_interval: float = 5.0):
        """Initialize the cooperative task.
        
        Args:
            name: Task name for logging and identification
            check_interval: How often to check for shutdown (seconds)
        """
        super().__init__()
        self._task_name = name
        self._check_interval = check_interval
        self._task_handle: Optional[asyncio.Task] = None
        self._running = False
        self._iterations = 0
        self._last_iteration_time: Optional[float] = None
        
        logger.debug("CooperativeTask initialized", 
                    task_name=name,
                    check_interval=check_interval)

    async def start(self) -> None:
        """Start the cooperative task."""
        if self._running:
            logger.warning("Task already running", task_name=self._task_name)
            return
            
        logger.info("Starting cooperative task", task_name=self._task_name)
        
        self._running = True
        self._task_handle = asyncio.create_task(
            self._run_loop(),
            name=f"cooperative_task_{self._task_name}"
        )

    async def stop(self) -> None:
        """Stop the cooperative task."""
        if not self._running:
            logger.debug("Task not running", task_name=self._task_name)
            return
            
        logger.info("Stopping cooperative task", task_name=self._task_name)
        
        # Request shutdown
        await self.request_shutdown()
        
        # Wait for task to complete
        if self._task_handle and not self._task_handle.done():
            try:
                await asyncio.wait_for(self._task_handle, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Task did not stop gracefully, cancelling",
                              task_name=self._task_name)
                self._task_handle.cancel()
                try:
                    await self._task_handle
                except asyncio.CancelledError:
                    pass
        
        self._running = False
        logger.info("Cooperative task stopped", task_name=self._task_name)

    async def _run_loop(self) -> None:
        """Main task execution loop with cooperative shutdown."""
        logger.debug("Starting task loop", task_name=self._task_name)
        
        try:
            while not self.is_shutdown_requested():
                iteration_start = time.time()
                
                try:
                    # Perform one iteration of work
                    await self._execute_iteration()
                    self._iterations += 1
                    self._last_iteration_time = time.time()
                    
                except Exception as e:
                    logger.exception("Task iteration failed", 
                                   task_name=self._task_name,
                                   iteration=self._iterations,
                                   error=str(e))
                    
                    # Handle iteration error
                    should_continue = await self._handle_iteration_error(e)
                    if not should_continue:
                        logger.error("Task stopping due to iteration error",
                                   task_name=self._task_name)
                        break
                
                # Wait for next iteration or shutdown
                iteration_duration = time.time() - iteration_start
                remaining_wait = max(0, self._check_interval - iteration_duration)
                
                if remaining_wait > 0:
                    # Wait with shutdown awareness
                    shutdown_requested = await self.wait_for_shutdown_or_timeout(remaining_wait)
                    if shutdown_requested:
                        logger.debug("Shutdown requested during wait",
                                   task_name=self._task_name)
                        break
                        
        except asyncio.CancelledError:
            logger.info("Task cancelled", task_name=self._task_name)
            raise
        except Exception as e:
            logger.exception("Task loop failed", 
                           task_name=self._task_name,
                           error=str(e))
            raise
        finally:
            logger.debug("Task loop ended", 
                        task_name=self._task_name,
                        iterations=self._iterations)

    @abstractmethod
    async def _execute_iteration(self) -> None:
        """Execute one iteration of the task.
        
        This method must be implemented by subclasses to define
        the actual work to be performed.
        
        Should be designed to complete quickly (within check_interval)
        and handle cancellation gracefully.
        """
        pass

    async def _handle_iteration_error(self, error: Exception) -> bool:
        """Handle errors that occur during task iteration.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True to continue task execution, False to stop
        """
        # Default behavior: log error and continue
        logger.warning("Task iteration error, continuing",
                      task_name=self._task_name,
                      error=str(error))
        return True

    async def _perform_shutdown(self) -> bool:
        """Perform task-specific shutdown."""
        logger.debug("Performing task shutdown", task_name=self._task_name)
        
        # Cancel the task if it's still running
        if self._task_handle and not self._task_handle.done():
            self._task_handle.cancel()
            try:
                await self._task_handle
            except asyncio.CancelledError:
                pass
                
        return True

    async def _perform_class_cleanup(self) -> None:
        """Perform task cleanup."""
        logger.debug("Performing task cleanup", task_name=self._task_name)
        self._running = False
        self._task_handle = None

    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self._running and not self.is_shutdown_requested()

    def get_task_metrics(self) -> Dict[str, Any]:
        """Get task execution metrics."""
        metrics = self.get_shutdown_metrics()
        metrics.update({
            "task_name": self._task_name,
            "running": self._running,
            "iterations": self._iterations,
            "last_iteration_time": self._last_iteration_time,
            "check_interval": self._check_interval,
        })
        return metrics


class PeriodicTask(CooperativeTask):
    """Cooperative task that executes work periodically.
    
    This is a concrete implementation that can be used for periodic
    background work with proper shutdown coordination.
    """

    def __init__(
        self, 
        name: str, 
        work_func: Callable,
        interval: float = 30.0,
        immediate_start: bool = False
    ):
        """Initialize the periodic task.
        
        Args:
            name: Task name
            work_func: Async or sync function to execute periodically
            interval: Interval between executions (seconds)
            immediate_start: Whether to execute immediately on start
        """
        super().__init__(name, check_interval=min(interval, 5.0))
        self._work_func = work_func
        self._interval = interval
        self._immediate_start = immediate_start
        self._next_execution = None
        
        logger.debug("PeriodicTask initialized",
                    task_name=name,
                    interval=interval,
                    immediate_start=immediate_start)

    async def _execute_iteration(self) -> None:
        """Execute periodic work if it's time."""
        current_time = time.time()
        
        # Initialize next execution time
        if self._next_execution is None:
            if self._immediate_start:
                self._next_execution = current_time
            else:
                self._next_execution = current_time + self._interval
                return
        
        # Check if it's time to execute
        if current_time >= self._next_execution:
            logger.debug("Executing periodic work", task_name=self._task_name)
            
            try:
                if asyncio.iscoroutinefunction(self._work_func):
                    await self._work_func()
                else:
                    self._work_func()
                    
                logger.debug("Periodic work completed", task_name=self._task_name)
                
            except Exception as e:
                logger.exception("Periodic work failed", 
                               task_name=self._task_name,
                               error=str(e))
                raise
            finally:
                # Schedule next execution
                self._next_execution = current_time + self._interval


class MonitoringTask(CooperativeTask):
    """Cooperative task for monitoring operations.
    
    Specialized for monitoring tasks that need to check conditions
    regularly and take action when needed.
    """

    def __init__(
        self, 
        name: str, 
        monitor_func: Callable,
        action_func: Optional[Callable] = None,
        check_interval: float = 30.0,
        action_threshold: int = 1
    ):
        """Initialize the monitoring task.
        
        Args:
            name: Task name
            monitor_func: Function that returns True if action is needed
            action_func: Optional function to execute when action is needed
            check_interval: How often to check (seconds)
            action_threshold: How many consecutive checks before action
        """
        super().__init__(name, check_interval)
        self._monitor_func = monitor_func
        self._action_func = action_func
        self._action_threshold = action_threshold
        self._consecutive_triggers = 0
        
        logger.debug("MonitoringTask initialized",
                    task_name=name,
                    check_interval=check_interval,
                    action_threshold=action_threshold)

    async def _execute_iteration(self) -> None:
        """Execute monitoring check."""
        logger.debug("Executing monitoring check", task_name=self._task_name)
        
        try:
            # Execute monitor function
            if asyncio.iscoroutinefunction(self._monitor_func):
                needs_action = await self._monitor_func()
            else:
                needs_action = self._monitor_func()
                
            if needs_action:
                self._consecutive_triggers += 1
                logger.debug("Monitor triggered",
                           task_name=self._task_name,
                           consecutive=self._consecutive_triggers,
                           threshold=self._action_threshold)
                
                # Check if we've reached the threshold
                if self._consecutive_triggers >= self._action_threshold:
                    if self._action_func:
                        logger.info("Executing monitor action", 
                                  task_name=self._task_name)
                        
                        if asyncio.iscoroutinefunction(self._action_func):
                            await self._action_func()
                        else:
                            self._action_func()
                            
                    # Reset counter after action
                    self._consecutive_triggers = 0
            else:
                # Reset counter if condition is not met
                if self._consecutive_triggers > 0:
                    logger.debug("Monitor condition cleared",
                               task_name=self._task_name)
                    self._consecutive_triggers = 0
                    
        except Exception as e:
            logger.exception("Monitoring check failed", 
                           task_name=self._task_name,
                           error=str(e))
            # Reset counter on error
            self._consecutive_triggers = 0
            raise

    def get_task_metrics(self) -> Dict[str, Any]:
        """Get monitoring task metrics."""
        metrics = super().get_task_metrics()
        metrics.update({
            "consecutive_triggers": self._consecutive_triggers,
            "action_threshold": self._action_threshold,
        })
        return metrics


async def create_cooperative_task(
    name: str,
    work_func: Callable,
    task_type: str = "periodic",
    **kwargs
) -> CooperativeTask:
    """Factory function for creating cooperative tasks.
    
    Args:
        name: Task name
        work_func: Function to execute
        task_type: Type of task ("periodic" or "monitoring")
        **kwargs: Additional arguments for task creation
        
    Returns:
        Configured cooperative task
    """
    if task_type == "periodic":
        return PeriodicTask(name, work_func, **kwargs)
    elif task_type == "monitoring":
        return MonitoringTask(name, work_func, **kwargs)
    else:
        raise ValueError(f"Unknown task type: {task_type}")

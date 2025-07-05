"""Centralized task lifecycle management for graceful shutdown.

This module provides enterprise-grade task management with proper resource
cleanup and shutdown coordination.
"""

import asyncio
import time
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


class TaskState(Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    """Information about a managed task."""
    name: str
    task: asyncio.Task
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    cleanup_callback: Optional[Callable] = None
    resource_tags: Set[str] = field(default_factory=set)
    priority: int = 0  # Higher number = higher priority for shutdown ordering


class TaskManager:
    """Centralized task lifecycle management.
    
    Provides enterprise-grade task management with:
    - Task registration and tracking
    - Graceful cancellation coordination
    - Resource cleanup verification
    - Task completion monitoring
    - Shutdown progress reporting
    """

    def __init__(self):
        """Initialize the task manager."""
        self._tasks: Dict[str, TaskInfo] = {}
        self._task_groups: Dict[str, Set[str]] = {}
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout = 30.0  # Default shutdown timeout
        self._cancellation_timeout = 5.0  # Time to wait for graceful cancellation
        
        # Metrics
        self._total_tasks_created = 0
        self._total_tasks_completed = 0
        self._total_tasks_cancelled = 0
        self._total_tasks_failed = 0
        
        logger.debug("TaskManager initialized")

    def register_task(
        self, 
        name: str, 
        coro: Any,
        *,
        group: Optional[str] = None,
        cleanup_callback: Optional[Callable] = None,
        resource_tags: Optional[Set[str]] = None,
        priority: int = 0
    ) -> asyncio.Task:
        """Register and start a new task.
        
        Args:
            name: Unique name for the task
            coro: Coroutine to execute
            group: Optional group name for batch operations
            cleanup_callback: Optional cleanup function to call on task completion
            resource_tags: Optional set of resource tags for cleanup tracking
            priority: Priority for shutdown ordering (higher = shutdown first)
            
        Returns:
            The created asyncio.Task
            
        Raises:
            ValueError: If task name already exists
        """
        if name in self._tasks:
            raise ValueError(f"Task '{name}' already exists")
            
        # Create the task
        task = asyncio.create_task(coro, name=name)
        
        # Create task info
        task_info = TaskInfo(
            name=name,
            task=task,
            state=TaskState.PENDING,
            cleanup_callback=cleanup_callback,
            resource_tags=resource_tags or set(),
            priority=priority
        )
        
        # Register the task
        self._tasks[name] = task_info
        self._total_tasks_created += 1
        
        # Add to group if specified
        if group:
            if group not in self._task_groups:
                self._task_groups[group] = set()
            self._task_groups[group].add(name)
            
        # Add completion callback
        task.add_done_callback(lambda t: self._on_task_completed(name, t))
        
        # Update state
        task_info.state = TaskState.RUNNING
        task_info.started_at = time.time()
        
        logger.debug("Task registered", 
                    name=name, 
                    group=group, 
                    priority=priority,
                    resource_tags=list(resource_tags or []))
        
        return task

    def _on_task_completed(self, name: str, task: asyncio.Task) -> None:
        """Handle task completion."""
        if name not in self._tasks:
            return
            
        task_info = self._tasks[name]
        task_info.completed_at = time.time()
        
        # Update state based on task result
        if task.cancelled():
            task_info.state = TaskState.CANCELLED
            self._total_tasks_cancelled += 1
            logger.debug("Task cancelled", name=name)
        elif task.exception():
            task_info.state = TaskState.FAILED
            self._total_tasks_failed += 1
            logger.warning("Task failed", 
                         name=name, 
                         error=str(task.exception()))
        else:
            task_info.state = TaskState.COMPLETED
            self._total_tasks_completed += 1
            logger.debug("Task completed", name=name)
            
        # Call cleanup callback if provided
        if task_info.cleanup_callback:
            try:
                if asyncio.iscoroutinefunction(task_info.cleanup_callback):
                    asyncio.create_task(task_info.cleanup_callback())
                else:
                    task_info.cleanup_callback()
            except Exception as e:
                logger.exception("Task cleanup callback failed", 
                               name=name, 
                               error=str(e))

    def get_task(self, name: str) -> Optional[TaskInfo]:
        """Get task information by name."""
        return self._tasks.get(name)

    def get_tasks_by_group(self, group: str) -> List[TaskInfo]:
        """Get all tasks in a group."""
        if group not in self._task_groups:
            return []
        return [self._tasks[name] for name in self._task_groups[group] 
                if name in self._tasks]

    def get_running_tasks(self) -> List[TaskInfo]:
        """Get all currently running tasks."""
        return [info for info in self._tasks.values() 
                if info.state == TaskState.RUNNING]

    def get_tasks_by_resource_tag(self, tag: str) -> List[TaskInfo]:
        """Get all tasks with a specific resource tag."""
        return [info for info in self._tasks.values() 
                if tag in info.resource_tags]

    async def cancel_task(self, name: str, timeout: Optional[float] = None) -> bool:
        """Cancel a specific task gracefully.
        
        Args:
            name: Name of the task to cancel
            timeout: Timeout for graceful cancellation
            
        Returns:
            True if task was cancelled successfully, False otherwise
        """
        if name not in self._tasks:
            logger.warning("Attempted to cancel non-existent task", name=name)
            return False
            
        task_info = self._tasks[name]
        if task_info.state not in (TaskState.RUNNING, TaskState.PENDING):
            logger.debug("Task not in cancellable state", 
                        name=name, 
                        state=task_info.state.value)
            return True
            
        logger.info("Cancelling task", name=name)
        task_info.state = TaskState.CANCELLING
        
        # Request cancellation
        task_info.task.cancel()
        
        # Wait for graceful cancellation
        cancel_timeout = timeout or self._cancellation_timeout
        try:
            await asyncio.wait_for(
                asyncio.shield(task_info.task), 
                timeout=cancel_timeout
            )
        except (asyncio.CancelledError, asyncio.TimeoutError):
            # Expected for cancelled tasks
            pass
        except Exception as e:
            logger.warning("Task raised exception during cancellation", 
                         name=name, 
                         error=str(e))
            
        return task_info.task.cancelled() or task_info.task.done()

    async def cancel_group(self, group: str, timeout: Optional[float] = None) -> int:
        """Cancel all tasks in a group.
        
        Args:
            group: Group name
            timeout: Timeout for graceful cancellation
            
        Returns:
            Number of tasks successfully cancelled
        """
        if group not in self._task_groups:
            logger.warning("Attempted to cancel non-existent group", group=group)
            return 0
            
        tasks = self.get_tasks_by_group(group)
        logger.info("Cancelling task group", group=group, count=len(tasks))
        
        # Cancel all tasks concurrently
        cancel_tasks = [
            self.cancel_task(task_info.name, timeout) 
            for task_info in tasks
        ]
        
        results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
        successful = sum(1 for result in results if result is True)
        
        logger.info("Task group cancellation completed", 
                   group=group, 
                   successful=successful, 
                   total=len(tasks))
        
        return successful

    async def cancel_all_tasks(self, timeout: Optional[float] = None) -> int:
        """Cancel all managed tasks.
        
        Args:
            timeout: Timeout for graceful cancellation
            
        Returns:
            Number of tasks successfully cancelled
        """
        running_tasks = self.get_running_tasks()
        if not running_tasks:
            logger.debug("No running tasks to cancel")
            return 0
            
        logger.info("Cancelling all tasks", count=len(running_tasks))
        
        # Sort by priority (higher priority cancelled first)
        sorted_tasks = sorted(running_tasks, key=lambda t: t.priority, reverse=True)
        
        # Cancel tasks in priority order
        cancelled_count = 0
        for task_info in sorted_tasks:
            if await self.cancel_task(task_info.name, timeout):
                cancelled_count += 1
                
        logger.info("All tasks cancellation completed", 
                   cancelled=cancelled_count, 
                   total=len(running_tasks))
        
        return cancelled_count

    async def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all tasks to complete.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if all tasks completed, False if timeout
        """
        running_tasks = self.get_running_tasks()
        if not running_tasks:
            return True
            
        logger.info("Waiting for task completion", count=len(running_tasks))
        
        # Create a list of task objects
        task_objects = [task_info.task for task_info in running_tasks]
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*task_objects, return_exceptions=True),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for task completion", 
                         timeout=timeout,
                         remaining=len(self.get_running_tasks()))
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get task manager metrics."""
        running_tasks = self.get_running_tasks()
        
        return {
            "total_created": self._total_tasks_created,
            "total_completed": self._total_tasks_completed,
            "total_cancelled": self._total_tasks_cancelled,
            "total_failed": self._total_tasks_failed,
            "currently_running": len(running_tasks),
            "groups": len(self._task_groups),
            "running_task_names": [t.name for t in running_tasks],
        }

    def cleanup(self) -> None:
        """Cleanup task manager resources."""
        logger.info("Cleaning up task manager")
        
        # Clear all tracking
        self._tasks.clear()
        self._task_groups.clear()
        
        logger.debug("Task manager cleanup completed")

    async def graceful_shutdown(self, timeout: Optional[float] = None) -> bool:
        """Perform graceful shutdown of all tasks.
        
        Args:
            timeout: Total timeout for shutdown
            
        Returns:
            True if shutdown completed successfully, False if timeout
        """
        shutdown_timeout = timeout or self._shutdown_timeout
        start_time = time.time()
        
        logger.info("Starting graceful task shutdown", timeout=shutdown_timeout)
        
        # Phase 1: Request cancellation of all tasks
        running_tasks = self.get_running_tasks()
        if not running_tasks:
            logger.info("No running tasks to shutdown")
            return True
            
        logger.info("Phase 1: Requesting task cancellation", count=len(running_tasks))
        
        # Cancel all tasks with remaining timeout
        remaining_timeout = shutdown_timeout - (time.time() - start_time)
        if remaining_timeout <= 0:
            logger.warning("Shutdown timeout exceeded before cancellation")
            return False
            
        cancelled_count = await self.cancel_all_tasks(remaining_timeout / 2)
        
        # Phase 2: Wait for completion
        remaining_timeout = shutdown_timeout - (time.time() - start_time)
        if remaining_timeout <= 0:
            logger.warning("Shutdown timeout exceeded after cancellation")
            return False
            
        logger.info("Phase 2: Waiting for task completion")
        completed = await self.wait_for_completion(remaining_timeout)
        
        # Report results
        final_running = len(self.get_running_tasks())
        total_time = time.time() - start_time
        
        if completed and final_running == 0:
            logger.info("Graceful shutdown completed successfully", 
                       duration=total_time,
                       cancelled=cancelled_count)
            return True
        else:
            logger.warning("Graceful shutdown incomplete", 
                         duration=total_time,
                         cancelled=cancelled_count,
                         still_running=final_running)
            return False

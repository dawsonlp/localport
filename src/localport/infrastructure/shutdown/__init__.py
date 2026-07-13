"""Graceful shutdown infrastructure for LocalPort daemon.

This package provides enterprise-grade shutdown capabilities including:
- Thread-safe signal handling with async coordination
- Multi-phase shutdown orchestration
- Resource cleanup accountability
- Cooperative task cancellation patterns
"""

from .cooperative_task import CooperativeTask
from .graceful_shutdown_mixin import GracefulShutdownMixin
from .shutdown_coordinator import ShutdownCoordinator
from .signal_handler import AsyncSignalHandler
from .task_manager import TaskManager

__all__ = [
    "AsyncSignalHandler",
    "ShutdownCoordinator",
    "TaskManager",
    "GracefulShutdownMixin",
    "CooperativeTask",
]

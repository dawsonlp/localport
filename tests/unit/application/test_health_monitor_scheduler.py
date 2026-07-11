"""Regression tests for HealthMonitorScheduler.

Covers two confirmed bugs on the daemon's live path:
- C1: stopping then restarting monitoring (e.g. hot config reload) must not raise.
- C2: each service must be driven by exactly one monitoring loop.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from localport.application.services.health_monitor_scheduler import HealthMonitorScheduler
from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology, ServiceStatus
from localport.domain.value_objects.connection_info import ConnectionInfo


def _running_service() -> Service:
    conn = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
    return Service.create(
        name="postgres",
        technology=ForwardingTechnology.KUBECTL,
        local_port=5433,
        remote_port=5432,
        connection_info=conn,
        health_check_config={"type": "tcp", "interval": 30},
        status=ServiceStatus.RUNNING,
    )


def _scheduler() -> HealthMonitorScheduler:
    sched = HealthMonitorScheduler(
        health_check_factory=MagicMock(),
        restart_manager=MagicMock(),
    )
    # Never perform a real health check; report healthy each iteration so no
    # restart is triggered and the loop stays cheap.
    sched._perform_health_check = AsyncMock(return_value=SimpleNamespace(is_healthy=True))
    return sched


@pytest.mark.asyncio
async def test_single_monitoring_loop_per_service():
    """C2: one loop per service, and no duplicate registration with the TaskManager."""
    sched = _scheduler()
    svc = _running_service()

    await sched.start_monitoring([svc])
    try:
        assert len(sched._cooperative_tasks) == 1
        task = sched._cooperative_tasks[svc.id]
        # The CooperativeTask owns the single running loop.
        assert task._task_handle is not None
        assert not task._task_handle.done()
        # The scheduler must NOT also register the loop with the TaskManager;
        # doing so previously ran a second, duplicate loop for every service.
        assert len(sched._task_manager._tasks) == 0
    finally:
        await sched.stop_monitoring()

    assert sched._cooperative_tasks == {}


@pytest.mark.asyncio
async def test_restart_monitoring_does_not_raise():
    """C1: stop then start again must not raise (previously ValueError on reload)."""
    sched = _scheduler()
    svc = _running_service()

    await sched.start_monitoring([svc])
    await sched.stop_monitoring()

    # Regression: this second start previously raised
    # ValueError("Task 'health_monitor_postgres' already exists").
    await sched.start_monitoring([svc])
    assert len(sched._cooperative_tasks) == 1

    await sched.stop_monitoring()

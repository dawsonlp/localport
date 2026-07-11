"""Behavioral tests for DaemonManager.

Characterizes the auto-start path (which must honor the `enabled` flag) using a
real in-memory service repository and mocked collaborators.
"""

from unittest.mock import MagicMock

import pytest

from localport.application.services.daemon_manager import DaemonManager
from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology, ServiceStatus
from localport.domain.value_objects.connection_info import ConnectionInfo
from localport.infrastructure.repositories.memory_service_repository import (
    MemoryServiceRepository,
)


def _service(name: str, local_port: int, *, enabled: bool) -> Service:
    conn = ConnectionInfo.kubectl(resource_name=name, namespace="default")
    return Service.create(
        name=name,
        technology=ForwardingTechnology.KUBECTL,
        local_port=local_port,
        remote_port=local_port,
        connection_info=conn,
        status=ServiceStatus.STOPPED,
        enabled=enabled,
    )


def _daemon(repo: MemoryServiceRepository) -> DaemonManager:
    return DaemonManager(
        service_repository=repo,
        config_repository=MagicMock(),
        service_manager=MagicMock(),
        health_monitor=MagicMock(),
    )


@pytest.mark.asyncio
async def test_auto_start_only_starts_enabled_services():
    repo = MemoryServiceRepository()
    await repo.save(_service("on-svc", 5433, enabled=True))
    await repo.save(_service("off-svc", 6444, enabled=False))

    daemon = _daemon(repo)

    started: list[str] = []

    async def fake_start(service: Service) -> None:
        started.append(service.name)

    daemon._start_service_safe = fake_start

    await daemon._auto_start_configured_services()

    assert started == ["on-svc"]

"""Tests for application services."""

import pytest

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestHealthMonitor:
    """Test cases for health monitoring."""

    @pytest.fixture
    def sample_service(self):
        """Create a sample service for testing."""
        conn = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
        return Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
            health_check_config={"type": "tcp", "interval": 30, "timeout": 5.0},
        )

    def test_service_has_health_config(self, sample_service):
        """Test that sample service has health check config."""
        assert sample_service.health_check_config is not None
        assert sample_service.health_check_config["type"] == "tcp"

    def test_service_creation(self, sample_service):
        """Test that sample service is created correctly."""
        assert sample_service.name == "postgres"
        assert sample_service.technology == ForwardingTechnology.KUBECTL
        assert sample_service.local_port == 5433


class TestDaemonManager:
    """Test cases for DaemonManager."""

    def test_daemon_manager_import(self):
        """Test that DaemonManager can be imported."""
        from localport.application.services.daemon_manager import DaemonManager

        assert DaemonManager is not None

    def test_health_monitor_scheduler_import(self):
        """Test that HealthMonitorScheduler can be imported."""
        from localport.application.services.health_monitor_scheduler import (
            HealthMonitorScheduler,
        )

        assert HealthMonitorScheduler is not None

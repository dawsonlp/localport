"""Tests for application use cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestStartServicesUseCase:
    """Test cases for start services use case."""

    def test_use_case_import(self):
        """Test that StartServicesUseCase can be imported."""
        from localport.application.use_cases.start_services import StartServicesUseCase
        assert StartServicesUseCase is not None

    def test_stop_services_import(self):
        """Test that StopServicesUseCase can be imported."""
        from localport.application.use_cases.stop_services import StopServicesUseCase
        assert StopServicesUseCase is not None


class TestManageDaemonUseCase:
    """Test cases for manage daemon use case."""

    def test_manage_daemon_import(self):
        """Test that ManageDaemonUseCase can be imported."""
        from localport.application.use_cases.manage_daemon import ManageDaemonUseCase
        assert ManageDaemonUseCase is not None

    def test_monitor_services_import(self):
        """Test that MonitorServicesUseCase can be imported."""
        from localport.application.use_cases.monitor_services import MonitorServicesUseCase
        assert MonitorServicesUseCase is not None
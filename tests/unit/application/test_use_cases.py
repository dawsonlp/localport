"""Comprehensive tests for application use cases."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.localport.application.dto.service_dto import (
    ServiceMonitorResult,
    ServiceStartResult,
)
from src.localport.application.use_cases.manage_daemon import (
    DaemonCommand,
    ManageDaemonCommand,
    ManageDaemonUseCase,
)
from src.localport.application.use_cases.monitor_services import (
    MonitorServicesCommand,
    MonitorServicesUseCase,
)
from src.localport.application.use_cases.start_services import (
    StartServicesCommand,
    StartServicesUseCase,
)
from src.localport.application.use_cases.stop_services import (
    StopServicesCommand,
    StopServicesUseCase,
)
from src.localport.domain.entities.service import (
    ForwardingTechnology,
    Service,
    ServiceStatus,
)


class TestStartServicesUseCase:
    """Test cases for StartServicesUseCase."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_service_repository, mock_service_manager):
        """Create StartServicesUseCase instance."""
        return StartServicesUseCase(mock_service_repository, mock_service_manager)

    @pytest.fixture
    def sample_service(self):
        """Create a sample service for testing."""
        return Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )

    @pytest.mark.asyncio
    async def test_start_all_services_success(self, use_case, mock_service_repository, mock_service_manager, sample_service):
        """Test starting all services successfully."""
        # Arrange
        mock_service_repository.find_all.return_value = [sample_service]
        mock_service_manager.start_service.return_value = ServiceStartResult.success_result(
            "test-service", 12345
        )

        command = StartServicesCommand(all_services=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].service_name == "test-service"
        assert results[0].process_id == 12345
        mock_service_repository.find_all.assert_called_once()
        mock_service_manager.start_service.assert_called_once_with(sample_service)

    @pytest.mark.asyncio
    async def test_start_services_by_name(self, use_case, mock_service_repository, mock_service_manager, sample_service):
        """Test starting services by name."""
        # Arrange
        mock_service_repository.find_by_name.return_value = sample_service
        mock_service_manager.start_service.return_value = ServiceStartResult.success_result(
            "test-service", 12345
        )

        command = StartServicesCommand(service_names=["test-service"])

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is True
        mock_service_repository.find_by_name.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_start_services_by_tags(self, use_case, mock_service_repository, mock_service_manager, sample_service):
        """Test starting services by tags."""
        # Arrange
        mock_service_repository.find_by_tags.return_value = [sample_service]
        mock_service_manager.start_service.return_value = ServiceStartResult.success_result(
            "test-service", 12345
        )

        command = StartServicesCommand(tags=["database"])

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is True
        mock_service_repository.find_by_tags.assert_called_once_with(["database"])

    @pytest.mark.asyncio
    async def test_start_service_failure(self, use_case, mock_service_repository, mock_service_manager, sample_service):
        """Test handling service start failure."""
        # Arrange
        mock_service_repository.find_all.return_value = [sample_service]
        mock_service_manager.start_service.side_effect = RuntimeError("Port already in use")

        command = StartServicesCommand(all_services=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is False
        assert "Port already in use" in results[0].error

    @pytest.mark.asyncio
    async def test_start_nonexistent_service(self, use_case, mock_service_repository, mock_service_manager):
        """Test starting a service that doesn't exist."""
        # Arrange
        mock_service_repository.find_by_name.return_value = None

        command = StartServicesCommand(service_names=["nonexistent"])

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 0
        mock_service_manager.start_service.assert_not_called()


class TestStopServicesUseCase:
    """Test cases for StopServicesUseCase."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_service_repository, mock_service_manager):
        """Create StopServicesUseCase instance."""
        return StopServicesUseCase(mock_service_repository, mock_service_manager)

    @pytest.fixture
    def running_service(self):
        """Create a running service for testing."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        service.status = ServiceStatus.RUNNING
        return service

    @pytest.mark.asyncio
    async def test_stop_all_services_success(self, use_case, mock_service_repository, mock_service_manager, running_service):
        """Test stopping all services successfully."""
        # Arrange
        mock_service_repository.find_all.return_value = [running_service]
        mock_service_manager.stop_service.return_value = True

        command = StopServicesCommand(all_services=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].service_name == "test-service"
        mock_service_manager.stop_service.assert_called_once_with(running_service)

    @pytest.mark.asyncio
    async def test_stop_service_failure(self, use_case, mock_service_repository, mock_service_manager, running_service):
        """Test handling service stop failure."""
        # Arrange
        mock_service_repository.find_all.return_value = [running_service]
        mock_service_manager.stop_service.side_effect = RuntimeError("Process not found")

        command = StopServicesCommand(all_services=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is False
        assert "Process not found" in results[0].error

    @pytest.mark.asyncio
    async def test_stop_with_force(self, use_case, mock_service_repository, mock_service_manager, running_service):
        """Test stopping services with force option."""
        # Arrange
        mock_service_repository.find_all.return_value = [running_service]
        mock_service_manager.stop_service.return_value = True

        command = StopServicesCommand(all_services=True, force=True, timeout=5.0)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].success is True


class TestMonitorServicesUseCase:
    """Test cases for MonitorServicesUseCase."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_health_monitor(self):
        """Create a mock health monitor."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_service_repository, mock_health_monitor):
        """Create MonitorServicesUseCase instance."""
        return MonitorServicesUseCase(mock_service_repository, mock_health_monitor)

    @pytest.fixture
    def healthy_service(self):
        """Create a healthy service for testing."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        service.status = ServiceStatus.RUNNING
        return service

    @pytest.mark.asyncio
    async def test_monitor_all_services(self, use_case, mock_service_repository, mock_health_monitor, healthy_service):
        """Test monitoring all services."""
        # Arrange
        mock_service_repository.find_all.return_value = [healthy_service]
        mock_health_monitor.check_service_health.return_value = ServiceMonitorResult(
            service_name="test-service",
            is_healthy=True,
            last_check=datetime.now(),
            failure_count=0
        )

        command = MonitorServicesCommand(all_services=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].service_name == "test-service"
        assert results[0].is_healthy is True
        assert results[0].failure_count == 0

    @pytest.mark.asyncio
    async def test_monitor_unhealthy_service_with_restart(self, use_case, mock_service_repository, mock_health_monitor, healthy_service):
        """Test monitoring unhealthy service with restart."""
        # Arrange
        healthy_service.status = ServiceStatus.FAILED
        mock_service_repository.find_all.return_value = [healthy_service]
        mock_health_monitor.check_service_health.return_value = ServiceMonitorResult(
            service_name="test-service",
            is_healthy=False,
            last_check=datetime.now(),
            failure_count=3,
            restart_attempted=True,
            restart_success=True
        )

        command = MonitorServicesCommand(all_services=True, restart_failed=True)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].restart_attempted is True
        assert results[0].restart_success is True

    @pytest.mark.asyncio
    async def test_monitor_with_interval(self, use_case, mock_service_repository, mock_health_monitor, healthy_service):
        """Test monitoring with custom interval."""
        # Arrange
        mock_service_repository.find_all.return_value = [healthy_service]
        mock_health_monitor.check_service_health.return_value = ServiceMonitorResult(
            service_name="test-service",
            is_healthy=True,
            last_check=datetime.now(),
            failure_count=0
        )

        command = MonitorServicesCommand(all_services=True, interval=60)

        # Act
        results = await use_case.execute(command)

        # Assert
        assert len(results) == 1
        assert results[0].is_healthy is True


class TestManageDaemonUseCase:
    """Test cases for ManageDaemonUseCase."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_service_repository, mock_service_manager):
        """Create ManageDaemonUseCase instance."""
        return ManageDaemonUseCase(mock_service_repository, mock_service_manager)

    @pytest.mark.asyncio
    async def test_start_daemon_success(self, use_case):
        """Test starting daemon successfully."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.START)

        with patch.object(use_case, '_is_daemon_running', return_value=False), \
             patch.object(use_case, '_start_daemon_process', return_value=12345), \
             patch.object(use_case, '_write_pid_file'):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.pid == 12345
            assert "started with PID 12345" in result.message

    @pytest.mark.asyncio
    async def test_start_daemon_already_running(self, use_case):
        """Test starting daemon when already running."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.START)

        with patch.object(use_case, '_is_daemon_running', return_value=True):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is False
            assert "already running" in result.error

    @pytest.mark.asyncio
    async def test_start_daemon_with_force(self, use_case):
        """Test starting daemon with force option."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.START, force=True)

        with patch.object(use_case, '_is_daemon_running', return_value=True), \
             patch.object(use_case, '_stop_daemon_process'), \
             patch.object(use_case, '_start_daemon_process', return_value=12345), \
             patch.object(use_case, '_write_pid_file'):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.pid == 12345

    @pytest.mark.asyncio
    async def test_stop_daemon_success(self, use_case):
        """Test stopping daemon successfully."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.STOP)

        with patch.object(use_case, '_is_daemon_running', return_value=True), \
             patch.object(use_case, '_get_daemon_pid', return_value=12345), \
             patch.object(use_case, '_stop_daemon_process'), \
             patch.object(use_case, '_remove_pid_file'):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.pid == 12345
            assert "stopped" in result.message

    @pytest.mark.asyncio
    async def test_stop_daemon_not_running(self, use_case):
        """Test stopping daemon when not running."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.STOP)

        with patch.object(use_case, '_is_daemon_running', return_value=False):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is False
            assert "not running" in result.error

    @pytest.mark.asyncio
    async def test_daemon_status_running(self, use_case, mock_service_repository):
        """Test getting daemon status when running."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.STATUS)
        mock_service_repository.find_all.return_value = [MagicMock()]  # One service

        with patch.object(use_case, '_is_daemon_running', return_value=True), \
             patch.object(use_case, '_get_daemon_pid', return_value=12345), \
             patch.object(use_case, '_get_daemon_uptime', return_value=3600.0), \
             patch.object(use_case, '_get_active_services_count', return_value=1):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.status.running is True
            assert result.status.pid == 12345
            assert result.status.uptime_seconds == 3600.0
            assert result.status.active_services == 1

    @pytest.mark.asyncio
    async def test_daemon_status_not_running(self, use_case):
        """Test getting daemon status when not running."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.STATUS)

        with patch.object(use_case, '_is_daemon_running', return_value=False):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.status.running is False
            assert "not running" in result.message

    @pytest.mark.asyncio
    async def test_restart_daemon(self, use_case):
        """Test restarting daemon."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.RESTART)

        with patch.object(use_case, '_is_daemon_running', return_value=True), \
             patch.object(use_case, '_get_daemon_pid', return_value=12345), \
             patch.object(use_case, '_stop_daemon_process'), \
             patch.object(use_case, '_remove_pid_file'), \
             patch.object(use_case, '_start_daemon_process', return_value=54321), \
             patch.object(use_case, '_write_pid_file'):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.pid == 54321
            assert "restarted" in result.message

    @pytest.mark.asyncio
    async def test_reload_daemon(self, use_case):
        """Test reloading daemon configuration."""
        # Arrange
        command = ManageDaemonCommand(DaemonCommand.RELOAD)

        with patch.object(use_case, '_is_daemon_running', return_value=True), \
             patch.object(use_case, '_get_daemon_pid', return_value=12345), \
             patch.object(use_case, '_send_reload_signal'):

            # Act
            result = await use_case.execute(command)

            # Assert
            assert result.success is True
            assert result.pid == 12345
            assert "reloaded" in result.message

    @pytest.mark.asyncio
    async def test_unknown_daemon_command(self, use_case):
        """Test handling unknown daemon command."""
        # Arrange - Create an invalid command by directly setting the enum value
        command = ManageDaemonCommand(DaemonCommand.START)
        command.command = "invalid"  # Manually set invalid command

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.success is False
        assert "Unknown daemon command" in result.error


class TestUseCaseIntegration:
    """Integration tests for use cases working together."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_health_monitor(self):
        """Create a mock health monitor."""
        return AsyncMock()

    @pytest.fixture
    def sample_services(self):
        """Create sample services for testing."""
        return [
            Service.create(
                name="postgres",
                technology=ForwardingTechnology.KUBECTL,
                local_port=5432,
                remote_port=5432,
                connection_info={"resource_name": "postgres"},
                tags=["database"]
            ),
            Service.create(
                name="redis",
                technology=ForwardingTechnology.SSH,
                local_port=6379,
                remote_port=6379,
                connection_info={"host": "redis.example.com"},
                tags=["cache"]
            )
        ]

    @pytest.mark.asyncio
    async def test_start_monitor_stop_workflow(self, mock_service_repository, mock_service_manager, mock_health_monitor, sample_services):
        """Test complete workflow: start -> monitor -> stop services."""
        # Arrange
        mock_service_repository.find_all.return_value = sample_services
        mock_service_manager.start_service.side_effect = [
            ServiceStartResult.success_result("postgres", 12345),
            ServiceStartResult.success_result("redis", 12346)
        ]
        mock_service_manager.stop_service.return_value = True
        mock_health_monitor.check_service_health.side_effect = [
            ServiceMonitorResult("postgres", True, datetime.now(), 0),
            ServiceMonitorResult("redis", True, datetime.now(), 0)
        ]

        start_use_case = StartServicesUseCase(mock_service_repository, mock_service_manager)
        monitor_use_case = MonitorServicesUseCase(mock_service_repository, mock_health_monitor)
        stop_use_case = StopServicesUseCase(mock_service_repository, mock_service_manager)

        # Act - Start services
        start_results = await start_use_case.execute(StartServicesCommand(all_services=True))

        # Act - Monitor services
        monitor_results = await monitor_use_case.execute(MonitorServicesCommand(all_services=True))

        # Act - Stop services
        stop_results = await stop_use_case.execute(StopServicesCommand(all_services=True))

        # Assert
        assert len(start_results) == 2
        assert all(r.success for r in start_results)

        assert len(monitor_results) == 2
        assert all(r.is_healthy for r in monitor_results)

        assert len(stop_results) == 2
        assert all(r.success for r in stop_results)

    @pytest.mark.asyncio
    async def test_daemon_lifecycle_with_services(self, mock_service_repository, mock_service_manager, sample_services):
        """Test daemon lifecycle with service management."""
        # Arrange
        mock_service_repository.find_all.return_value = sample_services
        daemon_use_case = ManageDaemonUseCase(mock_service_repository, mock_service_manager)

        with patch.object(daemon_use_case, '_is_daemon_running', side_effect=[False, True, True, False]), \
             patch.object(daemon_use_case, '_start_daemon_process', return_value=12345), \
             patch.object(daemon_use_case, '_write_pid_file'), \
             patch.object(daemon_use_case, '_get_daemon_pid', return_value=12345), \
             patch.object(daemon_use_case, '_get_daemon_uptime', return_value=3600.0), \
             patch.object(daemon_use_case, '_get_active_services_count', return_value=2), \
             patch.object(daemon_use_case, '_stop_daemon_process'), \
             patch.object(daemon_use_case, '_remove_pid_file'):

            # Act - Start daemon
            start_result = await daemon_use_case.execute(ManageDaemonCommand(DaemonCommand.START))

            # Act - Check status
            status_result = await daemon_use_case.execute(ManageDaemonCommand(DaemonCommand.STATUS))

            # Act - Stop daemon
            stop_result = await daemon_use_case.execute(ManageDaemonCommand(DaemonCommand.STOP))

            # Assert
            assert start_result.success is True
            assert start_result.pid == 12345

            assert status_result.success is True
            assert status_result.status.running is True
            assert status_result.status.active_services == 2

            assert stop_result.success is True

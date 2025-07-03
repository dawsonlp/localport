"""Comprehensive tests for application services."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.localport.application.services.daemon_manager import DaemonManager
from src.localport.application.services.health_monitor import HealthMonitor
from src.localport.domain.entities.service import (
    ForwardingTechnology,
    Service,
    ServiceStatus,
)


class TestHealthMonitor:
    """Test cases for HealthMonitor service."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_health_check_factory(self):
        """Create a mock health check factory."""
        return AsyncMock()

    @pytest.fixture
    def health_monitor(self, mock_service_repository, mock_service_manager, mock_health_check_factory):
        """Create HealthMonitor instance."""
        return HealthMonitor(
            mock_service_repository,
            mock_service_manager,
            mock_health_check_factory
        )

    @pytest.fixture
    def sample_service(self):
        """Create a sample service with health check configuration."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        service.health_check_config = {
            "type": "tcp",
            "timeout": 5.0,
            "failure_threshold": 3
        }
        service.status = ServiceStatus.RUNNING
        return service

    @pytest.mark.asyncio
    async def test_start_monitoring_success(self, health_monitor, mock_service_repository, sample_service):
        """Test starting health monitoring successfully."""
        # Arrange
        mock_service_repository.find_all.return_value = [sample_service]

        # Act
        await health_monitor.start_monitoring()

        # Assert
        assert health_monitor.is_monitoring is True
        assert health_monitor.monitored_service_count == 1
        mock_service_repository.find_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self, health_monitor, mock_service_repository):
        """Test starting monitoring when already running."""
        # Arrange
        health_monitor._is_monitoring = True

        # Act
        await health_monitor.start_monitoring()

        # Assert
        mock_service_repository.find_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, health_monitor):
        """Test stopping health monitoring."""
        # Arrange
        health_monitor._is_monitoring = True
        health_monitor._monitor_task = AsyncMock()

        # Act
        await health_monitor.stop_monitoring()

        # Assert
        assert health_monitor.is_monitoring is False
        health_monitor._monitor_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_service_health_no_config(self, health_monitor, sample_service):
        """Test health check for service without health check configuration."""
        # Arrange
        sample_service.health_check_config = None

        # Act
        result = await health_monitor.check_service_health(sample_service)

        # Assert
        assert result.service_name == "test-service"
        assert result.is_healthy is True  # Running service without health check is considered healthy
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_check_service_health_success(self, health_monitor, mock_health_check_factory, sample_service):
        """Test successful health check."""
        # Arrange
        mock_health_check = AsyncMock()
        mock_health_check.check.return_value = True
        mock_health_check_factory.create_health_check.return_value = mock_health_check

        # Initialize health state
        health_monitor._initialize_health_state(sample_service)

        # Act
        result = await health_monitor.check_service_health(sample_service)

        # Assert
        assert result.service_name == "test-service"
        assert result.is_healthy is True
        assert result.failure_count == 0
        assert result.restart_attempted is False
        mock_health_check.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_service_health_failure(self, health_monitor, mock_health_check_factory, sample_service):
        """Test failed health check."""
        # Arrange
        mock_health_check = AsyncMock()
        mock_health_check.check.return_value = False
        mock_health_check_factory.create_health_check.return_value = mock_health_check

        # Initialize health state
        health_monitor._initialize_health_state(sample_service)

        # Act
        result = await health_monitor.check_service_health(sample_service)

        # Assert
        assert result.service_name == "test-service"
        assert result.is_healthy is False
        assert result.failure_count == 1
        assert result.restart_attempted is False  # Below threshold

    @pytest.mark.asyncio
    async def test_check_service_health_restart_threshold(self, health_monitor, mock_health_check_factory, mock_service_manager, sample_service):
        """Test health check triggering restart when threshold is reached."""
        # Arrange
        mock_health_check = AsyncMock()
        mock_health_check.check.return_value = False
        mock_health_check_factory.create_health_check.return_value = mock_health_check

        # Mock successful restart
        from src.localport.application.dto.service_dto import ServiceStartResult
        mock_service_manager.stop_service.return_value = True
        mock_service_manager.start_service.return_value = ServiceStartResult.success_result("test-service", 12345)

        # Initialize health state and set failure count to threshold
        health_monitor._initialize_health_state(sample_service)
        health_monitor._failure_counts[sample_service.id] = 3

        # Act
        result = await health_monitor.check_service_health(sample_service)

        # Assert
        assert result.service_name == "test-service"
        assert result.is_healthy is False
        assert result.restart_attempted is True
        assert result.restart_success is True

    @pytest.mark.asyncio
    async def test_check_service_health_exception(self, health_monitor, mock_health_check_factory, sample_service):
        """Test health check with exception."""
        # Arrange
        mock_health_check_factory.create_health_check.side_effect = Exception("Health check error")

        # Act
        result = await health_monitor.check_service_health(sample_service)

        # Assert
        assert result.service_name == "test-service"
        assert result.is_healthy is False
        assert result.failure_count == 1
        assert "Health check error" in result.error

    @pytest.mark.asyncio
    async def test_get_health_status(self, health_monitor, sample_service):
        """Test getting health status for a service."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)

        # Act
        status = await health_monitor.get_health_status(sample_service.id)

        # Assert
        assert status is not None
        assert status.service_name == "test-service"
        assert status.check_type == "tcp"

    @pytest.mark.asyncio
    async def test_get_all_health_status(self, health_monitor, sample_service):
        """Test getting all health statuses."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)

        # Act
        statuses = await health_monitor.get_all_health_status()

        # Assert
        assert len(statuses) == 1
        assert sample_service.id in statuses

    @pytest.mark.asyncio
    async def test_reset_failure_count(self, health_monitor, sample_service):
        """Test resetting failure count for a service."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)
        health_monitor._failure_counts[sample_service.id] = 5

        # Act
        await health_monitor.reset_failure_count(sample_service.id)

        # Assert
        assert health_monitor._failure_counts[sample_service.id] == 0
        health_info = health_monitor._health_states[sample_service.id]
        assert health_info.consecutive_failures == 0
        assert health_info.status == "healthy"

    @pytest.mark.asyncio
    async def test_set_monitoring_interval(self, health_monitor):
        """Test setting monitoring interval."""
        # Act
        await health_monitor.set_monitoring_interval(60)

        # Assert
        assert health_monitor._default_check_interval == 60

    @pytest.mark.asyncio
    async def test_set_monitoring_interval_invalid(self, health_monitor):
        """Test setting invalid monitoring interval."""
        # Act & Assert
        with pytest.raises(ValueError, match="at least 5 seconds"):
            await health_monitor.set_monitoring_interval(3)

    @pytest.mark.asyncio
    async def test_set_failure_threshold(self, health_monitor, sample_service):
        """Test setting failure threshold for a service."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)

        # Act
        await health_monitor.set_failure_threshold(sample_service.id, 5)

        # Assert
        health_info = health_monitor._health_states[sample_service.id]
        assert health_info.failure_threshold == 5

    @pytest.mark.asyncio
    async def test_set_failure_threshold_invalid(self, health_monitor, sample_service):
        """Test setting invalid failure threshold."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)

        # Act & Assert
        with pytest.raises(ValueError, match="at least 1"):
            await health_monitor.set_failure_threshold(sample_service.id, 0)

    @pytest.mark.asyncio
    async def test_get_monitoring_statistics(self, health_monitor, mock_service_repository, sample_service):
        """Test getting monitoring statistics."""
        # Arrange
        health_monitor._initialize_health_state(sample_service)
        health_monitor._is_monitoring = True
        mock_service_repository.find_all.return_value = [sample_service]

        # Act
        stats = await health_monitor.get_monitoring_statistics()

        # Assert
        assert stats["is_monitoring"] is True
        assert stats["monitored_services"] == 1
        assert stats["healthy_services"] == 0  # Status is "unknown" initially
        assert stats["unhealthy_services"] == 1
        assert "monitoring_interval" in stats
        assert "restart_cooldown" in stats


class TestDaemonManager:
    """Test cases for DaemonManager service."""

    @pytest.fixture
    def mock_service_repository(self):
        """Create a mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_config_repository(self):
        """Create a mock config repository."""
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
    def daemon_manager(self, mock_service_repository, mock_config_repository, mock_service_manager, mock_health_monitor):
        """Create DaemonManager instance."""
        return DaemonManager(
            mock_service_repository,
            mock_config_repository,
            mock_service_manager,
            mock_health_monitor
        )

    @pytest.fixture
    def sample_services(self):
        """Create sample services for testing."""
        return [
            Service.create(
                name="service1",
                technology=ForwardingTechnology.KUBECTL,
                local_port=8080,
                remote_port=80,
                connection_info={"resource_name": "service1"}
            ),
            Service.create(
                name="service2",
                technology=ForwardingTechnology.SSH,
                local_port=9090,
                remote_port=90,
                connection_info={"host": "example.com"}
            )
        ]

    @pytest.mark.asyncio
    async def test_start_daemon_success(self, daemon_manager, mock_config_repository, mock_service_repository, sample_services):
        """Test starting daemon successfully."""
        # Arrange
        mock_config_repository.load_services.return_value = sample_services
        mock_service_repository.find_all.return_value = sample_services

        with patch.object(daemon_manager, '_setup_signal_handlers'), \
             patch.object(daemon_manager, '_start_background_tasks'):

            # Act
            await daemon_manager.start_daemon()

            # Assert
            assert daemon_manager.is_running is True
            assert daemon_manager.started_at is not None
            mock_config_repository.load_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_daemon_already_running(self, daemon_manager):
        """Test starting daemon when already running."""
        # Arrange
        daemon_manager._is_running = True

        # Act
        await daemon_manager.start_daemon()

        # Assert - Should not raise exception, just log warning
        assert daemon_manager.is_running is True

    @pytest.mark.asyncio
    async def test_start_daemon_failure(self, daemon_manager, mock_config_repository):
        """Test daemon start failure."""
        # Arrange
        mock_config_repository.load_services.side_effect = Exception("Config error")

        with patch.object(daemon_manager, '_setup_signal_handlers'), \
             patch.object(daemon_manager, 'stop_daemon') as mock_stop:

            # Act & Assert
            with pytest.raises(Exception, match="Config error"):
                await daemon_manager.start_daemon()

            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_daemon(self, daemon_manager, mock_health_monitor):
        """Test stopping daemon."""
        # Arrange
        daemon_manager._is_running = True
        daemon_manager._shutdown_event = asyncio.Event()

        with patch.object(daemon_manager, '_stop_all_services'), \
             patch.object(daemon_manager, '_cancel_background_tasks'), \
             patch.object(daemon_manager, '_restore_signal_handlers'):

            # Act
            await daemon_manager.stop_daemon()

            # Assert
            assert daemon_manager.is_running is False
            assert daemon_manager._shutdown_event.is_set()
            mock_health_monitor.stop_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_daemon_not_running(self, daemon_manager):
        """Test stopping daemon when not running."""
        # Arrange
        daemon_manager._is_running = False

        # Act
        await daemon_manager.stop_daemon()

        # Assert - Should not raise exception
        assert daemon_manager.is_running is False

    @pytest.mark.asyncio
    async def test_reload_configuration(self, daemon_manager, mock_config_repository, mock_health_monitor, sample_services):
        """Test reloading configuration."""
        # Arrange
        daemon_manager._is_running = True
        daemon_manager._enable_health_monitoring = True
        mock_config_repository.load_services.return_value = sample_services

        with patch.object(daemon_manager, '_reconcile_services'):

            # Act
            await daemon_manager.reload_configuration()

            # Assert
            mock_config_repository.load_services.assert_called_once()
            mock_health_monitor.stop_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_configuration_not_running(self, daemon_manager, mock_config_repository):
        """Test reloading configuration when daemon not running."""
        # Arrange
        daemon_manager._is_running = False

        # Act
        await daemon_manager.reload_configuration()

        # Assert
        mock_config_repository.load_services.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_daemon_status(self, daemon_manager, mock_service_repository, mock_health_monitor, sample_services):
        """Test getting daemon status."""
        # Arrange
        daemon_manager._is_running = True
        daemon_manager._started_at = datetime.now() - timedelta(hours=1)

        # Set up running services
        sample_services[0].status = ServiceStatus.RUNNING
        sample_services[1].status = ServiceStatus.STOPPED
        mock_service_repository.find_all.return_value = sample_services

        # Set up health monitoring
        mock_health_monitor.is_monitoring = True
        mock_health_monitor.get_all_health_status.return_value = {
            sample_services[0].id: MagicMock(last_check=datetime.now())
        }

        # Act
        status = await daemon_manager.get_daemon_status()

        # Assert
        assert status.is_running is True
        assert status.started_at == daemon_manager._started_at
        assert status.uptime_seconds is not None
        assert status.managed_services == 2
        assert status.active_forwards == 1
        assert status.health_checks_enabled is True
        assert status.last_health_check is not None

    @pytest.mark.asyncio
    async def test_run_until_shutdown(self, daemon_manager):
        """Test running daemon until shutdown."""
        # Arrange
        daemon_manager._is_running = True
        daemon_manager._shutdown_event = asyncio.Event()

        # Set shutdown event after short delay
        async def set_shutdown():
            await asyncio.sleep(0.1)
            daemon_manager._shutdown_event.set()

        with patch.object(daemon_manager, 'stop_daemon') as mock_stop:

            # Act
            shutdown_task = asyncio.create_task(set_shutdown())
            await daemon_manager.run_until_shutdown()
            await shutdown_task

            # Assert
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_until_shutdown_not_running(self, daemon_manager):
        """Test running daemon when not running."""
        # Arrange
        daemon_manager._is_running = False

        # Act & Assert
        with pytest.raises(RuntimeError, match="not running"):
            await daemon_manager.run_until_shutdown()

    @pytest.mark.asyncio
    async def test_auto_start_configured_services(self, daemon_manager, mock_service_repository, mock_service_manager, sample_services):
        """Test auto-starting configured services."""
        # Arrange
        mock_service_repository.find_all.return_value = sample_services

        from src.localport.application.dto.service_dto import ServiceStartResult
        mock_service_manager.start_service.return_value = ServiceStartResult.success_result("test", 12345)

        # Act
        await daemon_manager._auto_start_configured_services()

        # Assert
        assert mock_service_manager.start_service.call_count == 2

    @pytest.mark.asyncio
    async def test_auto_start_no_services(self, daemon_manager, mock_service_repository):
        """Test auto-starting when no services configured."""
        # Arrange
        mock_service_repository.find_all.return_value = []

        # Act
        await daemon_manager._auto_start_configured_services()

        # Assert - Should not raise exception
        mock_service_repository.find_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_auto_start_services(self, daemon_manager):
        """Test setting auto-start services configuration."""
        # Act
        await daemon_manager.set_auto_start_services(False)

        # Assert
        assert daemon_manager._auto_start_services is False

    @pytest.mark.asyncio
    async def test_set_health_monitoring_enable(self, daemon_manager, mock_health_monitor):
        """Test enabling health monitoring."""
        # Arrange
        daemon_manager._is_running = True
        mock_health_monitor.is_monitoring = False

        with patch.object(daemon_manager, '_start_health_monitoring') as mock_start:

            # Act
            await daemon_manager.set_health_monitoring(True)

            # Assert
            assert daemon_manager._enable_health_monitoring is True
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_health_monitoring_disable(self, daemon_manager, mock_health_monitor):
        """Test disabling health monitoring."""
        # Arrange
        daemon_manager._is_running = True
        mock_health_monitor.is_monitoring = True

        # Act
        await daemon_manager.set_health_monitoring(False)

        # Assert
        assert daemon_manager._enable_health_monitoring is False
        mock_health_monitor.stop_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_config_reload(self, daemon_manager):
        """Test setting config reload capability."""
        # Act
        await daemon_manager.set_config_reload(False)

        # Assert
        assert daemon_manager._config_reload_enabled is False

    def test_setup_signal_handlers_unix(self, daemon_manager):
        """Test setting up signal handlers on Unix systems."""
        with patch('sys.platform', 'linux'), \
             patch('signal.signal') as mock_signal:

            # Act
            daemon_manager._setup_signal_handlers()

            # Assert
            assert mock_signal.call_count == 3  # SIGTERM, SIGINT, SIGUSR1

    def test_setup_signal_handlers_windows(self, daemon_manager):
        """Test setting up signal handlers on Windows."""
        with patch('sys.platform', 'win32'), \
             patch('signal.signal') as mock_signal:

            # Act
            daemon_manager._setup_signal_handlers()

            # Assert
            mock_signal.assert_not_called()  # No signal setup on Windows

    def test_restore_signal_handlers(self, daemon_manager):
        """Test restoring signal handlers."""
        # Arrange
        daemon_manager._original_handlers = {15: MagicMock()}  # SIGTERM

        with patch('sys.platform', 'linux'), \
             patch('signal.signal') as mock_signal:

            # Act
            daemon_manager._restore_signal_handlers()

            # Assert
            mock_signal.assert_called_once()
            assert len(daemon_manager._original_handlers) == 0


class TestApplicationServiceIntegration:
    """Integration tests for application services working together."""

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        return {
            'service_repository': AsyncMock(),
            'config_repository': AsyncMock(),
            'health_check_factory': AsyncMock()
        }

    @pytest.fixture
    def service_manager(self):
        """Create a mock service manager."""
        return AsyncMock()

    @pytest.fixture
    def integrated_services(self, mock_repositories, service_manager):
        """Create integrated application services."""
        health_monitor = HealthMonitor(
            mock_repositories['service_repository'],
            service_manager,
            mock_repositories['health_check_factory']
        )

        daemon_manager = DaemonManager(
            mock_repositories['service_repository'],
            mock_repositories['config_repository'],
            service_manager,
            health_monitor
        )

        return {
            'health_monitor': health_monitor,
            'daemon_manager': daemon_manager,
            'service_manager': service_manager
        }

    @pytest.fixture
    def sample_service_with_health_check(self):
        """Create a sample service with health check configuration."""
        service = Service.create(
            name="integrated-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        service.health_check_config = {
            "type": "tcp",
            "timeout": 5.0,
            "failure_threshold": 2
        }
        service.status = ServiceStatus.RUNNING
        return service

    @pytest.mark.asyncio
    async def test_daemon_with_health_monitoring_lifecycle(self, integrated_services, mock_repositories, sample_service_with_health_check):
        """Test complete daemon lifecycle with health monitoring."""
        # Arrange
        daemon_manager = integrated_services['daemon_manager']
        health_monitor = integrated_services['health_monitor']

        mock_repositories['config_repository'].load_services.return_value = [sample_service_with_health_check]
        mock_repositories['service_repository'].find_all.return_value = [sample_service_with_health_check]

        with patch.object(daemon_manager, '_setup_signal_handlers'), \
             patch.object(daemon_manager, '_start_background_tasks'), \
             patch.object(daemon_manager, '_restore_signal_handlers'):

            # Act - Start daemon
            await daemon_manager.start_daemon()

            # Assert daemon started
            assert daemon_manager.is_running is True

            # Act - Check health monitoring started
            assert health_monitor.is_monitoring is True

            # Act - Stop daemon
            await daemon_manager.stop_daemon()

            # Assert daemon stopped
            assert daemon_manager.is_running is False
            assert health_monitor.is_monitoring is False

    @pytest.mark.asyncio
    async def test_health_monitor_with_service_restart(self, integrated_services, mock_repositories, sample_service_with_health_check):
        """Test health monitor triggering service restart through service manager."""
        # Arrange
        health_monitor = integrated_services['health_monitor']
        service_manager = integrated_services['service_manager']

        # Mock health check failure
        mock_health_check = AsyncMock()
        mock_health_check.check.return_value = False
        mock_repositories['health_check_factory'].create_health_check.return_value = mock_health_check

        # Mock successful restart
        from src.localport.application.dto.service_dto import ServiceStartResult
        service_manager.stop_service.return_value = True
        service_manager.start_service.return_value = ServiceStartResult.success_result("integrated-service", 12345)

        # Initialize health state and set failure count to threshold
        health_monitor._initialize_health_state(sample_service_with_health_check)
        health_monitor._failure_counts[sample_service_with_health_check.id] = 2

        # Act
        result = await health_monitor.check_service_health(sample_service_with_health_check)

        # Assert
        assert result.restart_attempted is True
        assert result.restart_success is True
        service_manager.stop_service.assert_called_once_with(sample_service_with_health_check)
        service_manager.start_service.assert_called_once_with(sample_service_with_health_check)

    @pytest.mark.asyncio
    async def test_daemon_configuration_reload_with_health_monitoring(self, integrated_services, mock_repositories, sample_service_with_health_check):
        """Test daemon configuration reload affecting health monitoring."""
        # Arrange
        daemon_manager = integrated_services['daemon_manager']
        health_monitor = integrated_services['health_monitor']

        daemon_manager._is_running = True
        daemon_manager._enable_health_monitoring = True

        # New service configuration
        new_service = Service.create(
            name="new-service",
            technology=ForwardingTechnology.SSH,
            local_port=9090,
            remote_port=90,
            connection_info={"host": "example.com"}
        )
        new_service.health_check_config = {"type": "http", "timeout": 3.0}

        mock_repositories['config_repository'].load_services.return_value = [sample_service_with_health_check, new_service]

        with patch.object(daemon_manager, '_reconcile_services'):

            # Act
            await daemon_manager.reload_configuration()

            # Assert
            mock_repositories['config_repository'].load_services.assert_called_once()
            # Health monitoring should be restarted
            health_monitor.stop_monitoring.assert_called()

    @pytest.mark.asyncio
    async def test_daemon_graceful_shutdown_with_services(self, integrated_services, mock_repositories, sample_service_with_health_check):
        """Test daemon graceful shutdown stopping all services."""
        # Arrange
        daemon_manager = integrated_services['daemon_manager']
        service_manager = integrated_services['service_manager']

        daemon_manager._is_running = True
        sample_service_with_health_check.status = ServiceStatus.RUNNING
        mock_repositories['service_repository'].find_all.return_value = [sample_service_with_health_check]
        service_manager.stop_service.return_value = True

        with patch.object(daemon_manager, '_cancel_background_tasks'), \
             patch.object(daemon_manager, '_restore_signal_handlers'):

            # Act
            await daemon_manager.stop_daemon()

            # Assert
            service_manager.stop_service.assert_called_once_with(sample_service_with_health_check)
            assert daemon_manager.is_running is False

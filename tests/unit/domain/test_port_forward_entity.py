"""Unit tests for PortForward entity."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from localport.domain.entities.port_forward import PortForward


class TestPortForwardEntity:
    """Unit tests for PortForward entity."""

    def test_create_port_forward(self) -> None:
        """Test port forward creation."""
        service_id = uuid4()
        started_at = datetime.now()

        port_forward = PortForward(
            service_id=service_id,
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=started_at
        )

        assert port_forward.service_id == service_id
        assert port_forward.process_id == 12345
        assert port_forward.local_port == 8080
        assert port_forward.remote_port == 80
        assert port_forward.started_at == started_at
        assert port_forward.restart_count == 0
        assert port_forward.last_health_check is None

    @patch('psutil.pid_exists')
    def test_is_process_alive_with_valid_pid(self, mock_pid_exists: MagicMock) -> None:
        """Test process alive check with valid PID."""
        mock_pid_exists.return_value = True

        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert port_forward.is_process_alive()
        mock_pid_exists.assert_called_once_with(12345)

    @patch('psutil.pid_exists')
    def test_is_process_alive_with_invalid_pid(self, mock_pid_exists: MagicMock) -> None:
        """Test process alive check with invalid PID."""
        mock_pid_exists.return_value = False

        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert not port_forward.is_process_alive()
        mock_pid_exists.assert_called_once_with(12345)

    def test_is_process_alive_with_no_pid(self) -> None:
        """Test process alive check with no PID."""
        port_forward = PortForward(
            service_id=uuid4(),
            process_id=None,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert not port_forward.is_process_alive()

    @patch('psutil.pid_exists')
    def test_is_process_alive_with_exception(self, mock_pid_exists: MagicMock) -> None:
        """Test process alive check when psutil raises exception."""
        mock_pid_exists.side_effect = Exception("Process error")

        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert not port_forward.is_process_alive()

    def test_increment_restart_count(self) -> None:
        """Test restart count increment."""
        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert port_forward.restart_count == 0

        port_forward.increment_restart_count()
        assert port_forward.restart_count == 1

        port_forward.increment_restart_count()
        assert port_forward.restart_count == 2

    def test_update_health_check_time(self) -> None:
        """Test health check time update."""
        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        assert port_forward.last_health_check is None

        # Update with current time
        port_forward.update_health_check_time()
        assert port_forward.last_health_check is not None
        assert isinstance(port_forward.last_health_check, datetime)

        # Update with specific time
        specific_time = datetime.now() - timedelta(minutes=5)
        port_forward.update_health_check_time(specific_time)
        assert port_forward.last_health_check == specific_time

    def test_get_uptime_seconds(self) -> None:
        """Test uptime calculation."""
        started_at = datetime.now() - timedelta(seconds=30)

        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=started_at
        )

        uptime = port_forward.get_uptime_seconds()
        assert uptime >= 30.0
        assert uptime < 35.0  # Allow some margin for test execution time

    def test_should_restart(self) -> None:
        """Test restart decision logic."""
        port_forward = PortForward(
            service_id=uuid4(),
            process_id=12345,
            local_port=8080,
            remote_port=80,
            started_at=datetime.now()
        )

        # Should restart with low restart count
        assert port_forward.should_restart(max_restarts=5)

        # Increment restart count
        for _ in range(4):
            port_forward.increment_restart_count()

        # Should still restart (4 < 5)
        assert port_forward.should_restart(max_restarts=5)

        # One more increment
        port_forward.increment_restart_count()

        # Should not restart (5 >= 5)
        assert not port_forward.should_restart(max_restarts=5)

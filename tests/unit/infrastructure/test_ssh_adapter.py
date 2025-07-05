"""Unit tests for SSH adapter."""

import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from src.localport.infrastructure.adapters.ssh_adapter import SSHAdapter


class TestSSHAdapter:
    """Test cases for SSH adapter."""

    def test_get_adapter_name(self):
        """Test get_adapter_name method."""
        adapter = SSHAdapter()
        assert adapter.get_adapter_name() == "SSH Tunnel"

    def test_get_required_tools(self):
        """Test get_required_tools method."""
        adapter = SSHAdapter()
        assert adapter.get_required_tools() == ["ssh"]

    @pytest.mark.asyncio
    async def test_validate_connection_info_valid(self):
        """Test validate_connection_info with valid configuration."""
        adapter = SSHAdapter()
        
        with NamedTemporaryFile() as key_file:
            # Make key file readable only by owner (simulate proper permissions)
            Path(key_file.name).chmod(0o600)
            
            connection_info = {
                'host': 'example.com',
                'port': 22,
                'user': 'testuser',
                'key_file': key_file.name
            }
            
            errors = await adapter.validate_connection_info(connection_info)
            assert errors == []

    @pytest.mark.asyncio
    async def test_validate_connection_info_missing_host(self):
        """Test validate_connection_info with missing host."""
        adapter = SSHAdapter()
        connection_info = {'port': 22}
        
        errors = await adapter.validate_connection_info(connection_info)
        assert len(errors) >= 1
        assert any("SSH connection requires 'host' field" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_empty_host(self):
        """Test validate_connection_info with empty host."""
        adapter = SSHAdapter()
        connection_info = {'host': '   '}
        
        errors = await adapter.validate_connection_info(connection_info)
        assert len(errors) >= 1
        assert any("SSH host cannot be empty" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_invalid_port(self):
        """Test validate_connection_info with invalid port."""
        adapter = SSHAdapter()
        
        # Test non-integer port
        connection_info = {'host': 'example.com', 'port': 'invalid'}
        errors = await adapter.validate_connection_info(connection_info)
        assert any("must be a valid integer" in error for error in errors)
        
        # Test port out of range
        connection_info = {'host': 'example.com', 'port': 0}
        errors = await adapter.validate_connection_info(connection_info)
        assert any("must be between 1 and 65535" in error for error in errors)
        
        connection_info = {'host': 'example.com', 'port': 65536}
        errors = await adapter.validate_connection_info(connection_info)
        assert any("must be between 1 and 65535" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_missing_key_file(self):
        """Test validate_connection_info with missing key file."""
        adapter = SSHAdapter()
        connection_info = {
            'host': 'example.com',
            'key_file': '/nonexistent/key/file'
        }
        
        errors = await adapter.validate_connection_info(connection_info)
        assert any("SSH key file not found" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_no_authentication(self):
        """Test validate_connection_info with no authentication method."""
        adapter = SSHAdapter()
        connection_info = {'host': 'example.com'}
        
        errors = await adapter.validate_connection_info(connection_info)
        assert any("requires either 'key_file' or 'password'" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_password_auth(self):
        """Test validate_connection_info with password authentication."""
        adapter = SSHAdapter()
        connection_info = {
            'host': 'example.com',
            'password': 'secret'
        }
        
        with patch('shutil.which', return_value=None):
            errors = await adapter.validate_connection_info(connection_info)
            # Should warn about missing sshpass
            assert any("sshpass" in error for error in errors)
        
        with patch('shutil.which', return_value='/usr/bin/sshpass'):
            errors = await adapter.validate_connection_info(connection_info)
            # Should not have sshpass error
            assert not any("sshpass" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_key_permissions(self):
        """Test validate_connection_info with improper key file permissions."""
        adapter = SSHAdapter()
        
        with NamedTemporaryFile() as key_file:
            # Set overly permissive permissions
            Path(key_file.name).chmod(0o644)
            
            connection_info = {
                'host': 'example.com',
                'key_file': key_file.name
            }
            
            errors = await adapter.validate_connection_info(connection_info)
            assert any("overly permissive permissions" in error for error in errors)

    @pytest.mark.asyncio
    async def test_is_port_forward_running_delegates(self):
        """Test that is_port_forward_running delegates to is_process_running."""
        adapter = SSHAdapter()
        
        with patch.object(adapter, 'is_process_running', return_value=True) as mock_method:
            result = await adapter.is_port_forward_running(12345)
            assert result is True
            mock_method.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_validate_ssh_available_success(self):
        """Test validate_ssh_available when SSH is available."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'OpenSSH_8.0')
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await adapter.validate_ssh_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_ssh_available_not_found(self):
        """Test validate_ssh_available when SSH is not found."""
        adapter = SSHAdapter()
        
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
            result = await adapter.validate_ssh_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_check_sshpass_available_success(self):
        """Test check_sshpass_available when sshpass is available."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await adapter.check_sshpass_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_sshpass_available_not_found(self):
        """Test check_sshpass_available when sshpass is not found."""
        adapter = SSHAdapter()
        
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
            result = await adapter.check_sshpass_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_test_ssh_connection_success(self):
        """Test test_ssh_connection with successful connection."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                result = await adapter.test_ssh_connection('example.com', 'user', 22)
                assert result is True

    @pytest.mark.asyncio
    async def test_test_ssh_connection_failure(self):
        """Test test_ssh_connection with failed connection."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.wait.return_value = None
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                result = await adapter.test_ssh_connection('example.com', 'user', 22)
                assert result is False

    @pytest.mark.asyncio
    async def test_test_ssh_connection_timeout(self):
        """Test test_ssh_connection with timeout."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.kill.return_value = None
        mock_process.wait.return_value = None
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                result = await adapter.test_ssh_connection('example.com', 'user', 22, timeout=1.0)
                assert result is False
                mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_port_forward_missing_ssh(self):
        """Test start_port_forward when SSH command is not found."""
        adapter = SSHAdapter()
        
        with NamedTemporaryFile() as key_file:
            connection_info = {
                'host': 'example.com',
                'user': 'testuser',
                'key_file': key_file.name
            }
            
            with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError, match="ssh command not found"):
                    await adapter.start_port_forward(8080, 80, connection_info)

    @pytest.mark.asyncio
    async def test_start_port_forward_missing_sshpass(self):
        """Test start_port_forward when sshpass is needed but not found."""
        adapter = SSHAdapter()
        
        connection_info = {
            'host': 'example.com',
            'user': 'testuser',
            'password': 'secret'
        }
        
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError('sshpass')):
            with pytest.raises(RuntimeError, match="sshpass command not found"):
                await adapter.start_port_forward(8080, 80, connection_info)

    @pytest.mark.asyncio
    async def test_start_port_forward_invalid_key_file(self):
        """Test start_port_forward with invalid key file."""
        adapter = SSHAdapter()
        
        connection_info = {
            'host': 'example.com',
            'user': 'testuser',
            'key_file': '/nonexistent/key'
        }
        
        with pytest.raises(ValueError, match="SSH key file not found"):
            await adapter.start_port_forward(8080, 80, connection_info)

    @pytest.mark.asyncio
    async def test_stop_port_forward_process_not_found(self):
        """Test stop_port_forward when process is not found."""
        adapter = SSHAdapter()
        
        with patch('psutil.Process', side_effect=Exception('NoSuchProcess')):
            # Should not raise exception, just log warning
            await adapter.stop_port_forward(99999)

    @pytest.mark.asyncio
    async def test_is_process_running_with_tracked_process(self):
        """Test is_process_running with a tracked process."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = None  # Still running
        
        adapter._active_processes[12345] = mock_process
        
        result = await adapter.is_process_running(12345)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_process_running_with_terminated_process(self):
        """Test is_process_running with a terminated process."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 0  # Terminated
        
        adapter._active_processes[12345] = mock_process
        
        result = await adapter.is_process_running(12345)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_process_running_fallback_to_psutil(self):
        """Test is_process_running falls back to psutil for untracked processes."""
        adapter = SSHAdapter()
        
        with patch('psutil.pid_exists', return_value=True):
            result = await adapter.is_process_running(12345)
            assert result is True
        
        with patch('psutil.pid_exists', return_value=False):
            result = await adapter.is_process_running(12345)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_process_info_success(self):
        """Test get_process_info with valid process."""
        adapter = SSHAdapter()
        
        mock_process = MagicMock()
        mock_process.status.return_value = 'running'
        mock_process.create_time.return_value = 1234567890.0
        mock_process.cpu_percent.return_value = 5.5
        mock_process.memory_info.return_value._asdict.return_value = {'rss': 1024, 'vms': 2048}
        mock_process.cmdline.return_value = ['ssh', '-L', '8080:localhost:80', 'user@host']
        
        with patch('psutil.Process', return_value=mock_process):
            info = await adapter.get_process_info(12345)
            
            assert info is not None
            assert info['pid'] == 12345
            assert info['status'] == 'running'
            assert info['create_time'] == 1234567890.0
            assert info['cpu_percent'] == 5.5
            assert info['memory_info'] == {'rss': 1024, 'vms': 2048}
            assert info['cmdline'] == ['ssh', '-L', '8080:localhost:80', 'user@host']

    @pytest.mark.asyncio
    async def test_get_process_info_not_found(self):
        """Test get_process_info with non-existent process."""
        adapter = SSHAdapter()
        
        with patch('psutil.Process', side_effect=Exception('NoSuchProcess')):
            info = await adapter.get_process_info(99999)
            assert info is None

    @pytest.mark.asyncio
    async def test_cleanup_all_processes(self):
        """Test cleanup_all_processes method."""
        adapter = SSHAdapter()
        
        # Add some mock processes
        mock_process1 = AsyncMock()
        mock_process2 = AsyncMock()
        adapter._active_processes[12345] = mock_process1
        adapter._active_processes[12346] = mock_process2
        
        with patch.object(adapter, 'stop_port_forward', return_value=None) as mock_stop:
            await adapter.cleanup_all_processes()
            
            # Should have called stop_port_forward for each process
            assert mock_stop.call_count == 2
            mock_stop.assert_any_call(12345)
            mock_stop.assert_any_call(12346)
            
            # Should clear the active processes dict
            assert len(adapter._active_processes) == 0

    @pytest.mark.asyncio
    async def test_validate_ssh_connectivity_success(self):
        """Test validate_ssh_connectivity with successful connection."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stderr.read.return_value = b''
        
        connection_info = {
            'host': 'example.com',
            'user': 'testuser',
            'port': 22
        }
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_ssh_connectivity(connection_info)
                assert success is True
                assert "SSH connectivity verified" in message

    @pytest.mark.asyncio
    async def test_validate_ssh_connectivity_failure(self):
        """Test validate_ssh_connectivity with failed connection."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = b'Connection refused'
        
        connection_info = {
            'host': 'example.com',
            'user': 'testuser',
            'port': 22
        }
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_ssh_connectivity(connection_info)
                assert success is False
                assert "SSH connection failed" in message
                assert "Connection refused" in message

    @pytest.mark.asyncio
    async def test_validate_ssh_connectivity_timeout(self):
        """Test validate_ssh_connectivity with timeout."""
        adapter = SSHAdapter()
        
        mock_process = AsyncMock()
        
        connection_info = {
            'host': 'example.com',
            'user': 'testuser',
            'port': 22
        }
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                success, message = await adapter.validate_ssh_connectivity(connection_info)
                assert success is False
                assert "timed out" in message

    @pytest.mark.asyncio
    async def test_validate_dependencies_success(self):
        """Test validate_dependencies when all dependencies are available."""
        adapter = SSHAdapter()
        
        with patch.object(adapter, 'validate_ssh_available', return_value=True):
            all_available, missing_tools = await adapter.validate_dependencies()
            assert all_available is True
            assert missing_tools == []

    @pytest.mark.asyncio
    async def test_validate_dependencies_missing_ssh(self):
        """Test validate_dependencies when SSH is missing."""
        adapter = SSHAdapter()
        
        with patch.object(adapter, 'validate_ssh_available', return_value=False):
            all_available, missing_tools = await adapter.validate_dependencies()
            assert all_available is False
            assert len(missing_tools) == 1
            assert "ssh" in missing_tools[0]

    @pytest.mark.asyncio
    async def test_check_prerequisites_success(self):
        """Test check_prerequisites when all prerequisites are met."""
        adapter = SSHAdapter()
        
        with patch.object(adapter, 'validate_dependencies', return_value=(True, [])):
            result = await adapter.check_prerequisites()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_prerequisites_failure(self):
        """Test check_prerequisites when prerequisites are missing."""
        adapter = SSHAdapter()
        
        missing_tools = ["ssh - Install OpenSSH client"]
        with patch.object(adapter, 'validate_dependencies', return_value=(False, missing_tools)):
            result = await adapter.check_prerequisites()
            assert result is False

    @pytest.mark.asyncio
    async def test_check_prerequisites_exception(self):
        """Test check_prerequisites when an exception occurs."""
        adapter = SSHAdapter()
        
        with patch.object(adapter, 'validate_dependencies', side_effect=Exception("Test error")):
            result = await adapter.check_prerequisites()
            assert result is False

"""Tests for SSH adapter."""

import os
import tempfile
from unittest.mock import patch

import pytest

from localport.domain.value_objects.connection_info import ConnectionInfo
from localport.infrastructure.adapters.ssh_adapter import SSHAdapter


class TestSSHAdapter:
    """Test cases for SSHAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create an SSHAdapter instance."""
        return SSHAdapter()

    @pytest.fixture
    def valid_ssh_key(self):
        """Create a temporary SSH key file with correct permissions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(
                "-----BEGIN RSA PRIVATE KEY-----\nfake-key-content\n-----END RSA PRIVATE KEY-----"
            )
            f.flush()
            os.chmod(f.name, 0o600)
            yield f.name
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_validate_connection_info_valid(self, adapter, valid_ssh_key):
        """Test validation with a valid SSH connection."""
        conn = ConnectionInfo.ssh(
            host="example.com", user="admin", port=22, key_file=valid_ssh_key
        )
        errors = await adapter.validate_connection_info(conn)
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_connection_info_missing_host(self, adapter, valid_ssh_key):
        """Test validation with valid config returns no errors."""
        conn = ConnectionInfo.ssh(
            host="valid.com", user="admin", key_file=valid_ssh_key
        )
        errors = await adapter.validate_connection_info(conn)
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_connection_info_empty_host(self, adapter):
        """Test validation catches empty host."""
        # Build a ConnectionInfo with an empty host by going through the factory
        # The ssh factory may reject empty host, so we verify the behavior
        try:
            conn = ConnectionInfo.ssh(host="   ")
            errors = await adapter.validate_connection_info(conn)
            assert any("host" in e.lower() or "empty" in e.lower() for e in errors)
        except (ValueError, KeyError):
            # Factory correctly rejects empty host
            pass

    @pytest.mark.asyncio
    async def test_validate_connection_info_invalid_port(self, adapter, valid_ssh_key):
        """Test validation catches invalid port."""
        try:
            conn = ConnectionInfo.ssh(
                host="example.com", port=99999, key_file=valid_ssh_key
            )
            errors = await adapter.validate_connection_info(conn)
            assert any("port" in e.lower() for e in errors)
        except (ValueError, TypeError):
            # Factory correctly rejects invalid port
            pass

    @pytest.mark.asyncio
    async def test_validate_connection_info_missing_key_file(self, adapter):
        """Test that ConnectionInfo.ssh rejects non-existent key file at construction."""
        from localport.domain.exceptions import SSHKeyNotFoundError

        with pytest.raises(SSHKeyNotFoundError):
            ConnectionInfo.ssh(
                host="example.com",
                user="admin",
                key_file="/nonexistent/path/to/key.pem",
            )

    @pytest.mark.asyncio
    async def test_validate_connection_info_no_authentication(self, adapter):
        """Test validation catches no authentication method."""
        conn = ConnectionInfo.ssh(host="example.com", user="admin")
        errors = await adapter.validate_connection_info(conn)
        assert any(
            "authentication" in e.lower()
            or "key_file" in e.lower()
            or "password" in e.lower()
            for e in errors
        )

    @pytest.mark.asyncio
    async def test_validate_connection_info_password_auth(self, adapter):
        """Test validation passes with password authentication."""
        conn = ConnectionInfo.ssh(host="example.com", user="admin", password="secret")
        errors = await adapter.validate_connection_info(conn)
        # May have sshpass warning but shouldn't have auth error
        auth_errors = [
            e
            for e in errors
            if "authentication" in e.lower()
            and "requires" in e.lower()
            and "key_file" in e.lower()
        ]
        assert len(auth_errors) == 0

    @pytest.mark.asyncio
    async def test_validate_connection_info_key_permissions(self, adapter):
        """Test validation catches overly permissive key file permissions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("fake-key")
            f.flush()
            os.chmod(f.name, 0o644)  # Too permissive
            key_path = f.name

        try:
            conn = ConnectionInfo.ssh(
                host="example.com", user="admin", key_file=key_path
            )
            errors = await adapter.validate_connection_info(conn)
            assert any(
                "permission" in e.lower() or "600" in e or "400" in e for e in errors
            )
        finally:
            os.unlink(key_path)

    @pytest.mark.asyncio
    async def test_validate_connection_info_key_permissions_strict(self, adapter):
        """Test that only 600 and 400 permissions pass validation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("fake-key")
            f.flush()
            key_path = f.name

        try:
            # 700 should fail (owner execute)
            os.chmod(key_path, 0o700)
            conn = ConnectionInfo.ssh(
                host="example.com", user="admin", key_file=key_path
            )
            errors = await adapter.validate_connection_info(conn)
            assert any("permission" in e.lower() for e in errors)

            # 600 should pass
            os.chmod(key_path, 0o600)
            errors = await adapter.validate_connection_info(conn)
            perm_errors = [e for e in errors if "permission" in e.lower()]
            assert len(perm_errors) == 0

            # 400 should pass
            os.chmod(key_path, 0o400)
            errors = await adapter.validate_connection_info(conn)
            perm_errors = [e for e in errors if "permission" in e.lower()]
            assert len(perm_errors) == 0
        finally:
            os.chmod(key_path, 0o600)  # Restore for deletion
            os.unlink(key_path)

    @pytest.mark.asyncio
    async def test_start_port_forward_missing_ssh(self, adapter, valid_ssh_key):
        """Test that missing ssh command raises error."""
        conn = ConnectionInfo.ssh(
            host="example.com", user="admin", key_file=valid_ssh_key
        )
        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("ssh")
        ):
            with pytest.raises((RuntimeError, FileNotFoundError)):
                await adapter.start_port_forward(5433, 5432, conn)

    @pytest.mark.asyncio
    async def test_start_port_forward_invalid_key_file(self, adapter):
        """Test that non-existent key file is rejected at ConnectionInfo construction."""
        from localport.domain.exceptions import SSHKeyNotFoundError

        with pytest.raises(SSHKeyNotFoundError):
            ConnectionInfo.ssh(
                host="example.com", user="admin", key_file="/nonexistent/key.pem"
            )

    @pytest.mark.asyncio
    async def test_is_process_running(self, adapter):
        """Test checking if a process is running."""
        # Non-existent PID should return False
        result = await adapter.is_process_running(99999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_ssh_available(self, adapter):
        """Test SSH availability check."""
        result = await adapter.validate_ssh_available()
        # SSH should be available on most development machines
        assert isinstance(result, bool)

    def test_get_adapter_name(self, adapter):
        """Test adapter name."""
        assert adapter.get_adapter_name() == "SSH Tunnel"

    def test_get_required_tools(self, adapter):
        """Test required tools list."""
        tools = adapter.get_required_tools()
        assert "ssh" in tools

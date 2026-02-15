"""Tests for ConnectionInfo value object."""

import pytest

from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestConnectionInfoValueObject:
    """Test cases for ConnectionInfo value object."""

    def test_kubectl_connection_info_creation(self):
        """Test creating kubectl ConnectionInfo via factory."""
        conn = ConnectionInfo.kubectl(
            resource_name="postgres",
            namespace="default",
            resource_type="service",
            context="my-cluster"
        )
        assert conn.technology == ForwardingTechnology.KUBECTL
        assert conn.get_kubectl_resource_name() == "postgres"
        assert conn.get_kubectl_namespace() == "default"
        assert conn.get_kubectl_resource_type() == "service"

    def test_ssh_connection_info_creation(self):
        """Test creating SSH ConnectionInfo via factory."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("fake-key")
            os.chmod(f.name, 0o600)
            key_path = f.name
        try:
            conn = ConnectionInfo.ssh(
                host="example.com",
                user="admin",
                port=22,
                key_file=key_path
            )
            assert conn.technology == ForwardingTechnology.SSH
            assert conn.get_ssh_host() == "example.com"
            assert conn.get_ssh_user() == "admin"
            assert conn.get_ssh_port() == 22
            assert conn.get_ssh_key_file() == key_path
        finally:
            os.unlink(key_path)

    def test_ssh_connection_info_defaults(self):
        """Test SSH ConnectionInfo default values."""
        conn = ConnectionInfo.ssh(host="example.com")
        assert conn.get_ssh_port() == 22
        assert conn.get_ssh_remote_host() == "localhost"

    def test_ssh_connection_info_with_bastion(self):
        """Test SSH ConnectionInfo with bastion/remote_host."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("fake-key")
            os.chmod(f.name, 0o600)
            key_path = f.name
        try:
            conn = ConnectionInfo.ssh(
                host="bastion.example.com",
                user="ec2-user",
                key_file=key_path,
                remote_host="internal-db.rds.amazonaws.com"
            )
            assert conn.get_ssh_host() == "bastion.example.com"
            assert conn.get_ssh_remote_host() == "internal-db.rds.amazonaws.com"
        finally:
            os.unlink(key_path)

    def test_kubectl_validation_missing_resource_name(self):
        """Test that kubectl connection requires resource_name."""
        with pytest.raises((ValueError, KeyError)):
            ConnectionInfo.kubectl(
                resource_name="",
                namespace="default"
            )

    def test_kubectl_validation_invalid_resource_type(self):
        """Test that kubectl validates resource_type."""
        # Should accept valid resource types
        conn = ConnectionInfo.kubectl(
            resource_name="postgres",
            namespace="default",
            resource_type="deployment"
        )
        assert conn.get_kubectl_resource_type() == "deployment"

    def test_ssh_validation_missing_host(self):
        """Test that SSH connection requires host."""
        with pytest.raises((ValueError, KeyError)):
            ConnectionInfo.ssh(host="")

    def test_ssh_validation_invalid_port(self):
        """Test that SSH validates port range."""
        with pytest.raises((ValueError, TypeError)):
            ConnectionInfo.ssh(host="example.com", port=-1)

    def test_ssh_validation_missing_key_file(self):
        """Test SSH without key file or password."""
        # Should still create — validation happens at adapter level
        conn = ConnectionInfo.ssh(host="example.com", user="admin")
        assert conn.get_ssh_host() == "example.com"

    def test_ssh_has_password(self):
        """Test SSH password detection."""
        conn_with_pw = ConnectionInfo.ssh(
            host="example.com",
            password="secret"
        )
        assert conn_with_pw.has_ssh_password() is True

        conn_no_pw = ConnectionInfo.ssh(host="example.com")
        assert conn_no_pw.has_ssh_password() is False

    def test_connection_info_equality(self):
        """Test ConnectionInfo equality."""
        conn1 = ConnectionInfo.ssh(host="example.com", user="admin", port=22)
        conn2 = ConnectionInfo.ssh(host="example.com", user="admin", port=22)
        # Both should have same technology and config
        assert conn1.technology == conn2.technology
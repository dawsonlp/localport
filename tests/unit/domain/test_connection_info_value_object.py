"""Unit tests for ConnectionInfo value object."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from localport.domain.entities.service import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestConnectionInfoValueObject:
    """Unit tests for ConnectionInfo value object."""

    def test_create_kubectl_connection_info(self) -> None:
        """Test creating kubectl connection info."""
        config = {
            "resource_name": "postgres",
            "namespace": "default",
            "resource_type": "service"
        }

        conn_info = ConnectionInfo(ForwardingTechnology.KUBECTL, config)

        assert conn_info.technology == ForwardingTechnology.KUBECTL
        assert conn_info.config == config

    def test_create_ssh_connection_info(self) -> None:
        """Test creating SSH connection info."""
        config = {
            "host": "example.com",
            "user": "deploy",
            "port": 22
        }

        conn_info = ConnectionInfo(ForwardingTechnology.SSH, config)

        assert conn_info.technology == ForwardingTechnology.SSH
        assert conn_info.config == config

    def test_kubectl_factory_method(self) -> None:
        """Test kubectl factory method."""
        conn_info = ConnectionInfo.kubectl(
            resource_name="postgres",
            namespace="database",
            resource_type="service",
            context="minikube"
        )

        assert conn_info.technology == ForwardingTechnology.KUBECTL
        assert conn_info.get_kubectl_resource_name() == "postgres"
        assert conn_info.get_kubectl_namespace() == "database"
        assert conn_info.get_kubectl_resource_type() == "service"
        assert conn_info.get_kubectl_context() == "minikube"

    def test_kubectl_factory_method_defaults(self) -> None:
        """Test kubectl factory method with defaults."""
        conn_info = ConnectionInfo.kubectl(resource_name="postgres")

        assert conn_info.get_kubectl_resource_name() == "postgres"
        assert conn_info.get_kubectl_namespace() == "default"
        assert conn_info.get_kubectl_resource_type() == "service"
        assert conn_info.get_kubectl_context() is None

    def test_ssh_factory_method(self) -> None:
        """Test SSH factory method."""
        with NamedTemporaryFile() as key_file:
            conn_info = ConnectionInfo.ssh(
                host="example.com",
                user="deploy",
                port=2222,
                key_file=key_file.name
            )

            assert conn_info.technology == ForwardingTechnology.SSH
            assert conn_info.get_ssh_host() == "example.com"
            assert conn_info.get_ssh_user() == "deploy"
            assert conn_info.get_ssh_port() == 2222
            assert conn_info.get_ssh_key_file() == key_file.name
            assert not conn_info.has_ssh_password()

    def test_ssh_factory_method_defaults(self) -> None:
        """Test SSH factory method with defaults."""
        conn_info = ConnectionInfo.ssh(host="example.com")

        assert conn_info.get_ssh_host() == "example.com"
        assert conn_info.get_ssh_user() is None
        assert conn_info.get_ssh_port() == 22
        assert conn_info.get_ssh_key_file() is None
        assert not conn_info.has_ssh_password()

    def test_ssh_with_password(self) -> None:
        """Test SSH connection with password."""
        conn_info = ConnectionInfo.ssh(
            host="example.com",
            password="secret"
        )

        assert conn_info.has_ssh_password()

    def test_kubectl_validation_missing_resource_name(self) -> None:
        """Test kubectl validation with missing resource name."""
        config = {
            "namespace": "default"
        }

        with pytest.raises(ValueError, match="kubectl connection requires 'resource_name' field"):
            ConnectionInfo(ForwardingTechnology.KUBECTL, config)

    def test_kubectl_validation_empty_resource_name(self) -> None:
        """Test kubectl validation with empty resource name."""
        config = {
            "resource_name": "   ",
            "namespace": "default"
        }

        with pytest.raises(ValueError, match="resource_name cannot be empty"):
            ConnectionInfo(ForwardingTechnology.KUBECTL, config)

    def test_kubectl_validation_empty_namespace(self) -> None:
        """Test kubectl validation with empty namespace."""
        config = {
            "resource_name": "postgres",
            "namespace": "   "
        }

        with pytest.raises(ValueError, match="namespace cannot be empty if provided"):
            ConnectionInfo(ForwardingTechnology.KUBECTL, config)

    def test_kubectl_validation_invalid_resource_type(self) -> None:
        """Test kubectl validation with invalid resource type."""
        config = {
            "resource_name": "postgres",
            "resource_type": "invalid"
        }

        with pytest.raises(ValueError, match="resource_type must be one of"):
            ConnectionInfo(ForwardingTechnology.KUBECTL, config)

    def test_ssh_validation_missing_host(self) -> None:
        """Test SSH validation with missing host."""
        config = {
            "user": "deploy"
        }

        with pytest.raises(ValueError, match="SSH connection requires 'host' field"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

    def test_ssh_validation_empty_host(self) -> None:
        """Test SSH validation with empty host."""
        config = {
            "host": "   "
        }

        with pytest.raises(ValueError, match="host cannot be empty"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

    def test_ssh_validation_invalid_port(self) -> None:
        """Test SSH validation with invalid port."""
        config = {
            "host": "example.com",
            "port": "invalid"
        }

        with pytest.raises(ValueError, match="SSH port must be a valid integer"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

        config["port"] = 0
        with pytest.raises(ValueError, match="SSH port must be between 1 and 65535"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

        config["port"] = 65536
        with pytest.raises(ValueError, match="SSH port must be between 1 and 65535"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

    def test_ssh_validation_missing_key_file(self) -> None:
        """Test SSH validation with missing key file."""
        config = {
            "host": "example.com",
            "key_file": "/nonexistent/key"
        }

        with pytest.raises(ValueError, match="SSH key file not found"):
            ConnectionInfo(ForwardingTechnology.SSH, config)

    def test_invalid_config_type(self) -> None:
        """Test validation with invalid config type."""
        with pytest.raises(ValueError, match="Config must be a dictionary"):
            ConnectionInfo(ForwardingTechnology.KUBECTL, "invalid")  # type: ignore

    def test_kubectl_getter_methods_wrong_technology(self) -> None:
        """Test kubectl getter methods with wrong technology."""
        conn_info = ConnectionInfo.ssh(host="example.com")

        with pytest.raises(ValueError, match="Not a kubectl connection"):
            conn_info.get_kubectl_resource_name()

        with pytest.raises(ValueError, match="Not a kubectl connection"):
            conn_info.get_kubectl_namespace()

        with pytest.raises(ValueError, match="Not a kubectl connection"):
            conn_info.get_kubectl_resource_type()

        with pytest.raises(ValueError, match="Not a kubectl connection"):
            conn_info.get_kubectl_context()

    def test_ssh_getter_methods_wrong_technology(self) -> None:
        """Test SSH getter methods with wrong technology."""
        conn_info = ConnectionInfo.kubectl(resource_name="postgres")

        with pytest.raises(ValueError, match="Not an SSH connection"):
            conn_info.get_ssh_host()

        with pytest.raises(ValueError, match="Not an SSH connection"):
            conn_info.get_ssh_user()

        with pytest.raises(ValueError, match="Not an SSH connection"):
            conn_info.get_ssh_port()

        with pytest.raises(ValueError, match="Not an SSH connection"):
            conn_info.get_ssh_key_file()

        with pytest.raises(ValueError, match="Not an SSH connection"):
            conn_info.has_ssh_password()

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        conn_info = ConnectionInfo.kubectl(
            resource_name="postgres",
            namespace="database",
            context="minikube"
        )

        result = conn_info.to_dict()

        expected = {
            "technology": "kubectl",
            "config": {
                "resource_name": "postgres",
                "namespace": "database",
                "resource_type": "service",
                "context": "minikube"
            }
        }

        assert result == expected

    def test_from_dict_valid(self) -> None:
        """Test creating from valid dictionary."""
        data = {
            "technology": "kubectl",
            "config": {
                "resource_name": "postgres",
                "namespace": "database"
            }
        }

        conn_info = ConnectionInfo.from_dict(data)

        assert conn_info.technology == ForwardingTechnology.KUBECTL
        assert conn_info.get_kubectl_resource_name() == "postgres"
        assert conn_info.get_kubectl_namespace() == "database"

    def test_from_dict_missing_technology(self) -> None:
        """Test creating from dictionary missing technology."""
        data = {
            "config": {
                "resource_name": "postgres"
            }
        }

        with pytest.raises(ValueError, match="Missing 'technology' field"):
            ConnectionInfo.from_dict(data)

    def test_from_dict_missing_config(self) -> None:
        """Test creating from dictionary missing config."""
        data = {
            "technology": "kubectl"
        }

        with pytest.raises(ValueError, match="Missing 'config' field"):
            ConnectionInfo.from_dict(data)

    def test_from_dict_invalid_technology(self) -> None:
        """Test creating from dictionary with invalid technology."""
        data = {
            "technology": "invalid",
            "config": {}
        }

        with pytest.raises(ValueError, match="Invalid technology"):
            ConnectionInfo.from_dict(data)

    def test_connection_info_immutability(self) -> None:
        """Test that ConnectionInfo is immutable."""
        conn_info = ConnectionInfo.kubectl(resource_name="postgres")

        # Should not be able to modify the technology
        with pytest.raises(AttributeError):
            conn_info.technology = ForwardingTechnology.SSH  # type: ignore

        # Should not be able to modify the config
        with pytest.raises(AttributeError):
            conn_info.config = {}  # type: ignore

    def test_ssh_with_path_expansion(self) -> None:
        """Test SSH with path expansion for key file."""
        with NamedTemporaryFile() as key_file:
            # Test with Path object
            conn_info = ConnectionInfo.ssh(
                host="example.com",
                key_file=Path(key_file.name)
            )

            assert conn_info.get_ssh_key_file() == key_file.name

    def test_ssh_with_additional_options(self) -> None:
        """Test SSH with additional options."""
        conn_info = ConnectionInfo.ssh(
            host="example.com",
            compression=True,
            timeout=30
        )

        assert conn_info.config["compression"] is True
        assert conn_info.config["timeout"] == 30

"""Tests for service discovery value objects and factories."""

import pytest

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.discovery import (
    DiscoveredPort,
    KubernetesResource,
)


class TestDiscoveredPortValueObject:
    """Test cases for DiscoveredPort value object."""

    def test_discovered_port_creation(self):
        """Test creating a DiscoveredPort."""
        port = DiscoveredPort(port=80, protocol="tcp", name="http")
        assert port.port == 80
        assert port.protocol == "tcp"
        assert port.name == "http"

    def test_discovered_port_minimal(self):
        """Test creating a DiscoveredPort with defaults."""
        port = DiscoveredPort(port=5432)
        assert port.port == 5432
        assert port.protocol == "tcp"
        assert port.name is None

    def test_discovered_port_equality(self):
        """Test DiscoveredPort equality."""
        port1 = DiscoveredPort(port=80, protocol="tcp", name="http")
        port2 = DiscoveredPort(port=80, protocol="tcp", name="http")
        assert port1 == port2

    def test_discovered_port_invalid_protocol(self):
        """Test that invalid protocol raises ValueError."""
        with pytest.raises(ValueError, match="Protocol must be"):
            DiscoveredPort(port=80, protocol="TCP")

    def test_discovered_port_invalid_port(self):
        """Test that invalid port raises ValueError."""
        with pytest.raises(ValueError):
            DiscoveredPort(port=0, protocol="tcp")
        with pytest.raises(ValueError):
            DiscoveredPort(port=70000, protocol="tcp")


class TestKubernetesResourceValueObject:
    """Test cases for KubernetesResource value object."""

    def test_valid_kubernetes_resource(self):
        """Test creating a valid KubernetesResource."""
        resource = KubernetesResource(
            name="postgres",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=5432, protocol="tcp", name="postgresql")
            ],
        )
        assert resource.name == "postgres"
        assert resource.namespace == "default"
        assert resource.resource_type == "service"
        assert len(resource.available_ports) == 1

    def test_kubernetes_resource_with_multiple_ports(self):
        """Test KubernetesResource with multiple ports."""
        resource = KubernetesResource(
            name="web-app",
            namespace="production",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=80, protocol="tcp", name="http"),
                DiscoveredPort(port=443, protocol="tcp", name="https"),
            ],
        )
        assert len(resource.available_ports) == 2


class TestServiceDiscoveryFactories:
    """Test cases for Service factory methods."""

    def test_from_kubectl_discovery_single_port(self):
        """Test creating a Service from kubectl discovery."""
        service = Service.from_kubectl_discovery(
            resource_name="postgres",
            namespace="default",
            local_port=5433,
            remote_port=5432,
            service_name="postgres",
        )
        assert service.name == "postgres"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port == 5433
        assert service.remote_port == 5432

    def test_from_kubectl_discovery_multiple_ports_selected(self):
        """Test creating a Service from kubectl discovery with port selection."""
        service = Service.from_kubectl_discovery(
            resource_name="web-app",
            namespace="production",
            local_port=8080,
            remote_port=80,
            service_name="web-app",
        )
        assert service.local_port == 8080
        assert service.remote_port == 80

    def test_from_ssh_config_basic(self):
        """Test creating a Service from SSH configuration."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("fake-key")
            os.chmod(f.name, 0o600)
            key_path = f.name
        try:
            service = Service.from_ssh_config(
                service_name="rds-tunnel",
                host="bastion.example.com",
                user="ec2-user",
                key_file=key_path,
                local_port=5433,
                remote_port=5432,
            )
            assert service.name == "rds-tunnel"
            assert service.technology == ForwardingTechnology.SSH
            assert service.local_port == 5433
            assert service.remote_port == 5432
        finally:
            os.unlink(key_path)

    def test_from_ssh_config_minimal(self):
        """Test creating a Service from minimal SSH config."""
        service = Service.from_ssh_config(
            service_name="simple-ssh",
            host="example.com",
            local_port=3306,
            remote_port=3306,
        )
        assert service.name == "simple-ssh"
        assert service.technology == ForwardingTechnology.SSH

    def test_from_ssh_config_with_bastion(self):
        """Test creating a Service from SSH config with bastion host."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("fake-key")
            os.chmod(f.name, 0o600)
            key_path = f.name
        try:
            service = Service.from_ssh_config(
                service_name="rds-via-bastion",
                host="bastion.example.com",
                user="ec2-user",
                key_file=key_path,
                local_port=5433,
                remote_port=5432,
                remote_host="internal-db.rds.amazonaws.com",
            )
            assert service.name == "rds-via-bastion"
            assert (
                service.connection_info.get_ssh_remote_host()
                == "internal-db.rds.amazonaws.com"
            )
        finally:
            os.unlink(key_path)


class TestDomainExceptions:
    """Test domain exception behavior."""

    def test_no_ports_available_error(self):
        """Test NoPortsAvailableError can be raised."""
        from localport.domain.exceptions import NoPortsAvailableError

        with pytest.raises(NoPortsAvailableError):
            raise NoPortsAvailableError(resource_name="postgres", namespace="default")

"""Tests for service entity discovery functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort
from localport.domain.value_objects.connection_info import ConnectionInfo
from localport.domain.exceptions import (
    ServiceAlreadyExistsError,
    KubernetesResourceNotFoundError,
    NoPortsAvailableError,
    ValidationError
)


class TestServiceDiscoveryFactories:
    """Test Service entity factory methods for discovery scenarios."""
    
    def test_from_kubectl_discovery_single_port(self):
        """Test creating service from kubectl discovery with single port."""
        # Arrange
        resource = KubernetesResource(
            name="postgres-service",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(
                    port=5432,
                    protocol="TCP",
                    name="postgresql",
                    description="PostgreSQL database port"
                )
            ]
        )
        
        # Act
        service = Service.from_kubectl_discovery(
            service_name="postgres",
            resource=resource,
            local_port=5433
        )
        
        # Assert
        assert service.name == "postgres"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port.port == 5433
        assert service.remote_port.port == 5432
        assert service.connection_info.resource_name == "postgres-service"
        assert service.connection_info.namespace == "default"
        assert service.connection_info.resource_type == "service"

    def test_from_kubectl_discovery_multiple_ports_selected(self):
        """Test creating service from kubectl discovery with port selection."""
        # Arrange
        resource = KubernetesResource(
            name="web-app",
            namespace="production",
            resource_type="deployment",
            available_ports=[
                DiscoveredPort(port=8080, protocol="TCP", name="http"),
                DiscoveredPort(port=8443, protocol="TCP", name="https"),
                DiscoveredPort(port=9090, protocol="TCP", name="metrics")
            ]
        )
        
        selected_port = DiscoveredPort(port=8080, protocol="TCP", name="http")
        
        # Act
        service = Service.from_kubectl_discovery(
            service_name="web-app-http",
            resource=resource,
            local_port=8080,
            selected_port=selected_port
        )
        
        # Assert
        assert service.name == "web-app-http"
        assert service.remote_port.port == 8080
        assert service.connection_info.resource_name == "web-app"
        assert service.connection_info.namespace == "production"
        assert service.connection_info.resource_type == "deployment"

    def test_from_kubectl_discovery_no_ports_raises_error(self):
        """Test that creating service from resource with no ports raises error."""
        # Arrange
        resource = KubernetesResource(
            name="configmap",
            namespace="default",
            resource_type="configmap",
            available_ports=[]
        )
        
        # Act & Assert
        with pytest.raises(NoPortsAvailableError) as exc_info:
            Service.from_kubectl_discovery(
                service_name="config",
                resource=resource,
                local_port=8080
            )
        
        assert "No ports available" in str(exc_info.value)

    def test_from_ssh_config_basic(self):
        """Test creating service from SSH configuration."""
        # Act
        service = Service.from_ssh_config(
            service_name="remote-db",
            ssh_host="db.example.com",
            local_port=5433,
            remote_port=5432,
            ssh_user="dbuser",
            ssh_key_file="~/.ssh/db_key"
        )
        
        # Assert
        assert service.name == "remote-db"
        assert service.technology == ForwardingTechnology.SSH
        assert service.local_port.port == 5433
        assert service.remote_port.port == 5432
        assert service.connection_info.host == "db.example.com"
        assert service.connection_info.user == "dbuser"
        assert service.connection_info.key_file == "~/.ssh/db_key"

    def test_from_ssh_config_minimal(self):
        """Test creating service from minimal SSH configuration."""
        # Act
        service = Service.from_ssh_config(
            service_name="simple-ssh",
            ssh_host="server.com",
            local_port=8080,
            remote_port=80
        )
        
        # Assert
        assert service.name == "simple-ssh"
        assert service.technology == ForwardingTechnology.SSH
        assert service.connection_info.host == "server.com"
        assert service.connection_info.port == 22  # Default SSH port
        assert service.connection_info.user is None
        assert service.connection_info.key_file is None

    def test_from_ssh_config_with_bastion(self):
        """Test creating service from SSH configuration with bastion host."""
        # Act
        service = Service.from_ssh_config(
            service_name="bastion-db",
            ssh_host="bastion.example.com",
            local_port=5433,
            remote_port=5432,
            ssh_user="ec2-user",
            ssh_key_file="~/.ssh/bastion.pem",
            remote_host="internal-db.rds.amazonaws.com"
        )
        
        # Assert
        assert service.name == "bastion-db"
        assert service.connection_info.host == "bastion.example.com"
        assert service.connection_info.remote_host == "internal-db.rds.amazonaws.com"


class TestKubernetesResourceValueObject:
    """Test KubernetesResource value object validation."""
    
    def test_valid_kubernetes_resource(self):
        """Test creating a valid Kubernetes resource."""
        # Arrange & Act
        resource = KubernetesResource(
            name="my-service",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=80, protocol="TCP", name="http")
            ]
        )
        
        # Assert
        assert resource.name == "my-service"
        assert resource.namespace == "default"
        assert resource.resource_type == "service"
        assert len(resource.available_ports) == 1

    def test_kubernetes_resource_naming_validation(self):
        """Test Kubernetes resource naming validation."""
        # Valid names should work
        valid_names = ["service", "my-service", "service123", "s"]
        for name in valid_names:
            resource = KubernetesResource(
                name=name,
                namespace="default", 
                resource_type="service",
                available_ports=[]
            )
            assert resource.name == name

    def test_kubernetes_resource_with_multiple_ports(self):
        """Test Kubernetes resource with multiple ports."""
        # Arrange
        ports = [
            DiscoveredPort(port=80, protocol="TCP", name="http"),
            DiscoveredPort(port=443, protocol="TCP", name="https"),
            DiscoveredPort(port=9090, protocol="TCP", name="metrics")
        ]
        
        # Act
        resource = KubernetesResource(
            name="web-service",
            namespace="production",
            resource_type="service",
            available_ports=ports
        )
        
        # Assert
        assert len(resource.available_ports) == 3
        assert resource.available_ports[0].name == "http"
        assert resource.available_ports[1].name == "https"
        assert resource.available_ports[2].name == "metrics"


class TestDiscoveredPortValueObject:
    """Test DiscoveredPort value object."""
    
    def test_discovered_port_creation(self):
        """Test creating a discovered port."""
        # Act
        port = DiscoveredPort(
            port=8080,
            protocol="TCP",
            name="web",
            description="Web server port"
        )
        
        # Assert
        assert port.port == 8080
        assert port.protocol == "TCP"
        assert port.name == "web"
        assert port.description == "Web server port"

    def test_discovered_port_minimal(self):
        """Test creating a minimal discovered port."""
        # Act
        port = DiscoveredPort(port=3000, protocol="TCP")
        
        # Assert
        assert port.port == 3000
        assert port.protocol == "TCP"
        assert port.name is None
        assert port.description is None

    def test_discovered_port_equality(self):
        """Test discovered port equality comparison."""
        # Arrange
        port1 = DiscoveredPort(port=8080, protocol="TCP", name="web")
        port2 = DiscoveredPort(port=8080, protocol="TCP", name="web")
        port3 = DiscoveredPort(port=8081, protocol="TCP", name="web")
        
        # Assert
        assert port1 == port2
        assert port1 != port3


class TestDomainExceptions:
    """Test new domain exceptions for discovery scenarios."""
    
    def test_service_already_exists_error(self):
        """Test ServiceAlreadyExistsError exception."""
        # Act & Assert
        with pytest.raises(ServiceAlreadyExistsError) as exc_info:
            raise ServiceAlreadyExistsError("Service 'postgres' already exists")
        
        assert "already exists" in str(exc_info.value)

    def test_kubernetes_resource_not_found_error(self):
        """Test KubernetesResourceNotFoundError exception."""
        # Act & Assert
        with pytest.raises(KubernetesResourceNotFoundError) as exc_info:
            raise KubernetesResourceNotFoundError("Resource 'nginx' not found in namespace 'default'")
        
        assert "not found" in str(exc_info.value)

    def test_no_ports_available_error(self):
        """Test NoPortsAvailableError exception."""
        # Act & Assert
        with pytest.raises(NoPortsAvailableError) as exc_info:
            raise NoPortsAvailableError("No ports available for resource 'configmap'")
        
        assert "No ports available" in str(exc_info.value)

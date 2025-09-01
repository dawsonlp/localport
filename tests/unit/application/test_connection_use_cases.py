"""Tests for connection management use cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from localport.application.dto.connection_dto import (
    AddConnectionRequest,
    AddConnectionResponse,
    RemoveConnectionRequest,
    RemoveConnectionResponse,
    ListConnectionsResponse
)
from localport.application.use_cases.add_connection import AddConnectionUseCase
from localport.application.use_cases.remove_connection import RemoveConnectionUseCase
from localport.application.use_cases.list_connections import ListConnectionsUseCase
from localport.domain.exceptions import (
    ServiceAlreadyExistsError,
    KubernetesResourceNotFoundError,
    NoPortsAvailableError
)
from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort


class TestAddConnectionUseCase:
    """Test AddConnectionUseCase with various scenarios."""

    @pytest.fixture
    def mock_config_repo(self):
        """Mock configuration repository."""
        mock_repo = AsyncMock()
        mock_repo.service_exists.return_value = False
        mock_repo.add_service_config.return_value = None
        return mock_repo

    @pytest.fixture
    def mock_discovery_repo(self):
        """Mock Kubernetes discovery repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_validation_service(self):
        """Mock connection validation service."""
        mock_service = AsyncMock()
        mock_service.validate_service_name.return_value = []
        mock_service.validate_port_availability.return_value = []
        mock_service.validate_ssh_host.return_value = []
        return mock_service

    @pytest.fixture
    def add_use_case(self, mock_config_repo, mock_discovery_repo, mock_validation_service):
        """Create AddConnectionUseCase with mocked dependencies."""
        return AddConnectionUseCase(
            config_repository=mock_config_repo,
            discovery_repository=mock_discovery_repo,
            validation_service=mock_validation_service
        )

    @pytest.mark.asyncio
    async def test_kubectl_flow_single_port(self, add_use_case, mock_discovery_repo):
        """Test kubectl flow with single port discovery."""
        # Arrange
        resource = KubernetesResource(
            name="postgres-service",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=5432, protocol="TCP", name="postgresql")
            ]
        )
        mock_discovery_repo.find_resource.return_value = resource
        
        request = AddConnectionRequest(
            service_name="postgres",
            technology="kubectl",
            connection_params={
                "resource_name": "postgres-service",
                "namespace": "default"
            },
            options={
                "local_port": 5433
            }
        )
        
        # Act
        response = await add_use_case.execute(request)
        
        # Assert
        assert response.success is True
        assert response.service_name == "postgres"
        assert "local_port" in response.configuration_added
        assert response.configuration_added["local_port"] == 5433
        assert response.configuration_added["remote_port"] == 5432
        
        # Verify repository calls
        mock_discovery_repo.find_resource.assert_called_once_with(
            "postgres-service", "default"
        )

    @pytest.mark.asyncio
    async def test_kubectl_flow_multiple_ports(self, add_use_case, mock_discovery_repo):
        """Test kubectl flow with multiple ports requiring selection."""
        # Arrange
        resource = KubernetesResource(
            name="web-app",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=8080, protocol="TCP", name="http"),
                DiscoveredPort(port=8443, protocol="TCP", name="https"),
                DiscoveredPort(port=9090, protocol="TCP", name="metrics")
            ]
        )
        mock_discovery_repo.find_resource.return_value = resource
        
        request = AddConnectionRequest(
            service_name="web-app",
            technology="kubectl",
            connection_params={
                "resource_name": "web-app",
                "namespace": "default",
                "selected_port": 8080  # User selected port
            },
            options={
                "local_port": 8080
            }
        )
        
        # Act
        response = await add_use_case.execute(request)
        
        # Assert
        assert response.success is True
        assert response.configuration_added["remote_port"] == 8080

    @pytest.mark.asyncio
    async def test_kubectl_flow_namespace_resolution(self, add_use_case, mock_discovery_repo):
        """Test kubectl flow with namespace resolution."""
        # Arrange
        # First call returns None (not found in specific namespace)
        # Second call returns matches in multiple namespaces
        mock_discovery_repo.find_resource.return_value = None
        mock_discovery_repo.search_all_namespaces.return_value = [
            ("staging", KubernetesResource(
                name="api-service", namespace="staging", resource_type="service",
                available_ports=[DiscoveredPort(port=8080, protocol="TCP")]
            )),
            ("production", KubernetesResource(
                name="api-service", namespace="production", resource_type="service", 
                available_ports=[DiscoveredPort(port=8080, protocol="TCP")]
            ))
        ]
        
        request = AddConnectionRequest(
            service_name="api",
            technology="kubectl",
            connection_params={
                "resource_name": "api-service",
                "namespace": "staging",  # User selected namespace
                "resolved_from_multiple": True
            },
            options={
                "local_port": 8080
            }
        )
        
        # Act
        response = await add_use_case.execute(request)
        
        # Assert
        assert response.success is True
        mock_discovery_repo.search_all_namespaces.assert_called_once_with("api-service")

    @pytest.mark.asyncio
    async def test_ssh_flow_basic(self, add_use_case, mock_config_repo):
        """Test SSH connection flow."""
        # Arrange
        request = AddConnectionRequest(
            service_name="remote-db",
            technology="ssh", 
            connection_params={
                "host": "db.example.com",
                "user": "dbuser",
                "key_file": "~/.ssh/db_key",
                "port": 22
            },
            options={
                "local_port": 5433,
                "remote_port": 5432
            }
        )
        
        # Act
        response = await add_use_case.execute(request)
        
        # Assert
        assert response.success is True
        assert response.service_name == "remote-db"
        assert response.configuration_added["technology"] == "ssh"
        assert response.configuration_added["connection"]["host"] == "db.example.com"

    @pytest.mark.asyncio
    async def test_service_already_exists_error(self, add_use_case, mock_config_repo):
        """Test error when service name already exists."""
        # Arrange
        mock_config_repo.service_exists.return_value = True
        
        request = AddConnectionRequest(
            service_name="existing-service",
            technology="ssh",
            connection_params={"host": "server.com"},
            options={"local_port": 8080, "remote_port": 80}
        )
        
        # Act & Assert
        with pytest.raises(ServiceAlreadyExistsError):
            await add_use_case.execute(request)

    @pytest.mark.asyncio
    async def test_kubernetes_resource_not_found_error(self, add_use_case, mock_discovery_repo):
        """Test error when Kubernetes resource not found."""
        # Arrange
        mock_discovery_repo.find_resource.return_value = None
        mock_discovery_repo.search_all_namespaces.return_value = []
        
        request = AddConnectionRequest(
            service_name="missing-service",
            technology="kubectl",
            connection_params={
                "resource_name": "missing-service",
                "namespace": "default"
            },
            options={"local_port": 8080}
        )
        
        # Act & Assert
        with pytest.raises(KubernetesResourceNotFoundError):
            await add_use_case.execute(request)


class TestRemoveConnectionUseCase:
    """Test RemoveConnectionUseCase."""

    @pytest.fixture
    def mock_config_repo(self):
        """Mock configuration repository."""
        mock_repo = AsyncMock()
        mock_repo.service_exists.return_value = True
        mock_repo.remove_service_config.return_value = True
        return mock_repo

    @pytest.fixture
    def mock_service_repo(self):
        """Mock service repository."""
        return AsyncMock()

    @pytest.fixture
    def remove_use_case(self, mock_config_repo, mock_service_repo):
        """Create RemoveConnectionUseCase with mocked dependencies."""
        return RemoveConnectionUseCase(
            config_repository=mock_config_repo,
            service_repository=mock_service_repo
        )

    @pytest.mark.asyncio
    async def test_remove_existing_service(self, remove_use_case, mock_config_repo, mock_service_repo):
        """Test removing an existing service."""
        # Arrange
        mock_service_repo.is_running.return_value = False
        request = RemoveConnectionRequest(service_name="test-service")
        
        # Act
        response = await remove_use_case.execute(request)
        
        # Assert
        assert response.success is True
        assert response.service_name == "test-service"
        assert response.was_running is False
        
        # Verify repository calls
        mock_config_repo.service_exists.assert_called_once_with("test-service")
        mock_config_repo.remove_service_config.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_remove_running_service(self, remove_use_case, mock_service_repo):
        """Test removing a currently running service."""
        # Arrange
        mock_service_repo.is_running.return_value = True
        mock_service_repo.stop_service.return_value = None
        request = RemoveConnectionRequest(service_name="running-service")
        
        # Act
        response = await remove_use_case.execute(request)
        
        # Assert
        assert response.success is True
        assert response.was_running is True
        
        # Verify service was stopped
        mock_service_repo.stop_service.assert_called_once_with("running-service")

    @pytest.mark.asyncio
    async def test_remove_non_existent_service(self, remove_use_case, mock_config_repo):
        """Test removing a non-existent service."""
        # Arrange
        mock_config_repo.service_exists.return_value = False
        request = RemoveConnectionRequest(service_name="missing-service")
        
        # Act
        response = await remove_use_case.execute(request)
        
        # Assert
        assert response.success is False
        assert response.service_name == "missing-service"


class TestListConnectionsUseCase:
    """Test ListConnectionsUseCase."""

    @pytest.fixture
    def mock_config_repo(self):
        """Mock configuration repository."""
        return AsyncMock()

    @pytest.fixture
    def list_use_case(self, mock_config_repo):
        """Create ListConnectionsUseCase with mocked dependencies."""
        return ListConnectionsUseCase(config_repository=mock_config_repo)

    @pytest.mark.asyncio
    async def test_list_connections_with_services(self, list_use_case, mock_config_repo):
        """Test listing connections with existing services."""
        # Arrange
        mock_services = [
            {
                "name": "postgres",
                "technology": "kubectl",
                "local_port": 5433,
                "remote_port": 5432,
                "connection": {"resource_name": "postgres-service", "namespace": "default"}
            },
            {
                "name": "redis",
                "technology": "ssh",
                "local_port": 6379,
                "remote_port": 6379,
                "connection": {"host": "redis.example.com", "user": "redis"}
            }
        ]
        mock_config_repo.load_configuration.return_value = {"services": mock_services}
        
        # Act
        response = await list_use_case.execute()
        
        # Assert
        assert response.total_count == 2
        assert len(response.services) == 2
        assert response.technology_breakdown["kubectl"] == 1
        assert response.technology_breakdown["ssh"] == 1
        
        # Check service details
        postgres_service = next(s for s in response.services if s.service_name == "postgres")
        assert postgres_service.technology == "kubectl"
        assert postgres_service.local_port == 5433

    @pytest.mark.asyncio
    async def test_list_connections_empty(self, list_use_case, mock_config_repo):
        """Test listing connections with no services."""
        # Arrange
        mock_config_repo.load_configuration.return_value = {"services": []}
        
        # Act
        response = await list_use_case.execute()
        
        # Assert
        assert response.total_count == 0
        assert len(response.services) == 0
        assert response.technology_breakdown == {}

    @pytest.mark.asyncio
    async def test_list_connections_technology_breakdown(self, list_use_case, mock_config_repo):
        """Test technology breakdown calculation."""
        # Arrange
        mock_services = [
            {"name": "svc1", "technology": "kubectl", "local_port": 8001, "remote_port": 8001, "connection": {}},
            {"name": "svc2", "technology": "kubectl", "local_port": 8002, "remote_port": 8002, "connection": {}},
            {"name": "svc3", "technology": "ssh", "local_port": 8003, "remote_port": 8003, "connection": {}},
            {"name": "svc4", "technology": "kubectl", "local_port": 8004, "remote_port": 8004, "connection": {}},
        ]
        mock_config_repo.load_configuration.return_value = {"services": mock_services}
        
        # Act
        response = await list_use_case.execute()
        
        # Assert
        assert response.total_count == 4
        assert response.technology_breakdown["kubectl"] == 3
        assert response.technology_breakdown["ssh"] == 1

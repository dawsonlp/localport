"""Tests for Kubernetes discovery infrastructure components."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from localport.infrastructure.adapters.kubernetes_discovery_adapter import KubernetesDiscoveryAdapter
from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort
from localport.domain.exceptions import KubernetesResourceNotFoundError
from localport.infrastructure.cluster_monitoring.kubectl_client import KubectlClient, KubectlError


class TestKubernetesDiscoveryAdapter:
    """Test KubernetesDiscoveryAdapter with mocked kubectl."""

    @pytest.fixture
    def mock_kubectl_client(self):
        """Mock kubectl client."""
        return AsyncMock(spec=KubectlClient)

    @pytest.fixture
    def discovery_adapter(self, mock_kubectl_client):
        """Create KubernetesDiscoveryAdapter with mocked kubectl client."""
        return KubernetesDiscoveryAdapter(kubectl_client=mock_kubectl_client)

    @pytest.mark.asyncio
    async def test_find_resource_service_found(self, discovery_adapter, mock_kubectl_client):
        """Test finding an existing Kubernetes service."""
        # Arrange
        mock_service_data = {
            "metadata": {
                "name": "postgres-service",
                "namespace": "default"
            },
            "spec": {
                "ports": [
                    {
                        "name": "postgresql",
                        "port": 5432,
                        "targetPort": 5432,
                        "protocol": "TCP"
                    }
                ]
            }
        }
        mock_kubectl_client._execute_command.return_value = (
            json.dumps(mock_service_data), "", 0
        )
        
        # Act
        resource = await discovery_adapter.find_resource("postgres-service", "default")
        
        # Assert
        assert resource is not None
        assert resource.name == "postgres-service"
        assert resource.namespace == "default"
        assert resource.resource_type == "service"
        assert len(resource.available_ports) == 1
        assert resource.available_ports[0].port == 5432
        assert resource.available_ports[0].name == "postgresql"

    @pytest.mark.asyncio
    async def test_find_resource_pod_found(self, discovery_adapter, mock_kubectl_client):
        """Test finding an existing Kubernetes pod."""
        # Arrange
        mock_pod_data = {
            "metadata": {
                "name": "web-app-pod",
                "namespace": "production"
            },
            "spec": {
                "containers": [
                    {
                        "name": "web-container",
                        "ports": [
                            {
                                "containerPort": 8080,
                                "name": "http",
                                "protocol": "TCP"
                            },
                            {
                                "containerPort": 9090,
                                "name": "metrics",
                                "protocol": "TCP"
                            }
                        ]
                    }
                ]
            }
        }
        
        # Mock sequence: service not found, pod found
        mock_kubectl_client._execute_command.side_effect = [
            ("", "not found", 1),  # Service not found
            (json.dumps(mock_pod_data), "", 0),  # Pod found
        ]
        
        # Act
        resource = await discovery_adapter.find_resource("web-app-pod", "production")
        
        # Assert
        assert resource is not None
        assert resource.name == "web-app-pod"
        assert resource.namespace == "production"
        assert resource.resource_type == "pod"
        assert len(resource.available_ports) == 2

    @pytest.mark.asyncio
    async def test_find_resource_not_found(self, discovery_adapter, mock_kubectl_client):
        """Test finding a non-existent Kubernetes resource."""
        # Arrange
        mock_kubectl_client._execute_command.return_value = (
            "", "not found", 1
        )
        
        # Act
        resource = await discovery_adapter.find_resource("missing-resource", "default")
        
        # Assert
        assert resource is None

    @pytest.mark.asyncio
    async def test_get_current_namespace(self, discovery_adapter, mock_kubectl_client):
        """Test getting current namespace from kubectl context."""
        # Arrange
        mock_config_data = {
            "current-context": "test-context",
            "contexts": [
                {
                    "name": "test-context",
                    "context": {
                        "namespace": "my-namespace",
                        "cluster": "test-cluster"
                    }
                }
            ]
        }
        mock_kubectl_client._execute_command.return_value = (
            json.dumps(mock_config_data), "", 0
        )
        
        # Act
        namespace = await discovery_adapter.get_current_namespace()
        
        # Assert
        assert namespace == "my-namespace"

    @pytest.mark.asyncio
    async def test_get_current_namespace_default_fallback(self, discovery_adapter, mock_kubectl_client):
        """Test fallback to default namespace when context has no namespace."""
        # Arrange
        mock_config_data = {
            "current-context": "test-context",
            "contexts": [
                {
                    "name": "test-context",
                    "context": {
                        "cluster": "test-cluster"
                        # No namespace specified
                    }
                }
            ]
        }
        mock_kubectl_client._execute_command.return_value = (
            json.dumps(mock_config_data), "", 0
        )
        
        # Act
        namespace = await discovery_adapter.get_current_namespace()
        
        # Assert
        assert namespace == "default"

    @pytest.mark.asyncio
    async def test_search_all_namespaces(self, discovery_adapter, mock_kubectl_client):
        """Test searching for resources across all namespaces."""
        # Arrange
        mock_response_data = {
            "items": [
                {
                    "metadata": {
                        "name": "api-service",
                        "namespace": "staging"
                    },
                    "spec": {
                        "ports": [{"port": 8080, "protocol": "TCP"}]
                    }
                },
                {
                    "metadata": {
                        "name": "api-service", 
                        "namespace": "production"
                    },
                    "spec": {
                        "ports": [{"port": 8080, "protocol": "TCP"}]
                    }
                }
            ]
        }
        
        # Mock successful response for service search
        mock_kubectl_client._execute_command.return_value = (
            json.dumps(mock_response_data), "", 0
        )
        
        # Act
        matches = await discovery_adapter.search_all_namespaces("api-service")
        
        # Assert
        assert len(matches) == 2
        
        staging_match = next((m for m in matches if m[0] == "staging"), None)
        assert staging_match is not None
        assert staging_match[1].name == "api-service"
        assert staging_match[1].namespace == "staging"
        
        production_match = next((m for m in matches if m[0] == "production"), None)
        assert production_match is not None
        assert production_match[1].name == "api-service"
        assert production_match[1].namespace == "production"

    @pytest.mark.asyncio
    async def test_get_available_ports_service(self, discovery_adapter, mock_kubectl_client):
        """Test getting available ports for a service."""
        # Arrange
        mock_service_data = {
            "metadata": {"name": "web-service", "namespace": "default"},
            "spec": {
                "ports": [
                    {
                        "name": "http",
                        "port": 80,
                        "targetPort": 8080,
                        "protocol": "TCP"
                    },
                    {
                        "name": "https",
                        "port": 443,
                        "targetPort": 8443,
                        "protocol": "TCP"
                    }
                ]
            }
        }
        mock_kubectl_client._execute_command.return_value = (
            json.dumps(mock_service_data), "", 0
        )
        
        # Act
        ports = await discovery_adapter.get_available_ports("web-service", "default")
        
        # Assert
        assert len(ports) == 2
        
        http_port = next((p for p in ports if p.name == "http"), None)
        assert http_port is not None
        assert http_port.port == 80
        assert http_port.protocol == "TCP"
        
        https_port = next((p for p in ports if p.name == "https"), None)
        assert https_port is not None
        assert https_port.port == 443
        assert https_port.protocol == "TCP"

    @pytest.mark.asyncio
    async def test_kubectl_command_failure_handling(self, discovery_adapter, mock_kubectl_client):
        """Test graceful handling of kubectl command failures."""
        # Arrange
        mock_kubectl_client._execute_command.return_value = (
            "", "kubectl: command not found", 127
        )
        
        # Act
        resource = await discovery_adapter.find_resource("test-service", "default")
        
        # Assert
        assert resource is None

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, discovery_adapter, mock_kubectl_client):
        """Test handling of invalid JSON responses from kubectl."""
        # Arrange
        mock_kubectl_client._execute_command.return_value = (
            "invalid json response", "", 0
        )
        
        # Act
        resource = await discovery_adapter.find_resource("test-service", "default")
        
        # Assert
        assert resource is None


class TestYamlConfigRepositoryExtensions:
    """Test YAML configuration repository service management extensions."""

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file for testing."""
        config_file = tmp_path / "test_config.yaml"
        initial_config = {
            "version": "1.0",
            "services": [
                {
                    "name": "existing-service",
                    "technology": "kubectl",
                    "local_port": 8080,
                    "remote_port": 8080,
                    "connection": {
                        "resource_name": "existing-service",
                        "namespace": "default"
                    }
                }
            ]
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        return config_file

    @pytest.fixture
    def yaml_repo(self, temp_config_file):
        """Create YamlConfigRepository with temporary config file."""
        return YamlConfigRepository(str(temp_config_file))

    @pytest.mark.asyncio
    async def test_service_exists_true(self, yaml_repo):
        """Test service_exists returns True for existing service."""
        # Act
        exists = await yaml_repo.service_exists("existing-service")
        
        # Assert
        assert exists is True

    @pytest.mark.asyncio
    async def test_service_exists_false(self, yaml_repo):
        """Test service_exists returns False for non-existing service."""
        # Act
        exists = await yaml_repo.service_exists("non-existent-service")
        
        # Assert
        assert exists is False

    @pytest.mark.asyncio
    async def test_get_service_names(self, yaml_repo):
        """Test getting list of service names."""
        # Act
        service_names = await yaml_repo.get_service_names()
        
        # Assert
        assert service_names == ["existing-service"]

    @pytest.mark.asyncio
    async def test_add_service_config(self, yaml_repo):
        """Test adding a new service configuration."""
        # Arrange
        new_service = {
            "name": "new-service",
            "technology": "ssh",
            "local_port": 5433,
            "remote_port": 5432,
            "connection": {
                "host": "db.example.com",
                "user": "dbuser"
            }
        }
        
        # Act
        await yaml_repo.add_service_config(new_service)
        
        # Assert
        service_names = await yaml_repo.get_service_names()
        assert "new-service" in service_names
        assert len(service_names) == 2

    @pytest.mark.asyncio
    async def test_remove_service_config(self, yaml_repo):
        """Test removing an existing service configuration."""
        # Act
        removed = await yaml_repo.remove_service_config("existing-service")
        
        # Assert
        assert removed is True
        service_names = await yaml_repo.get_service_names()
        assert "existing-service" not in service_names
        assert len(service_names) == 0

    @pytest.mark.asyncio
    async def test_remove_non_existent_service(self, yaml_repo):
        """Test removing a non-existent service returns False."""
        # Act
        removed = await yaml_repo.remove_service_config("non-existent")
        
        # Assert
        assert removed is False

    @pytest.mark.asyncio
    async def test_get_service_config(self, yaml_repo):
        """Test getting configuration for a specific service."""
        # Act
        service_config = await yaml_repo.get_service_config("existing-service")
        
        # Assert
        assert service_config is not None
        assert service_config["name"] == "existing-service"
        assert service_config["technology"] == "kubectl"
        assert service_config["local_port"] == 8080

    @pytest.mark.asyncio
    async def test_get_service_config_not_found(self, yaml_repo):
        """Test getting configuration for a non-existent service."""
        # Act
        service_config = await yaml_repo.get_service_config("non-existent")
        
        # Assert
        assert service_config is None

    @pytest.mark.asyncio
    async def test_update_service_config(self, yaml_repo):
        """Test updating an existing service configuration."""
        # Arrange
        updated_service = {
            "name": "existing-service",
            "technology": "kubectl", 
            "local_port": 9090,  # Changed port
            "remote_port": 8080,
            "connection": {
                "resource_name": "existing-service",
                "namespace": "production"  # Changed namespace
            }
        }
        
        # Act
        updated = await yaml_repo.update_service_config("existing-service", updated_service)
        
        # Assert
        assert updated is True
        
        # Verify the update
        service_config = await yaml_repo.get_service_config("existing-service")
        assert service_config["local_port"] == 9090
        assert service_config["connection"]["namespace"] == "production"

    @pytest.mark.asyncio
    async def test_update_non_existent_service(self, yaml_repo):
        """Test updating a non-existent service returns False."""
        # Arrange
        service_config = {
            "name": "non-existent",
            "technology": "ssh",
            "local_port": 8080,
            "remote_port": 80,
            "connection": {"host": "server.com"}
        }
        
        # Act
        updated = await yaml_repo.update_service_config("non-existent", service_config)
        
        # Assert
        assert updated is False

    @pytest.mark.asyncio
    async def test_backup_configuration(self, yaml_repo):
        """Test creating a configuration backup."""
        # Act
        backup_path = await yaml_repo.backup_configuration()
        
        # Assert
        assert backup_path is not None
        assert "backup_" in backup_path
        
        # Verify backup file exists
        from pathlib import Path
        assert Path(backup_path).exists()

    @pytest.mark.asyncio
    async def test_atomic_operations_with_backup(self, yaml_repo):
        """Test that operations are atomic with backup/rollback."""
        # This test would need more complex mocking to simulate failures
        # For now, we test that the backup functionality works
        
        # Act
        original_config = await yaml_repo.load_configuration()
        backup_path = await yaml_repo.backup_configuration()
        
        # Assert backup contains the same data
        backup_repo = YamlConfigRepository(backup_path)
        backup_config = await backup_repo.load_configuration()
        
        assert backup_config["services"] == original_config["services"]

    @pytest.mark.asyncio
    async def test_configuration_structure_preservation(self, yaml_repo):
        """Test that configuration structure and formatting are preserved."""
        # Act - Add a service and then load the config
        new_service = {
            "name": "test-preservation",
            "technology": "kubectl",
            "local_port": 3000,
            "remote_port": 3000,
            "connection": {"resource_name": "test", "namespace": "default"}
        }
        
        await yaml_repo.add_service_config(new_service)
        config = await yaml_repo.load_configuration()
        
        # Assert - Original structure is maintained
        assert "version" in config
        assert config["version"] == "1.0"
        assert "services" in config
        assert len(config["services"]) == 2
        
        # Find the added service
        added_service = next(s for s in config["services"] if s["name"] == "test-preservation")
        assert added_service["technology"] == "kubectl"

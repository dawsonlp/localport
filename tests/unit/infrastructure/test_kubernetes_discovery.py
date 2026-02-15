"""Tests for Kubernetes discovery infrastructure components."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort
from localport.domain.exceptions import KubernetesResourceNotFoundError


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

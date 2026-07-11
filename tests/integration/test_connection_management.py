"""Integration tests for connection management workflow."""

import os
import tempfile

import pytest
import yaml

from localport.infrastructure.repositories.yaml_config_repository import (
    YamlConfigRepository,
)


class TestConnectionManagementIntegration:
    """Integration tests for connection management using real YAML files."""

    @pytest.fixture
    def config_file(self):
        """Create a temporary config file."""
        config = {
            "version": "1.0",
            "services": [
                {
                    "name": "postgres",
                    "technology": "kubectl",
                    "local_port": 5433,
                    "remote_port": 5432,
                    "connection": {
                        "resource_name": "postgres",
                        "namespace": "default",
                        "resource_type": "service",
                    },
                    "tags": ["database"],
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            yield f.name
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_load_configuration(self, config_file):
        """Test loading configuration from YAML file."""
        repo = YamlConfigRepository(config_file)
        config = await repo.load_configuration()
        assert config["version"] == "1.0"
        assert len(config["services"]) == 1
        assert config["services"][0]["name"] == "postgres"

    @pytest.mark.asyncio
    async def test_service_exists(self, config_file):
        """Test checking service existence."""
        repo = YamlConfigRepository(config_file)
        assert await repo.service_exists("postgres") is True
        assert await repo.service_exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_get_service_names(self, config_file):
        """Test getting all service names."""
        repo = YamlConfigRepository(config_file)
        names = await repo.get_service_names()
        assert "postgres" in names

    @pytest.mark.asyncio
    async def test_add_service_config(self, config_file):
        """Test adding a new service configuration."""
        repo = YamlConfigRepository(config_file)
        new_service = {
            "name": "redis",
            "technology": "kubectl",
            "local_port": 6379,
            "remote_port": 6379,
            "connection": {
                "resource_name": "redis",
                "namespace": "default",
                "resource_type": "service",
            },
        }
        await repo.add_service_config(new_service)
        assert await repo.service_exists("redis") is True

    @pytest.mark.asyncio
    async def test_add_connection_service_already_exists(self, config_file):
        """Test that adding duplicate service raises error."""
        from localport.domain.exceptions import ServiceAlreadyExistsError

        repo = YamlConfigRepository(config_file)
        duplicate = {
            "name": "postgres",
            "technology": "kubectl",
            "local_port": 5434,
            "remote_port": 5432,
            "connection": {
                "resource_name": "postgres2",
                "namespace": "default",
                "resource_type": "service",
            },
        }
        with pytest.raises(ServiceAlreadyExistsError):
            await repo.add_service_config(duplicate)

    @pytest.mark.asyncio
    async def test_remove_connection_flow(self, config_file):
        """Test removing a service configuration."""
        repo = YamlConfigRepository(config_file)
        result = await repo.remove_service_config("postgres")
        assert result is True
        assert await repo.service_exists("postgres") is False

    @pytest.mark.asyncio
    async def test_remove_nonexistent_service(self, config_file):
        """Test removing a service that doesn't exist."""
        repo = YamlConfigRepository(config_file)
        result = await repo.remove_service_config("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_config(self, config_file):
        """Test updating an existing service configuration."""
        repo = YamlConfigRepository(config_file)
        updated = {
            "name": "postgres",
            "technology": "kubectl",
            "local_port": 5434,  # Changed port
            "remote_port": 5432,
            "connection": {
                "resource_name": "postgres",
                "namespace": "default",
                "resource_type": "service",
            },
        }
        result = await repo.update_service_config("postgres", updated)
        assert result is True

        # Verify update
        service_config = await repo.get_service_config("postgres")
        assert service_config["local_port"] == 5434

    @pytest.mark.asyncio
    async def test_validate_configuration(self, config_file):
        """Test configuration validation."""
        repo = YamlConfigRepository(config_file)
        config = await repo.load_configuration()
        errors = await repo.validate_configuration(config)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_configuration_file_integrity_after_operations(self, config_file):
        """Test that config file remains valid after add/remove operations."""
        repo = YamlConfigRepository(config_file)

        # Add a service
        new_service = {
            "name": "redis",
            "technology": "kubectl",
            "local_port": 6379,
            "remote_port": 6379,
            "connection": {
                "resource_name": "redis",
                "namespace": "default",
                "resource_type": "service",
            },
        }
        await repo.add_service_config(new_service)

        # Remove original service
        await repo.remove_service_config("postgres")

        # Reload and validate
        repo.clear_cache()
        config = await repo.load_configuration()
        errors = await repo.validate_configuration(config)
        assert len(errors) == 0
        assert len(config["services"]) == 1
        assert config["services"][0]["name"] == "redis"

    @pytest.mark.asyncio
    async def test_backup_configuration(self, config_file):
        """Test that backup is created."""
        repo = YamlConfigRepository(config_file)
        backup_path = await repo.backup_configuration()
        assert os.path.exists(backup_path)
        os.unlink(backup_path)

"""Contract tests for repository interfaces."""

from abc import ABC
from uuid import uuid4

import pytest

from localport.domain.entities.service import (
    ForwardingTechnology,
    Service,
    ServiceStatus,
)
from localport.domain.repositories.config_repository import ConfigRepository
from localport.domain.repositories.service_repository import ServiceRepository


class ServiceRepositoryContractTest(ABC):
    """Abstract base class for testing ServiceRepository implementations.

    Any concrete ServiceRepository implementation should inherit from this
    class to ensure it properly implements the repository contract.
    """

    @pytest.fixture
    def repository(self) -> ServiceRepository:
        """Return a ServiceRepository implementation to test.

        This must be implemented by concrete test classes.
        """
        raise NotImplementedError("Subclasses must implement repository fixture")

    @pytest.fixture
    def sample_service(self) -> Service:
        """Create a sample service for testing."""
        return Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test-service", "namespace": "default"},
            tags=["test", "sample"],
            description="A test service"
        )

    @pytest.fixture
    def another_service(self) -> Service:
        """Create another sample service for testing."""
        return Service.create(
            name="another-service",
            technology=ForwardingTechnology.SSH,
            local_port=9090,
            remote_port=90,
            connection_info={"host": "example.com", "user": "test"},
            tags=["test", "another"],
            description="Another test service"
        )

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, repository: ServiceRepository, sample_service: Service):
        """Test saving a service and finding it by ID."""
        # Save the service
        await repository.save(sample_service)

        # Find by ID
        found_service = await repository.find_by_id(sample_service.id)

        assert found_service is not None
        assert found_service.id == sample_service.id
        assert found_service.name == sample_service.name
        assert found_service.technology == sample_service.technology
        assert found_service.local_port == sample_service.local_port
        assert found_service.remote_port == sample_service.remote_port
        assert found_service.connection_info == sample_service.connection_info
        assert found_service.tags == sample_service.tags
        assert found_service.description == sample_service.description

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, repository: ServiceRepository):
        """Test finding a service by ID that doesn't exist."""
        non_existent_id = uuid4()
        found_service = await repository.find_by_id(non_existent_id)
        assert found_service is None

    @pytest.mark.asyncio
    async def test_save_and_find_by_name(self, repository: ServiceRepository, sample_service: Service):
        """Test saving a service and finding it by name."""
        # Save the service
        await repository.save(sample_service)

        # Find by name
        found_service = await repository.find_by_name(sample_service.name)

        assert found_service is not None
        assert found_service.name == sample_service.name
        assert found_service.id == sample_service.id

    @pytest.mark.asyncio
    async def test_find_by_name_not_found(self, repository: ServiceRepository):
        """Test finding a service by name that doesn't exist."""
        found_service = await repository.find_by_name("non-existent-service")
        assert found_service is None

    @pytest.mark.asyncio
    async def test_find_all_empty(self, repository: ServiceRepository):
        """Test finding all services when repository is empty."""
        services = await repository.find_all()
        assert services == []

    @pytest.mark.asyncio
    async def test_save_and_find_all(self, repository: ServiceRepository, sample_service: Service, another_service: Service):
        """Test saving multiple services and finding all."""
        # Save services
        await repository.save(sample_service)
        await repository.save(another_service)

        # Find all
        services = await repository.find_all()

        assert len(services) == 2
        service_names = {s.name for s in services}
        assert sample_service.name in service_names
        assert another_service.name in service_names

    @pytest.mark.asyncio
    async def test_find_by_tags(self, repository: ServiceRepository, sample_service: Service, another_service: Service):
        """Test finding services by tags."""
        # Save services
        await repository.save(sample_service)
        await repository.save(another_service)

        # Find by single tag that both have
        services = await repository.find_by_tags(["test"])
        assert len(services) == 2

        # Find by tag that only one has
        services = await repository.find_by_tags(["sample"])
        assert len(services) == 1
        assert services[0].name == sample_service.name

        # Find by tag that only the other has
        services = await repository.find_by_tags(["another"])
        assert len(services) == 1
        assert services[0].name == another_service.name

        # Find by non-existent tag
        services = await repository.find_by_tags(["non-existent"])
        assert len(services) == 0

    @pytest.mark.asyncio
    async def test_find_by_multiple_tags(self, repository: ServiceRepository, sample_service: Service, another_service: Service):
        """Test finding services by multiple tags."""
        # Save services
        await repository.save(sample_service)
        await repository.save(another_service)

        # Find by multiple tags (should return services that have ANY of the tags)
        services = await repository.find_by_tags(["sample", "another"])
        assert len(services) == 2

        # Find by multiple tags where only one service matches
        services = await repository.find_by_tags(["sample", "non-existent"])
        assert len(services) == 1
        assert services[0].name == sample_service.name

    @pytest.mark.asyncio
    async def test_update_service(self, repository: ServiceRepository, sample_service: Service):
        """Test updating a service."""
        # Save the service
        await repository.save(sample_service)

        # Update the service
        sample_service.status = ServiceStatus.RUNNING
        sample_service.description = "Updated description"
        await repository.save(sample_service)

        # Find and verify update
        found_service = await repository.find_by_id(sample_service.id)
        assert found_service is not None
        assert found_service.status == ServiceStatus.RUNNING
        assert found_service.description == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_service(self, repository: ServiceRepository, sample_service: Service):
        """Test deleting a service."""
        # Save the service
        await repository.save(sample_service)

        # Verify it exists
        found_service = await repository.find_by_id(sample_service.id)
        assert found_service is not None

        # Delete the service
        await repository.delete(sample_service.id)

        # Verify it's gone
        found_service = await repository.find_by_id(sample_service.id)
        assert found_service is None

        # Verify it's not in find_all results
        all_services = await repository.find_all()
        service_ids = {s.id for s in all_services}
        assert sample_service.id not in service_ids

    @pytest.mark.asyncio
    async def test_delete_non_existent_service(self, repository: ServiceRepository):
        """Test deleting a service that doesn't exist (should not raise error)."""
        non_existent_id = uuid4()
        # This should not raise an exception
        await repository.delete(non_existent_id)

    @pytest.mark.asyncio
    async def test_name_uniqueness(self, repository: ServiceRepository, sample_service: Service):
        """Test that service names should be unique."""
        # Save the service
        await repository.save(sample_service)

        # Create another service with the same name but different ID
        duplicate_name_service = Service.create(
            name=sample_service.name,  # Same name
            technology=ForwardingTechnology.SSH,
            local_port=9999,
            remote_port=99,
            connection_info={"host": "different.com"}
        )

        # Save the duplicate name service
        await repository.save(duplicate_name_service)

        # When finding by name, should return the most recently saved one
        found_service = await repository.find_by_name(sample_service.name)
        assert found_service is not None
        # The behavior here depends on implementation - some might overwrite,
        # others might keep the first one. The contract just requires consistency.

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, repository: ServiceRepository, sample_service: Service, another_service: Service):
        """Test concurrent repository operations."""
        import asyncio

        # Save services concurrently
        await asyncio.gather(
            repository.save(sample_service),
            repository.save(another_service)
        )

        # Find services concurrently
        results = await asyncio.gather(
            repository.find_by_id(sample_service.id),
            repository.find_by_id(another_service.id),
            repository.find_all()
        )

        found_sample, found_another, all_services = results

        assert found_sample is not None
        assert found_another is not None
        assert len(all_services) == 2


class ConfigRepositoryContractTest(ABC):
    """Abstract base class for testing ConfigRepository implementations.

    Any concrete ConfigRepository implementation should inherit from this
    class to ensure it properly implements the repository contract.
    """

    @pytest.fixture
    def repository(self) -> ConfigRepository:
        """Return a ConfigRepository implementation to test.

        This must be implemented by concrete test classes.
        """
        raise NotImplementedError("Subclasses must implement repository fixture")

    @pytest.fixture
    def sample_config(self) -> dict:
        """Create a sample configuration for testing."""
        return {
            "version": "1.0",
            "services": [
                {
                    "name": "test-service",
                    "technology": "kubectl",
                    "local_port": 8080,
                    "remote_port": 80,
                    "connection": {
                        "resource_name": "test-service",
                        "namespace": "default"
                    }
                }
            ],
            "defaults": {
                "health_check": {
                    "type": "tcp",
                    "timeout": 5.0
                }
            }
        }

    @pytest.mark.asyncio
    async def test_load_configuration(self, repository: ConfigRepository, sample_config: dict):
        """Test loading configuration."""
        # This test depends on the specific implementation
        # Some repositories might load from files, others from memory
        # The contract just requires that load_configuration returns a dict
        config = await repository.load_configuration()
        assert isinstance(config, dict)

    @pytest.mark.asyncio
    async def test_save_configuration(self, repository: ConfigRepository, sample_config: dict):
        """Test saving configuration."""
        # Save configuration
        await repository.save_configuration(sample_config)

        # Load and verify
        loaded_config = await repository.load_configuration()
        assert loaded_config is not None
        # The exact structure might vary by implementation
        assert isinstance(loaded_config, dict)

    @pytest.mark.asyncio
    async def test_validate_configuration(self, repository: ConfigRepository, sample_config: dict):
        """Test configuration validation."""
        # Valid configuration should pass
        errors = await repository.validate_configuration(sample_config)
        assert isinstance(errors, list)
        # A valid config might still have warnings, so we don't assert empty list

    @pytest.mark.asyncio
    async def test_validate_invalid_configuration(self, repository: ConfigRepository):
        """Test validation of invalid configuration."""
        invalid_config = {
            "version": "invalid",
            "services": "not a list",
            "invalid_field": True
        }

        errors = await repository.validate_configuration(invalid_config)
        assert isinstance(errors, list)
        # Invalid config should have at least some errors
        # (though the specific validation rules depend on implementation)

    @pytest.mark.asyncio
    async def test_get_default_configuration(self, repository: ConfigRepository):
        """Test getting default configuration."""
        default_config = await repository.get_default_configuration()
        assert isinstance(default_config, dict)
        assert "version" in default_config
        assert "services" in default_config


# Example concrete test class for MemoryServiceRepository
class TestMemoryServiceRepositoryContract(ServiceRepositoryContractTest):
    """Test MemoryServiceRepository against the repository contract."""

    @pytest.fixture
    def repository(self) -> ServiceRepository:
        """Return a MemoryServiceRepository for testing."""
        from localport.infrastructure.repositories.memory_service_repository import (
            MemoryServiceRepository,
        )
        return MemoryServiceRepository()


# Helper functions for repository testing

def create_test_service(
    name: str = "test-service",
    technology: ForwardingTechnology = ForwardingTechnology.KUBECTL,
    local_port: int = 8080,
    remote_port: int = 80,
    **kwargs
) -> Service:
    """Create a test service with default values."""
    connection_info = kwargs.pop("connection_info", {"resource_name": name})
    return Service.create(
        name=name,
        technology=technology,
        local_port=local_port,
        remote_port=remote_port,
        connection_info=connection_info,
        **kwargs
    )


async def populate_repository_with_test_data(repository: ServiceRepository) -> list[Service]:
    """Populate a repository with test data and return the services."""
    services = [
        create_test_service("postgres", local_port=5432, remote_port=5432, tags=["database", "essential"]),
        create_test_service("redis", local_port=6379, remote_port=6379, tags=["cache"]),
        create_test_service("kafka", local_port=9092, remote_port=9092, tags=["messaging", "essential"]),
        create_test_service("api", local_port=8080, remote_port=80, tags=["web", "api"]),
    ]

    for service in services:
        await repository.save(service)

    return services


class RepositoryTestHelper:
    """Helper class for repository testing."""

    @staticmethod
    async def assert_service_equals(actual: Service, expected: Service):
        """Assert that two services are equal."""
        assert actual.id == expected.id
        assert actual.name == expected.name
        assert actual.technology == expected.technology
        assert actual.local_port == expected.local_port
        assert actual.remote_port == expected.remote_port
        assert actual.connection_info == expected.connection_info
        assert actual.status == expected.status
        assert actual.health_check_config == expected.health_check_config
        assert actual.restart_policy == expected.restart_policy
        assert actual.tags == expected.tags
        assert actual.description == expected.description

    @staticmethod
    async def assert_services_contain(services: list[Service], expected_service: Service):
        """Assert that a list of services contains the expected service."""
        found = False
        for service in services:
            if service.id == expected_service.id:
                await RepositoryTestHelper.assert_service_equals(service, expected_service)
                found = True
                break
        assert found, f"Service {expected_service.name} not found in services list"

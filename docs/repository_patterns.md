# Repository Patterns and Usage

This document describes the repository patterns used in LocalPort and provides guidance on implementing and using repositories effectively.

## Overview

LocalPort uses the Repository pattern to abstract data access and provide a clean separation between the domain layer and data persistence concerns. This allows for flexible data storage implementations while maintaining a consistent interface for the application layer.

## Repository Interfaces

### ServiceRepository

The `ServiceRepository` interface provides methods for managing `Service` entities:

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from localport.domain.entities.service import Service

class ServiceRepository(ABC):
    """Repository interface for service persistence."""
    
    @abstractmethod
    async def save(self, service: Service) -> None:
        """Save a service (create or update)."""
        pass
    
    @abstractmethod
    async def find_by_id(self, service_id: UUID) -> Optional[Service]:
        """Find a service by its unique ID."""
        pass
    
    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[Service]:
        """Find a service by its name."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Service]:
        """Find all services."""
        pass
    
    @abstractmethod
    async def find_by_tags(self, tags: List[str]) -> List[Service]:
        """Find services that have any of the specified tags."""
        pass
    
    @abstractmethod
    async def delete(self, service_id: UUID) -> None:
        """Delete a service by its ID."""
        pass
```

### ConfigRepository

The `ConfigRepository` interface provides methods for managing configuration data:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ConfigRepository(ABC):
    """Repository interface for configuration management."""
    
    @abstractmethod
    async def load_configuration(self) -> Dict[str, Any]:
        """Load the current configuration."""
        pass
    
    @abstractmethod
    async def save_configuration(self, config: Dict[str, Any]) -> None:
        """Save configuration data."""
        pass
    
    @abstractmethod
    async def validate_configuration(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration and return list of errors."""
        pass
    
    @abstractmethod
    async def get_default_configuration(self) -> Dict[str, Any]:
        """Get default configuration template."""
        pass
```

## Implementation Guidelines

### 1. Repository Contract Compliance

All repository implementations must comply with the repository contracts defined by the abstract interfaces. Use the contract tests to ensure compliance:

```python
from tests.unit.domain.test_repository_contracts import ServiceRepositoryContractTest

class TestMyServiceRepository(ServiceRepositoryContractTest):
    @pytest.fixture
    def repository(self) -> ServiceRepository:
        return MyServiceRepository()
```

### 2. Error Handling

Repositories should handle errors gracefully and provide meaningful error messages:

```python
class MyServiceRepository(ServiceRepository):
    async def save(self, service: Service) -> None:
        try:
            # Implementation logic
            pass
        except DatabaseError as e:
            logger.error("Failed to save service", service_id=service.id, error=str(e))
            raise RepositoryError(f"Failed to save service {service.name}: {e}")
```

### 3. Async/Await Pattern

All repository methods are async to support non-blocking I/O operations:

```python
# Correct usage
service = await repository.find_by_name("my-service")
await repository.save(service)

# Incorrect - don't forget await
service = repository.find_by_name("my-service")  # This returns a coroutine!
```

### 4. Transaction Support

For repositories that support transactions, implement context manager pattern:

```python
class TransactionalRepository(ServiceRepository):
    async def __aenter__(self):
        await self.begin_transaction()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

# Usage
async with TransactionalRepository() as repo:
    await repo.save(service1)
    await repo.save(service2)
    # Automatically commits on success, rolls back on exception
```

## Available Implementations

### MemoryServiceRepository

An in-memory implementation suitable for testing and development:

```python
from localport.infrastructure.repositories.memory_service_repository import MemoryServiceRepository

# Create repository
repo = MemoryServiceRepository()

# Use repository
service = Service.create(name="test", ...)
await repo.save(service)
found = await repo.find_by_name("test")
```

**Characteristics:**
- Fast access (in-memory)
- No persistence (data lost on restart)
- Thread-safe with asyncio
- Suitable for testing and development

### YamlConfigRepository (Planned)

A file-based implementation for configuration management:

```python
from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository

# Create repository with config file path
repo = YamlConfigRepository("localport.yaml")

# Load configuration
config = await repo.load_configuration()

# Save configuration
await repo.save_configuration(updated_config)
```

**Characteristics:**
- File-based persistence
- Human-readable YAML format
- Environment variable substitution
- Configuration validation

## Usage Patterns

### 1. Dependency Injection

Inject repositories into use cases and services:

```python
class StartServicesUseCase:
    def __init__(self, service_repository: ServiceRepository):
        self._service_repository = service_repository
    
    async def execute(self, command: StartServicesCommand):
        services = await self._service_repository.find_by_tags(command.tags)
        # ... rest of implementation
```

### 2. Repository Factory

Use a factory pattern for creating repositories:

```python
class RepositoryFactory:
    @staticmethod
    def create_service_repository(config: Dict[str, Any]) -> ServiceRepository:
        repo_type = config.get("repository_type", "memory")
        
        if repo_type == "memory":
            return MemoryServiceRepository()
        elif repo_type == "file":
            return FileServiceRepository(config["file_path"])
        else:
            raise ValueError(f"Unknown repository type: {repo_type}")
```

### 3. Repository Composition

Combine multiple repositories for complex operations:

```python
class ServiceManager:
    def __init__(
        self,
        service_repo: ServiceRepository,
        config_repo: ConfigRepository
    ):
        self._service_repo = service_repo
        self._config_repo = config_repo
    
    async def load_services_from_config(self):
        config = await self._config_repo.load_configuration()
        for service_config in config["services"]:
            service = self._create_service_from_config(service_config)
            await self._service_repo.save(service)
```

### 4. Caching Pattern

Implement caching for frequently accessed data:

```python
class CachedServiceRepository(ServiceRepository):
    def __init__(self, underlying_repo: ServiceRepository):
        self._repo = underlying_repo
        self._cache = {}
    
    async def find_by_id(self, service_id: UUID) -> Optional[Service]:
        if service_id in self._cache:
            return self._cache[service_id]
        
        service = await self._repo.find_by_id(service_id)
        if service:
            self._cache[service_id] = service
        return service
    
    async def save(self, service: Service) -> None:
        await self._repo.save(service)
        self._cache[service.id] = service  # Update cache
```

## Testing Strategies

### 1. Contract Testing

Use abstract test classes to ensure all implementations follow the same contract:

```python
class TestMemoryServiceRepository(ServiceRepositoryContractTest):
    @pytest.fixture
    def repository(self) -> ServiceRepository:
        return MemoryServiceRepository()

class TestFileServiceRepository(ServiceRepositoryContractTest):
    @pytest.fixture
    def repository(self) -> ServiceRepository:
        return FileServiceRepository(temp_file_path)
```

### 2. Mock Repositories

Create mock repositories for testing application logic:

```python
class MockServiceRepository(ServiceRepository):
    def __init__(self):
        self.saved_services = []
        self.find_by_name_responses = {}
    
    async def save(self, service: Service) -> None:
        self.saved_services.append(service)
    
    async def find_by_name(self, name: str) -> Optional[Service]:
        return self.find_by_name_responses.get(name)
    
    # ... implement other methods

# Usage in tests
@pytest.fixture
def mock_repo():
    return MockServiceRepository()

async def test_use_case(mock_repo):
    # Setup mock responses
    mock_repo.find_by_name_responses["test"] = test_service
    
    # Test use case
    use_case = StartServicesUseCase(mock_repo)
    result = await use_case.execute(command)
    
    # Verify interactions
    assert len(mock_repo.saved_services) == 1
```

### 3. Integration Testing

Test repositories with real data stores:

```python
@pytest.mark.integration
async def test_database_repository():
    # Setup test database
    repo = DatabaseServiceRepository(test_db_url)
    
    # Test operations
    service = create_test_service()
    await repo.save(service)
    
    found = await repo.find_by_id(service.id)
    assert found is not None
    assert found.name == service.name
```

## Performance Considerations

### 1. Batch Operations

Implement batch operations for better performance:

```python
class BatchServiceRepository(ServiceRepository):
    async def save_batch(self, services: List[Service]) -> None:
        """Save multiple services in a single operation."""
        # Implementation depends on underlying storage
        pass
    
    async def find_by_ids(self, service_ids: List[UUID]) -> List[Service]:
        """Find multiple services by their IDs."""
        # More efficient than multiple find_by_id calls
        pass
```

### 2. Pagination

Support pagination for large datasets:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class PageRequest:
    page: int = 0
    size: int = 20
    sort_by: Optional[str] = None
    sort_desc: bool = False

@dataclass
class Page:
    content: List[Service]
    total_elements: int
    total_pages: int
    current_page: int

class PaginatedServiceRepository(ServiceRepository):
    async def find_all_paginated(self, page_request: PageRequest) -> Page:
        """Find services with pagination support."""
        pass
```

### 3. Indexing

Consider indexing strategies for frequently queried fields:

```python
class IndexedServiceRepository(ServiceRepository):
    def __init__(self):
        self._services = {}  # id -> service
        self._name_index = {}  # name -> service_id
        self._tag_index = {}  # tag -> set of service_ids
    
    async def save(self, service: Service) -> None:
        # Update main storage
        self._services[service.id] = service
        
        # Update indexes
        self._name_index[service.name] = service.id
        for tag in service.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(service.id)
```

## Best Practices

### 1. Keep Repositories Simple

Repositories should focus on data access, not business logic:

```python
# Good - simple data access
async def find_active_services(self) -> List[Service]:
    all_services = await self.find_all()
    return [s for s in all_services if s.status == ServiceStatus.RUNNING]

# Better - let the application layer handle filtering
# Repository just provides the data, use case applies business rules
```

### 2. Use Domain Objects

Repositories should work with domain objects, not DTOs or raw data:

```python
# Good - works with domain objects
async def save(self, service: Service) -> None:
    # Convert domain object to storage format internally
    pass

# Avoid - exposing storage details
async def save_raw(self, service_data: dict) -> None:
    pass
```

### 3. Handle Concurrency

Consider concurrent access patterns:

```python
class ConcurrentSafeRepository(ServiceRepository):
    def __init__(self):
        self._lock = asyncio.Lock()
        self._services = {}
    
    async def save(self, service: Service) -> None:
        async with self._lock:
            self._services[service.id] = service
```

### 4. Provide Clear Error Messages

Make debugging easier with descriptive error messages:

```python
async def find_by_name(self, name: str) -> Optional[Service]:
    if not name or not name.strip():
        raise ValueError("Service name cannot be empty or whitespace")
    
    try:
        # Implementation
        pass
    except Exception as e:
        logger.error("Failed to find service by name", name=name, error=str(e))
        raise RepositoryError(f"Failed to find service '{name}': {e}")
```

## Migration and Versioning

### 1. Schema Evolution

Plan for schema changes in persistent repositories:

```python
class VersionedRepository(ServiceRepository):
    CURRENT_VERSION = "1.2"
    
    async def load_service(self, data: dict) -> Service:
        version = data.get("version", "1.0")
        
        if version == "1.0":
            data = self._migrate_from_v1_0(data)
        elif version == "1.1":
            data = self._migrate_from_v1_1(data)
        
        return self._deserialize_service(data)
```

### 2. Backward Compatibility

Maintain backward compatibility when possible:

```python
async def save(self, service: Service) -> None:
    # Always save in current format
    data = self._serialize_service(service)
    data["version"] = self.CURRENT_VERSION
    await self._persist_data(data)
```

This repository pattern documentation provides a comprehensive guide for implementing and using repositories in LocalPort while maintaining clean architecture principles and ensuring testability and maintainability.

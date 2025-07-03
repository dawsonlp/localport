"""Service repository interface for service persistence."""

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.service import Service


class ServiceRepository(ABC):
    """Repository interface for service persistence."""

    @abstractmethod
    async def save(self, service: Service) -> None:
        """Save a service.

        Args:
            service: The service to save

        Raises:
            RepositoryError: If the service cannot be saved
        """
        pass

    @abstractmethod
    async def find_by_id(self, service_id: UUID) -> Service | None:
        """Find a service by ID.

        Args:
            service_id: The unique identifier of the service

        Returns:
            The service if found, None otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Service | None:
        """Find a service by name.

        Args:
            name: The name of the service

        Returns:
            The service if found, None otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def find_all(self) -> list[Service]:
        """Find all services.

        Returns:
            List of all services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def find_by_tags(self, tags: list[str]) -> list[Service]:
        """Find services by tags.

        Args:
            tags: List of tags to search for

        Returns:
            List of services that have any of the specified tags

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def find_enabled(self) -> list[Service]:
        """Find all enabled services.

        Returns:
            List of enabled services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def delete(self, service_id: UUID) -> bool:
        """Delete a service.

        Args:
            service_id: The unique identifier of the service to delete

        Returns:
            True if the service was deleted, False if it didn't exist

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def exists(self, service_id: UUID) -> bool:
        """Check if a service exists.

        Args:
            service_id: The unique identifier of the service

        Returns:
            True if the service exists, False otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count the total number of services.

        Returns:
            The total number of services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        pass


class RepositoryError(Exception):
    """Base exception for repository errors."""
    pass


class ServiceNotFoundError(RepositoryError):
    """Raised when a service is not found."""

    def __init__(self, service_id: UUID | None = None, service_name: str | None = None):
        if service_id:
            message = f"Service with ID {service_id} not found"
        elif service_name:
            message = f"Service with name '{service_name}' not found"
        else:
            message = "Service not found"
        super().__init__(message)
        self.service_id = service_id
        self.service_name = service_name


class DuplicateServiceError(RepositoryError):
    """Raised when attempting to create a service with a duplicate name."""

    def __init__(self, service_name: str):
        super().__init__(f"Service with name '{service_name}' already exists")
        self.service_name = service_name

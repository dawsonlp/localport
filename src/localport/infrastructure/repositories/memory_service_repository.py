"""In-memory service repository implementation."""

from uuid import UUID

import structlog

from ...domain.entities.service import Service
from ...domain.repositories.service_repository import (
    DuplicateServiceError,
    RepositoryError,
    ServiceRepository,
)

logger = structlog.get_logger()


class MemoryServiceRepository(ServiceRepository):
    """In-memory implementation of ServiceRepository."""

    def __init__(self) -> None:
        """Initialize the memory service repository."""
        self._services: dict[UUID, Service] = {}
        self._name_index: dict[str, UUID] = {}

    async def save(self, service: Service) -> None:
        """Save a service.

        Args:
            service: The service to save

        Raises:
            DuplicateServiceError: If a service with the same name already exists
            RepositoryError: If the service cannot be saved
        """
        try:
            # Check for duplicate name (excluding the same service)
            existing_id = self._name_index.get(service.name)
            if existing_id and existing_id != service.id:
                raise DuplicateServiceError(service.name)

            # Save the service
            self._services[service.id] = service
            self._name_index[service.name] = service.id

            logger.debug("Service saved",
                        service_id=service.id,
                        service_name=service.name)

        except DuplicateServiceError:
            raise
        except Exception as e:
            logger.error("Error saving service",
                        service_id=service.id,
                        error=str(e))
            raise RepositoryError(f"Failed to save service: {e}")

    async def find_by_id(self, service_id: UUID) -> Service | None:
        """Find a service by ID.

        Args:
            service_id: The unique identifier of the service

        Returns:
            The service if found, None otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            service = self._services.get(service_id)

            if service:
                logger.debug("Service found by ID", service_id=service_id)
            else:
                logger.debug("Service not found by ID", service_id=service_id)

            return service

        except Exception as e:
            logger.error("Error finding service by ID",
                        service_id=service_id,
                        error=str(e))
            raise RepositoryError(f"Failed to find service by ID: {e}")

    async def find_by_name(self, name: str) -> Service | None:
        """Find a service by name.

        Args:
            name: The name of the service

        Returns:
            The service if found, None otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            service_id = self._name_index.get(name)
            if service_id:
                service = self._services.get(service_id)
                logger.debug("Service found by name", service_name=name)
                return service
            else:
                logger.debug("Service not found by name", service_name=name)
                return None

        except Exception as e:
            logger.error("Error finding service by name",
                        service_name=name,
                        error=str(e))
            raise RepositoryError(f"Failed to find service by name: {e}")

    async def find_all(self) -> list[Service]:
        """Find all services.

        Returns:
            List of all services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            services = list(self._services.values())
            logger.debug("Found all services", count=len(services))
            return services

        except Exception as e:
            logger.error("Error finding all services", error=str(e))
            raise RepositoryError(f"Failed to find all services: {e}")

    async def find_by_tags(self, tags: list[str]) -> list[Service]:
        """Find services by tags.

        Args:
            tags: List of tags to search for

        Returns:
            List of services that have any of the specified tags

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            matching_services = []

            for service in self._services.values():
                # Check if service has any of the specified tags
                if any(tag in service.tags for tag in tags):
                    matching_services.append(service)

            logger.debug("Found services by tags",
                        tags=tags,
                        count=len(matching_services))

            return matching_services

        except Exception as e:
            logger.error("Error finding services by tags",
                        tags=tags,
                        error=str(e))
            raise RepositoryError(f"Failed to find services by tags: {e}")

    async def find_enabled(self) -> list[Service]:
        """Find all enabled services.

        Returns:
            List of enabled services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            enabled_services = []

            for service in self._services.values():
                # Check if service has enabled attribute and it's True
                # For now, assume all services are enabled since our Service entity
                # doesn't have an enabled field yet
                enabled_services.append(service)

            logger.debug("Found enabled services", count=len(enabled_services))
            return enabled_services

        except Exception as e:
            logger.error("Error finding enabled services", error=str(e))
            raise RepositoryError(f"Failed to find enabled services: {e}")

    async def delete(self, service_id: UUID) -> bool:
        """Delete a service.

        Args:
            service_id: The unique identifier of the service to delete

        Returns:
            True if the service was deleted, False if it didn't exist

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            service = self._services.get(service_id)
            if not service:
                logger.debug("Service not found for deletion", service_id=service_id)
                return False

            # Remove from both indexes
            del self._services[service_id]
            del self._name_index[service.name]

            logger.debug("Service deleted",
                        service_id=service_id,
                        service_name=service.name)

            return True

        except Exception as e:
            logger.error("Error deleting service",
                        service_id=service_id,
                        error=str(e))
            raise RepositoryError(f"Failed to delete service: {e}")

    async def exists(self, service_id: UUID) -> bool:
        """Check if a service exists.

        Args:
            service_id: The unique identifier of the service

        Returns:
            True if the service exists, False otherwise

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            exists = service_id in self._services
            logger.debug("Service existence check",
                        service_id=service_id,
                        exists=exists)
            return exists

        except Exception as e:
            logger.error("Error checking service existence",
                        service_id=service_id,
                        error=str(e))
            raise RepositoryError(f"Failed to check service existence: {e}")

    async def count(self) -> int:
        """Count the total number of services.

        Returns:
            The total number of services

        Raises:
            RepositoryError: If there's an error accessing the repository
        """
        try:
            count = len(self._services)
            logger.debug("Service count", count=count)
            return count

        except Exception as e:
            logger.error("Error counting services", error=str(e))
            raise RepositoryError(f"Failed to count services: {e}")

    async def clear(self) -> None:
        """Clear all services from the repository.

        This method is useful for testing and cleanup.
        """
        try:
            count = len(self._services)
            self._services.clear()
            self._name_index.clear()

            logger.debug("Repository cleared", previous_count=count)

        except Exception as e:
            logger.error("Error clearing repository", error=str(e))
            raise RepositoryError(f"Failed to clear repository: {e}")

    async def bulk_save(self, services: list[Service]) -> None:
        """Save multiple services in bulk.

        Args:
            services: List of services to save

        Raises:
            DuplicateServiceError: If any service has a duplicate name
            RepositoryError: If any service cannot be saved
        """
        try:
            # Check for duplicates within the batch and with existing services
            names_in_batch = set()
            for service in services:
                if service.name in names_in_batch:
                    raise DuplicateServiceError(service.name)
                names_in_batch.add(service.name)

                # Check against existing services (excluding same service)
                existing_id = self._name_index.get(service.name)
                if existing_id and existing_id != service.id:
                    raise DuplicateServiceError(service.name)

            # Save all services
            for service in services:
                self._services[service.id] = service
                self._name_index[service.name] = service.id

            logger.debug("Bulk save completed", count=len(services))

        except DuplicateServiceError:
            raise
        except Exception as e:
            logger.error("Error in bulk save",
                        count=len(services),
                        error=str(e))
            raise RepositoryError(f"Failed to bulk save services: {e}")

    async def find_by_status(self, status: str) -> list[Service]:
        """Find services by status.

        Args:
            status: Service status to filter by

        Returns:
            List of services with the specified status
        """
        try:
            from ...domain.entities.service import ServiceStatus

            # Convert string to ServiceStatus enum
            try:
                status_enum = ServiceStatus(status)
            except ValueError:
                logger.warning("Invalid service status", status=status)
                return []

            matching_services = [
                service for service in self._services.values()
                if service.status == status_enum
            ]

            logger.debug("Found services by status",
                        status=status,
                        count=len(matching_services))

            return matching_services

        except Exception as e:
            logger.error("Error finding services by status",
                        status=status,
                        error=str(e))
            raise RepositoryError(f"Failed to find services by status: {e}")

    def get_statistics(self) -> dict[str, int]:
        """Get repository statistics.

        Returns:
            Dictionary with repository statistics
        """
        try:
            from ...domain.entities.service import ForwardingTechnology, ServiceStatus

            stats = {
                "total_services": len(self._services),
                "by_status": {},
                "by_technology": {}
            }

            # Count by status
            for status in ServiceStatus:
                count = sum(1 for s in self._services.values() if s.status == status)
                stats["by_status"][status.value] = count

            # Count by technology
            for tech in ForwardingTechnology:
                count = sum(1 for s in self._services.values() if s.technology == tech)
                stats["by_technology"][tech.value] = count

            return stats

        except Exception as e:
            logger.error("Error getting repository statistics", error=str(e))
            return {"error": str(e)}

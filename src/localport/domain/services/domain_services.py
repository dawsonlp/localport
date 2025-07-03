"""Domain services for LocalPort business logic."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import structlog

from ..entities.health_check import HealthCheck
from ..entities.service import Service, ServiceStatus
from ..value_objects.connection_info import ConnectionInfo
from ..value_objects.port import Port

logger = structlog.get_logger()


class PortConflictResolver(ABC):
    """Domain service for resolving port conflicts."""

    @abstractmethod
    async def check_port_availability(self, port: Port) -> bool:
        """Check if a port is available for use.

        Args:
            port: Port to check

        Returns:
            True if port is available, False otherwise
        """
        pass

    @abstractmethod
    async def find_alternative_port(self, preferred_port: Port, range_start: int = 8000, range_end: int = 9000) -> Port | None:
        """Find an alternative port if the preferred one is not available.

        Args:
            preferred_port: The originally requested port
            range_start: Start of port range to search
            range_end: End of port range to search

        Returns:
            Alternative port if found, None otherwise
        """
        pass

    @abstractmethod
    async def resolve_conflicts(self, services: list[Service]) -> dict[str, Any]:
        """Resolve port conflicts among multiple services.

        Args:
            services: List of services to check for conflicts

        Returns:
            Dictionary with conflict resolution results
        """
        pass


class ServiceValidationService(ABC):
    """Domain service for validating service configurations."""

    @abstractmethod
    async def validate_service_configuration(self, service: Service) -> list[str]:
        """Validate a service configuration.

        Args:
            service: Service to validate

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    @abstractmethod
    async def validate_connection_info(self, connection_info: ConnectionInfo) -> list[str]:
        """Validate connection information.

        Args:
            connection_info: Connection info to validate

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    @abstractmethod
    async def validate_service_dependencies(self, services: list[Service]) -> dict[str, list[str]]:
        """Validate dependencies between services.

        Args:
            services: List of services to validate

        Returns:
            Dictionary mapping service names to dependency errors
        """
        pass


class ServiceLifecycleService(ABC):
    """Domain service for managing service lifecycle transitions."""

    @abstractmethod
    async def can_start_service(self, service: Service) -> bool:
        """Check if a service can be started.

        Args:
            service: Service to check

        Returns:
            True if service can be started
        """
        pass

    @abstractmethod
    async def can_stop_service(self, service: Service) -> bool:
        """Check if a service can be stopped.

        Args:
            service: Service to check

        Returns:
            True if service can be stopped
        """
        pass

    @abstractmethod
    async def can_restart_service(self, service: Service) -> bool:
        """Check if a service can be restarted.

        Args:
            service: Service to check

        Returns:
            True if service can be restarted
        """
        pass

    @abstractmethod
    async def determine_startup_order(self, services: list[Service]) -> list[Service]:
        """Determine the optimal startup order for services.

        Args:
            services: List of services to order

        Returns:
            Services ordered by startup priority
        """
        pass

    @abstractmethod
    async def determine_shutdown_order(self, services: list[Service]) -> list[Service]:
        """Determine the optimal shutdown order for services.

        Args:
            services: List of services to order

        Returns:
            Services ordered by shutdown priority
        """
        pass


class HealthCheckOrchestrator(ABC):
    """Domain service for orchestrating health checks across services."""

    @abstractmethod
    async def schedule_health_checks(self, services: list[Service]) -> dict[UUID, HealthCheck]:
        """Schedule health checks for multiple services.

        Args:
            services: Services to schedule health checks for

        Returns:
            Dictionary mapping service IDs to health check configurations
        """
        pass

    @abstractmethod
    async def evaluate_service_health(self, service: Service, health_check: HealthCheck) -> bool:
        """Evaluate the health of a service.

        Args:
            service: Service to evaluate
            health_check: Health check configuration

        Returns:
            True if service is healthy
        """
        pass

    @abstractmethod
    async def determine_restart_strategy(self, service: Service, failure_count: int) -> dict[str, Any] | None:
        """Determine restart strategy for a failed service.

        Args:
            service: Failed service
            failure_count: Number of consecutive failures

        Returns:
            Restart strategy configuration or None if no restart should be attempted
        """
        pass


class ServiceDiscoveryService(ABC):
    """Domain service for service discovery and dependency resolution."""

    @abstractmethod
    async def discover_service_dependencies(self, service: Service) -> list[str]:
        """Discover dependencies for a service.

        Args:
            service: Service to analyze

        Returns:
            List of service names this service depends on
        """
        pass

    @abstractmethod
    async def find_dependent_services(self, service_name: str, all_services: list[Service]) -> list[Service]:
        """Find services that depend on the given service.

        Args:
            service_name: Name of the service
            all_services: All available services

        Returns:
            List of services that depend on the given service
        """
        pass

    @abstractmethod
    async def build_dependency_graph(self, services: list[Service]) -> dict[str, list[str]]:
        """Build a dependency graph for services.

        Args:
            services: List of services

        Returns:
            Dictionary mapping service names to their dependencies
        """
        pass

    @abstractmethod
    async def detect_circular_dependencies(self, services: list[Service]) -> list[list[str]]:
        """Detect circular dependencies in service configuration.

        Args:
            services: List of services to analyze

        Returns:
            List of circular dependency chains
        """
        pass


class ServiceMetricsService(ABC):
    """Domain service for collecting and analyzing service metrics."""

    @abstractmethod
    async def calculate_service_reliability(self, service: Service, time_window_hours: int = 24) -> float:
        """Calculate service reliability score.

        Args:
            service: Service to analyze
            time_window_hours: Time window for calculation

        Returns:
            Reliability score between 0.0 and 1.0
        """
        pass

    @abstractmethod
    async def calculate_average_startup_time(self, service: Service, sample_size: int = 10) -> float:
        """Calculate average startup time for a service.

        Args:
            service: Service to analyze
            sample_size: Number of recent startups to consider

        Returns:
            Average startup time in seconds
        """
        pass

    @abstractmethod
    async def get_service_performance_metrics(self, service: Service) -> dict[str, Any]:
        """Get comprehensive performance metrics for a service.

        Args:
            service: Service to analyze

        Returns:
            Dictionary with performance metrics
        """
        pass

    @abstractmethod
    async def identify_performance_bottlenecks(self, services: list[Service]) -> dict[str, list[str]]:
        """Identify performance bottlenecks across services.

        Args:
            services: Services to analyze

        Returns:
            Dictionary mapping service names to identified bottlenecks
        """
        pass


class ServiceConfigurationService(ABC):
    """Domain service for managing service configurations."""

    @abstractmethod
    async def merge_configurations(self, base_config: dict[str, Any], override_config: dict[str, Any]) -> dict[str, Any]:
        """Merge service configurations with proper precedence.

        Args:
            base_config: Base configuration
            override_config: Override configuration

        Returns:
            Merged configuration
        """
        pass

    @abstractmethod
    async def validate_configuration_schema(self, config: dict[str, Any], schema_version: str) -> list[str]:
        """Validate configuration against schema.

        Args:
            config: Configuration to validate
            schema_version: Schema version to validate against

        Returns:
            List of validation errors
        """
        pass

    @abstractmethod
    async def migrate_configuration(self, config: dict[str, Any], from_version: str, to_version: str) -> dict[str, Any]:
        """Migrate configuration between versions.

        Args:
            config: Configuration to migrate
            from_version: Source version
            to_version: Target version

        Returns:
            Migrated configuration
        """
        pass

    @abstractmethod
    async def extract_environment_variables(self, config: dict[str, Any]) -> dict[str, str]:
        """Extract environment variables from configuration.

        Args:
            config: Configuration to analyze

        Returns:
            Dictionary of environment variables
        """
        pass


# Concrete implementations for basic domain services

class DefaultPortConflictResolver(PortConflictResolver):
    """Default implementation of port conflict resolver."""

    async def check_port_availability(self, port: Port) -> bool:
        """Check if a port is available using socket binding."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port.value))
                return True
        except OSError:
            return False

    async def find_alternative_port(self, preferred_port: Port, range_start: int = 8000, range_end: int = 9000) -> Port | None:
        """Find an alternative port in the specified range."""
        for port_num in range(range_start, range_end + 1):
            if port_num == preferred_port.value:
                continue

            candidate_port = Port(port_num)
            if await self.check_port_availability(candidate_port):
                logger.info("Found alternative port",
                           preferred=preferred_port.value,
                           alternative=port_num)
                return candidate_port

        return None

    async def resolve_conflicts(self, services: list[Service]) -> dict[str, Any]:
        """Resolve port conflicts among services."""
        conflicts = []
        port_usage = {}

        for service in services:
            port = service.local_port
            if port in port_usage:
                conflicts.append({
                    'port': port,
                    'services': [port_usage[port], service.name]
                })
            else:
                port_usage[port] = service.name

        return {
            'conflicts': conflicts,
            'total_services': len(services),
            'conflicted_ports': len(conflicts)
        }


class DefaultServiceValidationService(ServiceValidationService):
    """Default implementation of service validation."""

    async def validate_service_configuration(self, service: Service) -> list[str]:
        """Validate basic service configuration."""
        errors = []

        # Validate name
        if not service.name or not service.name.strip():
            errors.append("Service name cannot be empty")

        # Validate ports
        if not (1 <= service.local_port <= 65535):
            errors.append(f"Local port {service.local_port} is not valid (must be 1-65535)")

        if not (1 <= service.remote_port <= 65535):
            errors.append(f"Remote port {service.remote_port} is not valid (must be 1-65535)")

        # Validate connection info
        if not service.connection_info:
            errors.append("Connection info cannot be empty")

        return errors

    async def validate_connection_info(self, connection_info: ConnectionInfo) -> list[str]:
        """Validate connection information."""
        errors = []

        # Basic validation - can be extended based on connection type
        if not connection_info.data:
            errors.append("Connection info data cannot be empty")

        return errors

    async def validate_service_dependencies(self, services: list[Service]) -> dict[str, list[str]]:
        """Validate dependencies between services."""
        # Basic implementation - can be extended with actual dependency logic
        return {}


class DefaultServiceLifecycleService(ServiceLifecycleService):
    """Default implementation of service lifecycle management."""

    async def can_start_service(self, service: Service) -> bool:
        """Check if service can be started."""
        return service.status in [ServiceStatus.STOPPED, ServiceStatus.FAILED]

    async def can_stop_service(self, service: Service) -> bool:
        """Check if service can be stopped."""
        return service.status in [ServiceStatus.RUNNING, ServiceStatus.STARTING]

    async def can_restart_service(self, service: Service) -> bool:
        """Check if service can be restarted."""
        return service.can_restart()

    async def determine_startup_order(self, services: list[Service]) -> list[Service]:
        """Determine startup order based on tags and priorities."""
        # Simple implementation: essential services first, then others
        essential = [s for s in services if 'essential' in s.tags]
        others = [s for s in services if 'essential' not in s.tags]

        return essential + others

    async def determine_shutdown_order(self, services: list[Service]) -> list[Service]:
        """Determine shutdown order (reverse of startup order)."""
        startup_order = await self.determine_startup_order(services)
        return list(reversed(startup_order))

"""Factory for creating port forwarding adapter instances."""

from enum import Enum

import structlog

from ...domain.entities.service import ForwardingTechnology
from .base_adapter import AdapterNotAvailableError, PortForwardingAdapter
from .kubectl_adapter import KubectlAdapter
from .ssh_adapter import SSHAdapter

logger = structlog.get_logger()


class AdapterType(str, Enum):
    """Supported adapter types."""
    KUBECTL = "kubectl"
    SSH = "ssh"


class AdapterFactory:
    """Factory for creating port forwarding adapter instances."""

    def __init__(self):
        """Initialize the adapter factory."""
        self._adapters: dict[str, type[PortForwardingAdapter]] = {
            AdapterType.KUBECTL: KubectlAdapter,
            AdapterType.SSH: SSHAdapter,
        }
        self._adapter_instances: dict[str, PortForwardingAdapter] = {}

    async def create_adapter(self, adapter_type: str) -> PortForwardingAdapter | None:
        """Create an adapter instance.

        Args:
            adapter_type: Type of adapter to create

        Returns:
            Adapter instance or None if type not supported

        Raises:
            AdapterNotAvailableError: If adapter prerequisites are not met
        """
        adapter_type = adapter_type.lower()

        # Return cached instance if available
        if adapter_type in self._adapter_instances:
            return self._adapter_instances[adapter_type]

        if adapter_type not in self._adapters:
            logger.error("Unsupported adapter type",
                        type=adapter_type,
                        supported_types=list(self._adapters.keys()))
            return None

        adapter_class = self._adapters[adapter_type]

        try:
            # Create adapter instance
            adapter = adapter_class()

            # Check prerequisites
            if not await adapter.check_prerequisites():
                raise AdapterNotAvailableError(
                    f"Prerequisites not met for {adapter.get_adapter_name()} adapter. "
                    f"Required tools: {adapter.get_required_tools()}"
                )

            # Cache the instance
            self._adapter_instances[adapter_type] = adapter

            logger.info("Created adapter instance",
                       type=adapter_type,
                       name=adapter.get_adapter_name())

            return adapter

        except Exception as e:
            logger.error("Failed to create adapter instance",
                        type=adapter_type,
                        error=str(e))
            if isinstance(e, AdapterNotAvailableError):
                raise
            return None

    async def get_adapter(self, technology: ForwardingTechnology) -> PortForwardingAdapter | None:
        """Get an adapter for a specific forwarding technology.

        Args:
            technology: Forwarding technology enum

        Returns:
            Adapter instance or None if not available
        """
        adapter_type = technology.value
        return await self.create_adapter(adapter_type)

    def register_adapter(self, adapter_type: str, adapter_class: type[PortForwardingAdapter]) -> None:
        """Register a new adapter type.

        Args:
            adapter_type: Name of the adapter type
            adapter_class: Class implementing the adapter
        """
        adapter_type = adapter_type.lower()

        logger.info("Registering adapter type",
                   type=adapter_type,
                   class_name=adapter_class.__name__)

        self._adapters[adapter_type] = adapter_class

        # Clear cached instance if it exists
        self._adapter_instances.pop(adapter_type, None)

    def get_supported_types(self) -> list[str]:
        """Get list of supported adapter types.

        Returns:
            List of supported adapter type names
        """
        return list(self._adapters.keys())

    def is_supported(self, adapter_type: str) -> bool:
        """Check if an adapter type is supported.

        Args:
            adapter_type: Type to check

        Returns:
            True if supported, False otherwise
        """
        return adapter_type.lower() in self._adapters

    async def check_all_adapters(self) -> dict[str, bool]:
        """Check prerequisites for all registered adapters.

        Returns:
            Dictionary mapping adapter types to availability status
        """
        results = {}

        for adapter_type, adapter_class in self._adapters.items():
            try:
                adapter = adapter_class()
                available = await adapter.check_prerequisites()
                results[adapter_type] = available

                logger.debug("Adapter availability check",
                           type=adapter_type,
                           available=available,
                           required_tools=adapter.get_required_tools())

            except Exception as e:
                logger.error("Failed to check adapter prerequisites",
                           type=adapter_type,
                           error=str(e))
                results[adapter_type] = False

        return results

    async def get_available_adapters(self) -> list[str]:
        """Get list of adapters that have their prerequisites met.

        Returns:
            List of available adapter type names
        """
        availability = await self.check_all_adapters()
        return [adapter_type for adapter_type, available in availability.items() if available]

    async def cleanup_all_adapters(self) -> int:
        """Clean up dead processes from all adapter instances.

        Returns:
            Total number of processes cleaned up
        """
        total_cleaned = 0

        for adapter in self._adapter_instances.values():
            try:
                cleaned = await adapter.cleanup_dead_processes()
                total_cleaned += cleaned
            except Exception as e:
                logger.error("Failed to cleanup adapter processes",
                           adapter=adapter.get_adapter_name(),
                           error=str(e))

        if total_cleaned > 0:
            logger.info("Cleaned up dead processes from all adapters",
                       total_cleaned=total_cleaned)

        return total_cleaned

    def clear_cache(self) -> None:
        """Clear all cached adapter instances."""
        self._adapter_instances.clear()
        logger.debug("Cleared adapter instance cache")

    async def validate_connection_info(
        self,
        adapter_type: str,
        connection_info: dict[str, any]
    ) -> list[str]:
        """Validate connection information for a specific adapter type.

        Args:
            adapter_type: Type of adapter
            connection_info: Connection configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        try:
            adapter = await self.create_adapter(adapter_type)
            if not adapter:
                return [f"Adapter type '{adapter_type}' is not supported"]

            return await adapter.validate_connection_info(connection_info)

        except AdapterNotAvailableError as e:
            return [str(e)]
        except Exception as e:
            logger.error("Failed to validate connection info",
                        adapter_type=adapter_type,
                        error=str(e))
            return [f"Validation failed: {str(e)}"]


# Global factory instance
_default_factory = AdapterFactory()


async def create_adapter(adapter_type: str) -> PortForwardingAdapter | None:
    """Create an adapter using the default factory.

    Args:
        adapter_type: Type of adapter to create

    Returns:
        Adapter instance or None if type not supported
    """
    return await _default_factory.create_adapter(adapter_type)


async def get_adapter_for_technology(technology: ForwardingTechnology) -> PortForwardingAdapter | None:
    """Get an adapter for a specific forwarding technology.

    Args:
        technology: Forwarding technology enum

    Returns:
        Adapter instance or None if not available
    """
    return await _default_factory.get_adapter(technology)


def register_adapter(adapter_type: str, adapter_class: type[PortForwardingAdapter]) -> None:
    """Register a new adapter type with the default factory.

    Args:
        adapter_type: Name of the adapter type
        adapter_class: Class implementing the adapter
    """
    _default_factory.register_adapter(adapter_type, adapter_class)


def get_supported_adapter_types() -> list[str]:
    """Get list of supported adapter types.

    Returns:
        List of supported adapter type names
    """
    return _default_factory.get_supported_types()


async def get_available_adapters() -> list[str]:
    """Get list of adapters that have their prerequisites met.

    Returns:
        List of available adapter type names
    """
    return await _default_factory.get_available_adapters()


async def check_adapter_availability() -> dict[str, bool]:
    """Check prerequisites for all registered adapters.

    Returns:
        Dictionary mapping adapter types to availability status
    """
    return await _default_factory.check_all_adapters()


async def cleanup_all_adapter_processes() -> int:
    """Clean up dead processes from all adapters.

    Returns:
        Total number of processes cleaned up
    """
    return await _default_factory.cleanup_all_adapters()

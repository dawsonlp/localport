"""Discovery repository interface for Kubernetes resource discovery."""

from abc import ABC, abstractmethod
from typing import Any

from ..value_objects.discovery import KubernetesResource, DiscoveredPort


class KubernetesDiscoveryRepository(ABC):
    """Abstract repository for discovering Kubernetes resources and their ports.
    
    This interface defines the contract for discovering Kubernetes resources
    that can be used for port forwarding. Implementations will typically
    use kubectl or the Kubernetes API to perform discovery operations.
    """

    @abstractmethod
    async def find_resource(
        self,
        name: str,
        namespace: str | None = None,
        resource_type: str = "service"
    ) -> KubernetesResource | None:
        """Find a Kubernetes resource in the specified namespace.
        
        Args:
            name: Name of the resource to find
            namespace: Namespace to search in (None means use current namespace)
            resource_type: Type of resource to find (service, pod, deployment)
            
        Returns:
            KubernetesResource if found, None otherwise
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def get_available_ports(
        self,
        resource_name: str,
        namespace: str,
        resource_type: str = "service"
    ) -> list[DiscoveredPort]:
        """Get the available ports for a specific resource.
        
        Args:
            resource_name: Name of the resource
            namespace: Namespace containing the resource
            resource_type: Type of resource (service, pod, deployment)
            
        Returns:
            List of discovered ports for the resource
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def get_current_namespace(self) -> str:
        """Get the current Kubernetes namespace from the kubectl context.
        
        Returns:
            Current namespace name
            
        Raises:
            Exception: If there's an error determining the current namespace
        """
        pass

    @abstractmethod
    async def search_all_namespaces(
        self,
        resource_name: str,
        resource_type: str = "service"
    ) -> list[tuple[str, KubernetesResource]]:
        """Search for a resource across all namespaces.
        
        Args:
            resource_name: Name of the resource to search for
            resource_type: Type of resource (service, pod, deployment)
            
        Returns:
            List of tuples containing (namespace, KubernetesResource) for all matches
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def get_namespaces(self) -> list[str]:
        """Get all available namespaces in the cluster.
        
        Returns:
            List of namespace names
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def resource_exists(
        self,
        name: str,
        namespace: str,
        resource_type: str = "service"
    ) -> bool:
        """Check if a resource exists in the specified namespace.
        
        Args:
            name: Name of the resource
            namespace: Namespace to check
            resource_type: Type of resource (service, pod, deployment)
            
        Returns:
            True if resource exists, False otherwise
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def get_resource_json(
        self,
        name: str,
        namespace: str,
        resource_type: str = "service"
    ) -> dict[str, Any] | None:
        """Get the raw JSON representation of a resource.
        
        Args:
            name: Name of the resource
            namespace: Namespace containing the resource
            resource_type: Type of resource (service, pod, deployment)
            
        Returns:
            Raw JSON data from kubectl, or None if resource not found
            
        Raises:
            Exception: If there's an error communicating with Kubernetes
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate that kubectl is available and can connect to a cluster.
        
        Returns:
            True if kubectl is available and connected, False otherwise
        """
        pass

    @abstractmethod
    async def get_cluster_info(self) -> dict[str, Any]:
        """Get basic cluster information for context.
        
        Returns:
            Dictionary with cluster information (server URL, context, etc.)
            
        Raises:
            Exception: If there's an error getting cluster information
        """
        pass


class DiscoveryError(Exception):
    """Base exception for discovery-related errors."""
    pass


class KubernetesConnectionError(DiscoveryError):
    """Raised when unable to connect to Kubernetes cluster."""
    pass


class ResourceNotFoundError(DiscoveryError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_name: str, namespace: str, resource_type: str = "service"):
        self.resource_name = resource_name
        self.namespace = namespace
        self.resource_type = resource_type
        super().__init__(f"{resource_type} '{resource_name}' not found in namespace '{namespace}'")


class MultipleResourcesFoundError(DiscoveryError):
    """Raised when multiple resources are found across namespaces."""
    
    def __init__(self, resource_name: str, namespaces: list[str], resource_type: str = "service"):
        self.resource_name = resource_name
        self.namespaces = namespaces
        self.resource_type = resource_type
        super().__init__(f"{resource_type} '{resource_name}' found in multiple namespaces: {', '.join(namespaces)}")


class NoPortsAvailableError(DiscoveryError):
    """Raised when a resource has no discoverable ports."""
    
    def __init__(self, resource_name: str, namespace: str, resource_type: str = "service"):
        self.resource_name = resource_name
        self.namespace = namespace
        self.resource_type = resource_type
        super().__init__(f"{resource_type} '{resource_name}' in namespace '{namespace}' has no available ports")

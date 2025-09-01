"""Integration tests for connection management CLI flows."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from localport.cli.commands.config_commands import (
    add_connection_command,
    remove_connection_command,
    list_connections_command
)
from localport.cli.formatters.output_format import OutputFormat


class TestConnectionManagementIntegration:
    """Integration tests for complete connection management flows."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary configuration file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            initial_config = """
version: "1.0"
services:
  - name: existing-postgres
    technology: kubectl
    local_port: 5433
    remote_port: 5432
    connection:
      resource_name: postgres-service
      namespace: default
      resource_type: service
  - name: existing-ssh
    technology: ssh
    local_port: 8080
    remote_port: 80
    connection:
      host: web.example.com
      user: webuser
      port: 22
"""
            f.write(initial_config)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_kubectl_add_connection_flow_existing_resource(self, temp_config_file):
        """Test complete kubectl add connection flow with existing resource."""
        # Mock kubectl discovery to return a found service
        with patch('localport.infrastructure.adapters.kubernetes_discovery_adapter.KubernetesDiscoveryAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            
            # Mock finding the resource
            from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort
            mock_resource = KubernetesResource(
                name="redis-service",
                namespace="default",
                resource_type="service",
                available_ports=[
                    DiscoveredPort(port=6379, protocol="TCP", name="redis")
                ]
            )
            mock_adapter.find_resource.return_value = mock_resource
            mock_adapter.get_current_namespace.return_value = "default"
            
            # Mock configuration repository
            with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo
                mock_repo.service_exists.return_value = False
                mock_repo.add_service_config.return_value = None
                
                # Mock validation service
                with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                    mock_validation = AsyncMock()
                    mock_validation_class.return_value = mock_validation
                    mock_validation.validate_service_name.return_value = []
                    mock_validation.validate_port_availability.return_value = []
                    
                    # Act - Execute add connection command
                    await add_connection_command(
                        service_name="redis",
                        technology="kubectl",
                        resource_name="redis-service", 
                        namespace="default",
                        local_port=6379,
                        remote_port=None,  # Should be auto-detected
                        ssh_host=None,
                        ssh_user=None,
                        ssh_key=None,
                        ssh_port=22,
                        output_format=OutputFormat.TABLE,
                        verbosity=0
                    )
                    
                    # Assert - Verify the flow executed correctly
                    mock_adapter.find_resource.assert_called_once_with("redis-service", "default")
                    mock_repo.service_exists.assert_called_once_with("redis")
                    mock_repo.add_service_config.assert_called_once()
                    
                    # Verify the service configuration that was added
                    added_config = mock_repo.add_service_config.call_args[0][0]
                    assert added_config["name"] == "redis"
                    assert added_config["technology"] == "kubectl"
                    assert added_config["local_port"] == 6379
                    assert added_config["remote_port"] == 6379

    @pytest.mark.asyncio  
    async def test_kubectl_add_connection_flow_resource_not_found(self, temp_config_file):
        """Test kubectl add connection flow when resource is not found."""
        with patch('localport.infrastructure.adapters.kubernetes_discovery_adapter.KubernetesDiscoveryAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            
            # Mock resource not found
            mock_adapter.find_resource.return_value = None
            mock_adapter.search_all_namespaces.return_value = []
            
            with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo
                
                with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                    mock_validation = AsyncMock() 
                    mock_validation_class.return_value = mock_validation
                    
                    # Act & Assert - Should raise KubernetesResourceNotFoundError
                    from localport.domain.exceptions import KubernetesResourceNotFoundError
                    with pytest.raises(KubernetesResourceNotFoundError):
                        await add_connection_command(
                            service_name="missing-service",
                            technology="kubectl",
                            resource_name="missing-service",
                            namespace="default",
                            local_port=8080,
                            remote_port=None,
                            ssh_host=None,
                            ssh_user=None,
                            ssh_key=None,
                            ssh_port=22,
                            output_format=OutputFormat.TABLE,
                            verbosity=0
                        )

    @pytest.mark.asyncio
    async def test_ssh_add_connection_flow(self, temp_config_file):
        """Test complete SSH add connection flow."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.service_exists.return_value = False
            mock_repo.add_service_config.return_value = None
            
            with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                mock_validation = AsyncMock()
                mock_validation_class.return_value = mock_validation
                mock_validation.validate_service_name.return_value = []
                mock_validation.validate_port_availability.return_value = []
                mock_validation.validate_ssh_host.return_value = []
                
                # Act - Execute SSH add connection command
                await add_connection_command(
                    service_name="remote-api",
                    technology="ssh",
                    resource_name=None,
                    namespace=None,
                    local_port=3000,
                    remote_port=3000,
                    ssh_host="api.example.com",
                    ssh_user="apiuser",
                    ssh_key="~/.ssh/api_key",
                    ssh_port=22,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Assert - Verify SSH configuration was added
                mock_repo.add_service_config.assert_called_once()
                added_config = mock_repo.add_service_config.call_args[0][0]
                assert added_config["name"] == "remote-api"
                assert added_config["technology"] == "ssh"
                assert added_config["connection"]["host"] == "api.example.com"
                assert added_config["connection"]["user"] == "apiuser"
                assert added_config["connection"]["key_file"] == "~/.ssh/api_key"

    @pytest.mark.asyncio
    async def test_remove_connection_flow(self, temp_config_file):
        """Test complete remove connection flow."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.service_exists.return_value = True
            mock_repo.remove_service_config.return_value = True
            
            # Mock service repository (for checking if service is running)
            with patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
                mock_service_repo = AsyncMock()
                mock_service_repo_class.return_value = mock_service_repo
                mock_service_repo.is_running.return_value = False
                
                # Act - Execute remove connection command
                await remove_connection_command(
                    service_name="existing-postgres",
                    force=True,  # Skip confirmation prompt
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Assert - Verify removal flow
                mock_repo.service_exists.assert_called_once_with("existing-postgres")
                mock_repo.remove_service_config.assert_called_once_with("existing-postgres")

    @pytest.mark.asyncio
    async def test_remove_running_service_flow(self, temp_config_file):
        """Test removing a currently running service."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.service_exists.return_value = True
            mock_repo.remove_service_config.return_value = True
            
            with patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
                mock_service_repo = AsyncMock()
                mock_service_repo_class.return_value = mock_service_repo
                mock_service_repo.is_running.return_value = True  # Service is running
                mock_service_repo.stop_service.return_value = None
                
                # Act - Execute remove connection command
                await remove_connection_command(
                    service_name="existing-ssh",
                    force=True,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Assert - Verify service was stopped before removal
                mock_service_repo.stop_service.assert_called_once_with("existing-ssh")
                mock_repo.remove_service_config.assert_called_once_with("existing-ssh")

    @pytest.mark.asyncio
    async def test_list_connections_flow(self, temp_config_file):
        """Test complete list connections flow."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            
            # Mock configuration data
            mock_config = {
                "services": [
                    {
                        "name": "postgres",
                        "technology": "kubectl",
                        "local_port": 5433,
                        "remote_port": 5432,
                        "connection": {
                            "resource_name": "postgres-service",
                            "namespace": "default"
                        }
                    },
                    {
                        "name": "redis",
                        "technology": "ssh",
                        "local_port": 6379,
                        "remote_port": 6379,
                        "connection": {
                            "host": "redis.example.com",
                            "user": "redis"
                        }
                    }
                ]
            }
            mock_repo.load_configuration.return_value = mock_config
            
            # Act - Execute list connections command
            with patch('localport.cli.formatters.connection_formatter.ConnectionTableFormatter') as mock_formatter_class:
                mock_formatter = MagicMock()
                mock_formatter_class.return_value = mock_formatter
                
                await list_connections_command(
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Assert - Verify list was formatted and displayed
                mock_repo.load_configuration.assert_called_once()
                mock_formatter.format_connections_list.assert_called_once()
                
                # Verify the response passed to formatter
                call_args = mock_formatter.format_connections_list.call_args[0][0]
                assert call_args.total_count == 2
                assert len(call_args.services) == 2

    @pytest.mark.asyncio
    async def test_list_connections_json_output(self, temp_config_file):
        """Test list connections with JSON output format."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.load_configuration.return_value = {"services": []}
            
            # Act - Execute list with JSON output
            with patch('localport.cli.formatters.connection_formatter.ConnectionJsonFormatter') as mock_formatter_class:
                mock_formatter = MagicMock()
                mock_formatter_class.return_value = mock_formatter
                
                await list_connections_command(
                    output_format=OutputFormat.JSON,
                    verbosity=0
                )
                
                # Assert - Verify JSON formatter was used
                mock_formatter.format_connections_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_connection_service_already_exists(self, temp_config_file):
        """Test add connection when service name already exists."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.service_exists.return_value = True  # Service already exists
            
            with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                mock_validation = AsyncMock()
                mock_validation_class.return_value = mock_validation
                
                # Act & Assert - Should raise ServiceAlreadyExistsError
                from localport.domain.exceptions import ServiceAlreadyExistsError
                with pytest.raises(ServiceAlreadyExistsError):
                    await add_connection_command(
                        service_name="existing-postgres",  # Already exists in config
                        technology="kubectl",
                        resource_name="another-service",
                        namespace="default",
                        local_port=8080,
                        remote_port=None,
                        ssh_host=None,
                        ssh_user=None,
                        ssh_key=None,
                        ssh_port=22,
                        output_format=OutputFormat.TABLE,
                        verbosity=0
                    )

    @pytest.mark.asyncio
    async def test_error_handling_with_verbose_output(self, temp_config_file):
        """Test error handling displays appropriate messages based on verbosity."""
        with patch('localport.infrastructure.adapters.kubernetes_discovery_adapter.KubernetesDiscoveryAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            mock_adapter.find_resource.return_value = None
            mock_adapter.search_all_namespaces.return_value = []
            
            with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo
                
                with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                    mock_validation = AsyncMock()
                    mock_validation_class.return_value = mock_validation
                    
                    # Test with different verbosity levels
                    from localport.domain.exceptions import KubernetesResourceNotFoundError
                    
                    # Test verbose mode (should show more detail)
                    with pytest.raises(KubernetesResourceNotFoundError):
                        await add_connection_command(
                            service_name="missing",
                            technology="kubectl", 
                            resource_name="missing-service",
                            namespace="default",
                            local_port=8080,
                            remote_port=None,
                            ssh_host=None,
                            ssh_user=None,
                            ssh_key=None,
                            ssh_port=22,
                            output_format=OutputFormat.TABLE,
                            verbosity=2  # Debug verbosity
                        )

    @pytest.mark.asyncio
    async def test_configuration_file_integrity_after_operations(self, temp_config_file):
        """Test that configuration file remains valid after add/remove operations."""
        import yaml
        
        # Load initial config to verify structure
        with open(temp_config_file, 'r') as f:
            initial_config = yaml.safe_load(f)
        
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            # Use a real repository instance for this test to verify actual file operations
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(temp_config_file)
            mock_repo_class.return_value = real_repo
            
            with patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
                mock_validation = AsyncMock()
                mock_validation_class.return_value = mock_validation
                mock_validation.validate_service_name.return_value = []
                mock_validation.validate_port_availability.return_value = []
                mock_validation.validate_ssh_host.return_value = []
                
                # Act - Add a new SSH service
                await add_connection_command(
                    service_name="test-integrity",
                    technology="ssh",
                    resource_name=None,
                    namespace=None,
                    local_port=9000,
                    remote_port=9000,
                    ssh_host="test.example.com",
                    ssh_user="testuser",
                    ssh_key=None,
                    ssh_port=22,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Assert - Verify configuration file is still valid YAML
                with open(temp_config_file, 'r') as f:
                    updated_config = yaml.safe_load(f)
                
                assert "version" in updated_config
                assert "services" in updated_config
                assert len(updated_config["services"]) == len(initial_config["services"]) + 1
                
                # Verify the new service was added correctly
                new_service = next(s for s in updated_config["services"] if s["name"] == "test-integrity")
                assert new_service["technology"] == "ssh"
                assert new_service["local_port"] == 9000
                assert new_service["connection"]["host"] == "test.example.com"

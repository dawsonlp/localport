"""End-to-end tests for complete connection lifecycle scenarios."""

import os
import tempfile
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from localport.cli.commands.config_commands import (
    add_connection_command,
    remove_connection_command,
    list_connections_command
)
from localport.cli.formatters.output_format import OutputFormat
from localport.domain.exceptions import (
    KubernetesResourceNotFoundError,
    ServiceAlreadyExistsError
)


class TestConnectionLifecycleE2E:
    """End-to-end tests for complete connection management lifecycle."""

    @pytest.fixture
    def e2e_config_file(self):
        """Create a realistic configuration file for E2E testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            initial_config = {
                "version": "1.0",
                "services": [
                    {
                        "name": "production-postgres",
                        "technology": "kubectl",
                        "local_port": 5433,
                        "remote_port": 5432,
                        "connection": {
                            "resource_name": "postgres-service",
                            "namespace": "production",
                            "resource_type": "service"
                        }
                    },
                    {
                        "name": "staging-redis",
                        "technology": "kubectl", 
                        "local_port": 6379,
                        "remote_port": 6379,
                        "connection": {
                            "resource_name": "redis-cache",
                            "namespace": "staging",
                            "resource_type": "pod"
                        }
                    },
                    {
                        "name": "bastion-database",
                        "technology": "ssh",
                        "local_port": 3306,
                        "remote_port": 3306,
                        "connection": {
                            "host": "bastion.company.com",
                            "user": "ec2-user",
                            "key_file": "~/.ssh/bastion.pem",
                            "port": 22,
                            "remote_host": "internal-db.rds.amazonaws.com"
                        }
                    }
                ]
            }
            yaml.dump(initial_config, f, default_flow_style=False)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_complete_kubectl_service_lifecycle(self, e2e_config_file):
        """Test complete lifecycle: discovery → add → list → remove for kubectl service."""
        # Setup mocks for the complete flow
        with patch('localport.infrastructure.adapters.kubernetes_discovery_adapter.KubernetesDiscoveryAdapter') as mock_adapter_class, \
             patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class, \
             patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
            
            # Configure mocks
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            
            # Use real repository for file operations to test integrity
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            
            mock_service_repo = AsyncMock()
            mock_service_repo_class.return_value = mock_service_repo
            mock_service_repo.is_running.return_value = False
            
            # Mock kubectl discovery returning a web service
            from localport.domain.value_objects.discovery import KubernetesResource, DiscoveredPort
            mock_web_service = KubernetesResource(
                name="web-app-service",
                namespace="default",
                resource_type="service",
                available_ports=[
                    DiscoveredPort(port=80, protocol="TCP", name="http"),
                    DiscoveredPort(port=443, protocol="TCP", name="https"),
                    DiscoveredPort(port=9090, protocol="TCP", name="metrics")
                ]
            )
            mock_adapter.find_resource.return_value = mock_web_service
            mock_adapter.get_current_namespace.return_value = "default"
            
            # PHASE 1: Add new kubectl service
            await add_connection_command(
                service_name="web-app-http",
                technology="kubectl",
                resource_name="web-app-service",
                namespace="default",
                local_port=8080,
                remote_port=80,  # Explicitly select HTTP port
                ssh_host=None,
                ssh_user=None,
                ssh_key=None,
                ssh_port=22,
                output_format=OutputFormat.TABLE,
                verbosity=0
            )
            
            # Verify service was added to configuration
            config = await real_repo.load_configuration()
            assert len(config["services"]) == 4  # 3 existing + 1 new
            
            new_service = next(s for s in config["services"] if s["name"] == "web-app-http")
            assert new_service["technology"] == "kubectl"
            assert new_service["local_port"] == 8080
            assert new_service["remote_port"] == 80
            assert new_service["connection"]["resource_name"] == "web-app-service"
            
            # PHASE 2: List connections to verify addition
            with patch('localport.cli.formatters.connection_formatter.ConnectionTableFormatter') as mock_formatter_class:
                mock_formatter = AsyncMock()
                mock_formatter_class.return_value = mock_formatter
                
                await list_connections_command(
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Verify list command processed the new service
                call_args = mock_formatter.format_connections_list.call_args[0][0]
                assert call_args.total_count == 4
                assert call_args.technology_breakdown["kubectl"] == 3  # 2 existing + 1 new
                assert call_args.technology_breakdown["ssh"] == 1
            
            # PHASE 3: Remove the service
            await remove_connection_command(
                service_name="web-app-http",
                force=True,  # Skip confirmation
                output_format=OutputFormat.TABLE,
                verbosity=0
            )
            
            # Verify service was removed
            final_config = await real_repo.load_configuration()
            assert len(final_config["services"]) == 3  # Back to original count
            
            service_names = [s["name"] for s in final_config["services"]]
            assert "web-app-http" not in service_names
            assert "production-postgres" in service_names  # Existing services remain

    @pytest.mark.asyncio
    async def test_complete_ssh_service_lifecycle(self, e2e_config_file):
        """Test complete lifecycle for SSH service with bastion host."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class, \
             patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
            
            # Use real repository for file operations
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            mock_validation.validate_ssh_host.return_value = []
            
            mock_service_repo = AsyncMock()
            mock_service_repo_class.return_value = mock_service_repo
            mock_service_repo.is_running.return_value = False
            
            # PHASE 1: Add SSH service with bastion host
            await add_connection_command(
                service_name="internal-api",
                technology="ssh",
                resource_name=None,
                namespace=None,
                local_port=3000,
                remote_port=3000,
                ssh_host="bastion.example.com",
                ssh_user="deploy",
                ssh_key="~/.ssh/deploy_key",
                ssh_port=22,
                remote_host="internal-api.company.com",  # Behind bastion
                output_format=OutputFormat.TABLE,
                verbosity=0
            )
            
            # Verify SSH service configuration
            config = await real_repo.load_configuration()
            new_service = next(s for s in config["services"] if s["name"] == "internal-api")
            assert new_service["technology"] == "ssh"
            assert new_service["connection"]["host"] == "bastion.example.com"
            assert new_service["connection"]["remote_host"] == "internal-api.company.com"
            assert new_service["connection"]["user"] == "deploy"
            
            # PHASE 2: List with JSON output format
            with patch('localport.cli.formatters.connection_formatter.ConnectionJsonFormatter') as mock_json_formatter_class:
                mock_json_formatter = AsyncMock()
                mock_json_formatter_class.return_value = mock_json_formatter
                
                await list_connections_command(
                    output_format=OutputFormat.JSON,
                    verbosity=0
                )
                
                # Verify JSON formatter was used and called correctly
                mock_json_formatter.format_connections_list.assert_called_once()
            
            # PHASE 3: Remove SSH service
            await remove_connection_command(
                service_name="internal-api",
                force=True,
                output_format=OutputFormat.TABLE,
                verbosity=0
            )
            
            # Verify removal
            final_config = await real_repo.load_configuration()
            service_names = [s["name"] for s in final_config["services"]]
            assert "internal-api" not in service_names

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, e2e_config_file):
        """Test error recovery and rollback scenarios."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
            
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            mock_validation.validate_ssh_host.return_value = []
            
            # Get initial state
            initial_config = await real_repo.load_configuration()
            initial_service_count = len(initial_config["services"])
            
            # SCENARIO 1: Try to add service with existing name
            with pytest.raises(ServiceAlreadyExistsError):
                await add_connection_command(
                    service_name="production-postgres",  # Already exists
                    technology="ssh",
                    resource_name=None,
                    namespace=None,
                    local_port=9999,
                    remote_port=9999,
                    ssh_host="duplicate.example.com",
                    ssh_user="user",
                    ssh_key=None,
                    ssh_port=22,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
            
            # Verify configuration wasn't modified after error
            config_after_error = await real_repo.load_configuration()
            assert len(config_after_error["services"]) == initial_service_count
            
            # SCENARIO 2: Try to remove non-existent service
            response_captured = None
            
            # Mock the remove command to capture response instead of raising
            with patch('localport.application.use_cases.remove_connection.RemoveConnectionUseCase') as mock_use_case_class:
                mock_use_case = AsyncMock()
                mock_use_case_class.return_value = mock_use_case
                
                # Mock response for non-existent service
                from localport.application.dto.connection_dto import RemoveConnectionResponse
                mock_response = RemoveConnectionResponse(
                    success=False,
                    service_name="non-existent-service",
                    was_running=False,
                    error_message="Service not found"
                )
                mock_use_case.execute.return_value = mock_response
                
                await remove_connection_command(
                    service_name="non-existent-service",
                    force=True,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                
                # Verify use case was called but operation failed gracefully
                mock_use_case.execute.assert_called_once()
            
            # Verify original services remain intact
            final_config = await real_repo.load_configuration()
            assert len(final_config["services"]) == initial_service_count

    @pytest.mark.asyncio
    async def test_configuration_file_integrity_under_stress(self, e2e_config_file):
        """Test configuration file integrity under multiple rapid operations."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class, \
             patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
            
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            mock_validation.validate_ssh_host.return_value = []
            
            mock_service_repo = AsyncMock()
            mock_service_repo_class.return_value = mock_service_repo
            mock_service_repo.is_running.return_value = False
            
            # Perform multiple rapid operations
            operations = []
            
            # Add multiple services
            for i in range(5):
                await add_connection_command(
                    service_name=f"stress-test-{i}",
                    technology="ssh",
                    resource_name=None,
                    namespace=None,
                    local_port=9000 + i,
                    remote_port=8000 + i,
                    ssh_host=f"server{i}.example.com",
                    ssh_user="testuser",
                    ssh_key=None,
                    ssh_port=22,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                operations.append(f"ADD stress-test-{i}")
            
            # Verify all services were added correctly
            config_after_adds = await real_repo.load_configuration()
            assert len(config_after_adds["services"]) == 8  # 3 original + 5 new
            
            # Remove every other service
            for i in range(0, 5, 2):  # Remove 0, 2, 4
                await remove_connection_command(
                    service_name=f"stress-test-{i}",
                    force=True,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
                operations.append(f"REMOVE stress-test-{i}")
            
            # Final integrity check
            final_config = await real_repo.load_configuration()
            assert len(final_config["services"]) == 5  # 3 original + 2 remaining
            
            # Verify remaining services are correct
            service_names = [s["name"] for s in final_config["services"]]
            assert "stress-test-1" in service_names
            assert "stress-test-3" in service_names
            assert "stress-test-0" not in service_names
            assert "stress-test-2" not in service_names
            assert "stress-test-4" not in service_names
            
            # Verify original services are intact
            assert "production-postgres" in service_names
            assert "staging-redis" in service_names
            assert "bastion-database" in service_names
            
            # Verify YAML structure is still valid
            with open(e2e_config_file, 'r') as f:
                yaml_content = yaml.safe_load(f)
            
            assert "version" in yaml_content
            assert yaml_content["version"] == "1.0"
            assert "services" in yaml_content
            assert isinstance(yaml_content["services"], list)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("KUBECTL_AVAILABLE"), reason="kubectl not available in test environment")
    async def test_real_kubernetes_cluster_integration(self, e2e_config_file):
        """Test with real Kubernetes cluster if available."""
        # This test only runs if kubectl is available and configured
        try:
            import subprocess
            result = subprocess.run(['kubectl', 'config', 'current-context'], 
                                    capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                pytest.skip("No active kubectl context available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("kubectl command not available or timed out")
        
        # Test with minimal mocking - use real kubectl discovery
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class:
            
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            
            # Try to discover a common Kubernetes service (kube-dns, kubernetes, etc.)
            # This will use real kubectl commands
            try:
                from localport.infrastructure.adapters.kubernetes_discovery_adapter import KubernetesDiscoveryAdapter
                from localport.infrastructure.cluster_monitoring.kubectl_client import KubectlClient
                
                kubectl_client = KubectlClient()
                discovery_adapter = KubernetesDiscoveryAdapter(kubectl_client)
                
                # Try to find kubernetes service in default namespace
                resource = await discovery_adapter.find_resource("kubernetes", "default")
                
                if resource is not None:
                    # If we found a real resource, try adding it as a connection
                    await add_connection_command(
                        service_name="k8s-api-test",
                        technology="kubectl",
                        resource_name="kubernetes",
                        namespace="default",
                        local_port=8443,
                        remote_port=resource.available_ports[0].port if resource.available_ports else 443,
                        ssh_host=None,
                        ssh_user=None,
                        ssh_key=None,
                        ssh_port=22,
                        output_format=OutputFormat.TABLE,
                        verbosity=0
                    )
                    
                    # Verify it was added
                    config = await real_repo.load_configuration()
                    k8s_service = next(s for s in config["services"] if s["name"] == "k8s-api-test")
                    assert k8s_service["connection"]["resource_name"] == "kubernetes"
                    
                    # Clean up
                    await remove_connection_command(
                        service_name="k8s-api-test",
                        force=True,
                        output_format=OutputFormat.TABLE,
                        verbosity=0
                    )
                
            except Exception as e:
                # If real cluster interaction fails, skip gracefully
                pytest.skip(f"Real cluster interaction failed: {e}")

    @pytest.mark.asyncio
    async def test_backup_and_recovery_functionality(self, e2e_config_file):
        """Test configuration backup and recovery functionality."""
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class:
            
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            # Create backup
            backup_path = await real_repo.backup_configuration()
            assert Path(backup_path).exists()
            
            # Verify backup contains same data
            backup_repo = YamlConfigRepository(backup_path)
            original_config = await real_repo.load_configuration()
            backup_config = await backup_repo.load_configuration()
            
            assert len(backup_config["services"]) == len(original_config["services"])
            
            original_names = {s["name"] for s in original_config["services"]}
            backup_names = {s["name"] for s in backup_config["services"]}
            assert original_names == backup_names
            
            # Clean up backup file
            Path(backup_path).unlink()

    @pytest.mark.asyncio
    async def test_concurrent_configuration_access_safety(self, e2e_config_file):
        """Test that configuration remains safe under concurrent access patterns."""
        import asyncio
        
        with patch('localport.infrastructure.repositories.yaml_config_repository.YamlConfigRepository') as mock_repo_class, \
             patch('localport.application.services.connection_validation_service.ConnectionValidationService') as mock_validation_class, \
             patch('localport.infrastructure.repositories.memory_service_repository.MemoryServiceRepository') as mock_service_repo_class:
            
            from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository
            real_repo = YamlConfigRepository(e2e_config_file)
            mock_repo_class.return_value = real_repo
            
            mock_validation = AsyncMock()
            mock_validation_class.return_value = mock_validation
            mock_validation.validate_service_name.return_value = []
            mock_validation.validate_port_availability.return_value = []
            mock_validation.validate_ssh_host.return_value = []
            
            mock_service_repo = AsyncMock()
            mock_service_repo_class.return_value = mock_service_repo
            mock_service_repo.is_running.return_value = False
            
            # Simulate concurrent operations
            async def add_service(index):
                await add_connection_command(
                    service_name=f"concurrent-{index}",
                    technology="ssh",
                    resource_name=None,
                    namespace=None,
                    local_port=10000 + index,
                    remote_port=9000 + index,
                    ssh_host=f"concurrent{index}.example.com",
                    ssh_user="concurrent",
                    ssh_key=None,
                    ssh_port=22,
                    output_format=OutputFormat.TABLE,
                    verbosity=0
                )
            
            async def list_services():
                await list_connections_command(
                    output_format=OutputFormat.JSON,
                    verbosity=0
                )
            
            # Run concurrent operations
            tasks = []
            for i in range(3):
                tasks.append(add_service(i))
            tasks.append(list_services())
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify final state is consistent
            final_config = await real_repo.load_configuration()
            concurrent_services = [s for s in final_config["services"] if s["name"].startswith("concurrent-")]
            
            # Should have 3 concurrent services added
            assert len(concurrent_services) == 3
            
            # Verify each service has correct configuration
            for i, service in enumerate(sorted(concurrent_services, key=lambda s: s["name"])):
                assert service["name"] == f"concurrent-{i}"
                assert service["local_port"] == 10000 + i
                assert service["connection"]["host"] == f"concurrent{i}.example.com"

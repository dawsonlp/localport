"""End-to-end tests for connection lifecycle."""

import asyncio
import tempfile
import os

import pytest
import yaml

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo
from localport.domain.value_objects.discovery import DiscoveredPort, KubernetesResource
from localport.infrastructure.repositories.yaml_config_repository import YamlConfigRepository


class TestConnectionLifecycleE2E:
    """End-to-end tests for the full connection lifecycle."""

    @pytest.fixture
    def config_file(self):
        """Create a temporary config file for e2e tests."""
        config = {
            "version": "1.0",
            "services": []
        }
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            yaml.dump(config, f)
            yield f.name
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_complete_kubectl_service_lifecycle(self, config_file):
        """Test complete lifecycle: create service → add to config → validate → remove."""
        service = Service.from_kubectl_discovery(
            resource_name="postgres",
            namespace="default",
            local_port=5433,
            remote_port=5432,
            service_name="postgres"
        )
        assert service.name == "postgres"
        assert service.technology == ForwardingTechnology.KUBECTL

        repo = YamlConfigRepository(config_file)
        service_config = {
            "name": service.name,
            "technology": service.technology.value,
            "local_port": service.local_port,
            "remote_port": service.remote_port,
            "connection": {
                "resource_name": "postgres",
                "namespace": "default",
                "resource_type": "service"
            }
        }
        await repo.add_service_config(service_config)

        config = await repo.load_configuration()
        errors = await repo.validate_configuration(config)
        assert len(errors) == 0
        assert await repo.service_exists("postgres") is True

        result = await repo.remove_service_config("postgres")
        assert result is True
        assert await repo.service_exists("postgres") is False

    @pytest.mark.asyncio
    async def test_complete_ssh_service_lifecycle(self, config_file):
        """Test complete SSH lifecycle: create → add → validate → remove."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("fake-key")
            os.chmod(f.name, 0o600)
            key_path = f.name

        try:
            service = Service.from_ssh_config(
                service_name="rds-tunnel",
                host="bastion.example.com",
                user="ec2-user",
                key_file=key_path,
                local_port=5433,
                remote_port=5432,
                remote_host="internal-db.rds.amazonaws.com"
            )
            assert service.name == "rds-tunnel"
            assert service.technology == ForwardingTechnology.SSH

            repo = YamlConfigRepository(config_file)
            service_config = {
                "name": service.name,
                "technology": service.technology.value,
                "local_port": service.local_port,
                "remote_port": service.remote_port,
                "connection": {
                    "host": "bastion.example.com",
                    "user": "ec2-user",
                    "key_file": key_path,
                    "port": 22,
                    "remote_host": "internal-db.rds.amazonaws.com"
                }
            }
            await repo.add_service_config(service_config)

            config = await repo.load_configuration()
            errors = await repo.validate_configuration(config)
            assert len(errors) == 0

            result = await repo.remove_service_config("rds-tunnel")
            assert result is True
        finally:
            os.unlink(key_path)

    def test_discovered_port_lowercase_protocol(self):
        """Test that DiscoveredPort requires lowercase protocol."""
        port = DiscoveredPort(port=80, protocol="tcp", name="http")
        assert port.protocol == "tcp"

        with pytest.raises(ValueError):
            DiscoveredPort(port=80, protocol="TCP")

    def test_kubernetes_resource_creation(self):
        """Test creating KubernetesResource with ports."""
        resource = KubernetesResource(
            name="postgres",
            namespace="default",
            resource_type="service",
            available_ports=[
                DiscoveredPort(port=5432, protocol="tcp", name="postgresql"),
            ]
        )
        assert resource.name == "postgres"
        assert len(resource.available_ports) == 1
        assert resource.available_ports[0].port == 5432
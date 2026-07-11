"""Tests for Service entity."""

from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestServiceEntity:
    """Test cases for Service entity."""

    def test_create_service(self):
        """Test creating a service via factory method."""
        conn = ConnectionInfo.kubectl(
            resource_name="postgres", namespace="default", resource_type="service"
        )
        service = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
        )
        assert service.name == "postgres"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port == 5433
        assert service.remote_port == 5432
        assert service.id is not None

    def test_service_with_tags(self):
        """Test creating a service with tags."""
        conn = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
        service = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
            tags=["database", "production"],
        )
        assert "database" in service.tags
        assert "production" in service.tags

    def test_service_health_check(self):
        """Test service with health check configuration."""
        conn = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
        health_config = {
            "type": "tcp",
            "interval": 30,
            "timeout": 5.0,
            "failure_threshold": 3,
        }
        service = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
            health_check_config=health_config,
        )
        assert service.health_check_config is not None
        assert service.health_check_config["type"] == "tcp"

    def test_service_restart_capability(self):
        """Test service with restart policy."""
        conn = ConnectionInfo.ssh(host="example.com", user="admin")
        restart_policy = {
            "enabled": True,
            "max_attempts": 5,
            "initial_delay": 1,
            "backoff_multiplier": 2.0,
        }
        service = Service.create(
            name="ssh-tunnel",
            technology=ForwardingTechnology.SSH,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
            restart_policy=restart_policy,
        )
        assert service.restart_policy is not None
        assert service.restart_policy["enabled"] is True

    def test_tag_management(self):
        """Test adding tags to service."""
        conn = ConnectionInfo.kubectl(resource_name="redis", namespace="default")
        service = Service.create(
            name="redis",
            technology=ForwardingTechnology.KUBECTL,
            local_port=6379,
            remote_port=6379,
            connection_info=conn,
            tags=["cache"],
        )
        assert "cache" in service.tags

    def test_deterministic_service_id(self):
        """Test that service IDs are deterministic based on config."""
        conn = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
        service1 = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
        )
        service2 = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
        )
        assert service1.id == service2.id

    def test_different_config_different_id(self):
        """Test that different configs produce different IDs."""
        conn1 = ConnectionInfo.kubectl(resource_name="postgres", namespace="default")
        conn2 = ConnectionInfo.kubectl(resource_name="postgres", namespace="staging")
        service1 = Service.create(
            name="postgres-default",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn1,
        )
        service2 = Service.create(
            name="postgres-staging",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5434,
            remote_port=5432,
            connection_info=conn2,
        )
        assert service1.id != service2.id

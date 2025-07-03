"""Unit tests for Service entity."""


from localport.domain.entities.service import (
    ForwardingTechnology,
    Service,
    ServiceStatus,
)


class TestServiceEntity:
    """Unit tests for Service entity."""

    def test_create_service(self) -> None:
        """Test service creation."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )

        assert service.name == "test-service"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port == 8080
        assert service.remote_port == 80
        assert service.status == ServiceStatus.STOPPED
        assert service.tags == []
        assert service.connection_info == {"resource_name": "test"}

    def test_service_with_tags(self) -> None:
        """Test service creation with tags."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"},
            tags=["database", "essential"]
        )

        assert service.tags == ["database", "essential"]

    def test_service_health_check(self) -> None:
        """Test service health checking."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )

        assert not service.is_healthy()

        service.update_status(ServiceStatus.RUNNING)
        assert service.is_healthy()

        service.update_status(ServiceStatus.FAILED)
        assert not service.is_healthy()

    def test_service_restart_capability(self) -> None:
        """Test service restart capability."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )

        # Stopped service can restart
        assert service.can_restart()

        # Running service cannot restart
        service.update_status(ServiceStatus.RUNNING)
        assert not service.can_restart()

        # Failed service can restart
        service.update_status(ServiceStatus.FAILED)
        assert service.can_restart()

        # Starting service cannot restart
        service.update_status(ServiceStatus.STARTING)
        assert not service.can_restart()

    def test_tag_management(self) -> None:
        """Test tag management methods."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )

        # Initially no tags
        assert not service.has_tag("database")

        # Add tag
        service.add_tag("database")
        assert service.has_tag("database")
        assert "database" in service.tags

        # Adding same tag again doesn't duplicate
        service.add_tag("database")
        assert service.tags.count("database") == 1

        # Add another tag
        service.add_tag("essential")
        assert service.has_tag("essential")
        assert len(service.tags) == 2

        # Remove tag
        service.remove_tag("database")
        assert not service.has_tag("database")
        assert service.has_tag("essential")

        # Removing non-existent tag doesn't error
        service.remove_tag("nonexistent")
        assert len(service.tags) == 1

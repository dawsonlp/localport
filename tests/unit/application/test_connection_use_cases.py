"""Tests for connection management use cases."""

from localport.application.dto.connection_dto import (
    AddConnectionRequest,
    ListConnectionsRequest,
    RemoveConnectionRequest,
)
from localport.application.use_cases.add_connection import AddConnectionUseCase
from localport.application.use_cases.list_connections import ListConnectionsUseCase
from localport.application.use_cases.remove_connection import RemoveConnectionUseCase
from localport.domain.enums import ForwardingTechnology


class TestAddConnectionUseCase:
    """Test cases for AddConnectionUseCase."""

    def test_import(self):
        """Test that AddConnectionUseCase can be imported."""
        assert AddConnectionUseCase is not None

    def test_request_dto_creation(self):
        """Test creating an AddConnectionRequest."""
        request = AddConnectionRequest(
            service_name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            connection_params={"resource_name": "postgres", "namespace": "default"},
            options={"local_port": 5433, "remote_port": 5432},
        )
        assert request.service_name == "postgres"
        assert request.technology == ForwardingTechnology.KUBECTL


class TestRemoveConnectionUseCase:
    """Test cases for RemoveConnectionUseCase."""

    def test_import(self):
        """Test that RemoveConnectionUseCase can be imported."""
        assert RemoveConnectionUseCase is not None

    def test_request_dto_creation(self):
        """Test creating a RemoveConnectionRequest."""
        request = RemoveConnectionRequest(service_name="postgres")
        assert request.service_name == "postgres"


class TestListConnectionsUseCase:
    """Test cases for ListConnectionsUseCase."""

    def test_import(self):
        """Test that ListConnectionsUseCase can be imported."""
        assert ListConnectionsUseCase is not None

    def test_request_dto_creation(self):
        """Test creating a ListConnectionsRequest."""
        request = ListConnectionsRequest()
        assert request is not None

"""Tests for Port value object."""

import pytest

from localport.domain.value_objects.port import Port, WellKnownPorts


class TestPortValueObject:
    """Test cases for Port value object."""

    def test_create_valid_port(self):
        """Test creating a valid port."""
        port = Port(8080)
        assert port.value == 8080

    def test_create_port_boundary_low(self):
        """Test creating port at lower boundary."""
        port = Port(1)
        assert port.value == 1

    def test_create_port_boundary_high(self):
        """Test creating port at upper boundary."""
        port = Port(65535)
        assert port.value == 65535

    def test_create_port_with_invalid_range(self):
        """Test that ports outside valid range raise ValueError."""
        with pytest.raises(ValueError):
            Port(0)
        with pytest.raises(ValueError):
            Port(65536)
        with pytest.raises(ValueError):
            Port(-1)

    def test_create_port_with_non_integer(self):
        """Test that non-integer values raise ValueError."""
        with pytest.raises(ValueError):
            Port("abc")

    def test_port_equality(self):
        """Test port equality comparison."""
        assert Port(8080) == Port(8080)
        assert Port(8080) == 8080
        assert Port(8080) != Port(9090)

    def test_port_comparison(self):
        """Test port ordering."""
        assert Port(80) < Port(443)
        assert Port(443) > Port(80)

    def test_port_hash(self):
        """Test port hashing for use in sets/dicts."""
        port_set = {Port(80), Port(443), Port(80)}
        assert len(port_set) == 2

    def test_port_string_representation(self):
        """Test port string output."""
        port = Port(8080)
        assert str(port) == "8080"
        assert int(port) == 8080

    def test_port_from_string(self):
        """Test creating port from string."""
        port = Port.from_string("8080")
        assert port.value == 8080

    def test_port_is_valid(self):
        """Test static validation."""
        assert Port.is_valid_port(80) is True
        assert Port.is_valid_port(0) is False
        assert Port.is_valid_port(65536) is False
        assert Port.is_valid_port("443") is True

    def test_port_categories(self):
        """Test port category methods."""
        well_known_port = Port(80)
        assert well_known_port.is_well_known()
        assert well_known_port.is_privileged()

        registered_port = Port(8080)
        assert not registered_port.is_well_known()
        assert registered_port.is_registered()

        ephemeral_port = Port(49152)
        assert not ephemeral_port.is_well_known()
        assert not ephemeral_port.is_registered()
        assert ephemeral_port.is_ephemeral()

    def test_well_known_ports(self):
        """Test well-known port constants."""
        assert WellKnownPorts.SSH.value == 22
        assert WellKnownPorts.HTTP.value == 80
        assert WellKnownPorts.HTTPS.value == 443
        assert WellKnownPorts.POSTGRESQL.value == 5432
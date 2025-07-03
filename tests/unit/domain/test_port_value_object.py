"""Unit tests for Port value object."""

import pytest

from localport.domain.value_objects.port import Port, WellKnownPorts


class TestPortValueObject:
    """Unit tests for Port value object."""

    def test_create_valid_port(self) -> None:
        """Test creating a valid port."""
        port = Port(8080)
        assert port.value == 8080
        assert str(port) == "8080"
        assert int(port) == 8080

    def test_create_port_with_invalid_type(self) -> None:
        """Test creating port with invalid type."""
        with pytest.raises(ValueError, match="Port must be an integer"):
            Port("invalid")  # type: ignore

    def test_create_port_with_invalid_range(self) -> None:
        """Test creating port with invalid range."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            Port(0)

        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            Port(65536)

        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            Port(-1)

    def test_create_port_boundary_values(self) -> None:
        """Test creating ports at boundary values."""
        # Valid boundary values
        port_min = Port(1)
        assert port_min.value == 1

        port_max = Port(65535)
        assert port_max.value == 65535

    def test_from_string_valid(self) -> None:
        """Test creating port from valid string."""
        port = Port.from_string("8080")
        assert port.value == 8080

        # Test with whitespace
        port_with_space = Port.from_string("  3000  ")
        assert port_with_space.value == 3000

    def test_from_string_invalid(self) -> None:
        """Test creating port from invalid string."""
        with pytest.raises(ValueError, match="Invalid port string"):
            Port.from_string("invalid")

        with pytest.raises(ValueError, match="Invalid port string"):
            Port.from_string("65536")

        with pytest.raises(ValueError, match="Invalid port string"):
            Port.from_string("")

    def test_is_valid_port_static_method(self) -> None:
        """Test the static is_valid_port method."""
        assert Port.is_valid_port(80)
        assert Port.is_valid_port("443")
        assert Port.is_valid_port(1)
        assert Port.is_valid_port(65535)

        assert not Port.is_valid_port(0)
        assert not Port.is_valid_port(65536)
        assert not Port.is_valid_port(-1)
        assert not Port.is_valid_port("invalid")
        assert not Port.is_valid_port(None)

    def test_port_categories(self) -> None:
        """Test port category methods."""
        # Well-known port
        http_port = Port(80)
        assert http_port.is_well_known()
        assert http_port.is_privileged()
        assert not http_port.is_registered()
        assert not http_port.is_ephemeral()

        # Registered port
        custom_port = Port(8080)
        assert not custom_port.is_well_known()
        assert not custom_port.is_privileged()
        assert custom_port.is_registered()
        assert not custom_port.is_ephemeral()

        # Ephemeral port
        ephemeral_port = Port(32768)
        assert not ephemeral_port.is_well_known()
        assert not ephemeral_port.is_privileged()
        assert not ephemeral_port.is_registered()
        assert ephemeral_port.is_ephemeral()

        # Boundary cases
        privileged_boundary = Port(1023)
        assert privileged_boundary.is_well_known()
        assert privileged_boundary.is_privileged()

        registered_start = Port(1024)
        assert not registered_start.is_privileged()
        assert registered_start.is_registered()

    def test_port_equality(self) -> None:
        """Test port equality comparisons."""
        port1 = Port(8080)
        port2 = Port(8080)
        port3 = Port(3000)

        # Port to Port comparison
        assert port1 == port2
        assert port1 != port3

        # Port to int comparison
        assert port1 == 8080
        assert port1 != 3000

        # Port to other types
        assert port1 != "8080"
        assert port1 is not None

    def test_port_ordering(self) -> None:
        """Test port ordering comparisons."""
        port1 = Port(80)
        port2 = Port(443)
        port3 = Port(8080)

        # Port to Port comparison
        assert port1 < port2
        assert port2 < port3
        assert port1 <= port2
        assert port2 <= port2
        assert port3 > port2
        assert port2 > port1
        assert port3 >= port2
        assert port2 >= port2

        # Port to int comparison
        assert port1 < 443
        assert port1 <= 80
        assert port3 > 443
        assert port3 >= 8080

    def test_port_hashing(self) -> None:
        """Test port hashing for use in sets and dicts."""
        port1 = Port(8080)
        port2 = Port(8080)
        port3 = Port(3000)

        # Same ports should have same hash
        assert hash(port1) == hash(port2)

        # Different ports should have different hash (usually)
        assert hash(port1) != hash(port3)

        # Test in set
        port_set = {port1, port2, port3}
        assert len(port_set) == 2  # port1 and port2 are the same

        # Test in dict
        port_dict = {port1: "first", port2: "second", port3: "third"}
        assert len(port_dict) == 2
        assert port_dict[port1] == "second"  # port2 overwrote port1

    def test_port_immutability(self) -> None:
        """Test that Port is immutable."""
        port = Port(8080)

        # Should not be able to modify the value
        with pytest.raises(AttributeError):
            port.value = 3000  # type: ignore


class TestWellKnownPorts:
    """Unit tests for WellKnownPorts constants."""

    def test_common_ports(self) -> None:
        """Test common well-known ports."""
        assert WellKnownPorts.HTTP.value == 80
        assert WellKnownPorts.HTTPS.value == 443
        assert WellKnownPorts.SSH.value == 22
        assert WellKnownPorts.FTP.value == 21

        # Database ports
        assert WellKnownPorts.MYSQL.value == 3306
        assert WellKnownPorts.POSTGRESQL.value == 5432
        assert WellKnownPorts.MONGODB.value == 27017
        assert WellKnownPorts.REDIS.value == 6379

        # Message brokers
        assert WellKnownPorts.KAFKA.value == 9092
        assert WellKnownPorts.RABBITMQ.value == 5672

        # Development/monitoring
        assert WellKnownPorts.PROMETHEUS.value == 9090
        assert WellKnownPorts.GRAFANA.value == 3000

    def test_well_known_ports_are_port_instances(self) -> None:
        """Test that well-known ports are Port instances."""
        assert isinstance(WellKnownPorts.HTTP, Port)
        assert isinstance(WellKnownPorts.POSTGRESQL, Port)
        assert isinstance(WellKnownPorts.KAFKA, Port)

    def test_well_known_ports_equality(self) -> None:
        """Test equality with well-known ports."""
        assert WellKnownPorts.HTTP == Port(80)
        assert WellKnownPorts.HTTP == 80
        assert WellKnownPorts.POSTGRESQL == Port(5432)
        assert WellKnownPorts.POSTGRESQL == 5432

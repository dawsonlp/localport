"""Port value object for representing network ports."""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Port:
    """Value object representing a network port."""

    value: int

    def __post_init__(self) -> None:
        """Validate port value after creation."""
        if not isinstance(self.value, int):
            raise ValueError(f"Port must be an integer, got {type(self.value).__name__}. Example: port: 8080 or port: 5432")

        if not self.is_valid_port(self.value):
            raise ValueError(f"Port {self.value} is invalid. Use a port between 1 and 65535 (common ports: 80, 443, 8080, 5432)")

    @staticmethod
    def is_valid_port(port: int | str) -> bool:
        """Check if a port number is valid.

        Args:
            port: Port number to validate

        Returns:
            True if port is valid, False otherwise
        """
        try:
            port_int = int(port)
            return 1 <= port_int <= 65535
        except (ValueError, TypeError):
            return False

    @classmethod
    def from_string(cls, port_str: str) -> "Port":
        """Create a Port from a string representation.

        Args:
            port_str: String representation of the port

        Returns:
            Port instance

        Raises:
            ValueError: If the string cannot be converted to a valid port
        """
        try:
            port_int = int(port_str.strip())
            return cls(port_int)
        except ValueError as e:
            raise ValueError(f"Invalid port string '{port_str}': {e}")

    def is_privileged(self) -> bool:
        """Check if this is a privileged port (< 1024).

        Returns:
            True if port is privileged, False otherwise
        """
        return self.value < 1024

    def is_ephemeral(self) -> bool:
        """Check if this is an ephemeral port (>= 32768).

        Returns:
            True if port is ephemeral, False otherwise
        """
        return self.value >= 32768

    def is_well_known(self) -> bool:
        """Check if this is a well-known port (1-1023).

        Returns:
            True if port is well-known, False otherwise
        """
        return 1 <= self.value <= 1023

    def is_registered(self) -> bool:
        """Check if this is a registered port (1024-49151).

        Returns:
            True if port is registered, False otherwise
        """
        return 1024 <= self.value <= 49151

    def __str__(self) -> str:
        """String representation of the port."""
        return str(self.value)

    def __int__(self) -> int:
        """Integer representation of the port."""
        return self.value

    def __eq__(self, other: object) -> bool:
        """Check equality with another Port or integer."""
        if isinstance(other, Port):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return False

    def __lt__(self, other: Union["Port", int]) -> bool:
        """Less than comparison."""
        if isinstance(other, Port):
            return self.value < other.value
        elif isinstance(other, int):
            return self.value < other
        return NotImplemented

    def __le__(self, other: Union["Port", int]) -> bool:
        """Less than or equal comparison."""
        if isinstance(other, Port):
            return self.value <= other.value
        elif isinstance(other, int):
            return self.value <= other
        return NotImplemented

    def __gt__(self, other: Union["Port", int]) -> bool:
        """Greater than comparison."""
        if isinstance(other, Port):
            return self.value > other.value
        elif isinstance(other, int):
            return self.value > other
        return NotImplemented

    def __ge__(self, other: Union["Port", int]) -> bool:
        """Greater than or equal comparison."""
        if isinstance(other, Port):
            return self.value >= other.value
        elif isinstance(other, int):
            return self.value >= other
        return NotImplemented

    def __hash__(self) -> int:
        """Hash value for the port."""
        return hash(self.value)


# Common well-known ports as constants
class WellKnownPorts:
    """Common well-known port constants."""

    HTTP = Port(80)
    HTTPS = Port(443)
    SSH = Port(22)
    FTP = Port(21)
    TELNET = Port(23)
    SMTP = Port(25)
    DNS = Port(53)
    DHCP_SERVER = Port(67)
    DHCP_CLIENT = Port(68)
    POP3 = Port(110)
    IMAP = Port(143)
    SNMP = Port(161)
    LDAP = Port(389)
    SMTPS = Port(465)
    IMAPS = Port(993)
    POP3S = Port(995)

    # Database ports
    MYSQL = Port(3306)
    POSTGRESQL = Port(5432)
    MONGODB = Port(27017)
    REDIS = Port(6379)

    # Message brokers
    KAFKA = Port(9092)
    RABBITMQ = Port(5672)
    RABBITMQ_MANAGEMENT = Port(15672)

    # Development/monitoring
    PROMETHEUS = Port(9090)
    GRAFANA = Port(3000)
    ELASTICSEARCH = Port(9200)
    KIBANA = Port(5601)

"""Domain enums for LocalPort."""

from enum import Enum


class ServiceStatus(Enum):
    """Status of a port forwarding service."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"


class ForwardingTechnology(Enum):
    """Technology used for port forwarding."""

    KUBECTL = "kubectl"
    SSH = "ssh"

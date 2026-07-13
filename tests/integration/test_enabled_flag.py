"""Regression test for C3: the `enabled` flag must be honored by the loader.

Previously the YAML loader validated `enabled` but never propagated it to the
Service entity, so `enabled: false` services were silently started anyway.
"""

import os
import tempfile

import pytest
import yaml

from localport.infrastructure.repositories.yaml_config_repository import (
    YamlConfigRepository,
)


def _write_config(services: list[dict]) -> str:
    config = {"version": "1.0", "services": services}
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(config, f)
    f.close()
    return f.name


@pytest.mark.asyncio
async def test_enabled_flag_loaded_from_config():
    path = _write_config(
        [
            {
                "name": "on-svc",
                "technology": "kubectl",
                "local_port": 5433,
                "remote_port": 5432,
                "connection": {
                    "resource_name": "a",
                    "namespace": "default",
                    "resource_type": "service",
                },
            },
            {
                "name": "off-svc",
                "technology": "kubectl",
                "local_port": 6444,
                "remote_port": 6443,
                "connection": {
                    "resource_name": "b",
                    "namespace": "default",
                    "resource_type": "service",
                },
                "enabled": False,
            },
        ]
    )
    try:
        repo = YamlConfigRepository(path)
        services = await repo.load_services()
        by_name = {s.name: s for s in services}

        assert by_name["on-svc"].enabled is True  # default when omitted
        assert by_name["off-svc"].enabled is False  # regression: was silently True
    finally:
        os.unlink(path)

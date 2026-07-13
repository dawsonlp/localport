# Contributing to LocalPort

This is the single entry point for contributors. It covers setup, workflow,
quality gates, testing, the PR process, and releasing.

For system design, see the [Architecture Guide](docs/architecture.md).

## Prerequisites

- **Python 3.11+**
- **Git**
- **UV** for package management

LocalPort is a Unix-only project (Linux and macOS).

## Development Setup

1. Fork the repo, then clone your fork:

```bash
git clone https://github.com/dawsonlp/localport.git
cd localport
```

2. Run the setup script, activate the virtualenv, and verify:

```bash
./scripts/setup-dev.sh
source .venv/bin/activate

uv run pytest
localport --help
```

`setup-dev.sh` checks Python, installs UV if missing, creates `.venv`, runs
`uv sync --dev`, and installs the pre-commit hooks.

## Branching and Workflow

We use a structured branching model:

- **`main`**: production-ready, tagged releases only
- **`qa`**: pre-release testing and release candidates
- **`dev`**: active development and feature integration
- **`feature/*`**: individual features (short-lived)

Flow: `feature/*` → `dev` → `qa` → `main`. Hotfixes branch from `main` and are
backported to `dev`. Releases are tagged on `main`.

Start a feature:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```

Open the PR against `dev`.

## Quality Gates

CI runs on Ubuntu and macOS against Python 3.11 and 3.13. **The only enforced
gates are `ruff` and `black`:**

```bash
uv run ruff check .
uv run black --check .
```

Run both before pushing. `black` and `ruff` versions are pinned in
`pyproject.toml` and mirrored in `.pre-commit-config.yaml`.

**`mypy` is strict but local-only** — it is not a CI gate. It runs via the
pre-commit hook (if installed) and can be run manually:

```bash
uv run mypy src/
```

Ruff is deliberately configured as a bug-catcher, not a style nag (pyflakes,
bugbear, isort). Formatting is owned by `black`.

## Testing

The suite is roughly 193 tests across ~20 files. There is no `conftest.py` and
no `pytest.ini`; all pytest config lives in `pyproject.toml`
(`[tool.pytest.ini_options]`).

Layout:

```
tests/
├── e2e/            # end-to-end lifecycle tests (flat files)
├── integration/    # integration tests (flat files)
├── unit/
│   ├── application/
│   ├── cli/
│   ├── domain/
│   └── infrastructure/
└── fixtures/
    └── sample_configs/
```

Three markers are registered (`--strict-markers` is on, so undeclared markers
fail): `unit`, `integration`, `slow`.

Run tests:

```bash
uv run pytest                     # everything
uv run pytest -m "not integration"  # skip integration tests
uv run pytest --cov=src/localport   # with coverage
uv run pytest tests/unit/domain/test_service_entity.py  # one file
```

There is no coverage threshold gate — coverage is reported, not enforced.

### Adding a unit test

Tests use the real domain objects. `ForwardingTechnology` lives in
`localport.domain.enums`; `Service.create()` takes a `ConnectionInfo` value
object and integer ports, and a new service defaults to `STOPPED`:

```python
from localport.domain.entities.service import Service
from localport.domain.enums import ForwardingTechnology, ServiceStatus
from localport.domain.value_objects.connection_info import ConnectionInfo


class TestServiceEntity:
    def test_create_service_defaults_to_stopped(self):
        conn = ConnectionInfo.kubectl(
            resource_name="postgres", namespace="default"
        )
        service = Service.create(
            name="postgres",
            technology=ForwardingTechnology.KUBECTL,
            local_port=5433,
            remote_port=5432,
            connection_info=conn,
        )

        assert service.name == "postgres"
        assert service.status == ServiceStatus.STOPPED
        assert service.enabled is True
```

Mark async tests with `@pytest.mark.asyncio` and integration tests with
`@pytest.mark.integration`.

## Pull Request Process

Before submitting, search existing issues and PRs to avoid duplicate work, and
open an issue first to discuss large changes.

Your PR should:

- Pass `ruff` and `black` (CI enforces these)
- Include tests for new functionality
- Update relevant documentation and docstrings
- Use conventional, focused commit messages

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
```

At least one maintainer approval is required before merge.

## Releasing

Releases are tagged on `main`. Tag-triggered publishing to PyPI is handled by
`release.yml`. Pre-release tags (`vX.Y.Z-alpha.N`, `-beta.N`, `-rc.N`)
automatically publish to Test PyPI.

### Test PyPI

Test package distribution before a production release.

Trigger the "Test PyPI Publishing" workflow from the GitHub Actions tab (enter a
version such as `0.1.0-alpha.1`), or publish locally:

```bash
# Set the pre-release version, build, and publish
uv build
uv publish --index-url https://test.pypi.org/legacy/
```

Verify the install from Test PyPI (Test PyPI shares its namespace with PyPI, so
pull dependencies from the real index):

```bash
pipx install \
  --index-url https://test.pypi.org/simple/ \
  --pip-args="--extra-index-url https://pypi.org/simple/" \
  localport==0.1.0-alpha.1

localport --version
pipx uninstall localport
```

Automated tag-triggered release:

```bash
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
# → GitHub release, Test PyPI publish, install test
```

Common issues: version already exists on Test PyPI; dependency resolution
(use `--extra-index-url`); the `TEST_PYPI_API_TOKEN` secret must be set.

## Questions

Ask in GitHub Discussions or open an issue with the `question` label. For
security issues, email security@localport.dev instead of filing a public issue.

Thank you for contributing to LocalPort.

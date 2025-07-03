# Contributing to LocalPort

Thank you for your interest in contributing to LocalPort! This guide will help you get started with contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Community Guidelines](#community-guidelines)

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- **Python 3.13+** installed
- **Git** for version control
- **UV** for package management (recommended)
- Basic familiarity with:
  - Python async/await programming
  - Command-line tools
  - Port forwarding concepts
  - Either Kubernetes or SSH (depending on your contribution area)

### First-Time Contributors

If you're new to open source or LocalPort:

1. **Read the documentation**:
   - [Architecture Guide](docs/architecture.md) - Understand the system design
   - [Development Guide](docs/development.md) - Learn development workflows
   - [User Documentation](docs/) - Understand user-facing features

2. **Look for good first issues**:
   - Check issues labeled `good first issue`
   - Look for issues labeled `help wanted`
   - Consider documentation improvements

3. **Join the community**:
   - Read our [Code of Conduct](#code-of-conduct)
   - Ask questions in GitHub Discussions
   - Introduce yourself in your first PR

## Development Setup

### Quick Setup

1. **Fork and clone the repository**:
```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/localport.git
cd localport
```

2. **Set up development environment**:
```bash
# Run the setup script
./scripts/setup-dev.sh

# Activate virtual environment
source .venv/bin/activate

# Verify setup
uv run pytest
localport --help
```

3. **Configure Git**:
```bash
# Add upstream remote
git remote add upstream https://github.com/yourusername/localport.git

# Configure your identity
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### Branching Strategy

We use a structured branching model:

- **`main`**: Production-ready code, tagged releases only
- **`qa`**: Pre-release testing, integration testing, release candidates  
- **`dev`**: Active development, feature integration
- **`feature/*`**: Individual feature development (short-lived)

### Development Workflow

1. **Create a feature branch from dev**:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```

2. **Make your changes**:
   - Follow the [Code Standards](#code-standards)
   - Write tests for new functionality
   - Update documentation as needed

3. **Test your changes**:
```bash
# Run tests
uv run pytest

# Check code quality
uv run black --check .
uv run ruff check .
uv run mypy src/
```

4. **Commit your changes**:
```bash
git add .
git commit -m "feat: add new feature description"
```

5. **Push and create PR to dev**:
```bash
git push origin feature/your-feature-name
# Then create a Pull Request targeting the 'dev' branch on GitHub
```

### Release Process

- **Features**: `feature/*` → `dev` → `qa` → `main`
- **Hotfixes**: `hotfix/*` → `main` (with backport to `dev`)
- **Releases**: Tagged on `main` branch, trigger automated releases

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

#### 🐛 Bug Reports
- Use the bug report template
- Include steps to reproduce
- Provide system information
- Include relevant logs or error messages

#### ✨ Feature Requests
- Use the feature request template
- Explain the use case and motivation
- Consider implementation complexity
- Discuss alternatives you've considered

#### 🔧 Code Contributions
- Bug fixes
- New features
- Performance improvements
- Code refactoring

#### 📚 Documentation
- Fix typos or unclear explanations
- Add examples or tutorials
- Improve API documentation
- Translate documentation

#### 🧪 Testing
- Add test cases for existing functionality
- Improve test coverage
- Add integration tests
- Performance testing

### Finding Issues to Work On

1. **Good First Issues**: Perfect for newcomers
   - Usually well-defined and scoped
   - Have clear acceptance criteria
   - Include implementation guidance

2. **Help Wanted**: Issues where we need community help
   - May require specific expertise
   - Could be larger features
   - Often have design discussions

3. **Bug Reports**: Always welcome
   - Check if the bug is already reported
   - Reproduce the issue locally
   - Provide a minimal test case

## Pull Request Process

### Before Submitting

1. **Check existing work**:
   - Search for existing issues or PRs
   - Avoid duplicate work
   - Consider collaborating on existing efforts

2. **Discuss large changes**:
   - Open an issue for discussion first
   - Get feedback on your approach
   - Ensure alignment with project goals

### PR Requirements

Your pull request must:

1. **Pass all checks**:
   - All tests pass
   - Code quality checks pass
   - No merge conflicts

2. **Include tests**:
   - Unit tests for new functionality
   - Integration tests where appropriate
   - Maintain or improve test coverage

3. **Update documentation**:
   - Update relevant documentation
   - Add docstrings for new functions/classes
   - Update configuration examples if needed

4. **Follow commit conventions**:
   - Use conventional commit messages
   - Keep commits focused and atomic
   - Write clear commit messages

### PR Template

When creating a PR, please include:

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

### Review Process

1. **Automated checks**: Must pass before review
2. **Maintainer review**: At least one maintainer approval required
3. **Community feedback**: Other contributors may provide feedback
4. **Iteration**: Address feedback and update PR as needed
5. **Merge**: Maintainer will merge when ready

## Code Standards

### Python Style

We follow PEP 8 with some project-specific conventions:

```python
# Good: Clear, descriptive names
def start_port_forward_service(service: Service) -> PortForward:
    """Start a port forwarding service."""
    pass

# Good: Type hints for all functions
async def check_service_health(
    service: Service, 
    timeout: float = 5.0
) -> HealthStatus:
    """Check the health of a service."""
    pass

# Good: Structured logging
logger.info("Service started", 
           service_name=service.name,
           local_port=service.local_port)
```

### Architecture Guidelines

1. **Follow hexagonal architecture**:
   - Keep domain logic pure
   - Use dependency injection
   - Implement interfaces before concrete classes

2. **Error handling**:
   - Use specific exception types
   - Provide meaningful error messages
   - Log errors with context

3. **Async/await**:
   - Use async for I/O operations
   - Avoid blocking calls in async functions
   - Handle async exceptions properly

### Code Quality Tools

We use automated tools to maintain code quality:

```bash
# Code formatting
uv run black .

# Linting
uv run ruff check .

# Type checking
uv run mypy src/

# Pre-commit hooks (run automatically)
uv run pre-commit run --all-files
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── domain/             # Domain logic tests
│   ├── application/        # Application service tests
│   ├── infrastructure/     # Infrastructure tests (mocked)
│   └── cli/                # CLI tests
├── integration/            # Slower tests with real dependencies
│   ├── adapters/           # Adapter integration tests
│   └── end_to_end/         # Full workflow tests
└── fixtures/               # Test data and configurations
```

### Writing Tests

#### Unit Tests
```python
import pytest
from localport.domain.entities.service import Service

class TestService:
    """Unit tests for Service entity."""
    
    def test_create_service_success(self):
        """Test successful service creation."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        
        assert service.name == "test-service"
        assert service.status == ServiceStatus.STOPPED
    
    def test_create_service_validation(self):
        """Test service creation validation."""
        with pytest.raises(ValueError, match="Port must be"):
            Service.create(
                name="test",
                technology=ForwardingTechnology.KUBECTL,
                local_port=0,  # Invalid port
                remote_port=80,
                connection_info={}
            )
```

#### Async Tests
```python
import pytest

class TestAsyncService:
    """Tests for async service operations."""
    
    @pytest.mark.asyncio
    async def test_start_service(self):
        """Test async service startup."""
        service_manager = ServiceManager()
        service = create_test_service()
        
        result = await service_manager.start_service(service)
        
        assert result.success is True
        assert service.status == ServiceStatus.RUNNING
```

#### Integration Tests
```python
import pytest
from localport.infrastructure.adapters.kubectl_adapter import KubectlAdapter

class TestKubectlAdapter:
    """Integration tests for kubectl adapter."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_kubectl_port_forward(self):
        """Test kubectl port forward with real cluster."""
        adapter = KubectlAdapter()
        
        # This test requires a running Kubernetes cluster
        process_id = await adapter.start_port_forward(
            local_port=8080,
            remote_port=80,
            connection_info={
                "resource_name": "test-service",
                "namespace": "default"
            }
        )
        
        assert process_id is not None
        
        # Cleanup
        await adapter.stop_port_forward(process_id)
```

### Test Coverage

- Aim for >90% test coverage
- Focus on critical business logic
- Test error conditions and edge cases
- Use integration tests for adapter functionality

```bash
# Run tests with coverage
uv run pytest --cov=src/localport --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Documentation

### Types of Documentation

1. **Code Documentation**:
   - Docstrings for all public functions and classes
   - Inline comments for complex logic
   - Type hints for all function signatures

2. **User Documentation**:
   - Getting started guides
   - Configuration references
   - CLI documentation
   - Examples and tutorials

3. **Developer Documentation**:
   - Architecture guides
   - Development workflows
   - Extension guides
   - API references

### Documentation Standards

#### Docstrings
```python
def start_service(self, service: Service) -> ServiceResult:
    """Start a port forwarding service.
    
    Args:
        service: The service to start
        
    Returns:
        Result indicating success or failure
        
    Raises:
        ServiceError: If the service cannot be started
        
    Example:
        >>> service = Service.create(...)
        >>> result = manager.start_service(service)
        >>> assert result.success
    """
    pass
```

#### Markdown Documentation
- Use clear headings and structure
- Include code examples that work
- Add links between related documents
- Keep examples up to date

### Documentation Updates

When making changes that affect users:

1. **Update relevant documentation**
2. **Add examples for new features**
3. **Update configuration references**
4. **Consider adding troubleshooting sections**

## Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read and follow our Code of Conduct:

#### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

#### Our Standards

Examples of behavior that contributes to creating a positive environment:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

Examples of unacceptable behavior:

- The use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate

### Communication

#### GitHub Issues
- Use issue templates when available
- Provide clear, detailed descriptions
- Include relevant system information
- Be respectful in discussions

#### Pull Requests
- Reference related issues
- Explain your changes clearly
- Respond to feedback constructively
- Keep discussions focused on the code

#### Discussions
- Ask questions in GitHub Discussions
- Help other community members
- Share your use cases and experiences
- Provide feedback on proposed features

### Getting Help

If you need help:

1. **Check existing documentation**
2. **Search existing issues and discussions**
3. **Ask in GitHub Discussions**
4. **Create a new issue if needed**

For security issues, please email [security@localport.dev] instead of creating a public issue.

## Recognition

We value all contributions and will recognize contributors in:

- Release notes for significant contributions
- Contributors section in README
- Special recognition for long-term contributors

## Questions?

If you have questions about contributing:

- Check the [Development Guide](docs/development.md)
- Ask in GitHub Discussions
- Create an issue with the `question` label

Thank you for contributing to LocalPort! 🚀

#!/bin/bash

set -e

echo "Setting up LocalPort development environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2)
required_version="3.13"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 13) else 1)"; then
    echo "Error: Python 3.13+ required, found $python_version"
    exit 1
fi

# Install UV if not present
if ! command -v uv &> /dev/null; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Create virtual environment
echo "Creating virtual environment..."
uv venv --python 3.13

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv sync --dev

# Install pre-commit hooks
echo "Setting up pre-commit hooks..."
uv run pre-commit install

# Run initial tests
echo "Running initial tests..."
uv run pytest tests/ -v || echo "Tests will pass once implementation begins"

echo "Development environment setup complete!"
echo "To activate the environment: source .venv/bin/activate"
echo "To run tests: uv run pytest"
echo "To run linting: uv run ruff check ."
echo "To format code: uv run black ."

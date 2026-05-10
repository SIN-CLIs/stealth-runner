# stealth-sync Makefile - Development automation
# OpenSIN/sincode - Stealth Suite Setup Automation

.PHONY: install test lint format clean deploy help

# Colors
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
BLUE=\033[0;34m
NC=\033[0m

# Project metadata
PROJECT_NAME=stealth-sync
PYTHON=python3
PIP=pip3

# Virtual environment
VENV=.venv
PYTHON_BIN=$(VENV)/bin/python
PIP_BIN=$(VENV)/bin/pip

# Source directories
SRC_DIRS=src cli
TEST_DIR=tests

# Check if Python is available
ifeq ($(shell command -v $(PYTHON) 2> /dev/null),)
$(error Python 3.12+ is required but not found)
endif

# Check Python version
PYTHON_VERSION := $(shell $(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MIN_PYTHON_VERSION=3.12

ifeq ($(shell printf '%s\n%s' "$(PYTHON_VERSION)" "$(MIN_PYTHON_VERSION)" | sort -V | head -n1), $(MIN_PYTHON_VERSION))
$(error Python $(MIN_PYTHON_VERSION)+ is required, found $(PYTHON_VERSION))
endif

help:
	@echo "${BLUE}Available targets:${NC}"
	@echo "  ${GREEN}install${NC}       - Install project dependencies"
	@echo "  ${GREEN}test${NC}          - Run tests"
	@echo "  ${GREEN}lint${NC}          - Run linter (ruff)"
	@echo "  ${GREEN}format${NC}        - Format code (ruff)"
	@echo "  ${GREEN}type-check${NC}    - Run type checker (mypy)"
	@echo "  ${GREEN}clean${NC}         - Clean build artifacts"
	@echo "  ${GREEN}setup${NC}         - Run full setup (setup.sh)"
	@echo "  ${GREEN}verify${NC}        - Verify installation"
	@echo "  ${GREEN}deploy${NC}        - Deploy to production"

# Setup virtual environment and install dependencies
install: $(VENV)
	@echo "${BLUE}[INSTALL]${NC} Setting up virtual environment..."
	$(PIP_BIN) install --upgrade pip setuptools wheel
	$(PIP_BIN) install -e ".[dev]"
	@echo "${GREEN}[SUCCESS]${NC} Installation complete!"

$(VENV): pyproject.toml
	@echo "${BLUE}[INSTALL]${NC} Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "${GREEN}[SUCCESS]${NC} Virtual environment created at $(VENV)"

# Run tests
test: install
	@echo "${BLUE}[TEST]${NC} Running tests..."
	$(PIP_BIN) install pytest pytest-asyncio pytest-cov
	$(PIP_BIN) run pytest $(TEST_DIR) -v --tb=short --cov=src --cov-report=term-missing
	@echo "${GREEN}[SUCCESS]${NC} Tests passed!"

# Run linter
lint: install
	@echo "${BLUE}[LINT]${NC} Running linter (ruff)..."
	$(PIP_BIN) run ruff check $(SRC_DIRS) $(TEST_DIR)
	@echo "${GREEN}[SUCCESS]${NC} Linting complete!"

# Format code
format: install
	@echo "${BLUE}[FORMAT]${NC} Formatting code..."
	$(PIP_BIN) run ruff format $(SRC_DIRS) $(TEST_DIR)
	@echo "${GREEN}[SUCCESS]${NC} Code formatted!"

# Type checking
type-check: install
	@echo "${BLUE}[TYPE-CHECK]${NC} Running type checker (mypy)..."
	$(PIP_BIN) run mypy src/
	@echo "${GREEN}[SUCCESS]${NC} Type checking complete!"

# Combined lint and format
check: lint format type-check
	@echo "${GREEN}[SUCCESS]${NC} All checks passed!"

# Clean build artifacts
clean:
	@echo "${BLUE}[CLEAN]${NC} Removing build artifacts..."
	rm -rf .venv/ build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ logs/
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	@echo "${GREEN}[SUCCESS]${NC} Cleaned!"

# Run setup script
setup:
	@echo "${BLUE}[SETUP]${NC} Running setup script..."
	@bash scripts/setup.sh
	@echo "${GREEN}[SUCCESS]${NC} Setup complete!"

# Verify installation
verify:
	@echo "${BLUE}[VERIFY]${NC} Verifying installation..."
	@bash scripts/verify_installation.sh
	@echo "${GREEN}[SUCCESS]${NC} Verification complete!"

# Run all checks
pre-commit: check
	@echo "${GREEN}[SUCCESS]${NC} Pre-commit checks passed!"

# Deploy to production (placeholder)
deploy: install check
	@echo "${BLUE}[DEPLOY]${NC} Deploying to production..."
	@echo "${YELLOW}[INFO]${NC} This is a placeholder. Actual deployment would be configured separately."
	@echo "${GREEN}[SUCCESS]${NC} Deployment complete!"

# Start FastAPI server (production)
run:
	@echo "${BLUE}[RUN]${NC} Starting FastAPI server..."
	$(PYTHON_BIN) -m uvicorn api.main:app --host 0.0.0.0 --port 8889 --workers 1 --log-level info
	@echo "${GREEN}[SUCCESS]${NC} Server started!"

# Start FastAPI with auto-reload (development)
dev:
	@echo "${BLUE}[DEV]${NC} Starting FastAPI server with auto-reload..."
	$(PYTHON_BIN) -m uvicorn api.main:app --host 0.0.0.0 --port 8889 --reload --log-level debug
	@echo "${GREEN}[SUCCESS]${NC} Server started in dev mode!"

# Start background API (using start-api.sh)
start-bg:
	@echo "${BLUE}[START]${NC} Starting background API..."
	@bash agent-toolbox/start-api.sh --bg
	@echo "${GREEN}[SUCCESS]${NC} API started in background!"

# Stop background API
stop-bg:
	@echo "${BLUE}[STOP]${NC} Stopping background API..."
	@if [ -f api.pid ]; then kill $$(cat api.pid) && rm api.pid; echo "${GREEN}[SUCCESS]${NC} API stopped!"; else echo "${YELLOW}[WARN]${NC} No PID file found"; fi

# Show project info
info:
	@echo "${BLUE}Project Information:${NC}"
	@echo "  Name: $(PROJECT_NAME)"
	@echo "  Python: $(PYTHON_VERSION)"
	@echo "  Virtual Env: $(VENV)"
	@echo "  Source: $(SRC_DIRS)"
	@echo "  Tests: $(TEST_DIR)"

# Default target
.DEFAULT_GOAL := help

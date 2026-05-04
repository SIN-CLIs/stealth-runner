#!/bin/bash
# stealth-sync install script - Install as CLI tool
# OpenSIN/sincode - Stealth Suite Setup Automation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin*" ]]; then
    log_error "This install script is designed for macOS only."
    exit 1
fi

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is not installed. Please run scripts/setup.sh first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
log_info "Python version: $PYTHON_VERSION"

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

log_info "Project root: $PROJECT_ROOT"

# Check if pyproject.toml exists
if [[ ! -f "pyproject.toml" ]]; then
    log_error "pyproject.toml not found in project root"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d ".venv" ]]; then
    log_info "Creating virtual environment..."
    python3 -m venv .venv
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Install project in editable mode with dev dependencies
    log_info "Installing project dependencies..."
    pip install --upgrade pip
    pip install -e ".[dev]"
    
    # Deactivate virtual environment
    deactivate
else
    log_info "Virtual environment already exists"
fi

# Verify installation
log_info "Verifying installation..."
source .venv/bin/activate

if command -v stealth-sync &> /dev/null; then
    log_success "stealth-sync CLI installed successfully"
    stealth-sync --version
else
    log_error "stealth-sync CLI not found after installation"
    exit 1
fi

deactivate

log_success "Installation completed successfully!"
log_info "You can now use: stealth-sync"

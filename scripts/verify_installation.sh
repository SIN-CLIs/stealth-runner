#!/bin/bash
# stealth-sync verification script - Verify setup
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

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

log_info "Project root: $PROJECT_ROOT"

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
log_info "Python version: $PYTHON_VERSION"

# Check virtual environment
if [[ -d ".venv" ]]; then
    log_success "Virtual environment exists"
    VENV_SIZE=$(du -sh .venv 2>/dev/null | cut -f1 || echo "0")
    log_info "Virtual environment size: $VENV_SIZE"
else
    log_error "Virtual environment not found"
    exit 1
fi

# Check if pip is available in venv
if [[ -f ".venv/bin/pip" ]]; then
    log_success "pip available in virtual environment"
else
    log_error "pip not found in virtual environment"
    exit 1
fi

# Check project dependencies
if [[ -f "pyproject.toml" ]]; then
    log_success "pyproject.toml found"
else
    log_error "pyproject.toml not found"
    exit 1
fi

# Check CLI installation
source .venv/bin/activate

if command -v stealth-sync &> /dev/null; then
    log_success "stealth-sync CLI is installed"
    
    # Show version
    if stealth-sync --version &> /dev/null; then
        VERSION=$(stealth-sync --version)
        log_info "CLI version: $VERSION"
    fi
    
    # Show help
    if stealth-sync --help &> /dev/null; then
        log_info "CLI help available"
    fi
else
    log_error "stealth-sync CLI not found"
    exit 1
fi

deactivate

# Check for required directories
REQUIRED_DIRS=("src" "cli" "tests" "docs")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        log_success "Directory exists: $dir"
    else
        log_warning "Directory not found: $dir"
    fi
done

# Check for README
if [[ -f "README.md" ]]; then
    log_success "README.md found"
else
    log_warning "README.md not found"
fi

# Check for LICENSE
if [[ -f "LICENSE" ]]; then
    log_success "LICENSE found"
else
    log_warning "LICENSE not found"
fi

log_info ""
log_success "✓ Installation verification completed successfully!"
log_info "All critical components are properly installed and configured."

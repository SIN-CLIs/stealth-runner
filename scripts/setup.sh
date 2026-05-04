#!/bin/bash
# stealth-sync setup script - Automated dependency installation
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
    log_error "This setup script is designed for macOS only."
    exit 1
fi

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is not installed. Please install Python 3.12+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
log_info "Python version: $PYTHON_VERSION"

PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [[ "$PYTHON_MAJOR" -lt 3 || ("$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 12) ]]; then
    log_error "Python 3.12+ is required. Found: $PYTHON_VERSION"
    exit 1
fi

log_success "Python version check passed"

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    log_info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH
    if [[ -f /opt/homebrew/bin/brew ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# Update Homebrew
log_info "Updating Homebrew..."
brew update

# Install required system dependencies
log_info "Installing system dependencies..."
brew install -q git curl wget jq

# Install Python dependencies via pip
log_info "Installing Python dependencies..."
pip3 install --upgrade pip setuptools wheel

# Check if virtual environment tools are available
if ! python3 -m venv --help &> /dev/null; then
    log_info "Installing venv module..."
    python3 -m pip install --user virtualenv
fi

log_success "System dependencies installed successfully"
log_info "Setup completed successfully!"

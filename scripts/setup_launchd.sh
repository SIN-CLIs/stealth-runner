#!/bin/bash
# stealth-sync launchd setup script - Configure macOS launchd service
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
    log_error "This script is designed for macOS only."
    exit 1
fi

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

log_info "Project root: $PROJECT_ROOT"

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    log_error "Virtual environment not found. Please run scripts/install.sh first."
    exit 1
fi

# Get absolute path to virtual environment
VENV_PATH="$(cd ".venv" && pwd)"

# Create launchd plist file
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/com.opensin.stealth-sync.plist"

log_info "Creating launchd plist at: $LAUNCHD_PLIST"

cat > "$LAUNCHD_PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.opensin.stealth-sync</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PATH}/bin/python</string>
        <string>${PROJECT_ROOT}/cli/main.py</string>
        <string>monitor</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>ProcessType</key>
    <string>Interactive</string>
    
    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/logs/stealth-sync.log</string>
    
    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/logs/stealth-sync.err.log</string>
    
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${VENV_PATH}/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>PYTHONPATH</key>
        <string>${PROJECT_ROOT}</string>
    </dict>
    
    <key>StartInterval</key>
    <integer>60</integer>
</dict>
</plist>
PLIST_EOF

log_success "Launchd plist created successfully"

# Load the service
log_info "Loading launchd service..."
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || true

# Start the service
log_info "Starting launchd service..."
launchctl start com.opensin.stealth-sync 2>/dev/null || true

# Check service status
log_info "Checking service status..."
if launchctl list | grep -q "com.opensin.stealth-sync"; then
    log_success "Service loaded and running"
else
    log_warning "Service may not be running. Try: launchctl load $LAUNCHD_PLIST"
fi

log_info ""
log_info "To unload the service later, run:"
log_info "  launchctl unload $LAUNCHD_PLIST"
log_info ""
log_success "Launchd setup completed!"

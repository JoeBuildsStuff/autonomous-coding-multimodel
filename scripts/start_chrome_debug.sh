#!/bin/bash
#
# Start Chrome with Remote Debugging
# ==================================
#
# This script starts Chrome with remote debugging enabled, which allows
# the puppeteer-mcp-server to connect to an existing browser instance
# using the puppeteer_connect_active_tab tool.
#
# Usage:
#   ./scripts/start_chrome_debug.sh
#   ./scripts/start_chrome_debug.sh 9223  # Custom port
#
# Requirements:
#   - Google Chrome installed
#   - No existing Chrome instance (or it must be completely closed)
#

set -e

# Configuration
DEBUG_PORT="${1:-9222}"

# Detect Chrome path based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if [ ! -f "$CHROME_PATH" ]; then
        # Try Chrome Canary
        CHROME_PATH="/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CHROME_PATH=$(which google-chrome || which google-chrome-stable || which chromium-browser || echo "")
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash)
    CHROME_PATH="/c/Program Files/Google/Chrome/Application/chrome.exe"
    if [ ! -f "$CHROME_PATH" ]; then
        CHROME_PATH="/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    fi
fi

# Check if Chrome was found
if [ -z "$CHROME_PATH" ] || [ ! -f "$CHROME_PATH" ]; then
    echo "Error: Google Chrome not found"
    echo ""
    echo "Please install Chrome or set CHROME_PATH environment variable:"
    echo "  export CHROME_PATH=/path/to/chrome"
    echo ""
    echo "Common locations:"
    echo "  macOS:   /Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    echo "  Linux:   /usr/bin/google-chrome"
    echo "  Windows: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    exit 1
fi

# Check if port is already in use
if lsof -i :$DEBUG_PORT > /dev/null 2>&1; then
    echo "Warning: Port $DEBUG_PORT is already in use"
    echo ""
    echo "This could mean:"
    echo "  1. Chrome is already running with debugging enabled"
    echo "  2. Another process is using the port"
    echo ""
    echo "To use an existing Chrome instance, just run the agent with --enable-browser"
    echo "To use a different port, specify it: ./start_chrome_debug.sh 9223"
    echo ""
    read -p "Do you want to continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Starting Chrome with remote debugging on port $DEBUG_PORT..."
echo ""
echo "Chrome path: $CHROME_PATH"
echo "Debug port:  $DEBUG_PORT"
echo ""

# Create a temporary user data directory for clean debugging session
TEMP_PROFILE="/tmp/chrome-debug-profile-$$"
mkdir -p "$TEMP_PROFILE"

echo "User profile: $TEMP_PROFILE (temporary)"
echo ""
echo "Chrome will open. You can:"
echo "  - Browse normally - all tabs are accessible via debugging"
echo "  - Navigate to localhost:3000 to test your app"
echo "  - Use puppeteer_connect_active_tab to connect from the agent"
echo ""
echo "Press Ctrl+C to stop Chrome and exit"
echo ""

# Start Chrome with debugging
"$CHROME_PATH" \
    --remote-debugging-port="$DEBUG_PORT" \
    --user-data-dir="$TEMP_PROFILE" \
    --no-first-run \
    --no-default-browser-check \
    --disable-default-apps \
    2>&1

# Cleanup
rm -rf "$TEMP_PROFILE" 2>/dev/null || true

echo ""
echo "Chrome closed."

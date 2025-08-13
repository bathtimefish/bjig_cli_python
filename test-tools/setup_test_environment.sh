#!/bin/bash
#
# BraveJIG Router Test Environment Setup Script
#
# This script sets up a test environment using socat to enable simultaneous
# monitoring and CLI testing of the BraveJIG router communication.
#
# Usage:
#   ./setup_test_environment.sh [DEVICE] [BAUDRATE]
#
# Example:
#   ./setup_test_environment.sh /dev/ttyACM0 38400
#

set -e

# Default values
DEFAULT_DEVICE="/dev/ttyACM0"
DEFAULT_BAUDRATE="38400"

# Parse arguments
DEVICE=${1:-$DEFAULT_DEVICE}
BAUDRATE=${2:-$DEFAULT_BAUDRATE}

# Virtual device paths
PTY_MONITOR="/tmp/bjig_monitor"
PTY_CLI="/tmp/bjig_cli"

echo "=== BraveJIG Router Test Environment Setup ==="
echo "Physical Device: $DEVICE"
echo "Baudrate: $BAUDRATE"
echo "Monitor PTY: $PTY_MONITOR"
echo "CLI PTY: $PTY_CLI"
echo

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo "Error: Device $DEVICE not found"
    exit 1
fi

# Check if socat is installed
if ! command -v socat &> /dev/null; then
    echo "Error: socat is not installed"
    echo "Please install socat: brew install socat (macOS) or apt-get install socat (Linux)"
    exit 1
fi

# Kill any existing socat processes for these PTYs
echo "Cleaning up existing socat processes..."
pkill -f "socat.*$PTY_MONITOR" || true
pkill -f "socat.*$PTY_CLI" || true

# Remove existing PTY files
rm -f "$PTY_MONITOR" "$PTY_CLI"

echo "Starting socat multiplexer..."

# Create virtual devices that both connect to the physical device
# Note: This creates two separate connections - not true multiplexing
# For true multiplexing, we'll use a different approach

# Create monitor PTY (read-only connection for monitoring)
socat -d -d pty,link="$PTY_MONITOR",raw,echo=0 "$DEVICE,b$BAUDRATE,raw,echo=0" &
SOCAT_MONITOR_PID=$!

sleep 2

# Create CLI PTY (read-write connection for commands)
socat -d -d pty,link="$PTY_CLI",raw,echo=0 "$DEVICE,b$BAUDRATE,raw,echo=0" &
SOCAT_CLI_PID=$!

# Wait for PTY creation
echo "Waiting for PTY creation..."
for i in {1..10}; do
    if [ -e "$PTY_MONITOR" ] && [ -e "$PTY_CLI" ]; then
        break
    fi
    sleep 0.5
done

if [ ! -e "$PTY_MONITOR" ] || [ ! -e "$PTY_CLI" ]; then
    echo "Error: Failed to create PTY devices"
    kill $SOCAT_MONITOR_PID 2>/dev/null || true
    kill $SOCAT_CLI_PID 2>/dev/null || true
    exit 1
fi

# Set permissions
chmod 666 "$PTY_MONITOR" "$PTY_CLI"

echo "✅ Test environment setup complete!"
echo
echo "Virtual Devices Created:"
echo "  Monitor PTY: $PTY_MONITOR (for observing traffic)"
echo "  CLI PTY: $PTY_CLI (for running CLI commands)"
echo
echo "Usage:"
echo "  # Terminal 1 - Monitor traffic:"
echo "  python3 test_environment/serial_monitor.py $PTY_MONITOR"
echo
echo "  # Terminal 2 - Run CLI commands:"
echo "  python3 src/main.py --port $PTY_CLI --baud $BAUDRATE router get-version"
echo
echo "Process IDs: Monitor=$SOCAT_MONITOR_PID, CLI=$SOCAT_CLI_PID"
echo "To stop: kill $SOCAT_MONITOR_PID $SOCAT_CLI_PID"
echo

# Save PIDs for cleanup
echo "$SOCAT_MONITOR_PID $SOCAT_CLI_PID" > /tmp/bjig_socat.pid

echo "Environment is ready. Press Ctrl+C to stop."

# Wait for both processes
wait $SOCAT_MONITOR_PID
wait $SOCAT_CLI_PID
#!/bin/bash
#
# Simple BraveJIG Test Setup
#
# Since USB serial devices don't support multiple simultaneous connections,
# this script provides a simpler testing approach where we use the device
# directly for CLI commands and optionally capture traffic to a log file.
#

set -e

# Default values
DEFAULT_DEVICE="/dev/tty.usbmodem0000000000002"
DEFAULT_BAUDRATE="38400"

# Parse arguments
DEVICE=${1:-$DEFAULT_DEVICE}
BAUDRATE=${2:-$DEFAULT_BAUDRATE}

echo "=== Simple BraveJIG Test Setup ==="
echo "Physical Device: $DEVICE"
echo "Baudrate: $BAUDRATE"
echo

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo "Error: Device $DEVICE not found"
    exit 1
fi

# Test device accessibility
if ! python3 -c "import serial; s=serial.Serial('$DEVICE',$BAUDRATE,timeout=1); s.close()" 2>/dev/null; then
    echo "Warning: Cannot access device $DEVICE"
    echo "This might be due to permissions or the device being in use"
    echo "Try: sudo chmod 666 $DEVICE"
fi

echo "✅ Device verification complete!"
echo
echo "Usage:"
echo "  # Run CLI commands directly:"
echo "  python3 src/main.py --port $DEVICE --baud $BAUDRATE router get-version"
echo
echo "  # Run automated tests:"
echo "  python3 tests/test_runner.py router_basic --device $DEVICE --baudrate $BAUDRATE"
echo
echo "  # Monitor and log traffic (in background):"
echo "  python3 tests/simple_monitor.py $DEVICE $BAUDRATE > router_traffic.log 2>&1 &"
echo "  # Then run your CLI commands"
echo "  # Stop monitoring: pkill -f simple_monitor"
echo
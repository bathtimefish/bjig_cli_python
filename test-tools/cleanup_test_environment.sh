#!/bin/bash
#
# BraveJIG Router Test Environment Cleanup Script
#
# This script cleans up the test environment by stopping socat processes
# and removing virtual device files.
#

echo "=== BraveJIG Test Environment Cleanup ==="

# Stop socat processes if running
if [ -f /tmp/bjig_socat.pid ]; then
    PIDS=$(cat /tmp/bjig_socat.pid)
    echo "Stopping socat processes (PIDs: $PIDS)..."
    for PID in $PIDS; do
        kill $PID 2>/dev/null || true
    done
    rm -f /tmp/bjig_socat.pid
else
    echo "Stopping any socat processes for BraveJIG..."
    pkill -f "socat.*bjig_monitor" || true
    pkill -f "socat.*bjig_cli" || true
fi

# Remove virtual device files
echo "Removing virtual device files..."
rm -f /tmp/bjig_monitor /tmp/bjig_cli

echo "✅ Cleanup complete!"
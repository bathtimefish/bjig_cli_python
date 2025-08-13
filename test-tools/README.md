# BraveJIG CLI Test Environment

This directory contains tools for testing the BraveJIG CLI implementation with real hardware using socat for traffic monitoring.

## Overview

The test environment creates virtual serial devices that allow simultaneous monitoring and CLI operation on the same physical BraveJIG router connection.

```
Physical Router (/dev/ttyACM0)
            |
            | (socat multiplexer)
            |
    +-------+-------+
    |               |
Monitor PTY     CLI PTY
(/tmp/bjig_monitor) (/tmp/bjig_cli)
    |               |
serial_monitor.py  main.py commands
```

## Quick Start

### 1. Setup Environment

```bash
# Make scripts executable
chmod +x tests/setup_test_environment.sh
chmod +x tests/cleanup_test_environment.sh

# Start test environment (replace /dev/ttyACM0 with your router device)
./tests/setup_test_environment.sh /dev/ttyACM0 38400
```

### 2. Monitor Traffic (Terminal 1)

```bash
# Start real-time protocol monitor
python3 tests/serial_monitor.py /tmp/bjig_monitor
```

### 3. Run CLI Commands (Terminal 2)

```bash
# Test basic router commands
python3 src/main.py --port /tmp/bjig_cli --baud 38400 router get-version
python3 src/main.py --port /tmp/bjig_cli --baud 38400 router get-device-id

# Test illuminance sensor commands
python3 src/main.py --port /tmp/bjig_cli --baud 38400 module instant-uplink --module-id "001122334455667788"
python3 src/main.py --port /tmp/bjig_cli --baud 38400 module get-parameter --module-id "001122334455667788"
```

### 4. Automated Testing (Terminal 3)

```bash
# Run automated test suites
python3 tests/test_runner.py router_basic
python3 tests/test_runner.py illuminance_basic --module-id "001122334455667788"
python3 tests/test_runner.py all
```

### 5. Cleanup

```bash
# Stop test environment
./tests/cleanup_test_environment.sh
```

## Files Description

### `setup_test_environment.sh`
- Creates socat multiplexer for serial port sharing
- Establishes virtual devices `/tmp/bjig_monitor` and `/tmp/bjig_cli`
- Handles cleanup of existing processes

### `serial_monitor.py`
- Real-time BraveJIG protocol traffic analyzer
- Decodes JIG Info commands, Downlink requests, Uplink notifications
- Color-coded output with packet timing and statistics
- Specialized illuminance sensor data parsing

### `test_runner.py`
- Automated test suite runner
- Predefined test sequences for router and sensor commands
- Result tracking and summary reporting
- Timeout and error handling

### `cleanup_test_environment.sh`
- Stops all socat processes
- Removes virtual device files
- Clean shutdown of test environment

## Test Types

### Router Tests
- **router_basic**: get-version, get-device-id, get-scan-mode, keep-alive
- **router_advanced**: start/stop, scan mode changes, indexed device queries

### Illuminance Sensor Tests
- **illuminance_basic**: instant-uplink, get-parameter
- **illuminance_advanced**: set-parameter, verification, restart

### Monitoring Tests
- **monitor**: Start CLI monitor mode for specified duration
- **single**: Run individual command with monitoring

## Example Usage Scenarios

### Debugging Protocol Issues
```bash
# Terminal 1: Start monitor first
python3 tests/serial_monitor.py /tmp/bjig_monitor

# Terminal 2: Run failing command
python3 src/main.py --port /tmp/bjig_cli --baud 38400 module get-parameter --module-id "001122334455667788"

# Observe detailed protocol traffic in Terminal 1
```

### Parameter Testing
```bash
# Test parameter changes with monitoring
python3 tests/test_runner.py illuminance_advanced --module-id "YOUR_MODULE_ID"
```

### Continuous Integration Testing
```bash
# Run all tests and capture results
python3 tests/test_runner.py all --module-id "TEST_MODULE_ID" > test_results.log 2>&1
```

## Troubleshooting

### Device Not Found
```bash
# Check available serial devices
ls -la /dev/tty*

# Check USB device detection (macOS)
system_profiler SPUSBDataType | grep -A5 -B5 "Serial"
```

### Permission Issues
```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER

# Set device permissions (macOS/Linux)
sudo chmod 666 /dev/ttyACM0
```

### Socat Process Issues
```bash
# Check running socat processes
ps aux | grep socat

# Force cleanup
pkill -f socat
rm -f /tmp/bjig_*
```

### Monitor Not Showing Traffic
- Ensure setup script completed successfully
- Check that both monitor and CLI are using correct virtual devices
- Verify physical router is connected and responding

## Advanced Configuration

### Custom Baudrates
```bash
./setup_test_environment.sh /dev/ttyUSB0 115200
```

### Extended Monitoring
```bash
# Monitor with packet logging
python3 tests/serial_monitor.py /tmp/bjig_monitor 2>&1 | tee protocol.log
```

### Custom Test Sequences
Modify `test_runner.py` to add custom test sequences for your specific testing needs.

## Protocol Analysis Features

The serial monitor provides detailed analysis of:

- **JIG Info Commands**: Command identification, response codes, timing
- **Downlink Requests**: Device targeting, sensor commands, parameter data
- **Uplink Notifications**: Sensor data parsing, timestamp analysis
- **Error Notifications**: Error code interpretation, failure analysis
- **Illuminance Data**: Battery level, sampling rate, lux measurements

This comprehensive monitoring enables debugging of protocol implementation issues and verification of correct command execution.

# AsyncSerialMonitor

Event-driven asynchronous serial communication monitor specifically designed for IoT device testing, with particular focus on BraveJIG Router communication.

## Features

- **Asynchronous Data Reception**: Non-blocking continuous monitoring of serial data
- **Event-Driven Architecture**: Callback-based data handling for easy integration
- **Thread-Safe Command Transmission**: Send commands while monitoring
- **Robust Error Handling**: Comprehensive exception handling and recovery
- **BraveJIG Protocol Support**: Built-in support for BraveJIG communication protocols
- **Simple API**: Easy to use interface requiring minimal serial communication knowledge

## Quick Start

### Basic Usage

```python
from scripts import AsyncSerialMonitor

def on_data_received(data: bytes):
    print(f"Received: {data.hex()}")

def on_error(error: Exception):
    print(f"Error: {error}")

# Create and use monitor
with AsyncSerialMonitor('/dev/ttyACM0', 38400) as monitor:
    monitor.set_data_callback(on_data_received)
    monitor.set_error_callback(on_error)
    
    monitor.start_monitoring()
    
    # Send a command
    monitor.send(b'\x01\x02\x03\x04')
    
    # Keep monitoring
    input("Press Enter to stop...")
```

### BraveJIG Router Testing

```python
from scripts import AsyncSerialMonitor
import struct
import time

def on_data_received(data: bytes):
    print(f"BraveJIG data: {data.hex(' ').upper()}")

# BraveJIG Router default settings
with AsyncSerialMonitor('/dev/tty.usbmodem0000000000002', 38400) as monitor:
    monitor.set_data_callback(on_data_received)
    monitor.start_monitoring()
    
    # Send JIG INFO request (FW version)
    packet = struct.pack('<BBB', 0x01, 0x01, 0x02)  # Protocol, Type, CMD
    packet += struct.pack('<L', int(time.time()) + 9*3600)  # Local time (JST)
    packet += struct.pack('<L', int(time.time()))  # Unix time
    
    monitor.send(packet)
    
    time.sleep(5)  # Monitor for 5 seconds
```

## Installation

### Dependencies

```bash
pip install pyserial
```

### Python Requirements

- Python 3.7+
- pyserial
- threading (built-in)
- queue (built-in)
- logging (built-in)

## API Reference

### AsyncSerialMonitor

Main class for serial communication monitoring.

#### Constructor

```python
AsyncSerialMonitor(
    port: str = '/dev/ttyACM0',
    baudrate: int = 38400,
    timeout: float = 10.0,
    bytesize: int = 8,
    parity: str = 'N',
    stopbits: int = 1,
    logger: Optional[logging.Logger] = None
)
```

#### Methods

- `connect() -> bool`: Establish serial connection
- `disconnect() -> None`: Close serial connection
- `start_monitoring() -> None`: Start asynchronous data monitoring
- `stop_monitoring() -> None`: Stop data monitoring
- `send(data: bytes) -> bool`: Send data (thread-safe)
- `set_data_callback(callback)`: Set data reception callback
- `set_error_callback(callback)`: Set error handling callback
- `set_connection_callback(callback)`: Set connection state callback

#### Properties

- `is_connected: bool`: Connection status
- `is_monitoring: bool`: Monitoring status
- `statistics: dict`: Communication statistics

#### Context Manager

```python
with AsyncSerialMonitor(port, baudrate) as monitor:
    # Automatic connection and cleanup
    monitor.start_monitoring()
    # ... your code ...
# Automatic disconnect and resource cleanup
```

### Exceptions

- `AsyncSerialMonitorError`: Base exception
- `SerialConnectionError`: Connection related errors
- `SerialTimeoutError`: Timeout errors
- `SerialWriteError`: Write operation errors
- `MonitorNotStartedError`: Monitor not started
- `MonitorAlreadyStartedError`: Monitor already running

## Examples

See the `examples/` directory for complete usage examples:

- `basic_usage.py`: Basic serial communication example
- `brave_jig_test.py`: BraveJIG Router specific testing

## Testing

Run unit tests:

```bash
cd scripts/tests
python test_async_serial_monitor.py
```

## Architecture

```
External Program
    ↕ (Event Callbacks / Command Calls)
AsyncSerialMonitor
    ├── Monitor Thread (Data Reception)
    ├── Send Thread (Command Transmission)
    ├── Callback Thread Pool (Event Handling)
    └── pyserial (Hardware Interface)
         ↕
    Serial Device (BraveJIG Router)
```

### Key Design Features

1. **Thread Safety**: All operations are thread-safe
2. **Non-Blocking**: Data reception doesn't block command transmission
3. **Event-Driven**: Callbacks execute in separate thread pool
4. **Resource Management**: Automatic cleanup with context manager
5. **Error Recovery**: Robust error handling with callbacks

## BraveJIG Protocol Support

The monitor includes built-in support for BraveJIG communication protocols:

- Uplink notifications parsing
- Downlink request/response handling
- JIG INFO command support
- Error notification handling
- Little-endian data handling

## Configuration for BraveJIG Router

Default settings optimized for BraveJIG Router:

- Port: `/dev/tty.usbmodem0000000000002`
- Baudrate: `38400`
- Timeout: `10 seconds`
- Data bits: `8`
- Parity: `None`
- Stop bits: `1`

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure user has access to serial port
   ```bash
   sudo usermod -a -G dialout $USER
   # Then logout and login again
   ```

2. **Port Not Found**: Check available ports
   ```python
   ports = AsyncSerialMonitor.list_serial_ports()
   print(ports)
   ```

3. **Connection Timeout**: Verify device is connected and responsive

### Debug Logging

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

monitor = AsyncSerialMonitor(port, baudrate)
```

## License

This module is part of the BraveJIG test scripts project and is intended for development and testing purposes.

## Contributing

When contributing to this module:

1. Follow PEP 8 style guidelines
2. Add unit tests for new features
3. Update documentation
4. Test with actual BraveJIG hardware when possible
"""
AsyncSerialMonitor Package

Event-driven asynchronous serial communication monitoring for IoT devices.
Specifically designed for BraveJIG Router testing and communication.

Main Components:
- AsyncSerialMonitor: Main class for serial communication
- exceptions: Custom exception classes
- examples: Usage examples and demonstrations
- tests: Unit tests and integration tests

Author: Claude Code Assistant
Date: 2025-07-13
"""

from .async_serial_monitor import AsyncSerialMonitor
from .exceptions import (
    AsyncSerialMonitorError,
    SerialConnectionError,
    SerialTimeoutError,
    SerialWriteError,
    MonitorNotStartedError,
    MonitorAlreadyStartedError
)

__version__ = "1.0.0"
__author__ = "Claude Code Assistant"

__all__ = [
    'AsyncSerialMonitor',
    'AsyncSerialMonitorError',
    'SerialConnectionError',
    'SerialTimeoutError',
    'SerialWriteError',
    'MonitorNotStartedError',
    'MonitorAlreadyStartedError'
]
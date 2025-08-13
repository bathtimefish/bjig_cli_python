"""
Custom exceptions for AsyncSerialMonitor

Author: Claude Code Assistant
Date: 2025-07-23
"""


class AsyncSerialMonitorError(Exception):
    """Base exception for AsyncSerialMonitor errors"""
    pass


class SerialConnectionError(AsyncSerialMonitorError):
    """Exception raised when serial connection fails"""
    pass


class SerialTimeoutError(AsyncSerialMonitorError):
    """Exception raised when serial operation times out"""
    pass


class SerialWriteError(AsyncSerialMonitorError):
    """Exception raised when serial write operation fails"""
    pass


class MonitorNotStartedError(AsyncSerialMonitorError):
    """Exception raised when trying to use monitor before starting it"""
    pass


class MonitorAlreadyStartedError(AsyncSerialMonitorError):
    """Exception raised when trying to start monitor that's already started"""
    pass

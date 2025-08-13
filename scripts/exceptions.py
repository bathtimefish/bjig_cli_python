"""
Custom exceptions for AsyncSerialMonitor
"""


class AsyncSerialMonitorError(Exception):
    """Base exception for AsyncSerialMonitor"""
    pass


class SerialConnectionError(AsyncSerialMonitorError):
    """Raised when serial connection fails"""
    pass


class SerialTimeoutError(AsyncSerialMonitorError):
    """Raised when serial operation times out"""
    pass


class SerialWriteError(AsyncSerialMonitorError):
    """Raised when writing to serial port fails"""
    pass


class MonitorNotStartedError(AsyncSerialMonitorError):
    """Raised when trying to use monitor before starting"""
    pass


class MonitorAlreadyStartedError(AsyncSerialMonitorError):
    """Raised when trying to start monitor that's already running"""
    pass
"""
AsyncSerialMonitor - Event-driven asynchronous serial communication monitor

Features:
- Asynchronous data reception with event callbacks
- Command transmission capability
- Robust error handling and automatic reconnection
- Simple API for easy integration

Author: Claude Code Assistant
Date: 2025-07-13
"""

import asyncio
import logging
import threading
import time
from typing import Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import serial
import serial.tools.list_ports
from queue import Queue, Empty

try:
    from .exceptions import (
        AsyncSerialMonitorError,
        SerialConnectionError,
        SerialTimeoutError,
        SerialWriteError,
        MonitorNotStartedError,
        MonitorAlreadyStartedError
    )
except ImportError:
    from exceptions import (
        AsyncSerialMonitorError,
        SerialConnectionError,
        SerialTimeoutError,
        SerialWriteError,
        MonitorNotStartedError,
        MonitorAlreadyStartedError
    )


class AsyncSerialMonitor:
    """
    Event-driven asynchronous serial communication monitor
    
    This class provides a high-level interface for asynchronous serial communication
    with event-driven data reception and simple command transmission capabilities.
    """
    
    # Default configuration for BraveJIG Router
    DEFAULT_PORT = '/dev/cu.usbmodem0000000000002'
    DEFAULT_BAUDRATE = 38400
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_BYTESIZE = 8
    DEFAULT_PARITY = 'N'
    DEFAULT_STOPBITS = 1
    
    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        bytesize: int = DEFAULT_BYTESIZE,
        parity: str = DEFAULT_PARITY,
        stopbits: int = DEFAULT_STOPBITS,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize AsyncSerialMonitor
        
        Args:
            port: Serial port path (default: /dev/ttyACM0)
            baudrate: Communication speed (default: 38400)
            timeout: Read timeout in seconds (default: 10.0)
            bytesize: Number of data bits (default: 8)
            parity: Parity checking ('N', 'E', 'O') (default: 'N')
            stopbits: Number of stop bits (default: 1)
            logger: Custom logger instance
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        
        # Setup logging
        self.logger = logger or self._setup_default_logger()
        
        # Serial connection
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
        
        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Thread pool for callback execution
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="SerialCallback")
        
        # Callback functions
        self._data_callback: Optional[Callable[[bytes], None]] = None
        self._error_callback: Optional[Callable[[Exception], None]] = None
        self._connection_callback: Optional[Callable[[bool], None]] = None
        
        # Send queue for thread-safe transmission
        self._send_queue: Queue = Queue()
        self._send_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._bytes_received = 0
        self._bytes_sent = 0
        self._connection_attempts = 0
        
        self.logger.info(f"AsyncSerialMonitor initialized for {port} at {baudrate} baud")

    def _setup_default_logger(self) -> logging.Logger:
        """Setup default logger for the module"""
        logger = logging.getLogger('AsyncSerialMonitor')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def set_data_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Set callback function for received data
        
        Args:
            callback: Function to call when data is received (data: bytes) -> None
        """
        self._data_callback = callback
        self.logger.debug("Data callback set")

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """
        Set callback function for errors
        
        Args:
            callback: Function to call when error occurs (error: Exception) -> None
        """
        self._error_callback = callback
        self.logger.debug("Error callback set")

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """
        Set callback function for connection state changes
        
        Args:
            callback: Function to call when connection state changes (connected: bool) -> None
        """
        self._connection_callback = callback
        self.logger.debug("Connection callback set")

    def connect(self) -> bool:
        """
        Establish serial connection
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            SerialConnectionError: If connection fails
        """
        if self._is_connected:
            self.logger.warning("Already connected")
            return True
            
        try:
            self._connection_attempts += 1
            self.logger.info(f"Attempting to connect to {self.port} (attempt #{self._connection_attempts})")
            
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                write_timeout=self.timeout
            )
            
            # Test connection by checking if port is open
            if self._serial.is_open:
                self._is_connected = True
                self.logger.info(f"Successfully connected to {self.port}")
                
                # Notify connection callback
                if self._connection_callback:
                    self._executor.submit(self._connection_callback, True)
                    
                return True
            else:
                raise SerialConnectionError(f"Failed to open port {self.port}")
                
        except serial.SerialException as e:
            error_msg = f"Serial connection error: {e}"
            self.logger.error(error_msg)
            self._handle_error(SerialConnectionError(error_msg))
            return False
        except Exception as e:
            error_msg = f"Unexpected connection error: {e}"
            self.logger.error(error_msg)
            self._handle_error(SerialConnectionError(error_msg))
            return False

    def disconnect(self) -> None:
        """Disconnect from serial port"""
        if not self._is_connected:
            self.logger.debug("Already disconnected")
            return
            
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
                
            self._is_connected = False
            self.logger.info(f"Disconnected from {self.port}")
            
            # Notify connection callback
            if self._connection_callback:
                self._executor.submit(self._connection_callback, False)
                
        except Exception as e:
            error_msg = f"Error during disconnection: {e}"
            self.logger.error(error_msg)
            self._handle_error(AsyncSerialMonitorError(error_msg))

    def start_monitoring(self) -> None:
        """
        Start monitoring for incoming data
        
        Raises:
            MonitorAlreadyStartedError: If monitoring is already started
            MonitorNotStartedError: If not connected
        """
        if self._is_monitoring:
            raise MonitorAlreadyStartedError("Monitoring is already started")
            
        if not self._is_connected:
            raise MonitorNotStartedError("Must be connected before starting monitoring")
            
        self._is_monitoring = True
        self._stop_event.clear()
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="SerialMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        # Start send thread
        self._send_thread = threading.Thread(
            target=self._send_loop,
            name="SerialSender",
            daemon=True
        )
        self._send_thread.start()
        
        self.logger.info("Started monitoring")

    def stop_monitoring(self) -> None:
        """Stop monitoring for incoming data"""
        if not self._is_monitoring:
            self.logger.debug("Monitoring not started")
            return
            
        self._is_monitoring = False
        self._stop_event.set()
        
        # Wait for threads to finish
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
            
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=2.0)
            
        self.logger.info("Stopped monitoring")

    def send(self, data: bytes) -> bool:
        """
        Send data to serial port (thread-safe)
        
        Args:
            data: Binary data to send
            
        Returns:
            True if data was queued for sending, False otherwise
            
        Raises:
            MonitorNotStartedError: If monitoring is not started
        """
        if not self._is_monitoring:
            raise MonitorNotStartedError("Must start monitoring before sending data")
            
        try:
            self._send_queue.put(data, timeout=1.0)
            self.logger.debug(f"Queued {len(data)} bytes for sending")
            return True
        except Exception as e:
            error_msg = f"Failed to queue data for sending: {e}"
            self.logger.error(error_msg)
            self._handle_error(SerialWriteError(error_msg))
            return False

    def _monitor_loop(self) -> None:
        """Main monitoring loop (runs in separate thread)"""
        self.logger.debug("Monitor loop started")
        
        while not self._stop_event.is_set() and self._is_monitoring:
            try:
                if not self._is_connected or not self._serial or not self._serial.is_open:
                    self.logger.warning("Connection lost during monitoring")
                    break
                    
                # Check if data is available
                if self._serial.in_waiting > 0:
                    data = self._serial.read(self._serial.in_waiting)
                    if data:
                        self._bytes_received += len(data)
                        self.logger.debug(f"Received {len(data)} bytes")
                        
                        # Call data callback in thread pool
                        if self._data_callback:
                            self._executor.submit(self._data_callback, data)
                            
                else:
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.01)
                    
            except serial.SerialException as e:
                error_msg = f"Serial read error: {e}"
                self.logger.error(error_msg)
                self._handle_error(SerialConnectionError(error_msg))
                break
            except Exception as e:
                error_msg = f"Unexpected error in monitor loop: {e}"
                self.logger.error(error_msg)
                self._handle_error(AsyncSerialMonitorError(error_msg))
                break
                
        self.logger.debug("Monitor loop ended")

    def _send_loop(self) -> None:
        """Send loop (runs in separate thread)"""
        self.logger.debug("Send loop started")
        
        while not self._stop_event.is_set() and self._is_monitoring:
            try:
                # Get data from queue with timeout
                data = self._send_queue.get(timeout=0.1)
                
                if not self._is_connected or not self._serial or not self._serial.is_open:
                    self.logger.warning("Connection lost during sending")
                    break
                    
                # Send data
                bytes_written = self._serial.write(data)
                self._serial.flush()  # Ensure data is sent immediately
                
                self._bytes_sent += bytes_written
                self.logger.debug(f"Sent {bytes_written} bytes")
                
            except Empty:
                # Timeout - continue loop
                continue
            except serial.SerialTimeoutException as e:
                error_msg = f"Serial write timeout: {e}"
                self.logger.error(error_msg)
                self._handle_error(SerialTimeoutError(error_msg))
            except serial.SerialException as e:
                error_msg = f"Serial write error: {e}"
                self.logger.error(error_msg)
                self._handle_error(SerialWriteError(error_msg))
            except Exception as e:
                error_msg = f"Unexpected error in send loop: {e}"
                self.logger.error(error_msg)
                self._handle_error(AsyncSerialMonitorError(error_msg))
                
        self.logger.debug("Send loop ended")

    def _handle_error(self, error: Exception) -> None:
        """Handle errors by calling error callback"""
        if self._error_callback:
            self._executor.submit(self._error_callback, error)

    @property
    def is_connected(self) -> bool:
        """Check if connected to serial port"""
        return self._is_connected and self._serial and self._serial.is_open

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        return self._is_monitoring

    @property
    def statistics(self) -> dict:
        """Get communication statistics"""
        return {
            'bytes_received': self._bytes_received,
            'bytes_sent': self._bytes_sent,
            'connection_attempts': self._connection_attempts,
            'is_connected': self.is_connected,
            'is_monitoring': self.is_monitoring
        }

    def __enter__(self):
        """Context manager entry"""
        if not self.connect():
            raise SerialConnectionError(f"Failed to connect to {self.port}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_monitoring()
        self.disconnect()
        self._executor.shutdown(wait=True)

    @staticmethod
    def list_serial_ports() -> list:
        """List available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        monitoring = "monitoring" if self.is_monitoring else "idle"
        return f"AsyncSerialMonitor({self.port}@{self.baudrate}, {status}, {monitoring})"
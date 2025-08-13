"""
Unit tests for AsyncSerialMonitor

This module provides comprehensive unit tests for the AsyncSerialMonitor class,
including mock serial communication for testing without actual hardware.
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from async_serial_monitor import AsyncSerialMonitor
from exceptions import (
    AsyncSerialMonitorError,
    SerialConnectionError,
    MonitorNotStartedError,
    MonitorAlreadyStartedError
)


class TestAsyncSerialMonitor(unittest.TestCase):
    """Test cases for AsyncSerialMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_port = '/dev/ttyTEST'
        self.test_baudrate = 9600
        self.test_timeout = 1.0
        
        # Mock logger to avoid log output during tests
        self.mock_logger = Mock()
        
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_initialization(self):
        """Test AsyncSerialMonitor initialization"""
        monitor = AsyncSerialMonitor(
            port=self.test_port,
            baudrate=self.test_baudrate,
            timeout=self.test_timeout,
            logger=self.mock_logger
        )
        
        self.assertEqual(monitor.port, self.test_port)
        self.assertEqual(monitor.baudrate, self.test_baudrate)
        self.assertEqual(monitor.timeout, self.test_timeout)
        self.assertFalse(monitor.is_connected)
        self.assertFalse(monitor.is_monitoring)
    
    def test_default_initialization(self):
        """Test AsyncSerialMonitor with default parameters"""
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        self.assertEqual(monitor.port, AsyncSerialMonitor.DEFAULT_PORT)
        self.assertEqual(monitor.baudrate, AsyncSerialMonitor.DEFAULT_BAUDRATE)
        self.assertEqual(monitor.timeout, AsyncSerialMonitor.DEFAULT_TIMEOUT)
    
    def test_callback_setters(self):
        """Test callback function setters"""
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        data_callback = Mock()
        error_callback = Mock()
        connection_callback = Mock()
        
        monitor.set_data_callback(data_callback)
        monitor.set_error_callback(error_callback)
        monitor.set_connection_callback(connection_callback)
        
        self.assertEqual(monitor._data_callback, data_callback)
        self.assertEqual(monitor._error_callback, error_callback)
        self.assertEqual(monitor._connection_callback, connection_callback)
    
    @patch('serial.Serial')
    def test_successful_connection(self, mock_serial_class):
        """Test successful serial connection"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(
            port=self.test_port,
            baudrate=self.test_baudrate,
            logger=self.mock_logger
        )
        
        # Test connection
        result = monitor.connect()
        
        self.assertTrue(result)
        self.assertTrue(monitor.is_connected)
        mock_serial_class.assert_called_once_with(
            port=self.test_port,
            baudrate=self.test_baudrate,
            timeout=monitor.timeout,
            bytesize=monitor.bytesize,
            parity=monitor.parity,
            stopbits=monitor.stopbits,
            write_timeout=monitor.timeout
        )
    
    @patch('serial.Serial')
    def test_connection_failure(self, mock_serial_class):
        """Test connection failure handling"""
        # Setup mock to raise exception
        mock_serial_class.side_effect = Exception("Connection failed")
        
        monitor = AsyncSerialMonitor(
            port=self.test_port,
            baudrate=self.test_baudrate,
            logger=self.mock_logger
        )
        
        # Test connection failure
        result = monitor.connect()
        
        self.assertFalse(result)
        self.assertFalse(monitor.is_connected)
    
    @patch('serial.Serial')
    def test_disconnect(self, mock_serial_class):
        """Test disconnection"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        # Connect first
        monitor.connect()
        self.assertTrue(monitor.is_connected)
        
        # Test disconnect
        monitor.disconnect()
        
        self.assertFalse(monitor.is_connected)
        mock_serial.close.assert_called_once()
    
    @patch('serial.Serial')
    def test_start_monitoring_without_connection(self, mock_serial_class):
        """Test starting monitoring without connection raises exception"""
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        with self.assertRaises(MonitorNotStartedError):
            monitor.start_monitoring()
    
    @patch('serial.Serial')
    def test_start_monitoring_success(self, mock_serial_class):
        """Test successful monitoring start"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 0
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        # Connect and start monitoring
        monitor.connect()
        monitor.start_monitoring()
        
        self.assertTrue(monitor.is_monitoring)
        
        # Clean up
        monitor.stop_monitoring()
        monitor.disconnect()
    
    @patch('serial.Serial')
    def test_start_monitoring_already_started(self, mock_serial_class):
        """Test starting monitoring when already started raises exception"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 0
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        # Connect and start monitoring
        monitor.connect()
        monitor.start_monitoring()
        
        # Try to start again
        with self.assertRaises(MonitorAlreadyStartedError):
            monitor.start_monitoring()
        
        # Clean up
        monitor.stop_monitoring()
        monitor.disconnect()
    
    @patch('serial.Serial')
    def test_send_without_monitoring(self, mock_serial_class):
        """Test sending data without monitoring raises exception"""
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        with self.assertRaises(MonitorNotStartedError):
            monitor.send(b'test')
    
    @patch('serial.Serial')
    def test_send_success(self, mock_serial_class):
        """Test successful data sending"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 0
        mock_serial.write.return_value = 4
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        # Connect and start monitoring
        monitor.connect()
        monitor.start_monitoring()
        
        # Test sending
        test_data = b'test'
        result = monitor.send(test_data)
        
        self.assertTrue(result)
        
        # Give send thread time to process
        time.sleep(0.1)
        
        # Clean up
        monitor.stop_monitoring()
        monitor.disconnect()
    
    @patch('serial.Serial')
    def test_data_reception_callback(self, mock_serial_class):
        """Test data reception triggers callback"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 4
        mock_serial.read.return_value = b'test'
        mock_serial_class.return_value = mock_serial
        
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        # Setup callback
        data_callback = Mock()
        monitor.set_data_callback(data_callback)
        
        # Connect and start monitoring
        monitor.connect()
        monitor.start_monitoring()
        
        # Give monitor thread time to read data
        time.sleep(0.2)
        
        # Check callback was called
        data_callback.assert_called()
        
        # Clean up
        monitor.stop_monitoring()
        monitor.disconnect()
    
    @patch('serial.Serial')
    def test_context_manager(self, mock_serial_class):
        """Test context manager functionality"""
        # Setup mock
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 0
        mock_serial_class.return_value = mock_serial
        
        # Test context manager
        with AsyncSerialMonitor(logger=self.mock_logger) as monitor:
            self.assertTrue(monitor.is_connected)
        
        # After context, should be disconnected
        self.assertFalse(monitor.is_connected)
        mock_serial.close.assert_called()
    
    @patch('serial.Serial')
    def test_context_manager_connection_failure(self, mock_serial_class):
        """Test context manager with connection failure"""
        # Setup mock to fail
        mock_serial_class.side_effect = Exception("Connection failed")
        
        # Test context manager with connection failure
        with self.assertRaises(SerialConnectionError):
            with AsyncSerialMonitor(logger=self.mock_logger) as monitor:
                pass
    
    def test_statistics(self):
        """Test statistics property"""
        monitor = AsyncSerialMonitor(logger=self.mock_logger)
        
        stats = monitor.statistics
        
        self.assertIn('bytes_received', stats)
        self.assertIn('bytes_sent', stats)
        self.assertIn('connection_attempts', stats)
        self.assertIn('is_connected', stats)
        self.assertIn('is_monitoring', stats)
        
        self.assertEqual(stats['bytes_received'], 0)
        self.assertEqual(stats['bytes_sent'], 0)
        self.assertEqual(stats['connection_attempts'], 0)
        self.assertFalse(stats['is_connected'])
        self.assertFalse(stats['is_monitoring'])
    
    @patch('serial.tools.list_ports.comports')
    def test_list_serial_ports(self, mock_comports):
        """Test listing serial ports"""
        # Setup mock
        mock_port1 = Mock()
        mock_port1.device = '/dev/ttyUSB0'
        mock_port2 = Mock()
        mock_port2.device = '/dev/ttyACM0'
        mock_comports.return_value = [mock_port1, mock_port2]
        
        ports = AsyncSerialMonitor.list_serial_ports()
        
        self.assertEqual(ports, ['/dev/ttyUSB0', '/dev/ttyACM0'])
    
    def test_repr(self):
        """Test string representation"""
        monitor = AsyncSerialMonitor(
            port=self.test_port,
            baudrate=self.test_baudrate,
            logger=self.mock_logger
        )
        
        repr_str = repr(monitor)
        
        self.assertIn(self.test_port, repr_str)
        self.assertIn(str(self.test_baudrate), repr_str)
        self.assertIn('disconnected', repr_str)
        self.assertIn('idle', repr_str)


class TestAsyncSerialMonitorIntegration(unittest.TestCase):
    """Integration tests for AsyncSerialMonitor (require actual hardware)"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.mock_logger = Mock()
    
    @unittest.skip("Requires actual hardware")
    def test_real_hardware_connection(self):
        """Test with real hardware (skipped by default)"""
        # This test would require actual BraveJIG hardware
        # Uncomment and modify for real hardware testing
        
        monitor = AsyncSerialMonitor(
            port='/dev/tty.usbmodem0000000000002',
            baudrate=38400,
            logger=self.mock_logger
        )
        
        try:
            with monitor as m:
                m.start_monitoring()
                time.sleep(1)  # Monitor for 1 second
        except SerialConnectionError:
            self.skipTest("Hardware not available")


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncSerialMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncSerialMonitorIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
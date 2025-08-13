#!/usr/bin/env python3
"""
Simple BraveJIG Traffic Logger

This script logs all traffic on the BraveJIG serial connection.
Unlike the full monitor, this is designed to run in the background
and log traffic to a file while CLI commands are executed.

Usage:
    python3 simple_monitor.py <device> [baudrate] > traffic.log 2>&1 &
    
Example:
    python3 simple_monitor.py /dev/tty.usbmodem0000000000002 38400 > traffic.log 2>&1 &
"""

import sys
import os
import time
import signal
from datetime import datetime

# Add src to path for protocol imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import serial
except ImportError:
    print("Error: pyserial not installed. Please install: pip install pyserial")
    sys.exit(1)

class SimpleTrafficLogger:
    """Background traffic logger for BraveJIG serial communication"""
    
    def __init__(self, device: str, baudrate: int = 38400):
        self.device = device
        self.baudrate = baudrate
        self.running = False
        self.serial_conn = None
        
    def log_packet(self, data: bytes, direction: str = "TRAFFIC"):
        """Log a packet with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {direction}: {data.hex(' ').upper()}")
        sys.stdout.flush()
    
    def start_logging(self):
        """Start traffic logging"""
        print(f"# BraveJIG Traffic Logger Started")
        print(f"# Device: {self.device}")
        print(f"# Baudrate: {self.baudrate}")
        print(f"# Started: {datetime.now().isoformat()}")
        print("# Format: [timestamp] TRAFFIC: hex_data")
        print("#")
        
        try:
            self.serial_conn = serial.Serial(
                port=self.device,
                baudrate=self.baudrate,
                timeout=0.1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            self.running = True
            
            print(f"# Logging started at {datetime.now().isoformat()}")
            
            # Set up signal handler for graceful shutdown
            def signal_handler(signum, frame):
                print(f"\\n# Received signal {signum}, stopping logger...")
                self.stop_logging()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            last_activity = time.time()
            inactivity_logged = False
            
            while self.running:
                try:
                    if self.serial_conn.in_waiting > 0:
                        data = self.serial_conn.read(self.serial_conn.in_waiting)
                        if data:
                            self.log_packet(data)
                            last_activity = time.time()
                            inactivity_logged = False
                    else:
                        # Log periodic heartbeat if no activity
                        if time.time() - last_activity > 30 and not inactivity_logged:
                            print(f"# [{datetime.now().strftime('%H:%M:%S')}] No activity for 30+ seconds")
                            inactivity_logged = True
                        
                        time.sleep(0.01)  # Small delay
                        
                except serial.SerialException as e:
                    print(f"# Serial error: {e}")
                    break
                except Exception as e:
                    print(f"# Logger error: {e}")
                    break
                    
        except Exception as e:
            print(f"# Failed to start logger: {e}")
        finally:
            self.stop_logging()
    
    def stop_logging(self):
        """Stop traffic logging"""
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print(f"# Logging stopped at {datetime.now().isoformat()}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_monitor.py <device> [baudrate]")
        print("Example: python3 simple_monitor.py /dev/tty.usbmodem0000000000002 38400")
        sys.exit(1)
    
    device = sys.argv[1]
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 38400
    
    if not os.path.exists(device):
        print(f"Error: Device {device} not found")
        sys.exit(1)
    
    logger = SimpleTrafficLogger(device, baudrate)
    logger.start_logging()


if __name__ == '__main__':
    main()
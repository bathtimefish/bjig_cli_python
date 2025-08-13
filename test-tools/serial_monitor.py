#!/usr/bin/env python3
"""
BraveJIG Serial Traffic Monitor

This script monitors and decodes BraveJIG protocol traffic in real-time.
It provides detailed analysis of all JIG Info commands, Downlink requests,
Uplink notifications, and Error notifications.

Usage:
    python3 serial_monitor.py [DEVICE] [BAUDRATE]

Example:
    python3 serial_monitor.py /tmp/bjig_monitor 38400
"""

import sys
import os
import time
import threading
import signal
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path for protocol imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import serial
except ImportError:
    print("Error: pyserial not installed. Please install: pip install pyserial")
    sys.exit(1)

try:
    from protocol.bjig_protocol import BraveJIGProtocol
    from protocol.jiginfo import JigInfoCommand
    from protocol.common import SensorType
except ImportError as e:
    print(f"Error importing BraveJIG protocol: {e}")
    print("Please ensure the src/ directory structure is correct")
    sys.exit(1)


class BraveJIGMonitor:
    """Real-time BraveJIG protocol traffic monitor"""
    
    def __init__(self, device: str, baudrate: int = 38400):
        self.device = device
        self.baudrate = baudrate
        self.protocol = BraveJIGProtocol()
        self.running = False
        self.serial_conn = None
        
        # Statistics
        self.stats = {
            'packets_total': 0,
            'jig_info_requests': 0,
            'jig_info_responses': 0,
            'downlink_requests': 0,
            'downlink_responses': 0,
            'uplink_notifications': 0,
            'error_notifications': 0,
            'parse_errors': 0
        }
        
        # Color codes for terminal output
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m'
        }
    
    def colorize(self, text: str, color: str) -> str:
        """Add color to text if terminal supports it"""
        if sys.stdout.isatty():
            return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"
        return text
    
    def print_header(self):
        """Print monitor header"""
        print(self.colorize("=" * 80, 'cyan'))
        print(self.colorize("BraveJIG Serial Traffic Monitor", 'bold'))
        print(self.colorize(f"Device: {self.device} | Baudrate: {self.baudrate}", 'white'))
        print(self.colorize(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'white'))
        print(self.colorize("=" * 80, 'cyan'))
        print()
    
    def print_packet_header(self, direction: str, packet_type: str, raw_data: bytes):
        """Print packet header with timestamp and basic info"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Include milliseconds
        
        direction_color = 'green' if direction == 'TX' else 'blue'
        type_color = {
            'JIG_INFO_REQUEST': 'yellow',
            'JIG_INFO_RESPONSE': 'yellow', 
            'DOWNLINK_REQUEST': 'magenta',
            'DOWNLINK_RESPONSE': 'magenta',
            'UPLINK_NOTIFICATION': 'cyan',
            'ERROR_NOTIFICATION': 'red',
            'UNKNOWN': 'white'
        }.get(packet_type, 'white')
        
        print(f"[{timestamp}] {self.colorize(direction, direction_color)} " +
              f"{self.colorize(packet_type, type_color)} " +
              f"({len(raw_data)} bytes): {raw_data.hex(' ').upper()}")
    
    def analyze_jig_info_packet(self, data: bytes, direction: str):
        """Analyze JIG Info request/response packet"""
        try:
            if direction == 'TX':  # Likely request
                self.stats['jig_info_requests'] += 1
                self.print_packet_header(direction, 'JIG_INFO_REQUEST', data)
                
                # Parse JIG Info request
                if len(data) >= 3:
                    cmd_byte = data[2]
                    try:
                        cmd = JigInfoCommand(cmd_byte)
                        print(f"  Command: {cmd.name} (0x{cmd_byte:02X})")
                    except ValueError:
                        print(f"  Command: UNKNOWN (0x{cmd_byte:02X})")
                
            else:  # RX - Response
                self.stats['jig_info_responses'] += 1
                self.print_packet_header(direction, 'JIG_INFO_RESPONSE', data)
                
                # Parse response
                response = self.protocol.parse_response(data)
                if hasattr(response, 'cmd'):
                    try:
                        cmd = JigInfoCommand(response.cmd)
                        print(f"  Response to: {cmd.name} (0x{response.cmd:02X})")
                    except ValueError:
                        print(f"  Response to: UNKNOWN (0x{response.cmd:02X})")
                    
                    if hasattr(response, 'result'):
                        result_desc = "SUCCESS" if response.result == 0x00 else f"ERROR_0x{response.result:02X}"
                        result_color = 'green' if response.result == 0x00 else 'red'
                        print(f"  Result: {self.colorize(result_desc, result_color)}")
                    
                    if hasattr(response, 'data') and response.data:
                        print(f"  Data: {response.data.hex(' ').upper()}")
                        
        except Exception as e:
            print(f"  {self.colorize(f'Parse Error: {e}', 'red')}")
    
    def analyze_downlink_packet(self, data: bytes, direction: str):
        """Analyze Downlink request/response packet"""
        try:
            if direction == 'TX':  # Request
                self.stats['downlink_requests'] += 1
                self.print_packet_header(direction, 'DOWNLINK_REQUEST', data)
                
                # Extract device ID and sensor info if available
                if len(data) >= 16:
                    device_id = int.from_bytes(data[8:16], 'little')
                    print(f"  Target Device: 0x{device_id:016X}")
                    
                    if len(data) >= 18:
                        sensor_id = int.from_bytes(data[16:18], 'little')
                        sensor_desc = self.get_sensor_description(sensor_id)
                        print(f"  Sensor ID: 0x{sensor_id:04X} ({sensor_desc})")
                        
                        if len(data) >= 19:
                            cmd_byte = data[18]
                            cmd_desc = self.get_module_command_description(sensor_id, cmd_byte)
                            print(f"  Module Command: 0x{cmd_byte:02X} ({cmd_desc})")
            
            else:  # RX - Response
                self.stats['downlink_responses'] += 1
                self.print_packet_header(direction, 'DOWNLINK_RESPONSE', data)
                
                response = self.protocol.parse_response(data)
                if hasattr(response, 'device_id'):
                    print(f"  From Device: 0x{response.device_id:016X}")
                if hasattr(response, 'sensor_id'):
                    sensor_desc = self.get_sensor_description(response.sensor_id)
                    print(f"  Sensor ID: 0x{response.sensor_id:04X} ({sensor_desc})")
                if hasattr(response, 'result'):
                    result_desc = "SUCCESS" if response.result == 0x00 else f"ERROR_0x{response.result:02X}"
                    result_color = 'green' if response.result == 0x00 else 'red'
                    print(f"  Result: {self.colorize(result_desc, result_color)}")
                    
        except Exception as e:
            print(f"  {self.colorize(f'Parse Error: {e}', 'red')}")
    
    def analyze_uplink_packet(self, data: bytes):
        """Analyze Uplink notification packet"""
        try:
            self.stats['uplink_notifications'] += 1
            self.print_packet_header('RX', 'UPLINK_NOTIFICATION', data)
            
            notification = self.protocol.parse_response(data)
            if hasattr(notification, 'device_id'):
                print(f"  From Device: 0x{notification.device_id:016X}")
            if hasattr(notification, 'sensor_id'):
                sensor_desc = self.get_sensor_description(notification.sensor_id)
                print(f"  Sensor ID: 0x{notification.sensor_id:04X} ({sensor_desc})")
                
                # Special handling for illuminance sensor data
                if notification.sensor_id == 0x0121 and hasattr(notification, 'data'):
                    self.analyze_illuminance_data(notification.data)
                elif notification.sensor_id == 0x0000:
                    print(f"  Type: Parameter Information Uplink")
            
            if hasattr(notification, 'data') and notification.data:
                print(f"  Data Length: {len(notification.data)} bytes")
                if len(notification.data) <= 32:  # Show full data for small packets
                    print(f"  Data: {notification.data.hex(' ').upper()}")
                    
        except Exception as e:
            print(f"  {self.colorize(f'Parse Error: {e}', 'red')}")
    
    def analyze_error_packet(self, data: bytes):
        """Analyze Error notification packet"""
        try:
            self.stats['error_notifications'] += 1
            self.print_packet_header('RX', 'ERROR_NOTIFICATION', data)
            
            error = self.protocol.parse_response(data)
            if hasattr(error, 'cmd'):
                try:
                    cmd = JigInfoCommand(error.cmd)
                    print(f"  Failed Command: {cmd.name} (0x{error.cmd:02X})")
                except ValueError:
                    print(f"  Failed Command: UNKNOWN (0x{error.cmd:02X})")
            
            if hasattr(error, 'reason'):
                reason_desc = self.protocol.interpret_error_reason(error.reason)
                print(f"  {self.colorize(f'Error Reason: {reason_desc}', 'red')}")
                
        except Exception as e:
            print(f"  {self.colorize(f'Parse Error: {e}', 'red')}")
    
    def analyze_illuminance_data(self, data: bytes):
        """Analyze illuminance sensor data"""
        try:
            if len(data) >= 16:
                import struct
                offset = 4  # Skip SensorID + Sequence
                
                if offset < len(data):
                    battery = data[offset]
                    print(f"  Battery Level: {battery}%")
                    offset += 1
                
                if offset < len(data):
                    sampling = data[offset]
                    sampling_desc = "1Hz" if sampling == 0x00 else "2Hz" if sampling == 0x01 else f"Unknown({sampling})"
                    print(f"  Sampling: {sampling_desc}")
                    offset += 1
                
                if offset + 4 <= len(data):
                    sensor_time = struct.unpack('<L', data[offset:offset+4])[0]
                    dt = datetime.fromtimestamp(sensor_time)
                    print(f"  Sensor Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    offset += 4
                
                if offset + 2 <= len(data):
                    sample_count = struct.unpack('<H', data[offset:offset+2])[0]
                    print(f"  Sample Count: {sample_count}")
                    offset += 2
                    
                    # Read lux data
                    lux_values = []
                    for i in range(min(sample_count, (len(data) - offset) // 4)):
                        if offset + 4 <= len(data):
                            lux = struct.unpack('<f', data[offset:offset+4])[0]
                            lux_values.append(round(lux, 2))
                            offset += 4
                    
                    if lux_values:
                        if len(lux_values) <= 5:
                            print(f"  Lux Values: {lux_values}")
                        else:
                            avg_lux = sum(lux_values) / len(lux_values)
                            print(f"  Lux Values: {lux_values[:3]}...{lux_values[-2:]} (avg: {avg_lux:.2f})")
                            
        except Exception as e:
            print(f"  {self.colorize(f'Illuminance Parse Error: {e}', 'red')}")
    
    def get_sensor_description(self, sensor_id: int) -> str:
        """Get human-readable sensor description"""
        sensor_map = {
            0x0000: "End Device Main Unit",
            0x0121: "Illuminance Sensor",
            0x0131: "Accelerometer Sensor",
            # Add more sensor types as needed
        }
        return sensor_map.get(sensor_id, "Unknown Sensor")
    
    def get_module_command_description(self, sensor_id: int, cmd_byte: int) -> str:
        """Get module command description"""
        if sensor_id == 0x0121:  # Illuminance sensor
            cmd_map = {
                0x00: "INSTANT_UPLINK",
                0x05: "SET_PARAMETER", 
                0x0D: "GET_DEVICE_SETTING",
                0x12: "SENSOR_DFU",
                0xFD: "DEVICE_RESTART"
            }
            return cmd_map.get(cmd_byte, "Unknown")
        return "Unknown"
    
    def determine_packet_type_and_direction(self, data: bytes) -> tuple[str, str]:
        """Determine packet type and direction from raw data"""
        if len(data) < 2:
            return "UNKNOWN", "RX"
        
        packet_type = data[1]
        
        # Heuristic to determine direction (TX/RX)
        # This is simplified - in a real implementation you might use timing analysis
        # or separate TX/RX monitoring
        direction = "RX"  # Default to RX for monitoring
        
        if packet_type == 0x01:
            return "JIG_INFO", direction
        elif packet_type == 0x02:
            return "DOWNLINK", direction
        elif packet_type == 0x00:
            return "UPLINK", direction
        elif packet_type == 0x04:
            return "ERROR", direction
        else:
            return "UNKNOWN", direction
    
    def process_packet(self, data: bytes):
        """Process a received packet"""
        if not data:
            return
        
        self.stats['packets_total'] += 1
        
        packet_category, direction = self.determine_packet_type_and_direction(data)
        
        try:
            if packet_category == "JIG_INFO":
                self.analyze_jig_info_packet(data, direction)
            elif packet_category == "DOWNLINK":
                self.analyze_downlink_packet(data, direction)
            elif packet_category == "UPLINK":
                self.analyze_uplink_packet(data)
            elif packet_category == "ERROR":
                self.analyze_error_packet(data)
            else:
                self.print_packet_header(direction, 'UNKNOWN', data)
                self.stats['parse_errors'] += 1
                
        except Exception as e:
            print(f"{self.colorize(f'Packet Analysis Error: {e}', 'red')}")
            self.stats['parse_errors'] += 1
        
        print()  # Empty line after each packet
    
    def print_statistics(self):
        """Print monitoring statistics"""
        print(self.colorize("\n=== Traffic Statistics ===", 'cyan'))
        for key, value in self.stats.items():
            label = key.replace('_', ' ').title()
            print(f"{label}: {value}")
        print()
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n{self.colorize('Received signal, stopping monitor...', 'yellow')}")
        self.stop()
    
    def start(self):
        """Start monitoring"""
        try:
            self.serial_conn = serial.Serial(
                port=self.device,
                baudrate=self.baudrate,
                timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            self.print_header()
            print(f"{self.colorize('Monitor started. Press Ctrl+C to stop.', 'green')}\n")
            
            self.running = True
            
            # Set up signal handler
            signal.signal(signal.SIGINT, self.signal_handler)
            
            buffer = b''
            
            while self.running:
                try:
                    if self.serial_conn.in_waiting > 0:
                        chunk = self.serial_conn.read(self.serial_conn.in_waiting)
                        buffer += chunk
                        
                        # Simple packet extraction - look for valid packet starts
                        while len(buffer) >= 2:
                            # Check if we have a valid packet type
                            if buffer[1] in [0x00, 0x01, 0x02, 0x04]:  # Valid packet types
                                # Extract packet length if available
                                if len(buffer) >= 3:
                                    # Try to determine packet length
                                    expected_length = self.estimate_packet_length(buffer)
                                    
                                    if len(buffer) >= expected_length:
                                        packet = buffer[:expected_length]
                                        self.process_packet(packet)
                                        buffer = buffer[expected_length:]
                                    else:
                                        break  # Wait for more data
                                else:
                                    break  # Wait for more data
                            else:
                                # Skip invalid byte
                                buffer = buffer[1:]
                    
                    time.sleep(0.01)  # Small delay to prevent high CPU usage
                    
                except serial.SerialException as e:
                    print(f"{self.colorize(f'Serial Error: {e}', 'red')}")
                    break
                except Exception as e:
                    print(f"{self.colorize(f'Monitor Error: {e}', 'red')}")
                    
        except Exception as e:
            print(f"{self.colorize(f'Failed to start monitor: {e}', 'red')}")
        finally:
            self.stop()
    
    def estimate_packet_length(self, buffer: bytes) -> int:
        """Estimate packet length based on packet type"""
        if len(buffer) < 2:
            return 0
        
        packet_type = buffer[1]
        
        # Basic length estimation - you may need to adjust based on actual protocol
        if packet_type == 0x01:  # JIG Info
            return min(8, len(buffer))  # Typical JIG Info packet size
        elif packet_type == 0x02:  # Downlink
            if len(buffer) >= 3:
                # Downlink packets can vary, use a reasonable default
                return min(64, len(buffer))
        elif packet_type == 0x00:  # Uplink
            if len(buffer) >= 3:
                # Uplink packets can be large, use a reasonable default
                return min(128, len(buffer))
        elif packet_type == 0x04:  # Error
            return min(8, len(buffer))  # Error packets are typically small
        
        return min(16, len(buffer))  # Default fallback
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        
        self.print_statistics()
        print(f"{self.colorize('Monitor stopped.', 'yellow')}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 serial_monitor.py <device> [baudrate]")
        print("Example: python3 serial_monitor.py /tmp/bjig_monitor 38400")
        sys.exit(1)
    
    device = sys.argv[1]
    baudrate = int(sys.argv[2]) if len(sys.argv) > 2 else 38400
    
    if not os.path.exists(device):
        print(f"Error: Device {device} not found")
        sys.exit(1)
    
    monitor = BraveJIGMonitor(device, baudrate)
    monitor.start()


if __name__ == '__main__':
    main()
"""
BraveJIG Router specific test example

This example demonstrates how to use AsyncSerialMonitor specifically
for testing BraveJIG Router communication with proper protocol handling.
"""

import sys
import time
import signal
import struct
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from async_serial_monitor import AsyncSerialMonitor
from exceptions import AsyncSerialMonitorError


def setup_logging():
    """Setup logging for the example"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


class BraveJIGProtocolHandler:
    """Simple BraveJIG protocol handler for demonstration"""
    
    # Protocol constants
    PROTOCOL_VERSION = 0x01
    TYPE_UPLINK_NOTIFICATION = 0x00
    TYPE_DOWNLINK_REQUEST = 0x00
    TYPE_DOWNLINK_RESPONSE = 0x01
    TYPE_JIG_INFO_REQUEST = 0x01
    TYPE_JIG_INFO_RESPONSE = 0x02
    TYPE_ERROR_NOTIFICATION = 0xFF
    
    def __init__(self):
        self.received_packets = []
    
    def parse_packet(self, data: bytes) -> dict:
        """Parse received BraveJIG packet"""
        if len(data) < 2:
            return {"error": "Packet too short"}
            
        try:
            protocol_version = data[0]
            packet_type = data[1]
            
            result = {
                "protocol_version": protocol_version,
                "type": packet_type,
                "type_name": self._get_type_name(packet_type),
                "raw_data": data.hex(' ').upper(),
                "length": len(data)
            }
            
            if packet_type == self.TYPE_UPLINK_NOTIFICATION and len(data) >= 21:
                result.update(self._parse_uplink_notification(data))
            elif packet_type == self.TYPE_DOWNLINK_RESPONSE and len(data) >= 19:
                result.update(self._parse_downlink_response(data))
            elif packet_type == self.TYPE_JIG_INFO_RESPONSE and len(data) >= 15:
                result.update(self._parse_jig_info_response(data))
            elif packet_type == self.TYPE_ERROR_NOTIFICATION and len(data) >= 7:
                result.update(self._parse_error_notification(data))
                
            return result
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex(' ').upper()}
    
    def _get_type_name(self, packet_type: int) -> str:
        """Get human-readable packet type name"""
        type_names = {
            0x00: "UPLINK_NOTIFICATION",
            0x01: "DOWNLINK_RESPONSE/JIG_INFO_REQUEST", 
            0x02: "JIG_INFO_RESPONSE",
            0xFF: "ERROR_NOTIFICATION"
        }
        return type_names.get(packet_type, f"UNKNOWN(0x{packet_type:02X})")
    
    def _parse_uplink_notification(self, data: bytes) -> dict:
        """Parse uplink notification packet"""
        try:
            data_length = struct.unpack('<H', data[2:4])[0]
            unix_time = struct.unpack('<L', data[4:8])[0]
            device_id = struct.unpack('<Q', data[8:16])[0]
            sensor_id = struct.unpack('<H', data[16:18])[0]
            rssi = data[18]
            order = struct.unpack('<H', data[19:21])[0]
            
            return {
                "data_length": data_length,
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S'),
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "rssi": rssi,
                "order": order,
                "sensor_data": data[21:].hex(' ').upper() if len(data) > 21 else "None"
            }
        except Exception as e:
            return {"parse_error": str(e)}
    
    def _parse_downlink_response(self, data: bytes) -> dict:
        """Parse downlink response packet"""
        try:
            unix_time = struct.unpack('<L', data[2:6])[0]
            device_id = struct.unpack('<Q', data[6:14])[0]
            sensor_id = struct.unpack('<H', data[14:16])[0]
            order = struct.unpack('<H', data[16:18])[0]
            cmd = data[18]
            result = data[19]
            
            return {
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S'),
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "order": order,
                "cmd": f"0x{cmd:02X}",
                "result": f"0x{result:02X}",
                "result_desc": self._get_result_description(result)
            }
        except Exception as e:
            return {"parse_error": str(e)}
    
    def _parse_jig_info_response(self, data: bytes) -> dict:
        """Parse JIG INFO response packet"""
        try:
            unix_time = struct.unpack('<L', data[2:6])[0]
            cmd = data[6]
            router_device_id = struct.unpack('<Q', data[7:15])[0]
            response_data = data[15:].hex(' ').upper() if len(data) > 15 else "None"
            
            return {
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S'),
                "cmd": f"0x{cmd:02X}",
                "router_device_id": f"0x{router_device_id:016X}",
                "response_data": response_data
            }
        except Exception as e:
            return {"parse_error": str(e)}
    
    def _parse_error_notification(self, data: bytes) -> dict:
        """Parse error notification packet"""
        try:
            unix_time = struct.unpack('<L', data[2:6])[0]
            reason = data[6]
            
            return {
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S'),
                "reason": f"0x{reason:02X}",
                "reason_desc": self._get_error_reason(reason)
            }
        except Exception as e:
            return {"parse_error": str(e)}
    
    def _get_result_description(self, result: int) -> str:
        """Get result code description"""
        descriptions = {
            0x00: "Success",
            0x01: "Invalid Sensor ID",
            0x02: "Unsupported CMD",
            0x03: "Parameter out of range",
            0x04: "Connection failed",
            0x05: "Timeout",
            0x07: "Device not found",
            0x08: "Router busy",
            0x09: "Module busy"
        }
        return descriptions.get(result, f"Unknown result (0x{result:02X})")
    
    def _get_error_reason(self, reason: int) -> str:
        """Get error reason description"""
        reasons = {
            0x01: "Invalid request",
            0x02: "Downlink processing",
            0x06: "Device ID not registered"
        }
        return reasons.get(reason, f"Unknown error (0x{reason:02X})")
    
    def create_jig_info_request(self, cmd: int) -> bytes:
        """Create JIG INFO request packet"""
        # JIG INFO request structure (no Data Length field)
        local_time = int(time.time()) + 9*3600  # JST (UTC+9)
        unix_time = int(time.time())
        
        packet = struct.pack('<BBB', self.PROTOCOL_VERSION, self.TYPE_JIG_INFO_REQUEST, cmd)
        packet += struct.pack('<L', local_time)
        packet += struct.pack('<L', unix_time)
        
        return packet
    
    def create_downlink_request(self, device_id: int, sensor_id: int, cmd: int, data: bytes = b'') -> bytes:
        """Create downlink request packet"""
        data_length = len(data)
        unix_time = int(time.time())
        order = 0x0000
        
        packet = struct.pack('<BB', self.PROTOCOL_VERSION, self.TYPE_DOWNLINK_REQUEST)
        packet += struct.pack('<H', data_length)
        packet += struct.pack('<L', unix_time)
        packet += struct.pack('<Q', device_id)
        packet += struct.pack('<H', sensor_id)
        packet += struct.pack('<B', cmd)
        packet += struct.pack('<H', order)
        packet += data
        
        return packet


def on_data_received(data: bytes):
    """Callback function for received data with BraveJIG protocol parsing"""
    print(f"\n📥 Raw data received ({len(data)} bytes): {data.hex(' ').upper()}")
    
    # Parse as BraveJIG protocol
    parsed = protocol_handler.parse_packet(data)
    
    print("📋 Parsed packet:")
    for key, value in parsed.items():
        print(f"   {key}: {value}")
    
    # Store for statistics
    protocol_handler.received_packets.append(parsed)


def on_error(error: Exception):
    """Callback function for errors"""
    print(f"❌ Error: {error}")


def on_connection_changed(connected: bool):
    """Callback function for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(f"{status}")


def send_test_commands(monitor: AsyncSerialMonitor):
    """Send test commands to BraveJIG Router"""
    print("\n📤 Sending test commands...")
    
    # JIG INFO commands
    jig_commands = [
        (0x02, "FW Version Request"),
        (0x67, "Scan Mode Get"),
        (0x01, "Start"),
        (0x00, "Stop")
    ]
    
    for cmd_code, description in jig_commands:
        packet = protocol_handler.create_jig_info_request(cmd_code)
        print(f"📡 Sending {description} (CMD: 0x{cmd_code:02X})")
        print(f"   Data: {packet.hex(' ').upper()}")
        
        if monitor.send(packet):
            print("✅ Command sent successfully")
        else:
            print("❌ Failed to send command")
        
        time.sleep(2)  # Wait between commands
    
    # Example downlink request (immediate uplink request)
    print("\n📡 Sending Downlink Request (Immediate Uplink)")
    device_id = 0x1234567890ABCDEF  # Example device ID
    sensor_id = 0x0123  # Temperature/Humidity sensor
    cmd = 0x00  # Immediate uplink request
    
    packet = protocol_handler.create_downlink_request(device_id, sensor_id, cmd)
    print(f"   Data: {packet.hex(' ').upper()}")
    
    if monitor.send(packet):
        print("✅ Downlink request sent successfully")
    else:
        print("❌ Failed to send downlink request")


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Stopping BraveJIG test...")
    global test_running
    test_running = False


def main():
    """Main function for BraveJIG specific testing"""
    setup_logging()
    
    print("🚀 BraveJIG Router Test Example")
    print("=" * 50)
    
    # Setup signal handler for graceful shutdown
    global test_running, protocol_handler
    test_running = True
    protocol_handler = BraveJIGProtocolHandler()
    signal.signal(signal.SIGINT, signal_handler)
    
    # BraveJIG Router default settings
    port = '/dev/tty.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router at {port} ({baudrate} baud)")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            print(f"📊 Monitor: {monitor}")
            
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            print("▶️  Starting monitoring...")
            monitor.start_monitoring()
            
            # Send test commands
            send_test_commands(monitor)
            
            # Main monitoring loop
            print("\n🔄 Monitoring BraveJIG Router. Press Ctrl+C to stop...")
            print("💡 You should see uplink notifications from paired modules")
            
            last_stats_time = time.time()
            
            while test_running and monitor.is_monitoring:
                time.sleep(0.1)
                
                # Print statistics every 30 seconds
                current_time = time.time()
                if current_time - last_stats_time >= 30:
                    stats = monitor.statistics
                    print(f"\n📈 Communication Stats:")
                    print(f"   RX: {stats['bytes_received']} bytes")
                    print(f"   TX: {stats['bytes_sent']} bytes")
                    print(f"   Packets received: {len(protocol_handler.received_packets)}")
                    
                    # Show packet type summary
                    type_counts = {}
                    for packet in protocol_handler.received_packets:
                        type_name = packet.get('type_name', 'UNKNOWN')
                        type_counts[type_name] = type_counts.get(type_name, 0) + 1
                    
                    if type_counts:
                        print("   Packet types:")
                        for ptype, count in type_counts.items():
                            print(f"     {ptype}: {count}")
                    
                    last_stats_time = current_time
            
    except AsyncSerialMonitorError as e:
        print(f"❌ AsyncSerialMonitor error: {e}")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
    finally:
        print("🏁 BraveJIG test finished")
        print(f"📊 Total packets received: {len(protocol_handler.received_packets)}")


if __name__ == "__main__":
    main()
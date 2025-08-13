#!/usr/bin/env python3
"""
BraveJIG Protocol Analysis Test

Advanced test to analyze BraveJIG protocol packets and demonstrate protocol parsing.
"""

import time
import signal
import struct
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global flag for graceful shutdown
test_running = True
received_packets = []

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping protocol analysis...")
    test_running = False

class BraveJIGProtocolAnalyzer:
    """Analyze BraveJIG protocol packets"""
    
    def __init__(self):
        self.packet_count = 0
        self.sensor_types = {}
    
    def analyze_packet(self, data: bytes) -> dict:
        """Analyze received BraveJIG packet"""
        self.packet_count += 1
        
        if len(data) < 21:
            return {"error": "Packet too short", "raw": data.hex(' ').upper()}
        
        try:
            # Parse router header (20 bytes)
            protocol_version = data[0]
            packet_type = data[1]
            data_length = struct.unpack('<H', data[2:4])[0]
            unix_time = struct.unpack('<L', data[4:8])[0]
            device_id = struct.unpack('<Q', data[8:16])[0]
            sensor_id = struct.unpack('<H', data[16:18])[0]
            rssi = data[18] if data[18] < 128 else data[18] - 256  # Convert to signed
            order = struct.unpack('<H', data[19:21])[0]
            
            # Parse sensor data (starting at index 21)
            sensor_data = data[21:]
            
            result = {
                "packet_number": self.packet_count,
                "protocol_version": f"0x{protocol_version:02X}",
                "type": f"0x{packet_type:02X}",
                "type_name": self._get_type_name(packet_type),
                "data_length": data_length,
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "sensor_name": self._get_sensor_name(sensor_id),
                "rssi": f"{rssi} dBm",
                "order": order,
                "sensor_data_size": len(sensor_data),
                "raw_data": data.hex(' ').upper()
            }
            
            # Track sensor types
            if sensor_id not in self.sensor_types:
                self.sensor_types[sensor_id] = {
                    "name": self._get_sensor_name(sensor_id),
                    "count": 0,
                    "device_id": device_id
                }
            self.sensor_types[sensor_id]["count"] += 1
            
            # Parse sensor-specific data if it's an uplink notification
            if packet_type == 0x00 and len(sensor_data) >= 4:
                sensor_result = self._parse_sensor_data(sensor_id, sensor_data)
                result.update(sensor_result)
            
            return result
            
        except Exception as e:
            return {
                "error": f"Parse error: {e}",
                "raw_data": data.hex(' ').upper(),
                "packet_number": self.packet_count
            }
    
    def _get_type_name(self, packet_type: int) -> str:
        """Get packet type name"""
        types = {
            0x00: "UPLINK_NOTIFICATION",
            0x01: "DOWNLINK_RESPONSE/JIG_INFO_REQUEST",
            0x02: "JIG_INFO_RESPONSE",
            0xFF: "ERROR_NOTIFICATION"
        }
        return types.get(packet_type, f"UNKNOWN(0x{packet_type:02X})")
    
    def _get_sensor_name(self, sensor_id: int) -> str:
        """Get sensor name from sensor ID"""
        sensors = {
            0x0121: "Illuminance",
            0x0122: "Accelerometer",
            0x0123: "Temperature/Humidity", 
            0x0124: "Barometric Pressure",
            0x0125: "Distance/Ranging",
            0x0126: "Dry Contact Input",
            0x0127: "Wet Contact Input",
            0x0128: "2ch Contact Output"
        }
        return sensors.get(sensor_id, f"Unknown(0x{sensor_id:04X})")
    
    def _parse_sensor_data(self, sensor_id: int, data: bytes) -> dict:
        """Parse sensor-specific data"""
        try:
            if len(data) < 4:
                return {"sensor_parse": "Insufficient data"}
            
            # Common header: SensorID(2) + SequenceNo(2) 
            sensor_id_confirm = struct.unpack('<H', data[0:2])[0]
            sequence_no = struct.unpack('<H', data[2:4])[0]
            
            result = {
                "sensor_id_confirm": f"0x{sensor_id_confirm:04X}",
                "sequence_no": sequence_no
            }
            
            if len(data) >= 6:
                battery_level = data[4]
                sampling = data[5]
                result.update({
                    "battery_level": f"{battery_level}%",
                    "sampling": sampling
                })
            
            if len(data) >= 10:
                sensor_time = struct.unpack('<L', data[6:10])[0]
                result["sensor_time"] = datetime.fromtimestamp(sensor_time).strftime('%H:%M:%S')
            
            if len(data) >= 12:
                sample_num = struct.unpack('<H', data[10:12])[0]
                result["sample_count"] = sample_num
                
                # Parse measurement data based on sensor type
                if sensor_id == 0x0121:  # Illuminance
                    result.update(self._parse_illuminance(data[12:]))
                elif sensor_id == 0x0122:  # Accelerometer
                    result.update(self._parse_accelerometer(data[12:]))
                elif sensor_id == 0x0123:  # Temperature/Humidity
                    result.update(self._parse_temp_humidity(data[12:]))
                elif sensor_id == 0x0124:  # Pressure
                    result.update(self._parse_pressure(data[12:]))
                elif sensor_id == 0x0125:  # Distance
                    result.update(self._parse_distance(data[12:]))
            
            return result
            
        except Exception as e:
            return {"sensor_parse_error": str(e)}
    
    def _parse_temp_humidity(self, data: bytes) -> dict:
        """Parse temperature/humidity data"""
        result = {"measurements": []}
        try:
            for i in range(0, len(data), 8):  # 8 bytes per measurement
                if i + 8 <= len(data):
                    temp = struct.unpack('<f', data[i:i+4])[0]
                    humidity = struct.unpack('<f', data[i+4:i+8])[0]
                    result["measurements"].append({
                        "temperature": f"{temp:.2f}°C",
                        "humidity": f"{humidity:.1f}%"
                    })
        except:
            pass
        return result
    
    def _parse_accelerometer(self, data: bytes) -> dict:
        """Parse accelerometer data"""
        result = {"measurements": []}
        try:
            for i in range(0, len(data), 12):  # 12 bytes per measurement
                if i + 12 <= len(data):
                    x = struct.unpack('<f', data[i:i+4])[0]
                    y = struct.unpack('<f', data[i+4:i+8])[0]
                    z = struct.unpack('<f', data[i+8:i+12])[0]
                    result["measurements"].append({
                        "x_axis": f"{x:.2f}mG",
                        "y_axis": f"{y:.2f}mG", 
                        "z_axis": f"{z:.2f}mG"
                    })
        except:
            pass
        return result
    
    def _parse_pressure(self, data: bytes) -> dict:
        """Parse pressure data"""
        result = {"measurements": []}
        try:
            for i in range(0, len(data), 4):  # 4 bytes per measurement
                if i + 4 <= len(data):
                    pressure = struct.unpack('<f', data[i:i+4])[0]
                    result["measurements"].append({
                        "pressure": f"{pressure:.2f}hPa"
                    })
        except:
            pass
        return result
    
    def _parse_distance(self, data: bytes) -> dict:
        """Parse distance data"""
        result = {"measurements": []}
        try:
            for i in range(0, len(data), 4):  # 4 bytes per measurement
                if i + 4 <= len(data):
                    distance = struct.unpack('<f', data[i:i+4])[0]
                    result["measurements"].append({
                        "distance": f"{distance:.2f}mm"
                    })
        except:
            pass
        return result
    
    def _parse_illuminance(self, data: bytes) -> dict:
        """Parse illuminance data"""
        result = {"measurements": []}
        try:
            for i in range(0, len(data), 4):  # 4 bytes per measurement
                if i + 4 <= len(data):
                    illuminance = struct.unpack('<f', data[i:i+4])[0]
                    result["measurements"].append({
                        "illuminance": f"{illuminance:.2f}lux"
                    })
        except:
            pass
        return result
    
    def get_summary(self) -> dict:
        """Get analysis summary"""
        return {
            "total_packets": self.packet_count,
            "sensor_types": self.sensor_types
        }

# Global analyzer instance
analyzer = BraveJIGProtocolAnalyzer()

def on_data_received(data: bytes):
    """Callback for received data with protocol analysis"""
    global received_packets
    
    analysis = analyzer.analyze_packet(data)
    received_packets.append(analysis)
    
    print(f"\n📦 Packet #{analysis.get('packet_number', '?')}")
    print(f"   Type: {analysis.get('type_name', 'Unknown')}")
    print(f"   Sensor: {analysis.get('sensor_name', 'Unknown')}")
    print(f"   Time: {analysis.get('timestamp', 'Unknown')}")
    print(f"   RSSI: {analysis.get('rssi', 'Unknown')}")
    print(f"   Battery: {analysis.get('battery_level', 'Unknown')}")
    
    # Show measurements if available
    if 'measurements' in analysis and analysis['measurements']:
        print(f"   Measurements:")
        for i, measurement in enumerate(analysis['measurements'][:2]):  # Show first 2
            print(f"     [{i+1}] {measurement}")
        if len(analysis['measurements']) > 2:
            print(f"     ... and {len(analysis['measurements']) - 2} more")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(status)

def main():
    """Main protocol analysis function"""
    global test_running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔬 BraveJIG Protocol Analysis Test")
    print("=" * 45)
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router for protocol analysis...")
    print(f"   Port: {port}")
    print(f"   Duration: 120 seconds (2 uplink cycles)")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            monitor.start_monitoring()
            
            print("\n🔄 Analyzing BraveJIG protocol packets...")
            print("   60-second uplink intervals - monitoring 2 cycles")
            print("   Press Ctrl+C to stop early")
            
            # Monitor for 120 seconds (2 uplink cycles)
            start_time = time.time()
            
            while test_running and monitor.is_monitoring and (time.time() - start_time) < 120:
                time.sleep(0.1)
            
            # Print summary
            summary = analyzer.get_summary()
            print(f"\n📊 Analysis Summary:")
            print(f"   Total packets received: {summary['total_packets']}")
            print(f"   Unique sensors detected: {len(summary['sensor_types'])}")
            
            print(f"\n🔍 Detected Sensors:")
            for sensor_id, info in summary['sensor_types'].items():
                print(f"   • {info['name']} (ID: 0x{sensor_id:04X})")
                print(f"     Device: 0x{info['device_id']:016X}")
                print(f"     Packets: {info['count']}")
            
            # Show communication stats
            stats = monitor.statistics
            print(f"\n📈 Communication Statistics:")
            print(f"   Total bytes received: {stats['bytes_received']}")
            print(f"   Average packet size: {stats['bytes_received'] / max(summary['total_packets'], 1):.1f} bytes")
            
    except Exception as e:
        print(f"❌ Protocol analysis failed: {e}")
        return False
    
    print("🏁 Protocol analysis completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
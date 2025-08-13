#!/usr/bin/env python3
"""
Illuminance Sensor Parameter Acquisition Test

Test downlink parameter acquisition request to illuminance sensor and verify downlink response.
"""

import time
import signal
import struct
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global flag for graceful shutdown
test_running = True
downlink_responses = []
uplink_notifications = []

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping parameter acquisition test...")
    test_running = False

def create_illuminance_parameter_request(device_id: int) -> bytes:
    """Create illuminance sensor parameter acquisition downlink request
    
    Based on specification 6-4 パラメータ情報取得要求:
    - SensorID: 0x0000 (2 bytes) - End device main unit
    - CMD: 0x0D (1 byte) - Device information acquisition request  
    - Sequence No: 0xFFFF (2 bytes) - Fixed value
    - DATA: 0x00 (1 byte) - Parameter information acquisition request
    """
    # Common downlink request header (ルーター仕様書 5-2-1)
    protocol_version = 0x01
    packet_type = 0x00  # Downlink request
    unix_time = int(time.time())
    sensor_id = 0x0121  # Illuminance sensor
    cmd = 0x06  # GET_PARAMETER command
    order = 0x0000
    
    # Illuminance-specific parameter request data (6 bytes)
    param_data = struct.pack('<H', 0x0000)  # SensorID: End device main unit
    param_data += struct.pack('<B', 0x0D)   # CMD: Device information acquisition
    param_data += struct.pack('<H', 0xFFFF) # Sequence No: Fixed
    param_data += struct.pack('<B', 0x00)   # DATA: Parameter info acquisition
    
    data_length = len(param_data)
    
    # Build complete downlink request packet
    packet = struct.pack('<BB', protocol_version, packet_type)
    packet += struct.pack('<H', data_length)
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', device_id)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', cmd)
    packet += struct.pack('<H', order)
    packet += param_data
    
    return packet

def parse_downlink_response(data: bytes) -> dict:
    """Parse downlink response (Type: 0x01)"""
    try:
        if len(data) < 20:
            return {"error": "Response too short", "raw": data.hex(' ').upper()}
        
        protocol_version = data[0]
        packet_type = data[1]
        unix_time = struct.unpack('<L', data[2:6])[0]
        device_id = struct.unpack('<Q', data[6:14])[0]
        sensor_id = struct.unpack('<H', data[14:16])[0]
        order = struct.unpack('<H', data[16:18])[0]
        cmd = data[18]
        result = data[19]
        
        result_desc = get_result_description(result)
        
        return {
            "protocol_version": f"0x{protocol_version:02X}",
            "type": f"0x{packet_type:02X}",
            "type_name": "DOWNLINK_RESPONSE",
            "unix_time": unix_time,
            "timestamp": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
            "device_id": f"0x{device_id:016X}",
            "sensor_id": f"0x{sensor_id:04X}",
            "sensor_name": "Illuminance" if sensor_id == 0x0121 else f"Other(0x{sensor_id:04X})",
            "order": order,
            "cmd": f"0x{cmd:02X}",
            "cmd_name": get_cmd_name(cmd),
            "result": f"0x{result:02X}",
            "result_desc": result_desc,
            "success": result == 0x00,
            "raw": data.hex(' ').upper()
        }
        
    except Exception as e:
        return {"error": f"Parse error: {e}", "raw": data.hex(' ').upper()}

def parse_parameter_uplink(data: bytes) -> dict:
    """Parse parameter information uplink (based on spec 5-2)"""
    try:
        if len(data) < 21:
            return {"error": "Uplink too short"}
            
        # Common header
        sensor_id = struct.unpack('<H', data[16:18])[0]
        if sensor_id != 0x0121:
            return {"error": "Not illuminance sensor"}
            
        # Sensor data starts at index 21
        sensor_data = data[21:]
        if len(sensor_data) < 10:
            return {"error": "Insufficient sensor data"}
            
        # Parse based on 5-2 パラメータ情報 specification
        result = {}
        offset = 0
        
        # SensorID (2 bytes)
        if offset + 2 <= len(sensor_data):
            param_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result["param_sensor_id"] = f"0x{param_sensor_id:04X}"
            offset += 2
            
        # Sequence No (2 bytes)
        if offset + 2 <= len(sensor_data):
            sequence_no = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result["sequence_no"] = sequence_no
            offset += 2
            
        # Sensor Data section
        if offset + 2 <= len(sensor_data):
            connected_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result["connected_sensor_id"] = f"0x{connected_sensor_id:04X}"
            offset += 2
            
        # FW Version (3 bytes)
        if offset + 3 <= len(sensor_data):
            fw_version = sensor_data[offset:offset+3]
            result["fw_version"] = f"{fw_version[0]}.{fw_version[1]}.{fw_version[2]}"
            offset += 3
            
        # TimeZone (1 byte)
        if offset + 1 <= len(sensor_data):
            timezone = sensor_data[offset]
            result["timezone"] = timezone
            offset += 1
            
        # BLE Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            ble_mode = sensor_data[offset]
            result["ble_mode"] = ble_mode
            offset += 1
            
        # Tx Power (1 byte)
        if offset + 1 <= len(sensor_data):
            tx_power = sensor_data[offset]
            result["tx_power"] = tx_power
            offset += 1
            
        # Advertise Interval (2 bytes, little endian)
        if offset + 2 <= len(sensor_data):
            adv_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result["advertise_interval"] = adv_interval
            offset += 2
            
        # Sensor Uplink Interval (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
            result["sensor_uplink_interval"] = uplink_interval
            offset += 4
            
        # Sensor Read Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            read_mode = sensor_data[offset]
            result["sensor_read_mode"] = read_mode
            offset += 1
            
        # Sampling (1 byte)
        if offset + 1 <= len(sensor_data):
            sampling = sensor_data[offset]
            result["sampling"] = sampling
            offset += 1
            
        # HysteresisHigh (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            hysteresis_high = struct.unpack('<f', sensor_data[offset:offset+4])[0]
            result["hysteresis_high"] = hysteresis_high
            offset += 4
            
        # HysteresisLow (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            hysteresis_low = struct.unpack('<f', sensor_data[offset:offset+4])[0]
            result["hysteresis_low"] = hysteresis_low
            offset += 4
            
        return result
        
    except Exception as e:
        return {"error": f"Parameter parse error: {e}"}

def get_result_description(result: int) -> str:
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

def get_cmd_name(cmd: int) -> str:
    """Get command name"""
    commands = {
        0x00: "IMMEDIATE_UPLINK",
        0x05: "SET_PARAMETER",
        0x06: "GET_PARAMETER",
        0x07: "SENSOR_DFU",
        0x08: "DEVICE_RESET"
    }
    return commands.get(cmd, f"UNKNOWN(0x{cmd:02X})")

def on_data_received(data: bytes):
    """Callback for received data - distinguish between downlink responses and uplink notifications"""
    global downlink_responses, uplink_notifications
    
    if len(data) < 2:
        return
        
    packet_type = data[1]
    
    if packet_type == 0x01:  # Downlink response
        print(f"\n📥 Downlink Response: {data.hex(' ').upper()}")
        response = parse_downlink_response(data)
        downlink_responses.append(response)
        
        print(f"✅ Downlink Response Details:")
        print(f"   Device: {response.get('device_id', 'Unknown')}")
        print(f"   Sensor: {response.get('sensor_name', 'Unknown')}")
        print(f"   Command: {response.get('cmd_name', 'Unknown')}")
        print(f"   Result: {response.get('result_desc', 'Unknown')}")
        print(f"   Time: {response.get('timestamp', 'Unknown')}")
        
    elif packet_type == 0x00:  # Uplink notification
        # Check if this is illuminance sensor and might be parameter data
        if len(data) >= 18:
            sensor_id = struct.unpack('<H', data[16:18])[0]
            if sensor_id == 0x0121:  # Illuminance sensor
                device_id = struct.unpack('<Q', data[8:16])[0]
                print(f"\n📦 Illuminance Uplink: Device 0x{device_id:016X}")
                
                # Try to parse as parameter information
                param_info = parse_parameter_uplink(data)
                if "error" not in param_info:
                    print(f"🔍 Parameter Information Detected:")
                    print(f"   FW Version: {param_info.get('fw_version', 'Unknown')}")
                    print(f"   Uplink Interval: {param_info.get('sensor_uplink_interval', 'Unknown')} seconds")
                    print(f"   Advertise Interval: {param_info.get('advertise_interval', 'Unknown')}")
                    print(f"   Tx Power: {param_info.get('tx_power', 'Unknown')}")
                    print(f"   Hysteresis High: {param_info.get('hysteresis_high', 'Unknown')} lux")
                    print(f"   Hysteresis Low: {param_info.get('hysteresis_low', 'Unknown')} lux")
                    uplink_notifications.append(param_info)
                else:
                    print(f"📊 Regular sensor data (not parameter info)")
            else:
                print(f"📦 Other sensor uplink: 0x{sensor_id:04X}")
    else:
        print(f"📦 Other packet type: 0x{packet_type:02X}")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(status)

def main():
    """Main parameter acquisition test function"""
    global test_running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔬 BraveJIG Illuminance Parameter Acquisition Test")
    print("=" * 55)
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    # Known illuminance sensor device ID from previous tests
    illuminance_device_id = 0x2468800203400004
    
    print(f"🔧 Connecting to BraveJIG Router...")
    print(f"   Target: Illuminance Sensor (0x{illuminance_device_id:016X})")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            monitor.start_monitoring()
            
            print(f"\n📤 Sending parameter acquisition request...")
            
            # Create and send parameter acquisition request
            request_packet = create_illuminance_parameter_request(illuminance_device_id)
            print(f"   Request: {request_packet.hex(' ').upper()}")
            
            if monitor.send(request_packet):
                print(f"   ✅ Request sent successfully")
            else:
                print(f"   ❌ Failed to send request")
                return False
            
            print(f"\n⏳ Monitoring for downlink response and parameter uplink...")
            print(f"   Watching for Type: 0x01 (Downlink Response)")
            print(f"   Watching for Type: 0x00 (Parameter Uplink)")
            print(f"   Duration: 90 seconds")
            
            # Monitor for responses (90 seconds to catch 60-second uplink cycle)
            start_time = time.time()
            response_received = False
            
            while test_running and monitor.is_monitoring and (time.time() - start_time) < 90:
                # Check if we received a downlink response
                if downlink_responses and not response_received:
                    response_received = True
                    print(f"\n✅ Downlink response received! Continuing to monitor for parameter uplink...")
                
                time.sleep(0.1)
            
            # Summary
            print(f"\n📊 Test Summary:")
            print(f"   Downlink responses: {len(downlink_responses)}")
            print(f"   Parameter uplinks: {len(uplink_notifications)}")
            
            if downlink_responses:
                print(f"\n📋 Downlink Response Details:")
                for i, response in enumerate(downlink_responses):
                    success = "✅ Success" if response.get('success', False) else "❌ Failed"
                    print(f"   {i+1}. {response.get('sensor_name', 'Unknown')} - {response.get('result_desc', 'Unknown')} ({success})")
            
            if uplink_notifications:
                print(f"\n📋 Parameter Information:")
                for i, param in enumerate(uplink_notifications):
                    print(f"   {i+1}. FW: {param.get('fw_version', 'Unknown')}, Interval: {param.get('sensor_uplink_interval', 'Unknown')}s")
            
            # Communication stats
            stats = monitor.statistics
            print(f"\n📈 Communication Statistics:")
            print(f"   Bytes sent: {stats['bytes_sent']}")
            print(f"   Bytes received: {stats['bytes_received']}")
            
            # Test result
            success = len(downlink_responses) > 0 and any(r.get('success', False) for r in downlink_responses)
            return success
            
    except Exception as e:
        print(f"❌ Parameter acquisition test failed: {e}")
        return False
    
    print("🏁 Parameter acquisition test completed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
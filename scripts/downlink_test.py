#!/usr/bin/env python3
"""
Downlink Request Test

Test downlink requests to communicate with paired sensor modules.
"""

import time
import signal
import struct
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global flag for graceful shutdown
test_running = True
responses_received = []

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping downlink test...")
    test_running = False

def create_downlink_request(device_id: int, sensor_id: int, cmd: int, data: bytes = b'') -> bytes:
    """Create downlink request packet"""
    protocol_version = 0x01
    packet_type = 0x00
    data_length = len(data)
    unix_time = int(time.time())
    order = 0x0000
    
    packet = struct.pack('<BB', protocol_version, packet_type)
    packet += struct.pack('<H', data_length)
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', device_id)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', cmd)
    packet += struct.pack('<H', order)
    packet += data
    
    return packet

def parse_downlink_response(data: bytes) -> dict:
    """Parse downlink response"""
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
            "type_name": "DOWNLINK_RESPONSE" if packet_type == 0x01 else "UNKNOWN",
            "unix_time": unix_time,
            "timestamp": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
            "device_id": f"0x{device_id:016X}",
            "sensor_id": f"0x{sensor_id:04X}",
            "sensor_name": get_sensor_name(sensor_id),
            "order": order,
            "cmd": f"0x{cmd:02X}",
            "cmd_name": get_cmd_name(cmd),
            "result": f"0x{result:02X}",
            "result_desc": result_desc,
            "raw": data.hex(' ').upper()
        }
        
    except Exception as e:
        return {"error": f"Parse error: {e}", "raw": data.hex(' ').upper()}

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

def get_sensor_name(sensor_id: int) -> str:
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
    """Callback for received data"""
    global responses_received
    
    print(f"\n📥 Received {len(data)} bytes: {data.hex(' ').upper()}")
    
    # Check if this looks like a downlink response
    if len(data) >= 2 and data[1] == 0x01:  # Downlink response type
        response = parse_downlink_response(data)
        responses_received.append(response)
        
        print(f"✅ Downlink Response:")
        print(f"   Device: {response.get('device_id', 'Unknown')}")
        print(f"   Sensor: {response.get('sensor_name', 'Unknown')}")
        print(f"   Command: {response.get('cmd_name', 'Unknown')}")
        print(f"   Result: {response.get('result_desc', 'Unknown')}")
        print(f"   Time: {response.get('timestamp', 'Unknown')}")
        
    else:
        # Regular uplink notification - extract basic info
        if len(data) >= 18:
            try:
                device_id = struct.unpack('<Q', data[8:16])[0]
                sensor_id = struct.unpack('<H', data[16:18])[0]
                sensor_name = get_sensor_name(sensor_id)
                print(f"📦 Uplink from {sensor_name} (Device: 0x{device_id:016X})")
            except:
                print(f"📦 Uplink notification (parsing failed)")
        else:
            print(f"📦 Unknown packet")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(status)

def main():
    """Main downlink test function"""
    global test_running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("📡 BraveJIG Downlink Request Test")
    print("=" * 40)
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router...")
    
    # Known device IDs from previous tests
    test_devices = [
        (0x2468800203400004, 0x0121, "Illuminance"),
        (0x2468800205400011, 0x0123, "Temperature/Humidity"),
        (0x2468800206400006, 0x0124, "Barometric Pressure"),
        (0x246880020440000F, 0x0122, "Accelerometer"),
        (0x2468800207400001, 0x0125, "Distance/Ranging")
    ]
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            monitor.start_monitoring()
            
            print(f"\n📤 Sending immediate uplink requests to {len(test_devices)} devices...")
            
            for device_id, sensor_id, sensor_name in test_devices:
                if not test_running:
                    break
                    
                print(f"\n🚀 Requesting immediate uplink from {sensor_name}")
                print(f"   Device ID: 0x{device_id:016X}")
                print(f"   Sensor ID: 0x{sensor_id:04X}")
                
                # Create immediate uplink request (CMD 0x00, no data)
                packet = create_downlink_request(device_id, sensor_id, 0x00)
                print(f"   Data: {packet.hex(' ').upper()}")
                
                if monitor.send(packet):
                    print(f"   ✅ Request sent successfully")
                else:
                    print(f"   ❌ Failed to send request")
                
                # Wait for response (up to 5 seconds)
                response_start = time.time()
                initial_responses = len(responses_received)
                
                while (time.time() - response_start) < 5 and test_running:
                    if len(responses_received) > initial_responses:
                        break
                    time.sleep(0.1)
                
                if len(responses_received) <= initial_responses:
                    print(f"   ⚠️  No response received within 5 seconds")
                
                # Wait between requests
                time.sleep(2)
            
            # Monitor for additional responses
            print(f"\n⏳ Waiting for any additional responses...")
            time.sleep(5)
            
            # Summary
            print(f"\n📊 Test Summary:")
            print(f"   Devices tested: {len(test_devices)}")
            print(f"   Responses received: {len(responses_received)}")
            
            if responses_received:
                print(f"\n📋 Received Responses:")
                success_count = 0
                for i, response in enumerate(responses_received):
                    result_desc = response.get('result_desc', 'Unknown')
                    if result_desc == "Success":
                        success_count += 1
                    print(f"   {i+1}. {response.get('sensor_name', 'Unknown')} - {result_desc}")
                
                print(f"\n✅ Success rate: {success_count}/{len(responses_received)} ({100*success_count/len(responses_received):.1f}%)")
            
            # Communication stats
            stats = monitor.statistics
            print(f"\n📈 Communication Statistics:")
            print(f"   Bytes sent: {stats['bytes_sent']}")
            print(f"   Bytes received: {stats['bytes_received']}")
            
    except Exception as e:
        print(f"❌ Downlink test failed: {e}")
        return False
    
    print("🏁 Downlink test completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Illuminance Sensor Command Discovery Test

Systematically test all possible commands for illuminance sensor to discover supported ones
and capture true downlink responses (Type: 0x01).
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
test_results = []

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping command discovery test...")
    test_running = False

def create_downlink_request(device_id: int, sensor_id: int, cmd: int, data: bytes = b'') -> bytes:
    """Create downlink request packet"""
    protocol_version = 0x01
    packet_type = 0x00  # Downlink request
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
        
        return {
            "protocol_version": f"0x{protocol_version:02X}",
            "type": f"0x{packet_type:02X}",
            "type_name": "DOWNLINK_RESPONSE",
            "unix_time": unix_time,
            "timestamp": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
            "device_id": f"0x{device_id:016X}",
            "sensor_id": f"0x{sensor_id:04X}",
            "order": order,
            "cmd": f"0x{cmd:02X}",
            "cmd_name": get_cmd_name(cmd),
            "result": f"0x{result:02X}",
            "result_desc": get_result_description(result),
            "success": result == 0x00,
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

def get_cmd_name(cmd: int) -> str:
    """Get command name"""
    commands = {
        0x00: "IMMEDIATE_UPLINK",
        0x05: "SET_PARAMETER", 
        0x06: "GET_PARAMETER",
        0x07: "SENSOR_DFU",
        0x08: "DEVICE_RESET",
        0x0D: "GET_DEVICE_SETTING"  # From illuminance spec 6-4
    }
    return commands.get(cmd, f"UNKNOWN(0x{cmd:02X})")

def create_test_commands(device_id: int) -> list:
    """Create list of test commands to try"""
    sensor_id = 0x0121  # Illuminance sensor
    
    commands = [
        # Standard commands
        {"cmd": 0x00, "name": "IMMEDIATE_UPLINK", "data": b''},
        {"cmd": 0x05, "name": "SET_PARAMETER", "data": b''},
        {"cmd": 0x06, "name": "GET_PARAMETER", "data": b''},
        {"cmd": 0x07, "name": "SENSOR_DFU", "data": b''},
        {"cmd": 0x08, "name": "DEVICE_RESET", "data": b''},
        
        # Illuminance-specific commands from spec 6-4
        {"cmd": 0x06, "name": "GET_PARAMETER_WITH_DATA", "data": struct.pack('<HBHB', 0x0000, 0x0D, 0xFFFF, 0x00)},
        
        # Try other possible commands
        {"cmd": 0x0D, "name": "GET_DEVICE_SETTING", "data": b''},
        {"cmd": 0x01, "name": "TEST_CMD_01", "data": b''},
        {"cmd": 0x02, "name": "TEST_CMD_02", "data": b''},
        {"cmd": 0x03, "name": "TEST_CMD_03", "data": b''},
        {"cmd": 0x04, "name": "TEST_CMD_04", "data": b''},
        {"cmd": 0x09, "name": "TEST_CMD_09", "data": b''},
        {"cmd": 0x0A, "name": "TEST_CMD_0A", "data": b''},
        {"cmd": 0x0B, "name": "TEST_CMD_0B", "data": b''},
        {"cmd": 0x0C, "name": "TEST_CMD_0C", "data": b''},
        {"cmd": 0x0E, "name": "TEST_CMD_0E", "data": b''},
        {"cmd": 0x0F, "name": "TEST_CMD_0F", "data": b''}
    ]
    
    return commands

def on_data_received(data: bytes):
    """Callback for received data - focus on downlink responses"""
    global downlink_responses
    
    if len(data) < 2:
        return
        
    packet_type = data[1]
    
    if packet_type == 0x01:  # Downlink response - THIS IS WHAT WE WANT
        print(f"\n✅ DOWNLINK RESPONSE DETECTED!")
        print(f"   Raw: {data.hex(' ').upper()}")
        
        response = parse_downlink_response(data)
        downlink_responses.append(response)
        
        print(f"   Command: {response.get('cmd_name', 'Unknown')} ({response.get('cmd', 'Unknown')})")
        print(f"   Result: {response.get('result_desc', 'Unknown')} ({response.get('result', 'Unknown')})")
        print(f"   Device: {response.get('device_id', 'Unknown')}")
        print(f"   Time: {response.get('timestamp', 'Unknown')}")
        
    elif packet_type == 0x00:  # Uplink notification - ignore for now
        if len(data) >= 18:
            sensor_id = struct.unpack('<H', data[16:18])[0]
            if sensor_id == 0x0121:
                print(f"📦 Illuminance uplink (ignoring)")
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
    """Main command discovery function"""
    global test_running, test_results
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔍 BraveJIG Illuminance Command Discovery Test")
    print("=" * 55)
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    # Known illuminance sensor device ID
    illuminance_device_id = 0x2468800203400004
    
    print(f"🎯 Target: Illuminance Sensor (0x{illuminance_device_id:016X})")
    print(f"📡 Systematically testing all possible commands...")
    
    # Create test commands
    test_commands = create_test_commands(illuminance_device_id)
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            monitor.start_monitoring()
            
            print(f"\n🚀 Testing {len(test_commands)} commands...")
            print(f"   Looking for Type: 0x01 (DOWNLINK_RESPONSE)")
            
            for i, cmd_info in enumerate(test_commands):
                if not test_running:
                    break
                
                cmd = cmd_info["cmd"]
                name = cmd_info["name"]
                data = cmd_info["data"]
                
                print(f"\n📤 Test {i+1}/{len(test_commands)}: {name} (0x{cmd:02X})")
                
                # Create and send request
                packet = create_downlink_request(illuminance_device_id, 0x0121, cmd, data)
                print(f"   Request: {packet.hex(' ').upper()}")
                
                # Track responses before sending
                initial_responses = len(downlink_responses)
                
                if monitor.send(packet):
                    print(f"   ✅ Sent")
                else:
                    print(f"   ❌ Send failed")
                    continue
                
                # Wait for response (5 seconds max)
                response_start = time.time()
                response_received = False
                
                while (time.time() - response_start) < 5 and test_running:
                    if len(downlink_responses) > initial_responses:
                        response_received = True
                        break
                    time.sleep(0.1)
                
                # Record result
                result = {
                    "command": name,
                    "cmd_code": f"0x{cmd:02X}",
                    "data_length": len(data),
                    "response_received": response_received,
                    "response_time": time.time() - response_start if response_received else None
                }
                
                if response_received:
                    latest_response = downlink_responses[-1]
                    result.update({
                        "result_code": latest_response.get('result', 'Unknown'),
                        "result_desc": latest_response.get('result_desc', 'Unknown'),
                        "success": latest_response.get('success', False)
                    })
                    print(f"   ✅ Response: {latest_response.get('result_desc', 'Unknown')}")
                else:
                    print(f"   ⚠️  No response within 5 seconds")
                
                test_results.append(result)
                
                # Wait between commands
                time.sleep(1)
            
            # Summary
            print(f"\n📊 Command Discovery Summary:")
            print(f"   Commands tested: {len(test_results)}")
            print(f"   Responses received: {len(downlink_responses)}")
            
            # Show supported commands
            supported_commands = [r for r in test_results if r.get('response_received', False)]
            successful_commands = [r for r in test_results if r.get('success', False)]
            
            print(f"\n✅ Commands that received responses:")
            for cmd in supported_commands:
                status = "SUCCESS" if cmd.get('success', False) else cmd.get('result_desc', 'FAILED')
                print(f"   • {cmd['command']} ({cmd['cmd_code']}) - {status}")
            
            if successful_commands:
                print(f"\n🎉 Successfully executed commands:")
                for cmd in successful_commands:
                    print(f"   • {cmd['command']} ({cmd['cmd_code']})")
            
            print(f"\n📋 All Downlink Responses:")
            for i, response in enumerate(downlink_responses):
                success_icon = "✅" if response.get('success', False) else "❌"
                print(f"   {i+1}. {success_icon} {response.get('cmd_name', 'Unknown')} - {response.get('result_desc', 'Unknown')}")
            
            # Communication stats
            stats = monitor.statistics
            print(f"\n📈 Communication Statistics:")
            print(f"   Bytes sent: {stats['bytes_sent']}")
            print(f"   Bytes received: {stats['bytes_received']}")
            
            return len(supported_commands) > 0
            
    except Exception as e:
        print(f"❌ Command discovery test failed: {e}")
        return False
    
    print("🏁 Command discovery test completed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
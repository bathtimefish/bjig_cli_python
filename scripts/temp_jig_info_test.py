#!/usr/bin/env python3
"""
JIG INFO Command Test

Test JIG INFO commands to interact with BraveJIG Router directly.
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
    print("\n🛑 Stopping JIG INFO test...")
    test_running = False

def create_jig_info_request(cmd: int) -> bytes:
    """Create JIG INFO request packet"""
    protocol_version = 0x01
    packet_type = 0x01
    local_time = int(time.time()) + 9*3600  # JST (UTC+9)
    unix_time = int(time.time())
    
    packet = struct.pack('<BBB', protocol_version, packet_type, cmd)
    packet += struct.pack('<L', local_time)
    packet += struct.pack('<L', unix_time)
    
    return packet

def parse_jig_info_response(data: bytes) -> dict:
    """Parse JIG INFO response"""
    try:
        if len(data) < 15:
            return {"error": "Response too short", "raw": data.hex(' ').upper()}
        
        protocol_version = data[0]
        packet_type = data[1]
        unix_time = struct.unpack('<L', data[2:6])[0]
        cmd = data[6]
        router_device_id = struct.unpack('<Q', data[7:15])[0]
        response_data = data[15:] if len(data) > 15 else b''
        
        result = {
            "protocol_version": f"0x{protocol_version:02X}",
            "type": f"0x{packet_type:02X}",
            "type_name": "JIG_INFO_RESPONSE" if packet_type == 0x02 else "UNKNOWN",
            "unix_time": unix_time,
            "timestamp": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
            "cmd": f"0x{cmd:02X}",
            "cmd_name": get_cmd_name(cmd),
            "router_device_id": f"0x{router_device_id:016X}",
            "response_data": response_data.hex(' ').upper() if response_data else "None",
            "raw": data.hex(' ').upper()
        }
        
        # Parse specific responses
        if cmd == 0x02 and len(response_data) >= 3:  # FW Version
            major = response_data[0]
            minor = response_data[1]
            build = response_data[2]
            result["firmware_version"] = f"{major}.{minor}.{build}"
        elif cmd == 0x67 and len(response_data) >= 1:  # Scan Mode
            mode = response_data[0]
            mode_name = "Long Range" if mode == 0x00 else "Legacy" if mode == 0x01 else "Unknown"
            result["scan_mode"] = f"0x{mode:02X} ({mode_name})"
        elif cmd in [0x00, 0x01] and len(response_data) >= 1:  # Start/Stop
            success = response_data[0]
            result["result"] = "Success" if success == 0x01 else "Failed"
        
        return result
        
    except Exception as e:
        return {"error": f"Parse error: {e}", "raw": data.hex(' ').upper()}

def get_cmd_name(cmd: int) -> str:
    """Get command name"""
    commands = {
        0x00: "STOP",
        0x01: "START", 
        0x02: "FW_VERSION_GET",
        0x67: "SCAN_MODE_GET",
        0x69: "SCAN_MODE_SET_LONG_RANGE",
        0x6A: "SCAN_MODE_SET_LEGACY"
    }
    return commands.get(cmd, f"UNKNOWN(0x{cmd:02X})")

def on_data_received(data: bytes):
    """Callback for received data"""
    global responses_received
    
    print(f"\n📥 Received {len(data)} bytes: {data.hex(' ').upper()}")
    
    # Check if this looks like a JIG INFO response
    if len(data) >= 2 and data[1] == 0x02:  # JIG INFO response type
        response = parse_jig_info_response(data)
        responses_received.append(response)
        
        print(f"✅ JIG INFO Response:")
        print(f"   Command: {response.get('cmd_name', 'Unknown')}")
        print(f"   Time: {response.get('timestamp', 'Unknown')}")
        print(f"   Router ID: {response.get('router_device_id', 'Unknown')}")
        
        if 'firmware_version' in response:
            print(f"   🔧 Firmware Version: {response['firmware_version']}")
        elif 'scan_mode' in response:
            print(f"   📡 Scan Mode: {response['scan_mode']}")
        elif 'result' in response:
            print(f"   📋 Result: {response['result']}")
        
    else:
        # Regular uplink notification
        print(f"📦 Uplink notification (ignoring for this test)")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(status)

def main():
    """Main JIG INFO test function"""
    global test_running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🔧 BraveJIG JIG INFO Command Test")
    print("=" * 40)
    
    port = '/dev/tty.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router...")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            monitor.start_monitoring()
            
            # Test commands
            test_commands = [
                (0x02, "Get Firmware Version"),
                (0x67, "Get Scan Mode"),
                (0x00, "Stop Router"),
                (0x01, "Start Router")
            ]
            
            print(f"\n📤 Sending JIG INFO commands...")
            
            for cmd, description in test_commands:
                if not test_running:
                    break
                    
                print(f"\n🚀 Sending: {description} (CMD: 0x{cmd:02X})")
                
                packet = create_jig_info_request(cmd)
                print(f"   Data: {packet.hex(' ').upper()}")
                
                if monitor.send(packet):
                    print(f"   ✅ Command sent successfully")
                else:
                    print(f"   ❌ Failed to send command")
                
                # Wait for response (up to 3 seconds)
                response_start = time.time()
                initial_responses = len(responses_received)
                
                while (time.time() - response_start) < 3 and test_running:
                    if len(responses_received) > initial_responses:
                        break
                    time.sleep(0.1)
                
                if len(responses_received) <= initial_responses:
                    print(f"   ⚠️  No response received within 3 seconds")
                
                # Wait a bit between commands
                time.sleep(1)
            
            # Monitor for a few more seconds to catch any delayed responses
            print(f"\n⏳ Waiting for any additional responses...")
            time.sleep(3)
            
            # Summary
            print(f"\n📊 Test Summary:")
            print(f"   Commands sent: {len(test_commands)}")
            print(f"   Responses received: {len(responses_received)}")
            
            if responses_received:
                print(f"\n📋 Received Responses:")
                for i, response in enumerate(responses_received):
                    print(f"   {i+1}. {response.get('cmd_name', 'Unknown')} at {response.get('timestamp', 'Unknown')}")
                    if 'firmware_version' in response:
                        print(f"      Firmware: {response['firmware_version']}")
                    elif 'scan_mode' in response:
                        print(f"      Scan Mode: {response['scan_mode']}")
                    elif 'result' in response:
                        print(f"      Result: {response['result']}")
            
            # Communication stats
            stats = monitor.statistics
            print(f"\n📈 Communication Statistics:")
            print(f"   Bytes sent: {stats['bytes_sent']}")
            print(f"   Bytes received: {stats['bytes_received']}")
            
    except Exception as e:
        print(f"❌ JIG INFO test failed: {e}")
        return False
    
    print("🏁 JIG INFO test completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Downlink Response Hex Analysis and Parameter Information Monitoring

Analyze the received downlink response hex string and monitor for subsequent
parameter information uplink notification (SensorID: 0x0000).
"""

import time
import struct
import json
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage
parameter_uplink_received = False
parameter_data = None

def analyze_hex_response(hex_string: str) -> dict:
    """Analyze the downlink response hex string"""
    # Convert hex string to bytes
    hex_clean = hex_string.replace(' ', '')
    data = bytes.fromhex(hex_clean)
    
    print(f"📊 Downlink Response Analysis")
    print(f"=" * 50)
    print(f"Raw hex: {hex_string}")
    print(f"Total length: {len(data)} bytes")
    print(f"Expected length: 20 bytes (fixed)")
    print(f"Length valid: {'✅' if len(data) == 20 else '❌'}")
    print()
    
    if len(data) < 20:
        return {"error": "Response too short"}
    
    # Parse each field
    analysis = {}
    
    # Protocol Version (1 byte)
    protocol_version = data[0]
    print(f"Protocol Version: 0x{protocol_version:02X} ({'✅ Valid' if protocol_version == 0x01 else '❌ Invalid'})")
    analysis["protocol_version"] = {"value": protocol_version, "valid": protocol_version == 0x01}
    
    # Type (1 byte)
    packet_type = data[1]
    type_name = "DOWNLINK_RESPONSE" if packet_type == 0x01 else f"OTHER(0x{packet_type:02X})"
    print(f"Packet Type: 0x{packet_type:02X} ({type_name}) ({'✅ Valid' if packet_type == 0x01 else '❌ Invalid'})")
    analysis["packet_type"] = {"value": packet_type, "name": type_name, "valid": packet_type == 0x01}
    
    # Unix Time (4 bytes, little endian)
    unix_time_bytes = data[2:6]
    unix_time = struct.unpack('<L', unix_time_bytes)[0]
    timestamp = datetime.fromtimestamp(unix_time)
    print(f"Unix Time: 0x{unix_time:08X} ({unix_time})")
    print(f"  → {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    analysis["unix_time"] = {"value": unix_time, "timestamp": timestamp.isoformat()}
    
    # Device ID (8 bytes, little endian)
    device_id_bytes = data[6:14]
    device_id = struct.unpack('<Q', device_id_bytes)[0]
    print(f"Device ID: 0x{device_id:016X}")
    analysis["device_id"] = {"value": device_id, "hex": f"0x{device_id:016X}"}
    
    # Sensor ID (2 bytes, little endian)
    sensor_id_bytes = data[14:16]
    sensor_id = struct.unpack('<H', sensor_id_bytes)[0]
    sensor_name = "Illuminance" if sensor_id == 0x0121 else f"Other(0x{sensor_id:04X})"
    print(f"Sensor ID: 0x{sensor_id:04X} ({sensor_name}) ({'✅ Expected' if sensor_id == 0x0000 else '❌ Unexpected'})")
    analysis["sensor_id"] = {"value": sensor_id, "name": sensor_name, "expected_0x0000": sensor_id == 0x0000}
    
    # Order (2 bytes, little endian)
    order_bytes = data[16:18]
    order = struct.unpack('<H', order_bytes)[0]
    print(f"Order: 0x{order:04X} ({order})")
    analysis["order"] = {"value": order}
    
    # CMD (1 byte)
    cmd = data[18]
    cmd_name = get_cmd_name(cmd)
    print(f"Command: 0x{cmd:02X} ({cmd_name}) ({'✅ Expected' if cmd == 0x0D else '❌ Unexpected'})")
    analysis["cmd"] = {"value": cmd, "name": cmd_name, "expected_0x0D": cmd == 0x0D}
    
    # Result (1 byte)
    result = data[19]
    result_desc = get_result_description(result)
    success = result == 0x00
    print(f"Result: 0x{result:02X} ({result_desc}) ({'✅ Success' if success else '❌ Failed'})")
    analysis["result"] = {"value": result, "description": result_desc, "success": success}
    
    print()
    print("📋 Summary:")
    print(f"  Valid downlink response: {'✅' if packet_type == 0x01 and len(data) == 20 else '❌'}")
    print(f"  Command executed successfully: {'✅' if success else '❌'}")
    print(f"  Parameter acquisition request: {'✅ Successful' if success and cmd == 0x0D else '❌ Failed'}")
    
    # Check for unusual aspects
    print()
    print("🔍 Analysis Notes:")
    if sensor_id == 0x0000:
        print("  ✅ Sensor ID is 0x0000 as expected for parameter acquisition")
    else:
        print(f"  ⚠️  Sensor ID is 0x{sensor_id:04X}, expected 0x0000 for parameter acquisition")
    
    if cmd == 0x0D:
        print("  ✅ Command is 0x0D (GET_DEVICE_SETTING) as expected")
    else:
        print(f"  ⚠️  Command is 0x{cmd:02X}, expected 0x0D for parameter acquisition")
    
    if success:
        print("  ✅ Result indicates successful execution")
        print("  📡 Parameter information should be sent via uplink notification soon")
    else:
        print(f"  ❌ Command failed: {result_desc}")
    
    return analysis

def get_cmd_name(cmd: int) -> str:
    """Get command name"""
    commands = {
        0x00: "IMMEDIATE_UPLINK",
        0x05: "SET_PARAMETER",
        0x06: "GET_PARAMETER",
        0x07: "SENSOR_DFU",
        0x08: "DEVICE_RESET",
        0x0D: "GET_DEVICE_SETTING"
    }
    return commands.get(cmd, f"UNKNOWN(0x{cmd:02X})")

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
    return descriptions.get(result, f"Unknown(0x{result:02X})")

def parse_parameter_information(data: bytes) -> dict:
    """Parse parameter information uplink according to illuminance spec 5-2"""
    try:
        if len(data) < 21:
            return {"error": "Packet too short for uplink"}
        
        # Verify this is an uplink notification (Type: 0x00)
        packet_type = data[1]
        if packet_type != 0x00:
            return {"error": f"Not uplink notification, got type 0x{packet_type:02X}"}
        
        # Verify sensor ID is 0x0000 (parameter information identifier)
        sensor_id = struct.unpack('<H', data[16:18])[0]
        if sensor_id != 0x0000:
            return {"error": f"Not parameter info, sensor ID is 0x{sensor_id:04X}"}
        
        print(f"📡 Parameter Information Uplink Detected!")
        print(f"   Raw: {data.hex(' ').upper()}")
        print(f"   Type: 0x{packet_type:02X} (UPLINK_NOTIFICATION)")
        print(f"   Sensor ID: 0x{sensor_id:04X} (Parameter Information)")
        
        # Parse common uplink header
        data_length = struct.unpack('<H', data[2:4])[0]
        unix_time = struct.unpack('<L', data[4:8])[0]
        device_id = struct.unpack('<Q', data[8:16])[0]
        rssi = data[18] if data[18] < 128 else data[18] - 256
        order = struct.unpack('<H', data[19:21])[0]
        
        # Sensor data starts at index 21
        sensor_data = data[21:]
        
        print(f"   Device ID: 0x{device_id:016X}")
        print(f"   Data Length: {data_length} bytes")
        print(f"   Sensor Data: {len(sensor_data)} bytes")
        
        result = {
            "packet_info": {
                "type": "PARAMETER_INFORMATION_UPLINK",
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).isoformat(),
                "rssi": f"{rssi} dBm",
                "order": order,
                "data_length": data_length,
                "sensor_data_length": len(sensor_data),
                "raw_packet": data.hex(' ').upper()
            }
        }
        
        # Parse Sensor Data according to spec 5-2
        if len(sensor_data) < 10:
            result["error"] = "Insufficient sensor data for parameter parsing"
            return result
        
        offset = 0
        param_info = {}
        
        # SensorID (2 bytes) - エンドデバイス本体 (should be 0x0000)
        if offset + 2 <= len(sensor_data):
            end_device_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            param_info["end_device_sensor_id"] = {
                "value": f"0x{end_device_sensor_id:04X}",
                "expected": "0x0000",
                "valid": end_device_sensor_id == 0x0000,
                "description": "エンドデバイス本体"
            }
            offset += 2
        
        # Sequence No (2 bytes) - Fixed 0xFFFF
        if offset + 2 <= len(sensor_data):
            sequence_no = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            param_info["sequence_no"] = {
                "value": f"0x{sequence_no:04X}",
                "decimal": sequence_no,
                "expected": "0xFFFF",
                "valid": sequence_no == 0xFFFF,
                "description": "シーケンス番号（固定値）"
            }
            offset += 2
        
        # === Sensor Data section (照度モジュールパラメータ情報) ===
        sensor_data_info = {}
        
        # Connected Sensor ID (2 bytes) - 0x0121 (illuminance)
        if offset + 2 <= len(sensor_data):
            connected_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            sensor_data_info["connected_sensor_id"] = {
                "value": f"0x{connected_sensor_id:04X}",
                "name": "Illuminance" if connected_sensor_id == 0x0121 else f"Other(0x{connected_sensor_id:04X})",
                "expected": "0x0121",
                "valid": connected_sensor_id == 0x0121,
                "description": "本製品に接続されているSensorのSensorID"
            }
            offset += 2
        
        # FW Version (3 bytes)
        if offset + 3 <= len(sensor_data):
            fw_bytes = sensor_data[offset:offset+3]
            fw_version = f"{fw_bytes[0]}.{fw_bytes[1]}.{fw_bytes[2]}"
            sensor_data_info["fw_version"] = {
                "value": fw_version,
                "major": fw_bytes[0],
                "minor": fw_bytes[1],
                "patch": fw_bytes[2],
                "raw_bytes": fw_bytes.hex(' ').upper(),
                "description": "本製品のFWバージョン"
            }
            offset += 3
        
        # TimeZone (1 byte)
        if offset + 1 <= len(sensor_data):
            timezone = sensor_data[offset]
            sensor_data_info["timezone"] = {
                "value": timezone,
                "hex": f"0x{timezone:02X}",
                "description": "タイムゾーン設定"
            }
            offset += 1
        
        # BLE Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            ble_mode = sensor_data[offset]
            sensor_data_info["ble_mode"] = {
                "value": ble_mode,
                "hex": f"0x{ble_mode:02X}",
                "description": "Bluetooth LE通信モードの設定情報"
            }
            offset += 1
        
        # Tx Power (1 byte)
        if offset + 1 <= len(sensor_data):
            tx_power = sensor_data[offset]
            sensor_data_info["tx_power"] = {
                "value": tx_power,
                "hex": f"0x{tx_power:02X}",
                "description": "Bluetooth LE通信の送信電波出力"
            }
            offset += 1
        
        # Advertise Interval (2 bytes, little endian)
        if offset + 2 <= len(sensor_data):
            adv_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            sensor_data_info["advertise_interval"] = {
                "value": adv_interval,
                "hex": f"0x{adv_interval:04X}",
                "raw_bytes": sensor_data[offset:offset+2].hex(' ').upper(),
                "description": "Advertiseを発信する間隔",
                "encoding": "リトルエンディアン"
            }
            offset += 2
        
        # Sensor Uplink Interval (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
            sensor_data_info["sensor_uplink_interval"] = {
                "value": uplink_interval,
                "unit": "seconds",
                "hex": f"0x{uplink_interval:08X}",
                "raw_bytes": sensor_data[offset:offset+4].hex(' ').upper(),
                "description": "Sensor情報データをUplinkする間隔",
                "encoding": "リトルエンディアン"
            }
            offset += 4
        
        # Sensor Read Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            read_mode = sensor_data[offset]
            sensor_data_info["sensor_read_mode"] = {
                "value": read_mode,
                "hex": f"0x{read_mode:02X}",
                "description": "計測モード"
            }
            offset += 1
        
        # Sampling (1 byte)
        if offset + 1 <= len(sensor_data):
            sampling = sensor_data[offset]
            sensor_data_info["sampling"] = {
                "value": sampling,
                "hex": f"0x{sampling:02X}",
                "description": "サンプリング周期"
            }
            offset += 1
        
        # HysteresisHigh (4 bytes, little endian, IEEE 754 Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_high_bytes = sensor_data[offset:offset+4]
            hysteresis_high = struct.unpack('<f', hysteresis_high_bytes)[0]
            sensor_data_info["hysteresis_high"] = {
                "value": hysteresis_high,
                "unit": "Lux",
                "hex": f"0x{struct.unpack('<L', hysteresis_high_bytes)[0]:08X}",
                "raw_bytes": hysteresis_high_bytes.hex(' ').upper(),
                "description": "ヒステリシス(High):照度(Lux)",
                "encoding": "リトルエンディアン IEEE 754 Float"
            }
            offset += 4
        
        # HysteresisLow (4 bytes, little endian, IEEE 754 Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_low_bytes = sensor_data[offset:offset+4]
            hysteresis_low = struct.unpack('<f', hysteresis_low_bytes)[0]
            sensor_data_info["hysteresis_low"] = {
                "value": hysteresis_low,
                "unit": "Lux",
                "hex": f"0x{struct.unpack('<L', hysteresis_low_bytes)[0]:08X}",
                "raw_bytes": hysteresis_low_bytes.hex(' ').upper(),
                "description": "ヒステリシス(Low):照度(Lux)",
                "encoding": "リトルエンディアン IEEE 754 Float"
            }
            offset += 4
        
        # Check for remaining data
        if offset < len(sensor_data):
            remaining_data = sensor_data[offset:]
            sensor_data_info["remaining_data"] = {
                "length": len(remaining_data),
                "raw_bytes": remaining_data.hex(' ').upper(),
                "description": "仕様書に記載されていない追加データ"
            }
        
        result["parameter_information"] = param_info
        result["sensor_data"] = sensor_data_info
        
        # Validation summary
        result["validation"] = {
            "valid_parameter_uplink": True,
            "end_device_sensor_id_valid": param_info.get("end_device_sensor_id", {}).get("valid", False),
            "sequence_no_valid": param_info.get("sequence_no", {}).get("valid", False),
            "connected_sensor_id_valid": sensor_data_info.get("connected_sensor_id", {}).get("valid", False)
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Parameter parsing error: {e}", "raw": data.hex(' ').upper()}

def on_data_received(data: bytes):
    """Callback for monitoring parameter information uplink"""
    global parameter_uplink_received, parameter_data
    
    if len(data) < 18:
        return
    
    packet_type = data[1]
    
    if packet_type == 0x00:  # Uplink notification
        sensor_id = struct.unpack('<H', data[16:18])[0]
        
        if sensor_id == 0x0000:  # Parameter information uplink
            print(f"\n🎯 Parameter Information Uplink Detected!")
            parameter_data = parse_parameter_information(data)
            parameter_uplink_received = True
        else:
            print(f"📦 Other sensor uplink: 0x{sensor_id:04X} (ignoring)")
    else:
        print(f"📦 Other packet type: 0x{packet_type:02X} (ignoring)")

def monitor_parameter_uplink():
    """Monitor for parameter information uplink after successful downlink response"""
    global parameter_uplink_received, parameter_data
    
    print(f"\n📡 Monitoring for Parameter Information Uplink...")
    print(f"   Looking for: Type 0x00, Sensor ID 0x0000")
    print(f"   Timeout: 90 seconds (parameter info may not be sent immediately)")
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            # Wait up to 90 seconds for parameter uplink
            start_time = time.time()
            while not parameter_uplink_received and (time.time() - start_time) < 90:
                time.sleep(0.1)
            
            if parameter_uplink_received:
                print(f"\n✅ Parameter Information Received!")
                
                # Output complete JSON analysis
                json_output = json.dumps(parameter_data, ensure_ascii=False, indent=2)
                print(f"\n📊 COMPLETE PARAMETER INFORMATION ANALYSIS (JSON)")
                print(f"=" * 70)
                print(json_output)
                
                return True
            else:
                print(f"\n⚠️  No parameter information uplink received within 90 seconds")
                return False
                
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")
        return False

if __name__ == "__main__":
    # Analyze the received downlink response hex string
    hex_response = "01 01 B3 6E 73 68 04 00 40 03 02 80 68 24 00 00 FF FF 0D 00"
    analysis = analyze_hex_response(hex_response)
    
    # If downlink response was successful, monitor for parameter uplink
    if analysis.get("result", {}).get("success", False):
        print(f"\n🎉 Downlink response successful! Monitoring for parameter information...")
        monitor_parameter_uplink()
    else:
        print(f"\n❌ Downlink response failed, cannot proceed to parameter monitoring")
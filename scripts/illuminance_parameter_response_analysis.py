#!/usr/bin/env python3
"""
Illuminance Parameter Response Analysis

Send parameter acquisition request to illuminance sensor and analyze the complete
downlink response as JSON structure.
"""

import time
import struct
import json
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage for responses
downlink_responses = []
test_complete = False

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

def analyze_downlink_response_complete(data: bytes) -> dict:
    """Complete analysis of downlink response with all details"""
    try:
        analysis = {
            "response_metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "total_packet_length": len(data),
                "raw_packet_hex": data.hex(' ').upper(),
                "packet_structure": "ルーター仕様書 5-1-2 ダウンリンクレスポンス"
            }
        }
        
        if len(data) < 20:
            analysis["error"] = "Response packet too short"
            analysis["minimum_required_length"] = 20
            return analysis
        
        # Parse header fields according to spec 5-1-2
        offset = 0
        
        # Protocol Version (1 byte)
        protocol_version = data[offset]
        analysis["protocol_version"] = {
            "value": protocol_version,
            "hex": f"0x{protocol_version:02X}",
            "expected": "0x01",
            "valid": protocol_version == 0x01,
            "bytes": data[offset:offset+1].hex(' ').upper(),
            "description": "プロトコルバージョン (固定値)"
        }
        offset += 1
        
        # Type (1 byte)
        packet_type = data[offset]
        analysis["packet_type"] = {
            "value": packet_type,
            "hex": f"0x{packet_type:02X}",
            "name": "DOWNLINK_RESPONSE" if packet_type == 0x01 else f"OTHER(0x{packet_type:02X})",
            "expected": "0x01",
            "valid": packet_type == 0x01,
            "bytes": data[offset:offset+1].hex(' ').upper(),
            "description": "パケット種別 (ダウンリンクレスポンス)"
        }
        offset += 1
        
        # Unix Time (4 bytes, little endian)
        unix_time_bytes = data[offset:offset+4]
        unix_time = struct.unpack('<L', unix_time_bytes)[0]
        analysis["unix_time"] = {
            "value": unix_time,
            "hex": f"0x{unix_time:08X}",
            "datetime": datetime.fromtimestamp(unix_time).isoformat(),
            "formatted_time": datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S'),
            "bytes": unix_time_bytes.hex(' ').upper(),
            "encoding": "リトルエンディアン",
            "description": "Unix時間"
        }
        offset += 4
        
        # Device ID (8 bytes, little endian)
        device_id_bytes = data[offset:offset+8]
        device_id = struct.unpack('<Q', device_id_bytes)[0]
        analysis["device_id"] = {
            "value": device_id,
            "hex": f"0x{device_id:016X}",
            "bytes": device_id_bytes.hex(' ').upper(),
            "encoding": "リトルエンディアン",
            "description": "対象モジュールのDevice ID"
        }
        offset += 8
        
        # Sensor ID (2 bytes, little endian)
        sensor_id_bytes = data[offset:offset+2]
        sensor_id = struct.unpack('<H', sensor_id_bytes)[0]
        analysis["sensor_id"] = {
            "value": sensor_id,
            "hex": f"0x{sensor_id:04X}",
            "name": get_sensor_name(sensor_id),
            "expected": "0x0121",
            "valid": sensor_id == 0x0121,
            "bytes": sensor_id_bytes.hex(' ').upper(),
            "encoding": "リトルエンディアン",
            "description": "センサー種別ID"
        }
        offset += 2
        
        # Order (2 bytes, little endian)
        order_bytes = data[offset:offset+2]
        order = struct.unpack('<H', order_bytes)[0]
        analysis["order"] = {
            "value": order,
            "hex": f"0x{order:04X}",
            "bytes": order_bytes.hex(' ').upper(),
            "encoding": "リトルエンディアン",
            "description": "リクエストのOrderをコピー"
        }
        offset += 2
        
        # CMD (1 byte)
        cmd = data[offset]
        analysis["cmd"] = {
            "value": cmd,
            "hex": f"0x{cmd:02X}",
            "name": get_cmd_name(cmd),
            "bytes": data[offset:offset+1].hex(' ').upper(),
            "description": "対応するリクエストCMD"
        }
        offset += 1
        
        # Result (1 byte)
        result = data[offset]
        result_desc = get_result_description(result)
        analysis["result"] = {
            "value": result,
            "hex": f"0x{result:02X}",
            "description": result_desc,
            "success": result == 0x00,
            "error_category": get_error_category(result),
            "bytes": data[offset:offset+1].hex(' ').upper(),
            "interpretation": get_result_interpretation(result)
        }
        offset += 1
        
        # Check for additional data (should not exist according to spec)
        if offset < len(data):
            additional_data = data[offset:]
            analysis["additional_data"] = {
                "length": len(additional_data),
                "bytes": additional_data.hex(' ').upper(),
                "note": "仕様書によるとダウンリンクレスポンスは20バイト固定長",
                "unexpected": True
            }
        
        # Validation summary
        analysis["validation"] = {
            "packet_length_valid": len(data) == 20,
            "protocol_version_valid": protocol_version == 0x01,
            "packet_type_valid": packet_type == 0x01,
            "sensor_id_valid": sensor_id == 0x0121,
            "overall_valid": all([
                len(data) == 20,
                protocol_version == 0x01,
                packet_type == 0x01,
                sensor_id == 0x0121
            ])
        }
        
        # Parameter acquisition specific analysis
        analysis["parameter_acquisition_analysis"] = {
            "request_type": "パラメータ情報取得要求",
            "expected_behavior": "照度モジュール仕様書 5-2 パラメータ情報の返送",
            "actual_result": result_desc,
            "success": result == 0x00,
            "parameter_data_received": False,
            "reason": "コマンドがサポートされていない" if result == 0x02 else "その他のエラー"
        }
        
        return analysis
        
    except Exception as e:
        return {
            "error": f"Analysis error: {e}",
            "raw_packet_hex": data.hex(' ').upper(),
            "analysis_timestamp": datetime.now().isoformat()
        }

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
    return descriptions.get(result, f"Unknown result (0x{result:02X})")

def get_error_category(result: int) -> str:
    """Get error category"""
    if result == 0x00:
        return "SUCCESS"
    elif result in [0x01, 0x02, 0x03]:
        return "REQUEST_ERROR"
    elif result in [0x04, 0x05, 0x07]:
        return "COMMUNICATION_ERROR"
    elif result in [0x08, 0x09]:
        return "BUSY_ERROR"
    else:
        return "UNKNOWN_ERROR"

def get_result_interpretation(result: int) -> str:
    """Get detailed interpretation of result"""
    interpretations = {
        0x00: "コマンドが正常に実行され、パラメータ情報が取得できた",
        0x01: "指定されたSensor IDが無効または存在しない",
        0x02: "このセンサーでは指定されたコマンドがサポートされていない",
        0x03: "送信されたパラメータが範囲外または無効",
        0x04: "センサーとの通信に失敗した",
        0x05: "コマンド実行がタイムアウトした",
        0x07: "指定されたデバイスが見つからない",
        0x08: "ルーターがビジー状態でコマンドを処理できない",
        0x09: "センサーモジュールがビジー状態でコマンドを処理できない"
    }
    return interpretations.get(result, "不明なエラーコード")

def on_data_received(data: bytes):
    """Callback for received data"""
    global downlink_responses, test_complete
    
    if len(data) < 2:
        return
        
    packet_type = data[1]
    
    if packet_type == 0x01:  # Downlink response
        print(f"\n✅ DOWNLINK RESPONSE RECEIVED!")
        print(f"   Raw: {data.hex(' ').upper()}")
        
        # Perform complete analysis
        complete_analysis = analyze_downlink_response_complete(data)
        downlink_responses.append(complete_analysis)
        
        # Mark test as complete
        test_complete = True
        
        print(f"   Result: {complete_analysis.get('result', {}).get('description', 'Unknown')}")
        
    elif packet_type == 0x00:  # Uplink notification - ignore
        if len(data) >= 18:
            sensor_id = struct.unpack('<H', data[16:18])[0]
            print(f"📦 Uplink notification: 0x{sensor_id:04X} (ignoring)")

def main():
    """Main analysis function"""
    global test_complete
    
    print("🔬 BraveJIG Illuminance Parameter Response Complete Analysis")
    print("=" * 65)
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    # Known illuminance sensor device ID
    illuminance_device_id = 0x2468800203400004
    
    print(f"🎯 Target: Illuminance Sensor (0x{illuminance_device_id:016X})")
    print(f"📡 Sending parameter acquisition request...")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            # Create and send parameter acquisition request
            request_packet = create_illuminance_parameter_request(illuminance_device_id)
            print(f"\n📤 Request packet:")
            print(f"   Raw: {request_packet.hex(' ').upper()}")
            print(f"   Length: {len(request_packet)} bytes")
            
            if monitor.send(request_packet):
                print(f"   ✅ Request sent successfully")
            else:
                print(f"   ❌ Failed to send request")
                return False
            
            print(f"\n⏳ Waiting for downlink response...")
            
            # Wait for response (maximum 10 seconds)
            start_time = time.time()
            while not test_complete and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            if not downlink_responses:
                print("❌ No downlink response received")
                return False
            
            # Output complete JSON analysis
            complete_analysis = downlink_responses[0]
            json_output = json.dumps(complete_analysis, ensure_ascii=False, indent=2)
            
            print(f"\n📊 COMPLETE DOWNLINK RESPONSE ANALYSIS (JSON)")
            print("=" * 70)
            print(json_output)
            
            return True
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Packet Type Verification

Verify packet types and distinguish between uplink notifications and downlink responses.
"""

import time
import struct
import json
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage for different packet types
uplink_notifications = []
downlink_responses = []
other_packets = []

def analyze_packet_structure(data: bytes) -> dict:
    """Analyze packet structure and determine type"""
    try:
        if len(data) < 21:
            return {"error": "Packet too short", "raw": data.hex(' ').upper()}
        
        # Parse common header
        protocol_version = data[0]
        packet_type = data[1]
        
        analysis = {
            "raw_packet": data.hex(' ').upper(),
            "total_length": len(data),
            "protocol_version": f"0x{protocol_version:02X}",
            "packet_type": f"0x{packet_type:02X}",
            "timestamp": datetime.now().isoformat()
        }
        
        if packet_type == 0x00:  # Uplink notification
            analysis["type_name"] = "UPLINK_NOTIFICATION"
            analysis["structure"] = "ルーター仕様書 5-1-1"
            
            # Parse uplink structure
            data_length = struct.unpack('<H', data[2:4])[0]
            unix_time = struct.unpack('<L', data[4:8])[0]
            device_id = struct.unpack('<Q', data[8:16])[0]
            sensor_id = struct.unpack('<H', data[16:18])[0]
            rssi = data[18] if data[18] < 128 else data[18] - 256
            order = struct.unpack('<H', data[19:21])[0]
            
            analysis.update({
                "data_length": data_length,
                "unix_time": unix_time,
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "rssi": f"{rssi} dBm",
                "order": order,
                "sensor_data_start": 21,
                "sensor_data_length": len(data) - 21,
                "sensor_data": data[21:].hex(' ').upper()
            })
            
            # Determine if this is illuminance sensor
            if sensor_id == 0x0121:
                analysis["sensor_name"] = "Illuminance"
                analysis["is_parameter_data"] = False
                analysis["explanation"] = "通常のセンサーデータ（照度値）"
                
                # Parse illuminance data (simple structure)
                sensor_data = data[21:]
                if len(sensor_data) >= 12:
                    # Last 4 bytes are illuminance value
                    lux_bytes = sensor_data[-4:]
                    lux_value = struct.unpack('<f', lux_bytes)[0]
                    analysis["illuminance_value"] = f"{lux_value:.2f} lux"
            
        elif packet_type == 0x01:  # Downlink response
            analysis["type_name"] = "DOWNLINK_RESPONSE"
            analysis["structure"] = "ルーター仕様書 5-1-2"
            
            # Parse downlink response structure (fixed 20 bytes)
            unix_time = struct.unpack('<L', data[2:6])[0]
            device_id = struct.unpack('<Q', data[6:14])[0]
            sensor_id = struct.unpack('<H', data[14:16])[0]
            order = struct.unpack('<H', data[16:18])[0]
            cmd = data[18]
            result = data[19]
            
            analysis.update({
                "unix_time": unix_time,
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "order": order,
                "cmd": f"0x{cmd:02X}",
                "result": f"0x{result:02X}",
                "result_desc": get_result_description(result),
                "fixed_length": 20,
                "explanation": "コマンドの実行結果"
            })
            
        elif packet_type == 0x02:  # JIG INFO response
            analysis["type_name"] = "JIG_INFO_RESPONSE"
            analysis["structure"] = "ルーター仕様書 5-1-3"
            analysis["explanation"] = "JIG INFOコマンドの応答"
            
        else:
            analysis["type_name"] = f"UNKNOWN(0x{packet_type:02X})"
            analysis["explanation"] = "未知のパケットタイプ"
            
        return analysis
        
    except Exception as e:
        return {"error": f"Analysis error: {e}", "raw": data.hex(' ').upper()}

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

def check_parameter_data_possibility(data: bytes) -> dict:
    """Check if uplink data could be parameter information"""
    if len(data) < 21:
        return {"possible": False, "reason": "Packet too short"}
        
    packet_type = data[1]
    if packet_type != 0x00:
        return {"possible": False, "reason": "Not uplink notification"}
        
    sensor_id = struct.unpack('<H', data[16:18])[0]
    if sensor_id != 0x0121:
        return {"possible": False, "reason": "Not illuminance sensor"}
        
    sensor_data = data[21:]
    
    # Check if this could be parameter data according to spec 5-2
    # Minimum size for parameter data: 2+2+2+3+1+1+1+2+4+1+1+4+4 = 28 bytes
    if len(sensor_data) < 28:
        return {
            "possible": False, 
            "reason": f"Too short for parameter data (got {len(sensor_data)}, need ≥28)",
            "actual_size": len(sensor_data),
            "required_min_size": 28
        }
    
    # Check if first 2 bytes are 0x0000 (SensorID for end device)
    if len(sensor_data) >= 2:
        first_sensor_id = struct.unpack('<H', sensor_data[0:2])[0]
        if first_sensor_id != 0x0000:
            return {
                "possible": False,
                "reason": f"First SensorID should be 0x0000, got 0x{first_sensor_id:04X}",
                "first_bytes": sensor_data[0:2].hex(' ').upper()
            }
    
    # Check if sequence number is 0xFFFF
    if len(sensor_data) >= 4:
        sequence_no = struct.unpack('<H', sensor_data[2:4])[0]
        if sequence_no != 0xFFFF:
            return {
                "possible": False,
                "reason": f"Sequence No should be 0xFFFF, got 0x{sequence_no:04X}",
                "sequence_bytes": sensor_data[2:4].hex(' ').upper()
            }
    
    return {"possible": True, "reason": "Matches parameter data structure"}

def on_data_received(data: bytes):
    """Callback for received data"""
    global uplink_notifications, downlink_responses, other_packets
    
    analysis = analyze_packet_structure(data)
    packet_type = data[1] if len(data) > 1 else 0xFF
    
    print(f"\n📦 Received packet: Type 0x{packet_type:02X}")
    print(f"   Length: {len(data)} bytes")
    print(f"   Type: {analysis.get('type_name', 'Unknown')}")
    
    if packet_type == 0x00:  # Uplink
        uplink_notifications.append(analysis)
        sensor_id = struct.unpack('<H', data[16:18])[0] if len(data) >= 18 else 0
        if sensor_id == 0x0121:
            print(f"   💡 Illuminance sensor data")
            # Check if this could be parameter data
            param_check = check_parameter_data_possibility(data)
            print(f"   📊 Parameter data possibility: {param_check}")
            
    elif packet_type == 0x01:  # Downlink response
        downlink_responses.append(analysis)
        print(f"   ✅ Downlink response")
        
    else:
        other_packets.append(analysis)
        print(f"   ❓ Other packet type")

def main():
    """Main verification function"""
    print('🔍 BraveJIG Packet Type Verification')
    print('=' * 50)
    print('パケットタイプを正確に判定し、パラメータデータの可能性を検証します')
    
    try:
        with AsyncSerialMonitor() as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            print(f'\n⏳ 70秒間監視...')
            time.sleep(70)
            
            print(f'\n📊 検証結果サマリー:')
            print(f'   アップリンク通知: {len(uplink_notifications)}個')
            print(f'   ダウンリンクレスポンス: {len(downlink_responses)}個')
            print(f'   その他パケット: {len(other_packets)}個')
            
            # Show detailed analysis for illuminance packets
            illuminance_uplinks = [p for p in uplink_notifications 
                                 if p.get('sensor_id') == '0x0121']
            
            if illuminance_uplinks:
                print(f'\n💡 照度センサーアップリンク詳細:')
                for i, packet in enumerate(illuminance_uplinks[:3]):  # Show first 3
                    print(f'\n   パケット{i+1}:')
                    print(f'     Type: {packet.get("type_name")}')
                    print(f'     データ長: {packet.get("sensor_data_length")} bytes')
                    print(f'     説明: {packet.get("explanation")}')
                    if 'illuminance_value' in packet:
                        print(f'     照度値: {packet.get("illuminance_value")}')
            
            if downlink_responses:
                print(f'\n✅ ダウンリンクレスポンス詳細:')
                for i, packet in enumerate(downlink_responses):
                    print(f'\n   レスポンス{i+1}:')
                    print(f'     Type: {packet.get("type_name")}')
                    print(f'     Result: {packet.get("result_desc")}')
                    print(f'     Command: {packet.get("cmd")}')
            
            # Export detailed analysis
            all_analysis = {
                'summary': {
                    'uplink_count': len(uplink_notifications),
                    'downlink_count': len(downlink_responses),
                    'other_count': len(other_packets)
                },
                'uplink_notifications': uplink_notifications,
                'downlink_responses': downlink_responses,
                'other_packets': other_packets
            }
            
            print(f'\n💾 完全な解析結果をJSONで出力:')
            json_output = json.dumps(all_analysis, ensure_ascii=False, indent=2)
            print('=' * 60)
            print(json_output[:1000] + '...' if len(json_output) > 1000 else json_output)
            
            return True
            
    except Exception as e:
        print(f'❌ エラー: {e}')
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
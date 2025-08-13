#!/usr/bin/env python3
"""
Illuminance Parameter Detailed Analysis

Analyze illuminance sensor parameter information and output as JSON structure
according to specification 5-2 パラメータ情報.
"""

import time
import struct
import json
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage for parameter data
parameter_data = []

def parse_illuminance_parameter_detailed(data: bytes) -> dict:
    """Parse illuminance parameter information according to spec 5-2"""
    try:
        if len(data) < 21:
            return {'error': 'Packet too short'}
            
        # Common header
        sensor_id = struct.unpack('<H', data[16:18])[0]
        if sensor_id != 0x0121:
            return {'error': 'Not illuminance sensor'}
            
        # Sensor data starts at index 21
        sensor_data = data[21:]
        print(f'📊 Sensor data ({len(sensor_data)} bytes): {sensor_data.hex(" ").upper()}')
        
        result = {
            'packet_info': {
                'total_length': len(data),
                'sensor_data_length': len(sensor_data),
                'timestamp': datetime.now().isoformat(),
                'sensor_id': f'0x{sensor_id:04X}',
                'device_id': f'0x{struct.unpack("<Q", data[8:16])[0]:016X}'
            },
            'parameter_info': {}
        }
        
        if len(sensor_data) < 10:
            result['error'] = 'Insufficient sensor data'
            return result
            
        offset = 0
        
        # SensorID (2 bytes) - エンドデバイス本体
        if offset + 2 <= len(sensor_data):
            param_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result['parameter_info']['end_device_sensor_id'] = {
                'value': f'0x{param_sensor_id:04X}',
                'description': 'エンドデバイス本体',
                'bytes': sensor_data[offset:offset+2].hex(' ').upper()
            }
            offset += 2
            
        # Sequence No (2 bytes)
        if offset + 2 <= len(sensor_data):
            sequence_no = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result['parameter_info']['sequence_no'] = {
                'value': sequence_no,
                'hex': f'0x{sequence_no:04X}',
                'bytes': sensor_data[offset:offset+2].hex(' ').upper()
            }
            offset += 2
            
        # === Sensor Data section starts here ===
        result['parameter_info']['sensor_data'] = {}
        
        # Connected Sensor ID (2 bytes) - 0x0121 固定
        if offset + 2 <= len(sensor_data):
            connected_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result['parameter_info']['sensor_data']['connected_sensor_id'] = {
                'value': f'0x{connected_sensor_id:04X}',
                'description': '本製品に接続されているSensorのSensorID',
                'expected': '0x0121',
                'bytes': sensor_data[offset:offset+2].hex(' ').upper()
            }
            offset += 2
            
        # FW Version (3 bytes)
        if offset + 3 <= len(sensor_data):
            fw_bytes = sensor_data[offset:offset+3]
            fw_version = f'{fw_bytes[0]}.{fw_bytes[1]}.{fw_bytes[2]}'
            result['parameter_info']['sensor_data']['fw_version'] = {
                'value': fw_version,
                'major': fw_bytes[0],
                'minor': fw_bytes[1], 
                'patch': fw_bytes[2],
                'description': '本製品のFWバージョン',
                'bytes': fw_bytes.hex(' ').upper()
            }
            offset += 3
            
        # TimeZone (1 byte)
        if offset + 1 <= len(sensor_data):
            timezone = sensor_data[offset]
            result['parameter_info']['sensor_data']['timezone'] = {
                'value': timezone,
                'description': 'タイムゾーン設定',
                'bytes': f'{timezone:02X}'
            }
            offset += 1
            
        # BLE Mode (1 byte)  
        if offset + 1 <= len(sensor_data):
            ble_mode = sensor_data[offset]
            result['parameter_info']['sensor_data']['ble_mode'] = {
                'value': ble_mode,
                'description': 'Bluetooth LE通信モードの設定情報',
                'bytes': f'{ble_mode:02X}'
            }
            offset += 1
            
        # Tx Power (1 byte)
        if offset + 1 <= len(sensor_data):
            tx_power = sensor_data[offset]
            result['parameter_info']['sensor_data']['tx_power'] = {
                'value': tx_power,
                'description': 'Bluetooth LE通信の送信電波出力',
                'bytes': f'{tx_power:02X}'
            }
            offset += 1
            
        # Advertise Interval (2 bytes, little endian)
        if offset + 2 <= len(sensor_data):
            adv_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result['parameter_info']['sensor_data']['advertise_interval'] = {
                'value': adv_interval,
                'description': 'Advertiseを発信する間隔',
                'encoding': 'リトルエンディアン',
                'bytes': sensor_data[offset:offset+2].hex(' ').upper()
            }
            offset += 2
            
        # Sensor Uplink Interval (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
            result['parameter_info']['sensor_data']['sensor_uplink_interval'] = {
                'value': uplink_interval,
                'unit': 'seconds',
                'description': 'Sensor情報データをUplinkする間隔',
                'encoding': 'リトルエンディアン',
                'bytes': sensor_data[offset:offset+4].hex(' ').upper()
            }
            offset += 4
            
        # Sensor Read Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            read_mode = sensor_data[offset]
            result['parameter_info']['sensor_data']['sensor_read_mode'] = {
                'value': read_mode,
                'description': '計測モード',
                'bytes': f'{read_mode:02X}'
            }
            offset += 1
            
        # Sampling (1 byte)
        if offset + 1 <= len(sensor_data):
            sampling = sensor_data[offset]
            result['parameter_info']['sensor_data']['sampling'] = {
                'value': sampling,
                'description': 'サンプリング周期',
                'bytes': f'{sampling:02X}'
            }
            offset += 1
            
        # HysteresisHigh (4 bytes, little endian, Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_high_bytes = sensor_data[offset:offset+4]
            hysteresis_high = struct.unpack('<f', hysteresis_high_bytes)[0]
            result['parameter_info']['sensor_data']['hysteresis_high'] = {
                'value': hysteresis_high,
                'unit': 'Lux',
                'description': 'ヒステリシス(High):照度(Lux)',
                'encoding': 'リトルエンディアン IEEE 754 Float',
                'bytes': hysteresis_high_bytes.hex(' ').upper()
            }
            offset += 4
            
        # HysteresisLow (4 bytes, little endian, Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_low_bytes = sensor_data[offset:offset+4]
            hysteresis_low = struct.unpack('<f', hysteresis_low_bytes)[0]
            result['parameter_info']['sensor_data']['hysteresis_low'] = {
                'value': hysteresis_low,
                'unit': 'Lux',
                'description': 'ヒステリシス(Low):照度(Lux)',
                'encoding': 'リトルエンディアン IEEE 754 Float',
                'bytes': hysteresis_low_bytes.hex(' ').upper()
            }
            offset += 4
            
        # Remaining bytes analysis
        if offset < len(sensor_data):
            remaining = sensor_data[offset:]
            result['parameter_info']['remaining_data'] = {
                'length': len(remaining),
                'bytes': remaining.hex(' ').upper(),
                'description': '仕様書に記載されていない追加データ'
            }
            
        return result
        
    except Exception as e:
        return {'error': f'Parameter parse error: {e}', 'raw_data': data.hex(' ').upper()}

def on_data_received(data: bytes):
    """Callback for received data"""
    global parameter_data
    
    if len(data) >= 18:
        packet_type = data[1]
        sensor_id = struct.unpack('<H', data[16:18])[0]
        
        if packet_type == 0x00 and sensor_id == 0x0121:  # Illuminance uplink
            print(f'\n💡 照度センサーアップリンク検出')
            detailed_analysis = parse_illuminance_parameter_detailed(data)
            parameter_data.append(detailed_analysis)

def main():
    """Main analysis function"""
    global parameter_data
    
    print('💡 照度センサーパラメータ詳細解析')
    print('=' * 50)
    print('アップリンクパケット1個を詳細解析します...')
    
    try:
        with AsyncSerialMonitor() as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            # 70秒監視（60秒間隔を確実にキャッチ）
            start_time = time.time()
            while time.time() - start_time < 70 and len(parameter_data) == 0:
                time.sleep(1)
                
            if parameter_data:
                # 最初のパケットの詳細解析結果をJSON出力
                detailed_json = json.dumps(parameter_data[0], ensure_ascii=False, indent=2)
                print('\n📊 照度センサーパラメータ情報 (JSON)')
                print('=' * 60)
                print(detailed_json)
                return True
            else:
                print('⚠️ 照度センサーのアップリンクを受信できませんでした')
                return False
                
    except Exception as e:
        print(f'❌ エラー: {e}')
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
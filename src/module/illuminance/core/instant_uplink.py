"""
BraveJIG Illuminance Sensor Instant Uplink Command

即時Uplink要求コマンド実装
仕様書 6-1 即時Uplink要求 (CMD: 0x00 - SEND_DATA_AT_ONCE)

Request Format:
- SensorID: 0x0121 (2 bytes) - 照度モジュール
- CMD: 0x00 (1 byte) - 即時Uplink要求  
- Sequence No: 0xFFFF (2 bytes) - 固定
- DATA: なし

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
from typing import Dict, Any, Optional
from ..base_illuminance import IlluminanceSensorBase, IlluminanceCommand


class InstantUplinkCommand(IlluminanceSensorBase):
    """
    即時Uplink要求コマンド実装
    
    現在のセンサー値を即座に取得するコマンド
    scripts/illuminance_command_discovery.pyで実証済み
    """
    
    def __init__(self, device_id: str):
        """
        Initialize instant uplink command handler
        
        Args:
            device_id: Target device ID as hex string
        """
        super().__init__(device_id)
        self.command = IlluminanceCommand.INSTANT_UPLINK

    def create_instant_uplink_request(self) -> bytes:
        """
        Create instant uplink request according to spec 6-1
        
        Returns:
            bytes: Complete instant uplink request packet
        """
        # According to spec 6-1, instant uplink request has no DATA field
        # Device ID以降: [SensorID(2byte)],[CMD(1byte)],[Order(=SequenceNo)0xFFFF],[DATA なし]
        
        # Create the full downlink request packet using base class method
        request_packet = self.create_downlink_request(
            cmd=self.command,      # CMD: 0x00 (INSTANT_UPLINK)
            data=b'',             # DATA: なし (空)
            order=0xFFFF          # Order: 0xFFFF固定 (SequenceNo)
        )
        
        return request_packet


    def parse_sensor_uplink(self, uplink_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse sensor data uplink notification (Type: 0x00)
        
        This is called when an uplink notification arrives after instant uplink request
        
        Args:
            uplink_data: Raw uplink notification bytes
            
        Returns:
            Dict containing parsed sensor data or None if not illuminance sensor data
        """
        try:
            if len(uplink_data) < 21:
                return None
            
            # Use base class helper methods for validation
            if not self.is_illuminance_sensor_uplink(uplink_data):
                return None  # Not illuminance sensor data
            
            if not self.validate_uplink_for_device(uplink_data):
                return None  # Not our target device
            
            # Sensor data starts at offset 21
            sensor_data = uplink_data[21:]
            
            return self._parse_illuminance_sensor_data(sensor_data, uplink_data)
            
        except Exception as e:
            self.logger.error(f"Sensor uplink parse error: {e}")
            return None

    def _parse_illuminance_sensor_data(self, sensor_data: bytes, full_packet: bytes) -> Dict[str, Any]:
        """
        Parse illuminance sensor data according to spec 5-1
        
        Format:
        - SensorID (2 bytes): 0x0121
        - Sequence No (2 bytes)
        - Battery Level (1 byte): %
        - Sampling (1 byte): サンプリング周期
        - Time (4 bytes): センサーリード時刻
        - Sample Num (2 bytes): サンプル数 (little endian)
        - LuxData[0] (4 bytes): 照度情報 Float型 (little endian)
        - ... LuxData[n] (4 bytes each)
        """
        try:
            if len(sensor_data) < 12:  # Minimum size check (SensorID:2 + Time:4 + SampleNum:2 + LuxData:4)
                return {"error": "Insufficient sensor data"}
            
            offset = 0
            result = {
                "sensor_type": "illuminance",
                "device_id": f"{self.device_id:016X}",
                "raw_packet": full_packet.hex(' ').upper(),
                "sensor_data_hex": sensor_data.hex(' ').upper()
            }
            
            # BraveJIGパケットからSensorIDを取得（パケット内のbytes 16-17から）
            # センサーデータ自体にはSensorIDは含まれない
            result["sensor_id"] = "0121"  # 照度センサーの固定値
            
            # センサーデータの構造：Battery Level (1) + Sampling (1) + Time (4) + SampleNum (2) + LuxData...
            
            # Battery Level (1 byte)
            battery_level = sensor_data[offset]
            result["battery_level"] = f"{battery_level}%"
            offset += 1
            
            # Sampling (1 byte) 
            sampling = sensor_data[offset]
            result["sampling_period"] = sampling
            offset += 1
            
            # Time (4 bytes) - Unix timestamp
            sensor_time = struct.unpack('<L', sensor_data[offset:offset+4])[0]
            result["sensor_time"] = sensor_time
            result["sensor_time_readable"] = self._format_timestamp(sensor_time)
            offset += 4
            
            # Sample Num (2 bytes)
            sample_num = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            result["sample_count"] = sample_num
            offset += 2
            
            # LuxData array (4 bytes each, IEEE 754 Float, little endian)
            lux_data = []
            remaining_bytes = len(sensor_data) - offset
            expected_lux_bytes = sample_num * 4
            
            if remaining_bytes >= expected_lux_bytes:
                for i in range(sample_num):
                    if offset + 4 <= len(sensor_data):
                        lux_value = struct.unpack('<f', sensor_data[offset:offset+4])[0]
                        lux_data.append(round(lux_value, 2))
                        offset += 4
            
            result["lux_data"] = lux_data
            
            return result
            
        except Exception as e:
            return {"error": f"Sensor data parse error: {str(e)}"}

    def _format_timestamp(self, timestamp: int) -> str:
        """Format Unix timestamp to readable string"""
        try:
            import datetime
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return f"timestamp:{timestamp}"
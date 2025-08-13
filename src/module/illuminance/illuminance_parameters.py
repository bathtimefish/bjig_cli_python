"""
BraveJIG Illuminance Sensor Parameter Structures

照度センサー用共通パラメータ構造定義
get_parameter.py と set_parameter.py で共通利用するdataclass定義

仕様書参照:
- 6-2 パラメータ情報設定要求 (SET_REGISTER)  
- 6-4 パラメータ情報取得要求 (GET_DEVICE_SETTING)
- 5-2 パラメータ情報Uplink

Author: BraveJIG CLI Development Team
Date: 2025-08-01
"""

import struct
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union
import json


@dataclass
class IlluminanceParameters:
    """
    照度センサーパラメータ構造
    
    仕様書 6-2 SET_REGISTER 19-byte DATA format:
    - SensorID (2): 0x0121 固定
    - TimeZone (1): タイムゾーン設定
    - BLE Mode (1): Bluetooth LE通信モード
    - Tx Power (1): 送信電波出力
    - Advertise Interval (2): Advertise間隔 (little endian)
    - Sensor Uplink Interval (4): Uplink間隔 (little endian)
    - Sensor Read Mode (1): 計測モード
    - Sampling (1): サンプリング周期
    - HysteresisHigh (4): ヒステリシス(High) (IEEE 754 Float, little endian)
    - HysteresisLow (4): ヒステリシス(Low) (IEEE 754 Float, little endian)
    """
    
    # Core sensor identification
    sensor_id: int = 0x0121  # 照度センサー固定値
    
    # Communication parameters (settable only)
    timezone: int = 0x00  # 0x00=JST, 0x01=UTC
    ble_mode: int = 0x00  # 0x00=LongRange, 0x01=Legacy
    tx_power: int = 0x00  # 0x00=±0dBm, 0x01=+4dBm, etc.
    advertise_interval: int = 1000  # ms (100-10000)
    sensor_uplink_interval: int = 60  # seconds (5-86400)
    
    # Sensor operation parameters
    sensor_read_mode: int = 0x00  # 0x00=瞬時値, 0x01=検知, 0x02=サンプリング
    sampling: int = 0x00  # 0x00=1Hz, 0x01=2Hz
    hysteresis_high: int = 500  # Lux (40-83865) - stored as integer in hardware
    hysteresis_low: int = 400  # Lux (40-83865) - stored as integer in hardware
    
    # Note: connected_sensor_id and fw_version are read-only metadata
    # They are parsed separately and not included in SET_PARAMETER 19-byte structure
    
    def serialize_to_bytes(self) -> bytes:
        """
        Serialize parameters to 19-byte format for SET_PARAMETER request
        
        Returns:
            bytes: 19-byte parameter data for wire transmission
        """
        data = b''
        
        # SensorID (2 bytes) - 0x0121 fixed for illuminance sensor
        data += struct.pack('<H', self.sensor_id)
        
        # TimeZone (1 byte)
        data += struct.pack('<B', self.timezone)
        
        # BLE Mode (1 byte)
        data += struct.pack('<B', self.ble_mode)
        
        # Tx Power (1 byte)
        data += struct.pack('<B', self.tx_power)
        
        # Advertise Interval (2 bytes, little endian)
        data += struct.pack('<H', self.advertise_interval)
        
        # Sensor Uplink Interval (4 bytes, little endian)
        data += struct.pack('<L', self.sensor_uplink_interval)
        
        # Sensor Read Mode (1 byte)
        data += struct.pack('<B', self.sensor_read_mode)
        
        # Sampling (1 byte)
        data += struct.pack('<B', self.sampling)
        
        # HysteresisHigh (4 bytes, little endian integer)
        data += struct.pack('<L', int(self.hysteresis_high))
        
        # HysteresisLow (4 bytes, little endian integer)
        data += struct.pack('<L', int(self.hysteresis_low))
        
        return data
    
    @classmethod
    def deserialize_from_bytes(cls, sensor_data: bytes, offset: int = 0) -> tuple['IlluminanceParameters', Dict[str, Any]]:
        """
        Deserialize parameters from parameter information section
        
        Args:
            sensor_data: Parameter data bytes from uplink (24 bytes starting with Connected SensorID)
            offset: Starting offset in sensor_data (default 0 for parameter data section)
            
        Returns:
            Tuple of (IlluminanceParameters instance, metadata dict)
            
        Expected format (24 bytes):
        - Connected SensorID (2): 0x0121 for illuminance
        - FW Version (3): Major.Minor.Patch
        - TimeZone (1): 0x00=JST, 0x01=UTC
        - BLE Mode (1): 0x00=LongRange, 0x01=Legacy  
        - Tx Power (1): 0x00-0x08
        - Advertise Interval (2): milliseconds (little endian)
        - Sensor Uplink Interval (4): seconds (little endian)
        - Sensor Read Mode (1): 0x00=瞬時値, 0x01=検知, 0x02=サンプリング
        - Sampling (1): 0x00=1Hz, 0x01=2Hz
        - Hysteresis High (4): Lux value as integer (little endian)
        - Hysteresis Low (4): Lux value as integer (little endian)
        """
        params = cls()
        metadata = {}
        
        try:
            # Connected SensorID (2 bytes) - Should be 0x0121 (metadata, not in SET structure)
            connected_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            metadata['connected_sensor_id'] = connected_sensor_id
            offset += 2
            
            # FW Version (3 bytes) - metadata, not in SET structure
            if offset + 3 <= len(sensor_data):
                fw_bytes = sensor_data[offset:offset+3]
                metadata['fw_version'] = f"{fw_bytes[0]}.{fw_bytes[1]}.{fw_bytes[2]}"
                offset += 3
            
            # TimeZone (1 byte)
            if offset < len(sensor_data):
                params.timezone = sensor_data[offset]
                offset += 1
            
            # BLE Mode (1 byte)
            if offset < len(sensor_data):
                params.ble_mode = sensor_data[offset]
                offset += 1
            
            # Tx Power (1 byte)
            if offset < len(sensor_data):
                params.tx_power = sensor_data[offset]
                offset += 1
            
            # Advertise Interval (2 bytes, little endian)
            if offset + 2 <= len(sensor_data):
                params.advertise_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
                offset += 2
            
            # Sensor Uplink Interval (4 bytes, little endian)
            if offset + 4 <= len(sensor_data):
                params.sensor_uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
                offset += 4
            
            # Sensor Read Mode (1 byte)
            if offset < len(sensor_data):
                params.sensor_read_mode = sensor_data[offset]
                offset += 1
            
            # Sampling (1 byte)
            if offset < len(sensor_data):
                params.sampling = sensor_data[offset]
                offset += 1
            
            # HysteresisHigh (4 bytes, little endian integer)
            if offset + 4 <= len(sensor_data):
                params.hysteresis_high = struct.unpack('<L', sensor_data[offset:offset+4])[0]
                offset += 4
            
            # HysteresisLow (4 bytes, little endian integer)
            if offset + 4 <= len(sensor_data):
                params.hysteresis_low = struct.unpack('<L', sensor_data[offset:offset+4])[0]
                offset += 4
            
        except Exception as e:
            raise ValueError(f"Parameter deserialization failed: {str(e)}")
        
        return params, metadata
    
    def update_from_dict(self, update_data: Dict[str, Any]) -> 'IlluminanceParameters':
        """
        Create new parameter instance with updates applied
        
        Args:
            update_data: Dictionary with parameter updates
            
        Returns:
            New IlluminanceParameters instance with updates applied
        """
        # Create copy of current parameters
        updated = IlluminanceParameters(
            sensor_id=self.sensor_id,
            timezone=self.timezone,
            ble_mode=self.ble_mode,
            tx_power=self.tx_power,
            advertise_interval=self.advertise_interval,
            sensor_uplink_interval=self.sensor_uplink_interval,
            sensor_read_mode=self.sensor_read_mode,
            sampling=self.sampling,
            hysteresis_high=self.hysteresis_high,
            hysteresis_low=self.hysteresis_low
        )
        
        # Apply updates (excluding read-only metadata)
        for key, value in update_data.items():
            # Skip read-only metadata fields
            if key in ['connected_sensor_id', 'fw_version']:
                continue
                
            if hasattr(updated, key):
                # Type conversion for numeric fields
                if key in ['timezone', 'ble_mode', 'tx_power', 'advertise_interval', 
                          'sensor_uplink_interval', 'sensor_read_mode', 'sampling']:
                    value = int(value)
                elif key in ['hysteresis_high', 'hysteresis_low']:
                    value = int(value)
                
                setattr(updated, key, value)
        
        return updated
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate parameter values according to specifications
        
        Returns:
            Dict with validation results
        """
        result = {"valid": True, "errors": []}
        
        try:
            # TimeZone validation
            if not isinstance(self.timezone, int) or self.timezone not in [0x00, 0x01]:
                result["errors"].append("timezone must be 0x00 (JST) or 0x01 (UTC)")
            
            # BLE Mode validation
            if not isinstance(self.ble_mode, int) or self.ble_mode not in [0x00, 0x01]:
                result["errors"].append("ble_mode must be 0x00 (LongRange) or 0x01 (Legacy)")
            
            # Tx Power validation
            valid_tx_powers = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]
            if not isinstance(self.tx_power, int) or self.tx_power not in valid_tx_powers:
                result["errors"].append("tx_power must be one of: 0x00-0x08")
            
            # Advertise Interval validation (100ms - 10000ms)
            if not isinstance(self.advertise_interval, int) or not (100 <= self.advertise_interval <= 10000):
                result["errors"].append("advertise_interval must be 100-10000 ms")
            
            # Sensor Uplink Interval validation (5 - 86400 seconds)
            if not isinstance(self.sensor_uplink_interval, int) or not (5 <= self.sensor_uplink_interval <= 86400):
                result["errors"].append("sensor_uplink_interval must be 5-86400 seconds")
            
            # Sensor Read Mode validation
            if not isinstance(self.sensor_read_mode, int) or self.sensor_read_mode not in [0x00, 0x01, 0x02]:
                result["errors"].append("sensor_read_mode must be 0x00 (瞬時値), 0x01 (検知), or 0x02 (サンプリング)")
            
            # Sampling validation
            if not isinstance(self.sampling, int) or self.sampling not in [0x00, 0x01]:
                result["errors"].append("sampling must be 0x00 (1Hz) or 0x01 (2Hz)")
            
            # HysteresisHigh validation (40-83865 Lux)
            try:
                high_val = int(self.hysteresis_high)
                if not (40 <= high_val <= 83865):
                    result["errors"].append("hysteresis_high must be 40-83865 Lux")
            except (ValueError, TypeError):
                result["errors"].append("hysteresis_high must be an integer")
            
            # HysteresisLow validation (40-83865 Lux)
            try:
                low_val = int(self.hysteresis_low)
                if not (40 <= low_val <= 83865):
                    result["errors"].append("hysteresis_low must be 40-83865 Lux")
            except (ValueError, TypeError):
                result["errors"].append("hysteresis_low must be an integer")
            
            # Cross-validation: Low must be less than High
            try:
                if int(self.hysteresis_low) >= int(self.hysteresis_high):
                    result["errors"].append("hysteresis_low must be less than hysteresis_high")
            except (ValueError, TypeError):
                pass  # Already reported above
            
            # Set final validation result
            if result["errors"]:
                result["valid"] = False
                result["error"] = "; ".join(result["errors"])
            
        except Exception as e:
            result["valid"] = False
            result["error"] = f"Validation error: {str(e)}"
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert parameters to dictionary format
        
        Returns:
            Dictionary representation of parameters
        """
        return {
            "timezone": self.timezone,
            "ble_mode": self.ble_mode,
            "tx_power": self.tx_power,
            "advertise_interval": self.advertise_interval,
            "sensor_uplink_interval": self.sensor_uplink_interval,
            "sensor_read_mode": self.sensor_read_mode,
            "sampling": self.sampling,
            "hysteresis_high": self.hysteresis_high,
            "hysteresis_low": self.hysteresis_low
        }
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert parameters to JSON string
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON formatted string
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def to_display_format(self) -> Dict[str, Dict[str, Any]]:
        """
        Convert parameters to user-friendly display format with descriptions
        
        Returns:
            Dictionary with parameter values and descriptions
        """
        return {
            "timezone": {
                "value": self.timezone,
                "description": "JST" if self.timezone == 0x00 else "UTC" if self.timezone == 0x01 else f"Unknown({self.timezone})"
            },
            "ble_mode": {
                "value": self.ble_mode,
                "description": "LongRange" if self.ble_mode == 0x00 else "Legacy" if self.ble_mode == 0x01 else f"Unknown({self.ble_mode})"
            },
            "tx_power": {
                "value": self.tx_power,
                "description": {
                    0x00: "±0dBm", 0x01: "+4dBm", 0x02: "-4dBm", 0x03: "-8dBm",
                    0x04: "-12dBm", 0x05: "-16dBm", 0x06: "-20dBm", 0x07: "-40dBm", 0x08: "+8dBm"
                }.get(self.tx_power, f"Unknown({self.tx_power})")
            },
            "advertise_interval": {
                "value": self.advertise_interval,
                "unit": "ms"
            },
            "sensor_uplink_interval": {
                "value": self.sensor_uplink_interval,
                "unit": "seconds"
            },
            "sensor_read_mode": {
                "value": self.sensor_read_mode,
                "description": {
                    0x00: "瞬時値モード", 0x01: "検知モード", 0x02: "サンプリングモード"
                }.get(self.sensor_read_mode, f"Unknown({self.sensor_read_mode})")
            },
            "sampling": {
                "value": self.sampling,
                "description": {
                    0x00: "1Hz (1000ms)", 0x01: "2Hz (500ms)"
                }.get(self.sampling, f"Unknown({self.sampling})")
            },
            "hysteresis_high": {
                "value": int(self.hysteresis_high),
                "unit": "Lux"
            },
            "hysteresis_low": {
                "value": int(self.hysteresis_low),
                "unit": "Lux"
            }
        }
    
    @classmethod
    def create_default_template(cls) -> Dict[str, Any]:
        """
        Create parameter template with default values and descriptions
        
        Returns:
            Dict with default parameter values and descriptions
        """
        return {
            "timezone": {
                "value": 0x00,
                "description": "0x00=JST, 0x01=UTC",
                "valid_values": [0x00, 0x01]
            },
            "ble_mode": {
                "value": 0x00,
                "description": "0x00=LongRange, 0x01=Legacy",
                "valid_values": [0x00, 0x01]
            },
            "tx_power": {
                "value": 0x00,
                "description": "0x00=±0dBm, 0x01=+4dBm, 0x02=-4dBm, etc.",
                "valid_values": [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]
            },
            "advertise_interval": {
                "value": 1000,
                "description": "Advertise interval in milliseconds",
                "range": "100-10000"
            },
            "sensor_uplink_interval": {
                "value": 60,
                "description": "Sensor uplink interval in seconds",
                "range": "5-86400"
            },
            "sensor_read_mode": {
                "value": 0x00,
                "description": "0x00=瞬時値, 0x01=検知, 0x02=サンプリング",
                "valid_values": [0x00, 0x01, 0x02]
            },
            "sampling": {
                "value": 0x00,
                "description": "0x00=1Hz, 0x01=2Hz",
                "valid_values": [0x00, 0x01]
            },
            "hysteresis_high": {
                "value": 500,
                "description": "High threshold in Lux",
                "range": "40-83865"
            },
            "hysteresis_low": {
                "value": 400,
                "description": "Low threshold in Lux", 
                "range": "40-83865"
            }
        }
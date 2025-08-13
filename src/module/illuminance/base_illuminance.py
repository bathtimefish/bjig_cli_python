"""
BraveJIG Illuminance Sensor Module Base Class

照度センサーモジュール(BJ-MD-LUX-01)の基底クラス
実機テスト済みのscripts/illuminance_*.pyパターンに基づく実装

Key Features:
- SensorID: 0x0121 (固定値)
- 共通基底クラス(ModuleBase)を活用した最適化実装
- 照度センサー固有の機能のみを実装
- 重複コードを削減し保守性を向上

Author: BraveJIG CLI Development Team  
Date: 2025-07-31 (Updated: 2025-08-10)
"""

from typing import Dict, Any, Optional
from enum import IntEnum

from module.base_module import ModuleBase, ModuleCommand, UplinkWaitMixin


class IlluminanceCommand(IntEnum):
    """照度センサーコマンド定義 (実機テスト済み) - 共通コマンドのエイリアス"""
    INSTANT_UPLINK = ModuleCommand.INSTANT_UPLINK      # 即時Uplink要求 (SEND_DATA_AT_ONCE)
    SET_PARAMETER = ModuleCommand.SET_PARAMETER        # パラメータ設定 (SET_REGISTER)
    GET_DEVICE_SETTING = ModuleCommand.GET_PARAMETER   # パラメータ取得 (GET_DEVICE_SETTING)
    SENSOR_DFU = ModuleCommand.SENSOR_DFU             # センサーDFU (UPDATE_SENSOR_FIRMWARE)
    DEVICE_RESTART = ModuleCommand.DEVICE_RESTART     # デバイス再起動 (RESTART)


class IlluminanceSensorBase(ModuleBase, UplinkWaitMixin):
    """
    BraveJIG照度センサーモジュール基底クラス
    
    ModuleBaseを継承し、照度センサー固有の機能のみを実装
    共通機能（パケット作成、応答解析、エラーハンドリング等）はbase_moduleを活用
    """
    
    SENSOR_ID = 0x0121  # 照度センサー固定値
    
    def __init__(self, device_id: str):
        """
        Initialize illuminance sensor handler
        
        Args:
            device_id: Device ID as hex string (e.g., "2468800203400004")
        """
        super().__init__(device_id, self.SENSOR_ID, "illuminance")

    # 照度センサー固有の機能を実装
    # 共通機能（パケット作成、応答解析等）はModuleBaseから継承

    def get_device_info(self) -> Dict[str, Any]:
        """Get device information with illuminance-specific details"""
        base_info = super().get_device_info()
        base_info.update({
            "sensor_type": "Illuminance Sensor",
            "model": "BJ-MD-LUX-01", 
            "sensor_chip": "OPT3001 (TEXAS INSTRUMENTS)"
        })
        return base_info
    
    def get_module_specific_info(self) -> Dict[str, Any]:
        """Get illuminance module-specific information"""
        return {
            "sensor_type": "Illuminance Sensor",
            "model": "BJ-MD-LUX-01",
            "sensor_chip": "OPT3001 (TEXAS INSTRUMENTS)",
            "measurement_modes": ["瞬時値", "検知", "サンプリング"],
            "lux_range": "40.0-83865.0 Lux",
            "sampling_rates": ["1Hz", "2Hz"]
        }
    
    def create_parameter_structure(self):
        """Create illuminance parameter structure"""
        from .illuminance_parameters import IlluminanceParameters
        return IlluminanceParameters()
    
    # 照度センサー固有のヘルパーメソッド
    
    def wait_for_sensor_uplink(self, receive_callback, timeout: float = 30.0) -> Optional[bytes]:
        """
        Wait for illuminance sensor uplink (sensor_id=0x0121)
        
        Args:
            receive_callback: Function to receive data
            timeout: Timeout in seconds
            
        Returns:
            Uplink data bytes or None if timeout
        """
        return self.wait_for_uplink(receive_callback, self.SENSOR_ID, timeout, "illuminance sensor data")
    
    def wait_for_parameter_uplink(self, receive_callback, timeout: float = 30.0) -> Optional[bytes]:
        """
        Wait for parameter information uplink (sensor_id=0x0000)
        
        Args:
            receive_callback: Function to receive data
            timeout: Timeout in seconds
            
        Returns:
            Parameter uplink data bytes or None if timeout
        """
        return self.wait_for_uplink(receive_callback, 0x0000, timeout, "parameter info")
    
    def is_illuminance_sensor_uplink(self, uplink_data: bytes) -> bool:
        """
        Check if uplink data is from illuminance sensor
        
        Args:
            uplink_data: Raw uplink data
            
        Returns:
            True if from illuminance sensor (0x0121), False otherwise
        """
        if len(uplink_data) < 18:
            return False
        
        try:
            # Check packet type (should be 0x00 for uplink)
            if uplink_data[1] != 0x00:
                return False
            
            # Check sensor ID at offset 16-18
            import struct
            sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
            return sensor_id == self.SENSOR_ID
            
        except Exception:
            return False
    
    def is_parameter_info_uplink(self, uplink_data: bytes) -> bool:
        """
        Check if uplink data contains parameter information
        
        Args:
            uplink_data: Raw uplink data
            
        Returns:
            True if parameter info (sensor_id=0x0000), False otherwise
        """
        if len(uplink_data) < 18:
            return False
        
        try:
            # Check packet type (should be 0x00 for uplink)
            if uplink_data[1] != 0x00:
                return False
            
            # Check sensor ID at offset 16-18 (0x0000 for parameter info)
            import struct
            sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
            return sensor_id == 0x0000
            
        except Exception:
            return False
    
    def extract_device_id_from_uplink(self, uplink_data: bytes) -> Optional[int]:
        """
        Extract device ID from uplink packet
        
        Args:
            uplink_data: Raw uplink data
            
        Returns:
            Device ID as integer or None if cannot extract
        """
        if len(uplink_data) < 16:
            return None
        
        try:
            import struct
            device_id = struct.unpack('<Q', uplink_data[8:16])[0]
            return device_id
        except Exception:
            return None
    
    def validate_uplink_for_device(self, uplink_data: bytes) -> bool:
        """
        Validate that uplink is from the expected device
        
        Args:
            uplink_data: Raw uplink data
            
        Returns:
            True if from expected device, False otherwise
        """
        extracted_device_id = self.extract_device_id_from_uplink(uplink_data)
        return extracted_device_id == self.device_id if extracted_device_id is not None else False
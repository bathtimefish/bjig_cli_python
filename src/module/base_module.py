"""
BraveJIG Module Base Class

全モジュールで再利用可能な基底クラスと共通処理パターン
照度モジュールで検証済みのパターンを一般化

モジュール共通コマンド:
1. INSTANT_UPLINK (0x00) - 即時Uplink要求
2. SET_PARAMETER (0x05) - パラメータ設定
3. GET_PARAMETER (0x0D) - パラメータ取得
4. SENSOR_DFU (0x12) - センサーDFU
5. DEVICE_RESTART (0xFD) - デバイス再起動

Author: BraveJIG CLI Development Team  
Date: 2025-08-10
"""

import struct
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import IntEnum

from lib.datetime_util import get_current_unix_time


class ModuleCommand(IntEnum):
    """全モジュール共通コマンド定義"""
    INSTANT_UPLINK = 0x00      # 即時Uplink要求
    SET_PARAMETER = 0x05       # パラメータ設定
    GET_PARAMETER = 0x0D       # パラメータ取得
    SENSOR_DFU = 0x12         # センサーDFU
    DEVICE_RESTART = 0xFD     # デバイス再起動


@dataclass
class DownlinkRequest:
    """モジュール共通Downlinkリクエスト構造"""
    protocol_version: int = 0x01
    packet_type: int = 0x00  # Downlink request
    data_length: int = 0
    unix_time: int = 0
    device_id: int = 0
    sensor_id: int = 0x0000  # モジュールごとに設定
    cmd: int = 0x00
    order: int = 0x0000
    data: bytes = b''

    def to_bytes(self) -> bytes:
        """Convert to byte array using little-endian encoding"""
        packet = struct.pack('<BB', self.protocol_version, self.packet_type)
        packet += struct.pack('<H', self.data_length)
        packet += struct.pack('<L', self.unix_time)
        packet += struct.pack('<Q', self.device_id)
        packet += struct.pack('<H', self.sensor_id)
        packet += struct.pack('<B', self.cmd)
        packet += struct.pack('<H', self.order)
        packet += self.data
        return packet


@dataclass
class DownlinkResponse:
    """モジュール共通Downlinkレスポンス構造"""
    protocol_version: int
    packet_type: int
    unix_time: int
    device_id: int
    sensor_id: int
    order: int
    cmd: int
    result: int

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DownlinkResponse':
        """Parse Downlink response from byte array"""
        if len(data) < 20:
            raise ValueError(f"Response too short: {len(data)} bytes, expected 20+")
        
        protocol_version = data[0]
        packet_type = data[1]
        unix_time = struct.unpack('<L', data[2:6])[0]
        device_id = struct.unpack('<Q', data[6:14])[0]
        sensor_id = struct.unpack('<H', data[14:16])[0]
        order = struct.unpack('<H', data[16:18])[0]
        cmd = data[18]
        result = data[19]
        
        return cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            unix_time=unix_time,
            device_id=device_id,
            sensor_id=sensor_id,
            order=order,
            cmd=cmd,
            result=result
        )

    def is_success(self) -> bool:
        """Check if the response indicates success"""
        return self.result == 0x00


class ModuleBase(ABC):
    """
    BraveJIG モジュール基底クラス (現代化版)
    
    全モジュールで共通する処理パターンを提供:
    - Command Pipeline Pattern
    - Protocol Builder Pattern 
    - 統一エラーハンドリング
    - 現在動作中のロジックをベースに設計
    """
    
    def __init__(self, device_id: str, sensor_id: int, module_name: str):
        """
        Initialize module handler
        
        Args:
            device_id: Device ID as hex string (e.g., "2468800203400004")
            sensor_id: Sensor ID for this module type (e.g., 0x0121)
            module_name: Module name for logging (e.g., "illuminance")
        """
        self.device_id = int(device_id, 16)
        self.sensor_id = sensor_id
        self.module_name = module_name
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # === Protocol Builder Pattern (統一リクエスト作成) ===
    
    def create_instant_uplink_request(self) -> bytes:
        """Create instant uplink request - 動作確認済みパターン"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        data_payload = b''  # No data for instant uplink
        data_length = len(data_payload)
        
        # 動作確認済みのパターンを使用
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', self.sensor_id)     # SensorID
        packet += struct.pack('<B', 0x00)               # CMD: INSTANT_UPLINK
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA
        
        return packet
    
    def create_get_parameter_request(self) -> bytes:
        """Create get parameter request - 動作確認済みパターン"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        data_payload = struct.pack('<B', 0x00)  # Parameter info acquisition request
        data_length = len(data_payload)
        
        # spec 6-4に従った動作確認済みパターン
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: 0x0000 for parameter
        packet += struct.pack('<B', 0x0D)               # CMD: GET_DEVICE_SETTING
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA
        
        return packet
    
    def create_set_parameter_request(self, param_data: bytes) -> bytes:
        """Create set parameter request - 動作確認済みパターン"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        data_length = len(param_data)
        
        # spec 6-2に従った動作確認済みパターン  
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: 0x0000 for parameter
        packet += struct.pack('<B', 0x05)               # CMD: SET_REGISTER
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += param_data                            # DATA
        
        return packet
    
    def create_device_restart_request(self) -> bytes:
        """Create device restart request - 動作確認済みパターン"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        data_payload = b''  # No data for restart
        data_length = len(data_payload)
        
        # spec 6-5に従った動作確認済みパターン
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: 0x0000 for device restart
        packet += struct.pack('<B', 0xFD)               # CMD: DEVICE_RESTART
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA
        
        return packet

    # === Command Pipeline Pattern (統一実行フロー) ===
    
    def execute_command_with_response(self,
                                    request_packet: bytes,
                                    send_callback: Callable,
                                    receive_callback: Callable,
                                    timeout: float = 10.0,
                                    command_name: str = "command") -> Dict[str, Any]:
        """
        Execute command with downlink response pattern (動作確認済み)
        
        Args:
            request_packet: Request packet to send
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            command_name: Command name for logging
            
        Returns:
            Dict containing execution results
        """
        result = {
            "success": False,
            "command": command_name,
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}"
        }
        
        try:
            result["request_packet"] = request_packet.hex(' ').upper()
            
            self.logger.info(f"Sending {command_name} request: {request_packet.hex(' ').upper()}")
            
            if not send_callback(request_packet):
                result["error"] = f"Failed to send {command_name} request"
                return result
            
            # Wait for downlink response (動作確認済みのパターン)
            import time
            start_time = time.time()
            response_data = None
            
            while (time.time() - start_time) < timeout:
                response_data = receive_callback()
                if response_data and len(response_data) >= 2:
                    packet_type = response_data[1]
                    if packet_type == 0x01:  # Downlink response
                        break
                time.sleep(0.1)
            
            if not response_data:
                result["error"] = f"No response received within {timeout} seconds"
                return result
                
            # Parse downlink response
            response_info = self.parse_downlink_response(response_data)
            result["response"] = response_info
            
            if response_info["success"]:
                result["success"] = True
                result["message"] = f"{command_name.title()} completed successfully"
            else:
                error_desc = response_info.get('result_desc') or response_info.get('error', 'Unknown error')
                result["error"] = f"{command_name} failed: {error_desc}"
                
        except Exception as e:
            result["error"] = f"{command_name} execution failed: {str(e)}"
            self.logger.error(f"{command_name} error: {e}")
        
        return result

    # === 応答解析 (動作確認済み) ===
    
    def parse_downlink_response(self, response_data: bytes) -> Dict[str, Any]:
        """Parse downlink response using proven pattern"""
        try:
            response = DownlinkResponse.from_bytes(response_data)
            
            return {
                "success": response.is_success(),
                "protocol_version": f"0x{response.protocol_version:02X}",
                "packet_type": f"0x{response.packet_type:02X}",
                "unix_time": response.unix_time,
                "device_id": f"0x{response.device_id:016X}",
                "sensor_id": f"0x{response.sensor_id:04X}",
                "order": response.order,
                "cmd": f"0x{response.cmd:02X}",
                "cmd_name": self.get_cmd_name(response.cmd),
                "result": f"0x{response.result:02X}",
                "result_desc": self.get_result_description(response.result),
                "raw_data": response_data.hex(' ').upper(),
                "response_obj": response
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Response parse error: {str(e)}",
                "raw_data": response_data.hex(' ').upper()
            }

    def get_cmd_name(self, cmd: int) -> str:
        """Get command name from code"""
        cmd_names = {
            0x00: "INSTANT_UPLINK",
            0x05: "SET_PARAMETER", 
            0x0D: "GET_PARAMETER",
            0x12: "SENSOR_DFU",
            0xFD: "DEVICE_RESTART"
        }
        return cmd_names.get(cmd, f"UNKNOWN(0x{cmd:02X})")

    def get_result_description(self, result: int) -> str:
        """Get result code description (common error codes)"""
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

    def validate_device_id(self) -> bool:
        """Validate device ID format"""
        return 0 <= self.device_id <= 0xFFFFFFFFFFFFFFFF

    def get_device_info(self) -> Dict[str, Any]:
        """Get basic device information"""
        return {
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}",
            "module_name": self.module_name,
        }

    # === 抽象メソッド（各モジュールで実装） ===
    
    @abstractmethod
    def get_module_specific_info(self) -> Dict[str, Any]:
        """Get module-specific information (implemented by each module)"""
        pass

    @abstractmethod
    def create_parameter_structure(self) -> Any:
        """Create module-specific parameter structure"""
        pass


class UplinkWaitMixin:
    """Uplink待機処理の共通Mixin"""
    
    def wait_for_uplink(self,
                       receive_callback: Callable,
                       expected_sensor_id: int,
                       timeout: float = 30.0,
                       uplink_type: str = "sensor_data") -> Optional[bytes]:
        """
        Wait for uplink with specific sensor ID
        
        Args:
            receive_callback: Function to receive data
            expected_sensor_id: Expected sensor ID in uplink
            timeout: Timeout in seconds
            uplink_type: Type description for logging
            
        Returns:
            Uplink data bytes or None if timeout
        """
        self.logger.info(f"Waiting for {uplink_type} uplink from sensor {expected_sensor_id:04X}...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            uplink_data = receive_callback()
            if uplink_data and len(uplink_data) >= 18:
                packet_type = uplink_data[1]
                if packet_type == 0x00:  # Uplink notification
                    sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
                    if sensor_id == expected_sensor_id:
                        self.logger.info(f"{uplink_type.title()} uplink received successfully")
                        return uplink_data
            time.sleep(0.1)
        
        self.logger.warning(f"No {uplink_type} uplink received within {timeout} seconds")
        return None
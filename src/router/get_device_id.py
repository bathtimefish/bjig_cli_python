"""
BraveJIG Router Get Device ID Command

デバイスIDリスト取得コマンドの実装
JIG Info Request CMD=0xCF (全取得) または CMD=0x03-0x66 (インデックス指定) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any, Optional

from .base_command import ParameterizedRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class GetDeviceIdCommand(ParameterizedRouterCommand):
    """
    Device ID list retrieval command implementation
    
    Supports two modes:
    1. Get all device IDs (CMD=0xCF)
    2. Get specific device ID by index (CMD=0x03 + index)
    """

    @property
    def command_name(self) -> str:
        return "get_device_id"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.GET_DEVICE_ID_ALL  # Default command

    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate device ID command parameters
        
        Args:
            device_index: Optional device index (0-99) or None for all devices
            
        Returns:
            bool: True if parameters are valid
            
        Raises:
            ValueError: If device_index is out of range
        """
        device_index = kwargs.get('device_index')
        
        if device_index is not None:
            if not isinstance(device_index, int) or device_index < 0 or device_index > 99:
                raise ValueError(f"Device index must be between 0 and 99, got: {device_index}")
        
        return True

    def get_command_code(self, **kwargs) -> int:
        """
        Get command code based on device index parameter
        
        Args:
            device_index: Optional device index (0-99) or None for all devices
            
        Returns:
            int: JIG Info command code
        """
        device_index = kwargs.get('device_index')
        
        if device_index is None:
            # Get all device IDs
            return JigInfoCommand.GET_DEVICE_ID_ALL
        else:
            # Get specific device ID by index
            return self.protocol.cmd_from_device_index(device_index)

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process device ID response data"""
        base_data = super().process_response_data(response)
        
        # Process device ID data if available
        device_info = self._parse_device_id_data(response.data, response.cmd)
        
        base_data.update({
            "operation": "get_device_id",
            "device_info": device_info,
            "description": "BraveJIG router device ID information"
        })
        
        return base_data

    def _parse_device_id_data(self, data: bytes, cmd: int) -> Dict[str, Any]:
        """
        Parse device ID data from response
        
        Args:
            data: Raw device ID data bytes
            cmd: Command code that was used
            
        Returns:
            Dict containing parsed device ID information
        """
        if not data:
            return {
                "status": "no_device_data",
                "message": "No device ID data received from router",
                "command_type": self._get_command_type(cmd)
            }
        
        device_info = {
            "raw_data": data.hex(),
            "data_length": len(data),
            "command_type": self._get_command_type(cmd),
            "status": "device_data_received"
        }
        
        # Parse device ID data based on command type
        if cmd == JigInfoCommand.GET_DEVICE_ID_ALL:
            device_info.update(self._parse_all_devices_data(data))
        else:
            device_info.update(self._parse_single_device_data(data, cmd))
        
        return device_info

    def _get_command_type(self, cmd: int) -> str:
        """Get human-readable command type"""
        if cmd == JigInfoCommand.GET_DEVICE_ID_ALL:
            return "get_all_devices"
        else:
            device_index = cmd - 0x03  # CMD 0x03 corresponds to index 0
            return f"get_device_index_{device_index}"

    def _parse_all_devices_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse data for all devices command
        
        Args:
            data: Raw device list data
            
        Returns:
            Dict containing parsed device list
        """
        parsed_data = {
            "request_type": "all_devices",
            "devices": []
        }
        
        # Device ID parsing - format depends on BraveJIG specification
        # For now, provide basic parsing assuming 8-byte device IDs
        if len(data) >= 8 and len(data) % 8 == 0:
            device_count = len(data) // 8
            parsed_data["device_count"] = device_count
            
            for i in range(device_count):
                offset = i * 8
                device_id_bytes = data[offset:offset + 8]
                device_id = int.from_bytes(device_id_bytes, byteorder='little')
                
                parsed_data["devices"].append({
                    "index": i,
                    "device_id": f"0x{device_id:016x}",
                    "device_id_int": device_id,
                    "raw_bytes": device_id_bytes.hex()
                })
        else:
            parsed_data["note"] = f"Unexpected data length: {len(data)} bytes (expected multiple of 8)"
            parsed_data["device_count"] = 0
        
        return parsed_data

    def _parse_single_device_data(self, data: bytes, cmd: int) -> Dict[str, Any]:
        """
        Parse data for single device command
        
        Args:
            data: Raw device data
            cmd: Command code used
            
        Returns:
            Dict containing parsed single device info
        """
        device_index = cmd - 0x03
        
        parsed_data = {
            "request_type": "single_device",
            "requested_index": device_index
        }
        
        if len(data) >= 8:
            device_id_bytes = data[:8]
            device_id = int.from_bytes(device_id_bytes, byteorder='little')
            
            parsed_data.update({
                "device_id": f"0x{device_id:016x}",
                "device_id_int": device_id,
                "raw_bytes": device_id_bytes.hex(),
                "status": "device_found"
            })
        else:
            parsed_data.update({
                "status": "invalid_data",
                "note": f"Expected at least 8 bytes for device ID, got {len(data)}"
            })
        
        return parsed_data
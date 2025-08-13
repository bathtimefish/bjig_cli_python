"""
BraveJIG Router Remove Device ID Command

デバイスID削除コマンドの実装
JIG Info Request CMD=0x6B (全削除) または CMD=0x6C-0xCE (インデックス指定削除) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any, Optional

from .base_command import ParameterizedRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class RemoveDeviceIdCommand(ParameterizedRouterCommand):
    """
    Device ID removal command implementation
    
    Supports two modes:
    1. Remove all device IDs (CMD=0x6B)
    2. Remove specific device ID by index (CMD=0x6C + index)
    """

    @property
    def command_name(self) -> str:
        return "remove_device_id"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.REMOVE_DEVICE_ID_ALL  # Default command

    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate device ID removal parameters
        
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
            # Remove all device IDs
            return JigInfoCommand.REMOVE_DEVICE_ID_ALL
        else:
            # Remove specific device ID by index
            return self._cmd_from_remove_index(device_index)

    def _cmd_from_remove_index(self, index: int) -> int:
        """
        Convert device index to REMOVE_DEVICE_ID command code
        
        Args:
            index: Device index (0-99)
            
        Returns:
            int: Command code for removing device at index
        """
        if 0 <= index <= 99:
            # REMOVE_DEVICE_ID_INDEX_0 = 0x6C, so index 0 -> 0x6C, index 1 -> 0x6D, etc.
            return JigInfoCommand.REMOVE_DEVICE_ID_INDEX_0 + index
        else:
            raise ValueError(f"Device index {index} out of range (0-99)")

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process device ID removal response data"""
        base_data = super().process_response_data(response)
        
        # Process removal result information
        removal_info = self._parse_removal_result(response.data, response.cmd)
        
        base_data.update({
            "operation": "remove_device_id",
            "removal_info": removal_info,
            "description": "BraveJIG router device ID removal operation"
        })
        
        return base_data

    def _parse_removal_result(self, data: bytes, cmd: int) -> Dict[str, Any]:
        """
        Parse device ID removal result data
        
        Args:
            data: Raw removal result data bytes
            cmd: Command code that was used
            
        Returns:
            Dict containing parsed removal result information
        """
        removal_info = {
            "command_type": self._get_removal_command_type(cmd),
            "command_code": f"0x{cmd:02x}",
            "status": "removal_completed"
        }
        
        if cmd == JigInfoCommand.REMOVE_DEVICE_ID_ALL:
            removal_info.update({
                "operation_type": "remove_all_devices",
                "description": "All device IDs have been removed from the router"
            })
        else:
            device_index = cmd - JigInfoCommand.REMOVE_DEVICE_ID_INDEX_0
            removal_info.update({
                "operation_type": "remove_single_device",
                "device_index": device_index,
                "description": f"Device ID at index {device_index} has been removed from the router"
            })
        
        # Parse any additional response data
        if data:
            removal_info.update({
                "raw_data": data.hex(),
                "data_length": len(data),
                "additional_info": "Response contains additional data - check specification for details"
            })
        else:
            removal_info["additional_info"] = "No additional response data"
        
        return removal_info

    def _get_removal_command_type(self, cmd: int) -> str:
        """Get human-readable command type for removal operation"""
        if cmd == JigInfoCommand.REMOVE_DEVICE_ID_ALL:
            return "remove_all_devices"
        else:
            device_index = cmd - JigInfoCommand.REMOVE_DEVICE_ID_INDEX_0
            return f"remove_device_index_{device_index}"

    def format_output(self, result, output_format: str = "json") -> str:
        """
        Format device ID removal command result for output
        
        Args:
            result: Command execution result
            output_format: Output format ("json", "text")
            
        Returns:
            str: Formatted output string
        """
        if output_format.lower() == "json":
            return result.to_json()
        else:
            # Enhanced text format for device ID removal
            if result.success:
                removal_info = result.response_data.get('removal_info', {})
                operation_type = removal_info.get('operation_type', 'unknown')
                
                if operation_type == "remove_all_devices":
                    return "All device IDs removed successfully"
                elif operation_type == "remove_single_device":
                    device_index = removal_info.get('device_index', 'unknown')
                    return f"Device ID at index {device_index} removed successfully"
                else:
                    return "Device ID removal completed successfully"
            else:
                return f"Failed to remove device ID: {result.error_message}"
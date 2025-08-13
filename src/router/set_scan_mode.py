"""
BraveJIG Router Set Scan Mode Command

スキャンモード設定コマンドの実装
JIG Info Request CMD=0x6A (LEGACY) または CMD=0x69 (LONG_RANGE) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import ParameterizedRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class SetScanModeCommand(ParameterizedRouterCommand):
    """
    Router scan mode configuration command implementation
    
    Supports setting scan mode to:
    - Mode 0: Legacy/Standard BLE scanning (CMD=0x6A)
    - Mode 1: Long Range BLE scanning (CMD=0x69)
    """

    @property
    def command_name(self) -> str:
        return "set_scan_mode"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.SET_SCAN_MODE_LEGACY  # Default command

    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate scan mode parameters
        
        Args:
            mode: Scan mode value (0=Legacy, 1=Long Range)
            
        Returns:
            bool: True if parameters are valid
            
        Raises:
            ValueError: If mode is invalid
        """
        mode = kwargs.get('mode')
        
        if mode is None:
            raise ValueError("Mode parameter is required")
        
        if not isinstance(mode, int) or mode not in [0, 1]:
            raise ValueError(f"Mode must be 0 (Legacy) or 1 (Long Range), got: {mode}")
        
        return True

    def get_command_code(self, **kwargs) -> int:
        """
        Get command code based on scan mode parameter
        
        Args:
            mode: Scan mode value (0=Legacy, 1=Long Range)
            
        Returns:
            int: JIG Info command code
        """
        mode = kwargs.get('mode')
        
        if mode == 0:
            return JigInfoCommand.SET_SCAN_MODE_LONG_RANGE
        elif mode == 1:
            return JigInfoCommand.SET_SCAN_MODE_LEGACY
        else:
            # This should not happen due to validation, but just in case
            raise ValueError(f"Invalid scan mode: {mode}")

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process scan mode configuration response data"""
        base_data = super().process_response_data(response)
        
        # Determine which mode was set based on command code
        mode_info = self._get_mode_info_from_cmd(response.cmd)
        
        base_data.update({
            "operation": "set_scan_mode",
            "mode_info": mode_info,
            "description": f"BraveJIG router scan mode set to {mode_info['mode_name']}"
        })
        
        return base_data

    def _get_mode_info_from_cmd(self, cmd: int) -> Dict[str, Any]:
        """
        Get mode information from command code
        
        Args:
            cmd: Command code that was executed
            
        Returns:
            Dict containing mode information
        """
        if cmd == JigInfoCommand.SET_SCAN_MODE_LEGACY:
            return {
                "mode_value": 0,
                "mode_name": "Legacy Mode",
                "mode_description": "Standard BLE scanning with normal range",
                "command_code": f"0x{cmd:02x}"
            }
        elif cmd == JigInfoCommand.SET_SCAN_MODE_LONG_RANGE:
            return {
                "mode_value": 1,
                "mode_name": "Long Range Mode", 
                "mode_description": "Extended range BLE scanning for better coverage",
                "command_code": f"0x{cmd:02x}"
            }
        else:
            return {
                "mode_value": None,
                "mode_name": "Unknown Mode",
                "mode_description": f"Unknown scan mode command: 0x{cmd:02x}",
                "command_code": f"0x{cmd:02x}"
            }

    def create_request(self, **kwargs) -> bytes:
        """
        Create scan mode configuration request
        
        Args:
            mode: Scan mode to set (0=Legacy, 1=Long Range)
            
        Returns:
            bytes: Encoded JIG Info request packet
        """
        # Store mode for response processing
        self._requested_mode = kwargs.get('mode')
        return super().create_request(**kwargs)

    def format_output(self, result, output_format: str = "json") -> str:
        """
        Format scan mode command result for output
        
        Args:
            result: Command execution result
            output_format: Output format ("json", "text")
            
        Returns:
            str: Formatted output string
        """
        if output_format.lower() == "json":
            return result.to_json()
        else:
            # Enhanced text format for scan mode
            if result.success:
                mode_info = result.response_data.get('mode_info', {})
                mode_name = mode_info.get('mode_name', 'Unknown')
                return f"Scan mode set to {mode_name} successfully"
            else:
                return f"Failed to set scan mode: {result.error_message}"
"""
BraveJIG Router Get Scan Mode Command

スキャンモード取得コマンドの実装
JIG Info Request CMD=0x67 (GET_SCAN_MODE) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import SimpleRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class GetScanModeCommand(SimpleRouterCommand):
    """
    Router scan mode retrieval command implementation
    
    Sends JIG Info Request with CMD=0x67 to retrieve the current
    scanning mode configuration from the BraveJIG router.
    """

    @property
    def command_name(self) -> str:
        return "get_scan_mode"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.GET_SCAN_MODE

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process scan mode response data"""
        base_data = super().process_response_data(response)
        
        # Process scan mode data if available
        scan_mode_info = self._parse_scan_mode_data(response.data)
        
        base_data.update({
            "operation": "get_scan_mode",
            "scan_mode_info": scan_mode_info,
            "description": "BraveJIG router current scan mode configuration"
        })
        
        return base_data

    def _parse_scan_mode_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse scan mode data from response
        
        Args:
            data: Raw scan mode data bytes
            
        Returns:
            Dict containing parsed scan mode information
        """
        if not data:
            return {
                "status": "no_scan_mode_data",
                "message": "No scan mode data received from router"
            }
        
        scan_mode_info = {
            "raw_data": data.hex(),
            "data_length": len(data),
            "status": "scan_mode_data_received"
        }
        
        # Parse scan mode value - typically a single byte or integer
        if len(data) >= 1:
            mode_value = data[0]
            scan_mode_info.update({
                "mode_value": mode_value,
                "mode_description": self._get_scan_mode_description(mode_value),
                "parsed": True
            })
            
            # Additional parsing for multi-byte scan mode data
            if len(data) > 1:
                scan_mode_info["additional_data"] = data[1:].hex()
                scan_mode_info["note"] = "Additional scan mode parameters present"
        else:
            scan_mode_info.update({
                "parsed": False,
                "note": "Insufficient data for scan mode parsing"
            })
        
        return scan_mode_info

    def _get_scan_mode_description(self, mode_value: int) -> str:
        """
        Get human-readable description for scan mode value
        
        Args:
            mode_value: Numeric scan mode value
            
        Returns:
            str: Human-readable scan mode description
        """
        scan_modes = {
            0: "Legacy Mode - Standard BLE scanning",
            1: "Long Range Mode - Extended range BLE scanning",
            # Add more modes as specified in BraveJIG documentation
        }
        
        return scan_modes.get(mode_value, f"Unknown scan mode: {mode_value}")
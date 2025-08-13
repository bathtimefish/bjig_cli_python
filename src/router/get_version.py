"""
BraveJIG Router Get Version Command

ルーターファームウェアバージョン取得コマンドの実装
JIG Info Request CMD=0x02 (GET_VERSION) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import SimpleRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class GetVersionCommand(SimpleRouterCommand):
    """
    Router firmware version retrieval command implementation
    
    Sends JIG Info Request with CMD=0x02 to retrieve the firmware version
    information from the BraveJIG router.
    """

    @property
    def command_name(self) -> str:
        return "get_version"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.GET_VERSION

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process firmware version response data"""
        base_data = super().process_response_data(response)
        
        # Process version data if available
        version_info = self._parse_version_data(response.data)
        
        base_data.update({
            "operation": "get_version",
            "version_info": version_info,
            "description": "BraveJIG router firmware version information"
        })
        
        return base_data

    def _parse_version_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse firmware version data from response
        
        Args:
            data: Raw version data bytes
            
        Returns:
            Dict containing parsed version information
        """
        if not data:
            return {
                "status": "no_version_data",
                "message": "No version data received from router"
            }
        
        # Version data parsing - exact format depends on BraveJIG specification
        # For now, provide raw data and basic parsing
        version_info = {
            "raw_data": data.hex(),
            "data_length": len(data),
            "status": "version_data_received"
        }
        
        # Try to extract version string if data contains text
        try:
            if len(data) > 0:
                # Attempt to decode as text (common for version strings)
                version_text = data.decode('utf-8', errors='ignore').strip('\x00')
                if version_text and all(ord(c) < 128 for c in version_text):
                    version_info["version_string"] = version_text
                    version_info["parsed"] = True
                else:
                    version_info["parsed"] = False
                    version_info["note"] = "Binary version data - check specification for parsing details"
        except Exception:
            version_info["parsed"] = False
            version_info["note"] = "Unable to parse version data as text"
        
        return version_info
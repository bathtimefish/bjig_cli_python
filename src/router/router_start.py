"""
BraveJIG Router Start Command

ルーター起動コマンドの実装
JIG Info Request CMD=0x01 (ROUTER_START) を使用

Author: BraveJIG CLI Development Team  
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import SimpleRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class RouterStartCommand(SimpleRouterCommand):
    """
    Router start command implementation
    
    Sends JIG Info Request with CMD=0x01 to start the BraveJIG router.
    This command initiates router operations and enables device scanning.
    """

    @property
    def command_name(self) -> str:
        return "router_start"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.ROUTER_START

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process router start response data"""
        base_data = super().process_response_data(response)
        
        # Add router start specific information
        base_data.update({
            "operation": "start",
            "status": "Router started successfully" if response.data else "Router start initiated",
            "description": "BraveJIG router has been started and is ready for device operations"
        })
        
        return base_data
"""
BraveJIG Router Stop Command

ルーター停止コマンドの実装
JIG Info Request CMD=0x00 (ROUTER_STOP) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import SimpleRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class RouterStopCommand(SimpleRouterCommand):
    """
    Router stop command implementation
    
    Sends JIG Info Request with CMD=0x00 to stop the BraveJIG router.
    This command terminates router operations and stops device scanning.
    """

    @property
    def command_name(self) -> str:
        return "router_stop"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.ROUTER_STOP

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process router stop response data"""
        base_data = super().process_response_data(response)
        
        # Add router stop specific information
        base_data.update({
            "operation": "stop",
            "status": "Router stopped successfully" if response.data else "Router stop initiated",
            "description": "BraveJIG router has been stopped and device operations are terminated"
        })
        
        return base_data
"""
BraveJIG Router Keep Alive Command

キープアライブコマンドの実装
JIG Info Request CMD=0xD0 (KEEP_ALIVE) を使用

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Dict, Any

from .base_command import SimpleRouterCommand
from protocol.bjig_protocol import JigInfoCommand, JigInfoResponse


class KeepAliveCommand(SimpleRouterCommand):
    """
    Router keep alive command implementation
    
    Sends JIG Info Request with CMD=0xD0 to maintain connection/session
    with the BraveJIG router. This prevents timeout and keeps the 
    communication channel active.
    """

    @property
    def command_name(self) -> str:
        return "keep_alive"

    @property
    def jig_info_cmd(self) -> JigInfoCommand:
        return JigInfoCommand.KEEP_ALIVE

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Process keep alive response data"""
        base_data = super().process_response_data(response)
        
        # Add keep alive specific information
        base_data.update({
            "operation": "keep_alive",
            "status": "Connection maintained successfully",
            "description": "Keep alive signal sent to BraveJIG router to maintain active connection"
        })
        
        return base_data
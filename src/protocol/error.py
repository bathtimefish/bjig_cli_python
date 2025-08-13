"""
BraveJIG Error Notification Protocol

エラー通知の構造定義と処理関数
BraveJIG仕様書 5-1-5. エラー通知 に基づく実装

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

from .common import interpret_error_reason


@dataclass
class ErrorNotification:
    """Error notification structure following specs 5-1-5 (Type: 0xFF)"""
    protocol_version: int
    packet_type: int  # 0xFF for error notification
    unix_time: int
    reason: int

    @classmethod
    def from_bytes(cls, data: bytes) -> 'ErrorNotification':
        """Parse Error notification from byte array (7 bytes total)"""
        if len(data) < 7:
            raise ValueError(f"Error notification too short: {len(data)} bytes, expected 7")
        
        protocol_version = data[0]
        packet_type = data[1]  # Should be 0xFF
        unix_time = struct.unpack('<L', data[2:6])[0]
        reason = data[6]
        
        return cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            unix_time=unix_time,
            reason=reason
        )

    def get_error_description(self) -> str:
        """Get human-readable error description"""
        return interpret_error_reason(self.reason)
    
    def to_json(self) -> str:
        """Convert error notification to JSON format"""
        result = {
            "protocol_version": f"0x{self.protocol_version:02X}",
            "packet_type": f"0x{self.packet_type:02X}",
            "packet_type_name": "ERROR_NOTIFICATION",
            "unix_time": self.unix_time,
            "timestamp": datetime.fromtimestamp(self.unix_time).strftime('%Y-%m-%d %H:%M:%S'),
            "reason": f"0x{self.reason:02X}",
            "reason_description": self.get_error_description(),
            "raw_data": f"{self.protocol_version:02X} {self.packet_type:02X} {self.unix_time & 0xFF:02X} {(self.unix_time >> 8) & 0xFF:02X} {(self.unix_time >> 16) & 0xFF:02X} {(self.unix_time >> 24) & 0xFF:02X} {self.reason:02X}"
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)


def parse_error_notification(data: bytes) -> ErrorNotification:
    """
    Parse error notification data
    
    Args:
        data: Raw error notification bytes
        
    Returns:
        ErrorNotification: Parsed error notification object
    """
    return ErrorNotification.from_bytes(data)
"""
BraveJIG JIG Info Request/Response Protocol

JIG Info リクエスト・レスポンスの構造定義と処理関数

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
import json
import sys
from enum import IntEnum
from dataclasses import dataclass, asdict
from typing import Any, Optional, Dict
from datetime import datetime

from lib.datetime_util import create_protocol_time_fields


class JigInfoCommand(IntEnum):
    """JIG Info command mapping from CLI to CMD values"""
    ROUTER_STOP = 0x00
    ROUTER_START = 0x01
    GET_VERSION = 0x02
    GET_DEVICE_ID_INDEX_0 = 0x03
    # ... pattern continues for indices
    GET_DEVICE_ID_INDEX_99 = 0x66
    GET_SCAN_MODE = 0x67
    SET_SCAN_MODE_LONG_RANGE = 0x69
    SET_SCAN_MODE_LEGACY = 0x6A
    REMOVE_DEVICE_ID_ALL = 0x6B
    REMOVE_DEVICE_ID_INDEX_0 = 0x6C
    # ... pattern continues for indices
    REMOVE_DEVICE_ID_INDEX_99 = 0xCE
    GET_DEVICE_ID_ALL = 0xCF
    KEEP_ALIVE = 0xD0
    # Error notifications and other commands continue...


@dataclass
class JigInfoRequest:
    """JIG Info request structure (no Data Length field)"""
    protocol_version: int = 0x01
    packet_type: int = 0x01
    cmd: int = 0x00
    local_time: int = 0
    unix_time: int = 0

    def to_bytes(self) -> bytes:
        """Convert to byte array using little-endian encoding"""
        packet = struct.pack('<BBB', self.protocol_version, self.packet_type, self.cmd)
        packet += struct.pack('<L', self.local_time)
        packet += struct.pack('<L', self.unix_time)
        return packet


@dataclass
class JigInfoResponse:
    """JIG Info response structure (real hardware format)"""
    protocol_version: int
    packet_type: int
    unix_time: int
    cmd: int
    router_device_id: int
    data: bytes
    
    # Parsed data fields for specific commands
    parsed_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_bytes(cls, data: bytes) -> 'JigInfoResponse':
        """Parse JIG Info response from byte array using real hardware format"""
        if len(data) < 15:
            raise ValueError(f"JIG Info response too short: {len(data)} bytes, expected 15+")
        
        protocol_version = data[0]
        packet_type = data[1]
        unix_time = struct.unpack('<L', data[2:6])[0]
        cmd = data[6]
        router_device_id = struct.unpack('<Q', data[7:15])[0]
        response_data = data[15:] if len(data) > 15 else b''
        
        # Create response instance
        response = cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            unix_time=unix_time,
            cmd=cmd,
            router_device_id=router_device_id,
            data=response_data
        )
        
        # Parse command-specific data
        response._parse_command_data()
        
        return response
    
    def _parse_command_data(self):
        """Parse command-specific data based on CMD value"""
        if self.cmd == 0x02 and len(self.data) >= 3:  # GET_VERSION
            major = self.data[0]
            minor = self.data[1] 
            build = self.data[2]
            self.parsed_data = {
                "major": major,
                "minor": minor,
                "build": build,
                "version_string": f"{major}.{minor}.{build}"
            }
        elif self.cmd == 0x67 and len(self.data) >= 1:  # GET_SCAN_MODE
            mode = self.data[0]
            mode_name = "Long Range" if mode == 0x00 else "Legacy" if mode == 0x01 else "Long Range"
            self.parsed_data = {
                "mode": mode,
                "mode_name": mode_name
            }
        elif (self.cmd in [0x00, 0x01, 0x69, 0x6A, 0x6B, 0xD0] or (0x6C <= self.cmd <= 0xCE)) and len(self.data) >= 1:  # ROUTER_STOP/START/SET_SCAN_MODE/REMOVE_DEVICE_ID/KEEP_ALIVE
            success = self.data[0]
            self.parsed_data = {
                "success": success == 0x01,
                "result": "Success" if success == 0x01 else "Failed"
            }
        elif self.cmd == 0xCF and len(self.data) >= 9:  # GET_DEVICE_ID_ALL
            # Parse device ID list: first byte is device count, followed by 8-byte device IDs
            device_count = self.data[0]
            devices = []
            
            # Parse 8-byte device IDs starting from offset 1
            offset = 1
            device_index = 0
            
            while offset + 8 <= len(self.data) and device_index < device_count:
                device_id_bytes = self.data[offset:offset + 8]
                device_id = struct.unpack('<Q', device_id_bytes)[0]
                devices.append({
                    "index": device_index,
                    "device_id": f"{device_id:016X}"
                })
                offset += 8
                device_index += 1
            
            self.parsed_data = {
                "device_count": device_count,
                "devices": devices
            }
        elif 0x03 <= self.cmd <= 0x66 and len(self.data) >= 9:  # GET_DEVICE_ID_INDEX_X
            # Parse single device ID (9 bytes: 1 byte index + 8 bytes device ID)
            index = self.data[0]
            device_id_bytes = self.data[1:9]
            device_id = struct.unpack('<Q', device_id_bytes)[0]
            self.parsed_data = {
                "index": index,
                "device_id": f"{device_id:016X}"
            }
    
    def to_json(self) -> str:
        """Convert response to JSON format"""
        result = {
            "protocol_version": f"0x{self.protocol_version:02X}",
            "packet_type": f"0x{self.packet_type:02X}",
            "packet_type_name": "JIG_INFO_RESPONSE",
            "unix_time": self.unix_time,
            "timestamp": datetime.fromtimestamp(self.unix_time).strftime('%Y-%m-%d %H:%M:%S'),
            "cmd": f"0x{self.cmd:02X}",
            "cmd_name": self._get_cmd_name(),
            "router_device_id": f"{self.router_device_id:016X}",
            "raw_data": self.data.hex(' ').upper() if self.data else "None"
        }
        
        # Add parsed data if available
        if self.parsed_data:
            result["data"] = self.parsed_data
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    def _get_cmd_name(self) -> str:
        """Get command name from CMD value"""
        cmd_names = {
            0x00: "ROUTER_STOP",
            0x01: "ROUTER_START",
            0x02: "GET_VERSION",
            0x67: "GET_SCAN_MODE", 
            0x69: "SET_SCAN_MODE_LONG_RANGE",
            0x6A: "SET_SCAN_MODE_LEGACY",
            0x6B: "REMOVE_DEVICE_ID_ALL",
            0xCF: "GET_DEVICE_ID_ALL",
            0xD0: "KEEP_ALIVE"
        }
        
        # Handle GET_DEVICE_ID_INDEX_X commands (0x03-0x66)
        if 0x03 <= self.cmd <= 0x66:
            index = self.cmd - 0x03
            return f"GET_DEVICE_ID_INDEX_{index}"
        
        # Handle REMOVE_DEVICE_ID_INDEX_X commands (0x6C-0xCE)
        if 0x6C <= self.cmd <= 0xCE:
            index = self.cmd - 0x6C
            return f"REMOVE_DEVICE_ID_INDEX_{index}"
        
        return cmd_names.get(self.cmd, f"UNKNOWN(0x{self.cmd:02X})")


def create_jig_info_request(cmd: int) -> bytes:
    """
    Create JIG Info request using time values acceptable to BraveJIG router
    
    Args:
        cmd: JIG Info command value
        
    Returns:
        bytes: Encoded request packet
    """
    import time
    import struct
    from datetime import datetime, timezone, timedelta
    
    protocol_version = 0x01
    packet_type = 0x01
    
    # Use current UTC time as base
    current_utc = int(time.time())
    
    # Calculate JST time (UTC + 9 hours) for local_time field
    jst_time = current_utc + 9 * 3600
    
    # Use current UTC time for unix_time field
    unix_time = current_utc
    
    # Pack the request packet
    packet = struct.pack('<BBB', protocol_version, packet_type, cmd)
    packet += struct.pack('<L', jst_time)  # Local Time (JST)
    packet += struct.pack('<L', unix_time)  # Unix Time (UTC)
    return packet


def parse_jig_info_response(data: bytes) -> JigInfoResponse:
    """
    Parse JIG Info response data
    
    Args:
        data: Raw response bytes
        
    Returns:
        JigInfoResponse: Parsed response object
    """
    return JigInfoResponse.from_bytes(data)
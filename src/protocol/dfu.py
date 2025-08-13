"""
BraveJIG DFU Request/Response Protocol

DFU (Device Firmware Update) リクエスト・レスポンスの構造定義と処理関数
BraveJIG仕様書 5-2-3. DFU リクエスト に基づく実装

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
from dataclasses import dataclass
from typing import List

from lib.datetime_util import get_current_unix_time


@dataclass
class DfuRequest:
    """DFU request structure (Type 0x03)"""
    protocol_version: int = 0x01
    packet_type: int = 0x03
    unix_time: int = 0
    total_length: int = 0

    def to_bytes(self) -> bytes:
        """Convert to byte array using little-endian encoding"""
        packet = struct.pack('<BB', self.protocol_version, self.packet_type)
        packet += struct.pack('<L', self.unix_time)
        packet += struct.pack('<L', self.total_length)
        return packet


@dataclass
class DfuResponse:
    """DFU response structure (Type 0x03)"""
    protocol_version: int
    packet_type: int
    unix_time: int
    result: int

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DfuResponse':
        """Parse DFU response from byte array"""
        if len(data) < 7:
            raise ValueError("DFU response too short")
        
        protocol_version, packet_type = struct.unpack('<BB', data[:2])
        unix_time = struct.unpack('<L', data[2:6])[0]
        result = struct.unpack('<B', data[6:7])[0]
        
        return cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            unix_time=unix_time,
            result=result
        )

    def to_json(self) -> str:
        """Convert DFU response to JSON format"""
        import json
        from lib.datetime_util import unix_time_to_readable
        
        data = {
            "protocol_version": f"0x{self.protocol_version:02X}",
            "packet_type": f"0x{self.packet_type:02X}",
            "packet_type_name": "DFU_RESPONSE",
            "unix_time": self.unix_time,
            "timestamp": unix_time_to_readable(self.unix_time),
            "result": f"0x{self.result:02X}",
            "result_description": "DFU Ready" if self.result == 0x01 else "DFU Rejected",
            "success": self.result == 0x01
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)


@dataclass
class DfuChunk:
    """DFU firmware chunk for transfer"""
    packet_size: int
    dfu_image: bytes

    def to_bytes(self) -> bytes:
        """Convert chunk to byte array"""
        packet = struct.pack('<H', self.packet_size)
        packet += self.dfu_image
        return packet

    @classmethod
    def from_firmware_data(cls, firmware_data: bytes, offset: int) -> 'DfuChunk':
        """Create chunk from firmware data at specified offset"""
        remaining = len(firmware_data) - offset
        chunk_size = min(1024, remaining)
        
        chunk_data = firmware_data[offset:offset + chunk_size]
        
        return cls(
            packet_size=chunk_size,
            dfu_image=chunk_data
        )


def create_dfu_request(total_length: int) -> bytes:
    """
    Create DFU initiation request (Phase 1)
    
    Args:
        total_length: Total firmware size in bytes
        
    Returns:
        bytes: Encoded DFU request packet
    """
    unix_time = get_current_unix_time()
    
    request = DfuRequest(
        unix_time=unix_time,
        total_length=total_length
    )
    
    return request.to_bytes()


def parse_dfu_response(data: bytes) -> DfuResponse:
    """
    Parse DFU response data
    
    Args:
        data: Raw DFU response bytes
        
    Returns:
        DfuResponse: Parsed DFU response
    """
    return DfuResponse.from_bytes(data)


def split_firmware_into_chunks(firmware_data: bytes) -> List[bytes]:
    """
    Split firmware into properly sized chunks for DFU transfer
    
    Args:
        firmware_data: Complete firmware binary data
        
    Returns:
        List[bytes]: List of chunk packets ready for transmission
    """
    chunks = []
    total_size = len(firmware_data)
    offset = 0
    
    while offset < total_size:
        # Create chunk from current offset
        chunk = DfuChunk.from_firmware_data(firmware_data, offset)
        chunks.append(chunk.to_bytes())
        
        # Move to next chunk
        offset += chunk.packet_size
    
    return chunks
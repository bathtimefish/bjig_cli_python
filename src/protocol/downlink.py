"""
BraveJIG Downlink Request/Response Protocol

Downlink リクエスト・レスポンスの構造定義と処理関数
モジュール通信用のDownlinkプロトコル実装

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
from dataclasses import dataclass

from lib.datetime_util import get_current_unix_time
from .common import SensorType


@dataclass
class DownlinkRequest:
    """Downlink request structure with Data Length field"""
    protocol_version: int = 0x01
    packet_type: int = 0x02
    data_length: int = 0
    unix_time: int = 0
    device_id: int = 0
    sensor_id: int = 0
    request_id: int = 0
    data: bytes = b''

    def to_bytes(self) -> bytes:
        """Convert to byte array using little-endian encoding"""
        packet = struct.pack('<BBH', self.protocol_version, self.packet_type, self.data_length)
        packet += struct.pack('<L', self.unix_time)
        packet += struct.pack('<Q', self.device_id)
        packet += struct.pack('<H', self.sensor_id)
        packet += struct.pack('<B', self.request_id)
        packet += self.data
        return packet


@dataclass
class DownlinkResponse:
    """Downlink response structure (fixed 19-byte structure)"""
    protocol_version: int
    packet_type: int
    data_length: int
    unix_time: int
    device_id: int
    sensor_id: int
    request_id: int
    result: int

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DownlinkResponse':
        """Parse Downlink response from 19-byte array"""
        if len(data) != 19:
            raise ValueError(f"Downlink response must be 19 bytes, got {len(data)}")
        
        protocol_version, packet_type = struct.unpack('<BB', data[:2])
        data_length = struct.unpack('<H', data[2:4])[0]
        unix_time = struct.unpack('<L', data[4:8])[0]
        device_id = struct.unpack('<Q', data[8:16])[0]
        sensor_id = struct.unpack('<H', data[16:18])[0]
        result = struct.unpack('<B', data[18:19])[0]
        
        return cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            data_length=data_length,
            unix_time=unix_time,
            device_id=device_id,
            sensor_id=sensor_id,
            request_id=0,  # Not present in response
            result=result
        )


@dataclass
class UplinkNotification:
    """Uplink notification structure from device modules"""
    protocol_version: int
    packet_type: int
    data_length: int
    unix_time: int
    device_id: int
    sensor_id: int
    rssi: int        # RSSI value (signed int, 1 byte)
    order: int       # Order/sequence number (unsigned int, 2 bytes)
    data: bytes      # actual payload data

    @classmethod
    def from_bytes(cls, data: bytes) -> 'UplinkNotification':
        """Parse Uplink notification from byte array"""
        if len(data) < 21:
            raise ValueError("Uplink notification too short (minimum 21 bytes required)")
        
        protocol_version, packet_type = struct.unpack('<BB', data[:2])
        data_length = struct.unpack('<H', data[2:4])[0]
        unix_time = struct.unpack('<L', data[4:8])[0]
        device_id = struct.unpack('<Q', data[8:16])[0]
        sensor_id = struct.unpack('<H', data[16:18])[0]
        
        # RSSI (byte 18) - signed int
        rssi = struct.unpack('<b', data[18:19])[0]  # 'b' for signed byte
        
        # Order/sequence number (bytes 19-20) - unsigned int, little endian
        order = struct.unpack('<H', data[19:21])[0]
        
        # Data starts at byte 21
        notification_data = data[21:] if len(data) > 21 else b''

        return cls(
            protocol_version=protocol_version,
            packet_type=packet_type,
            data_length=data_length,
            unix_time=unix_time,
            device_id=device_id,
            sensor_id=sensor_id,
            rssi=rssi,
            order=order,
            data=notification_data
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        from datetime import datetime
        
        return {
            "protocol_version": f"0x{self.protocol_version:02X}",
            "packet_type": f"0x{self.packet_type:02X}",
            "packet_type_name": "UPLINK_NOTIFICATION",
            "data_length": self.data_length,
            "unix_time": self.unix_time,
            "timestamp": datetime.fromtimestamp(self.unix_time).strftime('%Y-%m-%d %H:%M:%S'),
            "device_id": f"{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}",
            "rssi": self.rssi,
            "order": self.order,
            "data_hex": self.data.hex(' ').upper(),
            "data_length_bytes": len(self.data)
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def create_downlink_request(device_id: int, sensor_id: int, 
                          request_id: int = 0x01, data: bytes = b'') -> bytes:
    """
    Create Downlink request using proven pattern from scripts/downlink_test.py
    
    Args:
        device_id: Target device ID
        sensor_id: Target sensor type ID
        request_id: Request identifier
        data: Additional data payload
        
    Returns:
        bytes: Encoded request packet
    """
    unix_time = get_current_unix_time()
    data_length = 13 + len(data)  # Fixed header size + data
    
    request = DownlinkRequest(
        data_length=data_length,
        unix_time=unix_time,
        device_id=device_id,
        sensor_id=sensor_id,
        request_id=request_id,
        data=data
    )
    
    return request.to_bytes()


def parse_downlink_response(data: bytes) -> DownlinkResponse:
    """
    Parse Downlink response data
    
    Args:
        data: Raw response bytes
        
    Returns:
        DownlinkResponse: Parsed response object
    """
    return DownlinkResponse.from_bytes(data)


def parse_uplink_notification(data: bytes) -> UplinkNotification:
    """
    Parse Uplink notification data
    
    Args:
        data: Raw notification bytes
        
    Returns:
        UplinkNotification: Parsed notification object
    """
    return UplinkNotification.from_bytes(data)
"""
BraveJIG Protocol Layer - Unified Interface

BraveJIGプロトコル通信の統一インターフェース
分割されたプロトコルモジュールを統合して提供

Key features:
- JIG Info command support with real device mappings
- Downlink request/response handling
- DFU (Device Firmware Update) support
- Error notification handling
- Little-endian encoding throughout
- Integration with AsyncSerialMonitor

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from typing import Any, Dict, List, Tuple, Optional, Union

from .common import (
    SensorType, TEST_DEVICES,
    cmd_from_device_index, scan_mode_cmd, interpret_error_reason
)
from .jiginfo import (
    JigInfoCommand, JigInfoRequest, JigInfoResponse,
    create_jig_info_request, parse_jig_info_response
)
from .dfu import (
    DfuRequest, DfuResponse, DfuChunk,
    create_dfu_request, parse_dfu_response, split_firmware_into_chunks
)
from .error import (
    ErrorNotification, parse_error_notification
)
from .downlink import (
    DownlinkRequest, DownlinkResponse, UplinkNotification,
    create_downlink_request, parse_downlink_response, parse_uplink_notification
)


class BraveJIGProtocol:
    """
    Unified BraveJIG protocol handler consolidating proven patterns
    from scripts/ directory into a maintainable, extensible framework.
    """
    
    # Real device IDs from proven test scripts
    TEST_DEVICES = TEST_DEVICES

    def __init__(self):
        """Initialize protocol handler"""
        self._device_registry: Dict[int, Tuple[int, str]] = {}
        self._initialize_device_registry()

    def _initialize_device_registry(self):
        """Initialize device registry with known test devices"""
        for device_id, sensor_type, description in self.TEST_DEVICES:
            self._device_registry[device_id] = (sensor_type, description)

    # JIG Info Protocol Methods
    def create_jig_info_request(self, cmd: int) -> bytes:
        """Create JIG Info request"""
        return create_jig_info_request(cmd)

    # DFU Protocol Methods  
    def create_dfu_request(self, total_length: int) -> bytes:
        """Create DFU initiation request"""
        return create_dfu_request(total_length)

    def parse_dfu_response(self, data: bytes) -> DfuResponse:
        """Parse DFU response data"""
        return parse_dfu_response(data)

    def split_firmware_into_chunks(self, firmware_data: bytes) -> List[bytes]:
        """Split firmware into properly sized chunks for DFU transfer"""
        return split_firmware_into_chunks(firmware_data)

    # Downlink Protocol Methods
    def create_downlink_request(self, device_id: int, sensor_id: int, 
                              request_id: int = 0x01, data: bytes = b'') -> bytes:
        """Create Downlink request"""
        return create_downlink_request(device_id, sensor_id, request_id, data)

    # Unified Response Parsing
    def parse_response(self, data: bytes) -> Any:
        """
        Parse incoming response data and return appropriate structure
        
        Args:
            data: Raw response bytes from router
            
        Returns:
            Parsed response object (JigInfoResponse, DfuResponse, etc.)
        """
        if len(data) < 2:
            raise ValueError("Response too short")
        
        packet_type = data[1]
        
        if packet_type == 0x01:  # Should not occur based on real hardware
            return parse_jig_info_response(data)
        elif packet_type == 0x02:  # JIG Info response OR Downlink response
            # Real hardware uses packet type 0x02 for JIG Info responses
            # Try JIG Info response format first (15+ bytes), then Downlink (19 bytes)
            if len(data) >= 15 and len(data) != 19:
                # Likely JIG Info response (15+ bytes but not exactly 19)
                try:
                    return parse_jig_info_response(data)
                except ValueError:
                    # Fall back to Downlink if JIG Info parsing fails
                    return parse_downlink_response(data)
            elif len(data) == 19:
                # Likely Downlink response (exactly 19 bytes)
                try:
                    return parse_downlink_response(data)
                except ValueError:
                    # Fall back to JIG Info if Downlink parsing fails
                    return parse_jig_info_response(data)
            else:
                # Try JIG Info first for shorter packets
                try:
                    return parse_jig_info_response(data)
                except ValueError:
                    return parse_downlink_response(data)
        elif packet_type == 0x03:  # DFU response or Uplink notification
            # Need to distinguish based on context or additional parsing
            try:
                return parse_dfu_response(data)
            except ValueError:
                return parse_uplink_notification(data)
        elif packet_type == 0x04:  # Error notification (old)
            return parse_error_notification(data)
        elif packet_type == 0xFF:  # Error notification (per specs 5-1-5)
            return parse_error_notification(data)
        else:
            raise ValueError(f"Unknown packet type: 0x{packet_type:02x}")

    # Device Registry Methods
    def get_device_info(self, device_id: int) -> Optional[Tuple[int, str]]:
        """Get device information from registry"""
        return self._device_registry.get(device_id)

    def get_all_known_devices(self) -> List[Tuple[int, int, str]]:
        """Get all known devices with their IDs, sensor types, and descriptions"""
        return [(device_id, sensor_type, desc) 
                for device_id, (sensor_type, desc) in self._device_registry.items()]

    # Command Mapping Utilities
    def cmd_from_device_index(self, index: int) -> int:
        """Convert device index to JIG Info CMD value"""
        return cmd_from_device_index(index)

    def scan_mode_cmd(self, mode: int) -> int:
        """Convert scan mode value to SET_SCAN_MODE CMD"""
        return scan_mode_cmd(mode)

    def interpret_error_reason(self, reason: int) -> str:
        """Interpret error reason code per specs 5-1-5"""
        return interpret_error_reason(reason)
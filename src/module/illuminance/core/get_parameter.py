"""
BraveJIG Illuminance Sensor Get Parameter Command

パラメータ取得コマンド実装
仕様書 6-4 パラメータ情報取得要求 (CMD: 0x0D - GET_DEVICE_SETTING)

Request Format:
- SensorID: 0x0000 (2 bytes) - エンドデバイス本体
- CMD: 0x0D (1 byte) - デバイス情報取得要求
- Sequence No: 0xFFFF (2 bytes) - 固定
- DATA: 0x00 (1 byte) - パラメータ情報取得要求

Response: Parameter information via uplink (Type: 0x00, SensorID: 0x0000)

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
from typing import Dict, Any, Optional
from ..base_illuminance import IlluminanceSensorBase, IlluminanceCommand
from ..illuminance_parameters import IlluminanceParameters


class GetParameterCommand(IlluminanceSensorBase):
    """
    パラメータ取得コマンド実装
    
    デバイス設定情報を取得するコマンド
    scripts/illuminance_parameter_test.pyで実証済み
    """
    
    def __init__(self, device_id: str):
        """
        Initialize get parameter command handler
        
        Args:
            device_id: Target device ID as hex string
        """
        super().__init__(device_id)
        self.command = IlluminanceCommand.GET_DEVICE_SETTING

    def create_get_parameter_request(self) -> bytes:
        """
        Create parameter acquisition request according to spec 6-4
        
        According to spec 6-4, the packet structure should be:
        - SensorID: 0x0000 (End device main unit) - NOT 0x0121
        - CMD: 0x0D (Device information acquisition request)
        - Sequence No: 0xFFFF (Fixed)
        - DATA: 0x00 (Parameter information acquisition request)
        
        Returns:
            bytes: Complete parameter acquisition request packet
        """
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        data_payload = struct.pack('<B', 0x00)  # DATA: Parameter info acquisition request
        data_length = len(data_payload)
        
        # Build packet according to spec 6-4 - use SensorID 0x0000 NOT 0x0121
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit (spec 6-4)
        packet += struct.pack('<B', 0x0D)               # CMD: GET_DEVICE_SETTING
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA: 0x00
        
        self.logger.info(
            f"Created parameter acquisition request for device 0x{self.device_id:016X}"
        )
        self.logger.info(f"Sending parameter acquisition request: {packet.hex(' ').upper()}")
        
        return packet

    def execute_get_parameter(self,
                             send_callback,
                             receive_callback,
                             uplink_timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute parameter acquisition command
        
        Args:
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            uplink_timeout: Timeout for parameter uplink (longer for uplink)
            
        Returns:
            Dict containing execution results and parameter information
        """
        result = {
            "success": False,
            "command": "get_parameter",
            "device_id": f"{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}"
        }
        
        try:
            # Phase 1: Send parameter acquisition request
            request_packet = self.create_get_parameter_request()
            result["request_packet"] = request_packet.hex(' ').upper()
            
            self.logger.info(f"Sending parameter acquisition request: {request_packet.hex(' ').upper()}")
            
            if not send_callback(request_packet):
                result["error"] = "Failed to send parameter acquisition request"
                return result
            
            # Phase 2: Wait for downlink response using base class method
            command_result = self.execute_command_with_response(
                request_packet, send_callback, receive_callback, timeout=10.0, command_name="get_parameter"
            )
            
            result["downlink_response"] = command_result.get("response", {})
            
            if not command_result["success"]:
                result["error"] = f"Parameter request failed: {command_result.get('error', 'Unknown error')}"
                return result
            
            # Phase 3: Wait for parameter information uplink using optimized method
            self.logger.info("Parameter request accepted, waiting for parameter uplink...")
            
            parameter_uplink = self.wait_for_parameter_uplink(receive_callback, uplink_timeout)
            
            if not parameter_uplink:
                result["error"] = f"No parameter uplink received within {uplink_timeout} seconds"
                return result
            
            # Parse parameter information
            param_info = self.parse_parameter_uplink(parameter_uplink)
            if param_info and "error" not in param_info:
                result["success"] = True
                result["parameter_info"] = param_info
                result["message"] = "Parameter acquisition completed successfully"
                
                self.logger.info("Parameter information acquired successfully")
            else:
                result["error"] = f"Parameter parsing failed: {param_info.get('error', 'Unknown error')}"
                
        except Exception as e:
            result["error"] = f"Parameter acquisition failed: {str(e)}"
            self.logger.error(f"Parameter acquisition error: {e}")
        
        return result

    def parse_parameter_uplink(self, uplink_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse parameter information uplink according to spec 5-2
        
        Args:
            uplink_data: Raw parameter uplink bytes (complete BraveJIG packet)
            
        Returns:
            Dict containing parsed parameter information
        """
        try:
            if len(uplink_data) < 43:  # 18 (header) + 2 (seq) + 24 (param data) - 1 = 43
                return {"error": "Uplink packet too short"}
            
            # Verify this is parameter information (SensorID: 0x0000)
            sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
            if sensor_id != 0x0000:
                return {"error": f"Not parameter info, sensor ID: 0x{sensor_id:04X}"}
            
            # Parse packet structure:
            # Bytes 0-17: BraveJIG packet header (protocol, type, length, time, device_id, sensor_id)
            # Bytes 18-20: Sequence No (3 bytes: C3 FF FF)
            # Bytes 21-44: Parameter data section (24 bytes)
            
            param_data_start = 21  # Skip header (18) + sequence (3) 
            param_data = uplink_data[param_data_start:]
            
            if len(param_data) < 24:  # Must have exactly 24 bytes of parameter data
                return {"error": f"Insufficient parameter data ({len(param_data)} bytes, expected 24)"}
            
            return self._parse_parameter_structure(param_data, uplink_data)
            
        except Exception as e:
            return {"error": f"Parameter uplink parse error: {str(e)}"}

    def _parse_parameter_structure(self, param_data: bytes, full_packet: bytes) -> Dict[str, Any]:
        """
        Parse parameter data structure using IlluminanceParameters dataclass
        
        Args:
            param_data: 24-byte parameter data section (Connected SensorID + FW Version + parameters)
            full_packet: Complete uplink packet for debugging
            
        Returns:
            Dict containing parsed parameter information
        """
        try:
            # Basic packet info
            result = {
                "parameter_type": "illuminance_sensor",
                "device_id": f"{self.device_id:016X}",
                "raw_packet": full_packet.hex(' ').upper(),
                "param_data_hex": param_data.hex(' ').upper()
            }
            
            # Validate parameter data length
            if len(param_data) < 24:
                return {"error": f"Parameter data too short: {len(param_data)} bytes, expected 24"}
            
            # Parse parameters using corrected IlluminanceParameters dataclass
            try:
                params, metadata = IlluminanceParameters.deserialize_from_bytes(param_data, offset=0)
                
                # Convert to display format and merge with result
                display_params = params.to_display_format()
                result.update(display_params)
                
                # Add metadata (fw_version and connected_sensor_id)
                if 'fw_version' in metadata:
                    result["fw_version"] = metadata['fw_version']
                if 'connected_sensor_id' in metadata:
                    result["connected_sensor_id"] = f"{metadata['connected_sensor_id']:04X}"
                
                # Note: _parameters_object is excluded from result to maintain JSON serialization
                
                # Add success indicator
                result["success"] = True
                
            except Exception as parse_error:
                result["error"] = f"Parameter parsing failed: {str(parse_error)}"
            
            return result
            
        except Exception as e:
            return {"error": f"Parameter structure parse error: {str(e)}"}

    def format_parameter_summary(self, param_info: Dict[str, Any]) -> str:
        """
        Format parameter information for display
        
        Args:
            param_info: Parsed parameter information
            
        Returns:
            Formatted parameter summary string
        """
        if "error" in param_info:
            return f"Parameter Error: {param_info['error']}"
        
        lines = [
            f"=== Illuminance Sensor Parameters ===",
            f"Device ID: {param_info.get('device_id', 'Unknown')}",
            f"Connected Sensor: {param_info.get('connected_sensor_id', 'Unknown')}",
            f"Firmware Version: {param_info.get('fw_version', 'Unknown')}",
            f"",
            f"=== Communication Settings ===",
            f"BLE Mode: {param_info.get('ble_mode', {}).get('description', 'Unknown')}",
            f"Tx Power: {param_info.get('tx_power', {}).get('description', 'Unknown')}",
            f"Advertise Interval: {param_info.get('advertise_interval', {}).get('value', 'Unknown')} ms",
            f"Uplink Interval: {param_info.get('sensor_uplink_interval', {}).get('value', 'Unknown')} seconds",
            f"",
            f"=== Sensor Settings ===",
            f"Read Mode: {param_info.get('sensor_read_mode', {}).get('description', 'Unknown')}",
            f"Sampling: {param_info.get('sampling', {}).get('description', 'Unknown')}",
            f"Hysteresis High: {param_info.get('hysteresis_high', {}).get('value', 'Unknown')} Lux",
            f"Hysteresis Low: {param_info.get('hysteresis_low', {}).get('value', 'Unknown')} Lux",
        ]
        
        return "\n".join(lines)
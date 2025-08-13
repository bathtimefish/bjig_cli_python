"""
BraveJIG Illuminance Sensor Device Restart Command

デバイス再起動コマンド実装
仕様書 6-5 デバイス再起動要求 (CMD: 0xFD - RESTART)

Request Format:
- SensorID: 0x0000 (2 bytes) - エンドデバイス本体
- CMD: 0xFD (1 byte) - デバイス再起動
- Sequence No: 0xFFFF (2 bytes) - 固定
- DATA: なし

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
from typing import Dict, Any
from ..base_illuminance import IlluminanceSensorBase, IlluminanceCommand


class DeviceRestartCommand(IlluminanceSensorBase):
    """
    デバイス再起動コマンド実装
    
    モジュールの再起動を要求するコマンド
    実機テスト済みパターンに基づく実装
    """
    
    def __init__(self, device_id: str):
        """
        Initialize device restart command handler
        
        Args:
            device_id: Target device ID as hex string
        """
        super().__init__(device_id)
        self.command = IlluminanceCommand.DEVICE_RESTART

    def create_device_restart_request(self) -> bytes:
        """
        Create device restart request according to spec 6-5
        
        According to spec 6-5, the packet structure should be:
        - SensorID: 0x0000 (End device main unit)
        - CMD: 0xFD (Device restart)
        - Sequence No: 0xFFFF (Fixed)
        - DATA: なし (no data)
        
        Returns:
            bytes: Complete device restart request packet
        """
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        data_payload = b''  # No data according to spec 6-5
        data_length = len(data_payload)
        
        # Build packet according to spec 6-5 - use SensorID 0x0000
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit
        packet += struct.pack('<B', 0xFD)               # CMD: DEVICE_RESTART
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA: empty
        
        self.logger.info(
            f"Created device restart request for device 0x{self.device_id:016X}"
        )
        
        return packet

    def execute_device_restart(self,
                              send_callback,
                              receive_callback,
                              timeout: float = 10.0) -> Dict[str, Any]:
        """
        Execute device restart command
        
        Args:
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            
        Returns:
            Dict containing execution results
        """
        result = {
            "success": False,
            "command": "device_restart",
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}"
        }
        
        try:
            # Create device restart request
            request_packet = self.create_device_restart_request()
            result["request_packet"] = request_packet.hex(' ').upper()
            
            self.logger.info(f"Sending device restart request: {request_packet.hex(' ').upper()}")
            
            if not send_callback(request_packet):
                result["error"] = "Failed to send device restart request"
                return result
            
            # Wait for downlink response using base class method
            command_result = self.execute_command_with_response(
                request_packet, send_callback, receive_callback, timeout=timeout, command_name="device_restart"
            )
            
            result["downlink_response"] = command_result.get("response", {})
            
            if command_result["success"]:
                result["success"] = True
                result["message"] = "Device restart command completed successfully"
                result["restart_info"] = {
                    "restart_initiated": True,
                    "note": "Device restart command accepted"
                }
                
                self.logger.info(
                    f"Device restart command accepted. "
                    f"Device 0x{self.device_id:016X} will restart."
                )
            else:
                result["error"] = f"Restart command failed: {command_result.get('error', 'Unknown error')}"
                
        except Exception as e:
            result["error"] = f"Device restart execution failed: {str(e)}"
            self.logger.error(f"Device restart execution error: {e}")
        
        return result

    def format_restart_summary(self, restart_result: Dict[str, Any]) -> str:
        """
        Format restart result for display
        
        Args:
            restart_result: Restart execution result
            
        Returns:
            Formatted restart summary string
        """
        if restart_result.get("success", False):
            lines = [
                f"=== Device Restart Successful ===",
                f"Device ID: {restart_result.get('device_id', 'Unknown')}",
                f"Command: {restart_result.get('command', 'Unknown')}",
                f"Status: {restart_result.get('message', 'Unknown')}",
                f"",
                f"=== Restart Information ===",
            ]
            
            restart_info = restart_result.get("restart_info", {})
            if restart_info:
                lines.extend([
                    f"Restart Initiated: {restart_info.get('restart_initiated', 'Unknown')}",
                    f"Expected Downtime: {restart_info.get('expected_downtime', 'Unknown')}",
                    f"Note: {restart_info.get('note', 'No additional information')}",
                ])
            
            lines.extend([
                f"",
                f"⚠️  Important Notes:",
                f"   - Device will be offline during restart",
                f"   - Monitor LED indicators for restart completion",
                f"   - Blue LED (2 seconds) indicates successful restart",
                f"   - If device doesn't restart, check power connection"
            ])
            
        else:
            lines = [
                f"=== Device Restart Failed ===",
                f"Device ID: {restart_result.get('device_id', 'Unknown')}",
                f"Error: {restart_result.get('error', 'Unknown error')}",
                f"",
                f"🔧 Troubleshooting:",
                f"   - Verify device is online and responsive",
                f"   - Check router connection",
                f"   - Ensure device is not in DFU or error state",
                f"   - Try manual power cycle if restart fails"
            ]
        
        return "\n".join(lines)

    @staticmethod
    def get_restart_warnings() -> str:
        """
        Get restart warnings and precautions
        
        Returns:
            Warning message string
        """
        return """
⚠️  DEVICE RESTART WARNINGS:

1. Data Loss Prevention:
   - Ensure all important sensor data has been uploaded
   - Current measurement cycle will be interrupted

2. Timing Considerations:
   - Device will be offline for 10-30 seconds
   - Uplink notifications will stop during restart
   - Next scheduled uplink may be delayed

3. Configuration Preservation:
   - All parameters stored in non-volatile memory are preserved
   - Pairing information remains intact
   - Calibration data is not affected

4. When to Restart:
   - After parameter changes that require restart
   - To clear temporary error states
   - As troubleshooting step for connectivity issues
   - NOT during DFU operations

5. Restart Indicators:
   - Blue LED: 2 seconds ON → OFF indicates successful restart
   - Red LED blinking: Restart failed or error state
   - No LED activity: Check power and connections
        """.strip()

    def validate_restart_conditions(self) -> Dict[str, Any]:
        """
        Validate conditions for safe restart
        
        Returns:
            Dict with validation results and recommendations
        """
        # Basic validation - more comprehensive checks could be added
        # based on device state monitoring
        
        validation = {
            "safe_to_restart": True,
            "warnings": [],
            "recommendations": []
        }
        
        # Add general recommendations
        validation["recommendations"].extend([
            "Ensure device is not currently uploading critical data",
            "Consider timing restart between measurement cycles",
            "Monitor device LED indicators after restart",
            "Have manual power cycle option available as backup"
        ])
        
        # Add warnings for specific conditions
        validation["warnings"].extend([
            "Device will be offline during restart process",
            "Current measurement cycle will be interrupted",
            "Restart during DFU operations is not supported"
        ])
        
        return validation
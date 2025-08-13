"""
BraveJIG Illuminance Sensor Set Parameter Command

パラメータ設定コマンド実装
仕様書 6-2 パラメータ情報設定要求 (CMD: 0x05 - SET_REGISTER)

Request Format (19 bytes total):
- SensorID (2): 0x0121 固定
- TimeZone (1): タイムゾーン設定
- BLE Mode (1): Bluetooth LE通信モード
- Tx Power (1): 送信電波出力
- Advertise Interval (2): Advertise間隔 (little endian)
- Sensor Uplink Interval (4): Uplink間隔 (little endian)
- Sensor Read Mode (1): 計測モード
- Sampling (1): サンプリング周期
- HysteresisHigh (4): ヒステリシス(High) (IEEE 754 Float, little endian)
- HysteresisLow (4): ヒステリシス(Low) (IEEE 754 Float, little endian)

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
import json
from typing import Dict, Any, Optional, Union, List
from ..base_illuminance import IlluminanceSensorBase, IlluminanceCommand
from ..illuminance_parameters import IlluminanceParameters


class SetParameterCommand(IlluminanceSensorBase):
    """
    パラメータ設定コマンド実装
    
    デバイスパラメータを設定するコマンド
    scripts/illuminance_parameter_setting_test.pyで実証済み
    """
    
    def __init__(self, device_id: str):
        """
        Initialize set parameter command handler
        
        Args:
            device_id: Target device ID as hex string
        """
        super().__init__(device_id)
        self.command = IlluminanceCommand.SET_PARAMETER

    def create_set_parameter_request(self, parameters: IlluminanceParameters) -> bytes:
        """
        Create parameter setting request according to spec 6-2
        
        Args:
            parameters: IlluminanceParameters instance with settings
            
        Returns:
            bytes: Complete parameter setting request packet
        """
        from lib.datetime_util import get_current_unix_time
        
        # Serialize parameters to 19-byte DATA format using dataclass method
        param_data = parameters.serialize_to_bytes()
        unix_time = get_current_unix_time()
        data_length = len(param_data)
        
        # Build packet according to spec 6-2 - use SensorID 0x0000 like GET_PARAMETER
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit (like GET_PARAMETER)
        packet += struct.pack('<B', 0x05)               # CMD: SET_REGISTER
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += param_data                            # DATA: 19-byte parameter data
        
        self.logger.info(
            f"Created parameter setting request for device 0x{self.device_id:016X}, "
            f"parameter data ({len(param_data)} bytes): {param_data.hex(' ').upper()}"
        )
        
        return packet

    def execute_set_parameter(self,
                             update_data: Union[str, Dict[str, Any]],
                             send_callback,
                             receive_callback,
                             timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute parameter setting command with GET->UPDATE->SET->OUTPUT flow
        
        Args:
            update_data: Parameter updates (JSON string or dict)
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds (longer for full flow)
            
        Returns:
            Dict containing execution results and updated parameters JSON
        """
        result = {
            "success": False,
            "command": "set_parameter",
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}"
        }
        
        try:
            # Parse update data if string
            if isinstance(update_data, str):
                try:
                    update_dict = json.loads(update_data)
                except json.JSONDecodeError as e:
                    result["error"] = f"Invalid JSON update data: {str(e)}"
                    return result
            else:
                update_dict = update_data
            
            # STEP 1: GET - Retrieve current parameters
            self.logger.info("Step 1: Getting current parameters...")
            current_params = self._get_current_parameters(send_callback, receive_callback, timeout)
            
            if current_params is None:
                result["error"] = "Failed to get current parameters"
                return result
            
            result["current_parameters"] = current_params.to_display_format()
            self.logger.info("Current parameters retrieved successfully")
            
            # STEP 2: UPDATE - Merge update data with current parameters
            self.logger.info("Step 2: Updating parameters...")
            update_result = self._update_parameters_with_data(current_params, update_dict)
            
            if "error" in update_result:
                result["error"] = f"Parameter update failed: {update_result['error']}"
                return result
            
            updated_params = update_result["parameters"]
            result["parameter_changes"] = update_result["changes"]
            result["updated_parameters"] = updated_params.to_display_format()
            self.logger.info(f"Parameters updated: {len(update_result['changes'])} changes")
            
            # STEP 3: SET - Send updated parameters
            self.logger.info("Step 3: Setting updated parameters...")
            set_result = self._send_parameter_update(updated_params, send_callback, receive_callback, timeout)
            
            if not set_result.get("success", False):
                result["error"] = f"Parameter setting failed: {set_result.get('error', 'Unknown error')}"
                result["set_response"] = set_result
                return result
            
            result["set_response"] = set_result
            
            # STEP 4: OUTPUT - Format final parameters as JSON
            self.logger.info("Step 4: Formatting output...")
            result["success"] = True
            result["message"] = "Parameter setting completed successfully"
            result["final_parameters_json"] = self._format_parameters_as_json(updated_params)
            
            self.logger.info("Parameter setting flow completed successfully")
                
        except Exception as e:
            result["error"] = f"Parameter setting execution failed: {str(e)}"
            self.logger.error(f"Parameter setting error: {e}")
        
        return result

    def _construct_parameters_from_dict(self, param_dict: Dict[str, Any]) -> IlluminanceParameters:
        """
        Construct IlluminanceParameters from dictionary format (fallback method)
        
        Args:
            param_dict: Parameter dictionary from old format
            
        Returns:
            IlluminanceParameters instance
        """
        params = IlluminanceParameters()
        
        # Extract values from nested dict format if needed
        for key in ['timezone', 'ble_mode', 'tx_power', 'advertise_interval', 
                   'sensor_uplink_interval', 'sensor_read_mode', 'sampling',
                   'hysteresis_high', 'hysteresis_low']:
            if key in param_dict:
                value = param_dict[key]
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]
                setattr(params, key, value)
        
        # Note: connected_sensor_id and fw_version are read-only metadata
        # They are not settable parameters and are excluded from SET_PARAMETER operations
        
        return params

    # Note: Parameter validation is now handled by IlluminanceParameters.validate() method

    def create_parameter_template(self) -> Dict[str, Any]:
        """
        Create parameter template with default values
        
        Returns:
            Dict with default parameter values and descriptions
        """
        return IlluminanceParameters.create_default_template()

    def _get_current_parameters(self, send_callback, receive_callback, timeout: float) -> Optional[IlluminanceParameters]:
        """
        Get current parameters using GET_PARAMETER command
        
        Returns:
            IlluminanceParameters instance or None if failed
        """
        try:
            from .get_parameter import GetParameterCommand
            
            get_command = GetParameterCommand(f"{self.device_id:016X}")
            result = get_command.execute_get_parameter(send_callback, receive_callback, timeout)
            
            if result.get("success", False):
                param_info = result.get("parameter_info", {})
                # Extract the parameters object if available
                if "_parameters_object" in param_info:
                    return param_info["_parameters_object"]
                else:
                    # Fallback: construct from individual fields (if old format)
                    return self._construct_parameters_from_dict(param_info)
            else:
                self.logger.error(f"Parameter acquisition failed: {result.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            self.logger.error(f"Get parameter error: {str(e)}")
            return None

    def _update_parameters_with_data(self, current_params: IlluminanceParameters, 
                                   update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update current parameters with provided update data
        
        Args:
            current_params: Current IlluminanceParameters instance
            update_data: Update data from --data argument
            
        Returns:
            Dict with updated parameters and changes list
        """
        try:
            # Create updated parameters using dataclass method
            updated_params = current_params.update_from_dict(update_data)
            
            # Validate updated parameters
            validation_result = updated_params.validate()
            if not validation_result["valid"]:
                return {"error": f"Updated parameters validation failed: {validation_result['error']}"}
            
            # Track changes by comparing before/after
            changes = []
            current_dict = current_params.to_dict()
            updated_dict = updated_params.to_dict()
            
            for key, new_value in updated_dict.items():
                old_value = current_dict.get(key)
                if old_value != new_value:
                    changes.append({
                        "field": key,
                        "old_value": old_value,
                        "new_value": new_value
                    })
            
            return {
                "parameters": updated_params,
                "changes": changes
            }
            
        except Exception as e:
            return {"error": f"Parameter update error: {str(e)}"}

    def _send_parameter_update(self, parameters: IlluminanceParameters, 
                             send_callback, receive_callback, timeout: float) -> Dict[str, Any]:
        """
        Send parameter update using SET_PARAMETER command
        
        Args:
            parameters: IlluminanceParameters instance to set
            send_callback: Function to send data
            receive_callback: Function to receive response
            timeout: Response timeout
            
        Returns:
            Dict with setting results
        """
        try:
            # Create and send parameter setting request
            request_packet = self.create_set_parameter_request(parameters)
            
            self.logger.info(f"Sending parameter setting request: {request_packet.hex(' ').upper()}")
            
            if not send_callback(request_packet):
                return {"success": False, "error": "Failed to send parameter setting request"}
            
            # Wait for downlink response
            import time
            start_time = time.time()
            response_data = None
            
            while (time.time() - start_time) < timeout:
                response_data = receive_callback()
                if response_data:
                    break
                time.sleep(0.1)
            
            if not response_data:
                return {"success": False, "error": f"No response received within {timeout} seconds"}
            
            # Parse downlink response
            response_info = self.parse_downlink_response(response_data)
            
            if response_info["success"]:
                return {
                    "success": True,
                    "message": "Parameter setting completed successfully",
                    "response": response_info
                }
            else:
                return {
                    "success": False,
                    "error": f"Parameter setting failed: {response_info['result_desc']}",
                    "response": response_info
                }
                
        except Exception as e:
            return {"success": False, "error": f"Send parameter update error: {str(e)}"}

    def _format_parameters_as_json(self, parameters: IlluminanceParameters) -> str:
        """
        Format parameters as JSON string for output
        
        Args:
            parameters: IlluminanceParameters instance
            
        Returns:
            JSON formatted string
        """
        try:
            return parameters.to_json(indent=2)
        except Exception as e:
            return f'{{"error": "JSON formatting failed: {str(e)}"}}'

    def format_parameter_change_summary(self, changes: List[Dict[str, Any]]) -> str:
        """
        Format parameter changes for display
        
        Args:
            changes: List of parameter changes
            
        Returns:
            Formatted change summary string
        """
        if not changes:
            return "No parameter changes detected"
        
        lines = ["Parameter Changes:"]
        for change in changes:
            field = change["field"]
            old_val = change["old_value"]
            new_val = change["new_value"]
            
            if old_val is None:
                lines.append(f"  + {field}: {new_val} (new)")
            else:
                lines.append(f"  - {field}: {old_val} → {new_val}")
        
        return "\n".join(lines)
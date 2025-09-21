"""
BraveJIG Illuminance Module - Unified Interface

照度モジュール(BJ-MD-LUX-01)の統合インターフェース
全てのコマンドを統一されたインターフェースで提供

Commands:
1. instant_uplink - 即時センサーデータ取得
2. get_parameter - パラメータ情報取得
3. set_parameter - パラメータ設定
4. sensor_dfu - センサーDFU
5. device_restart - デバイス再起動

Author: BraveJIG CLI Development Team  
Date: 2025-08-10
"""

from typing import Dict, Any, Union, Optional, Callable
import logging

from .base_illuminance import IlluminanceSensorBase
from .core.instant_uplink import InstantUplinkCommand
from .core.get_parameter import GetParameterCommand
from .core.set_parameter import SetParameterCommand
from .core.sensor_dfu import SensorDfuCommand
from .core.device_restart import DeviceRestartCommand
from .illuminance_parameters import IlluminanceParameters


class IlluminanceModule(IlluminanceSensorBase):
    """
    照度モジュール統合クラス
    
    全てのコマンドを統一されたインターフェースで提供
    共通基底クラスPatternに基づく設計
    """
    
    def __init__(self, device_id: str):
        """
        Initialize illuminance module
        
        Args:
            device_id: Device ID as hex string (e.g., "2468800203400004")
        """
        super().__init__(device_id)
        
        # Command instances (lazy initialization)
        self._instant_uplink = None
        self._get_parameter = None
        self._set_parameter = None
        self._sensor_dfu = None
        self._device_restart = None
        
        self.logger.info(f"Illuminance module initialized for device {device_id}")
    
    # Command factory methods
    def _get_instant_uplink_command(self) -> InstantUplinkCommand:
        """Get instant uplink command instance"""
        if self._instant_uplink is None:
            self._instant_uplink = InstantUplinkCommand(f"{self.device_id:016X}")
        return self._instant_uplink
    
    def _get_parameter_command(self) -> GetParameterCommand:
        """Get parameter command instance"""
        if self._get_parameter is None:
            self._get_parameter = GetParameterCommand(f"{self.device_id:016X}")
        return self._get_parameter
    
    def _get_set_parameter_command(self) -> SetParameterCommand:
        """Get set parameter command instance"""
        if self._set_parameter is None:
            self._set_parameter = SetParameterCommand(f"{self.device_id:016X}")
        return self._set_parameter
    
    def _get_sensor_dfu_command(self) -> SensorDfuCommand:
        """Get sensor DFU command instance"""
        if self._sensor_dfu is None:
            self._sensor_dfu = SensorDfuCommand(f"{self.device_id:016X}")
        return self._sensor_dfu
    
    def _get_device_restart_command(self) -> DeviceRestartCommand:
        """Get device restart command instance"""
        if self._device_restart is None:
            self._device_restart = DeviceRestartCommand(f"{self.device_id:016X}")
        return self._device_restart
    
    # Unified command interface
    def instant_uplink(self, 
                      send_callback: Callable,
                      receive_callback: Callable,
                      timeout: float = 10.0) -> Dict[str, Any]:
        """
        Execute instant uplink command (即時Uplink要求)
        
        Args:
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            
        Returns:
            Dict containing command results
        """
        command = self._get_instant_uplink_command()
        return command.execute_instant_uplink(send_callback, receive_callback, timeout)
    
    def get_parameter(self,
                     send_callback: Callable,
                     receive_callback: Callable,
                     uplink_timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute parameter acquisition command (パラメータ情報取得要求)
        
        Args:
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            uplink_timeout: Timeout for parameter uplink (longer for uplink)
            
        Returns:
            Dict containing parameter information
        """
        command = self._get_parameter_command()
        return command.execute_get_parameter(send_callback, receive_callback, uplink_timeout)
    
    def set_parameter(self,
                     update_data: Union[str, Dict[str, Any]],
                     send_callback: Callable,
                     receive_callback: Callable,
                     timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute parameter setting command (パラメータ情報設定要求)
        
        Args:
            update_data: Parameter updates (JSON string or dict)
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            
        Returns:
            Dict containing setting results and updated parameters
        """
        command = self._get_set_parameter_command()
        return command.execute_set_parameter(update_data, send_callback, receive_callback, timeout)
    
    def sensor_dfu(self,
                  dfu_data: bytes,
                  send_callback: Callable,
                  receive_callback: Callable,
                  timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute sensor DFU command (センサーDFU要求)
        
        Args:
            dfu_data: DFU firmware data
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            
        Returns:
            Dict containing DFU results
        """
        command = self._get_sensor_dfu_command()
        return command.execute_sensor_dfu(dfu_data, send_callback, receive_callback, timeout)
    
    def device_restart(self,
                      send_callback: Callable,
                      receive_callback: Callable,
                      timeout: float = 10.0) -> Dict[str, Any]:
        """
        Execute device restart command (デバイス再起動要求)
        
        Args:
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            timeout: Response timeout in seconds
            
        Returns:
            Dict containing restart results
        """
        command = self._get_device_restart_command()
        return command.execute_device_restart(send_callback, receive_callback, timeout)
    
    # Utility methods
    def parse_sensor_uplink(self, uplink_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse sensor data uplink notification
        
        Args:
            uplink_data: Raw uplink notification bytes
            
        Returns:
            Dict containing parsed sensor data or None if not illuminance data
        """
        command = self._get_instant_uplink_command()
        return command.parse_sensor_uplink(uplink_data)
    
    def create_parameter_template(self) -> Dict[str, Any]:
        """
        Create parameter template with default values
        
        Returns:
            Dict with default parameter values and descriptions
        """
        return IlluminanceParameters.create_default_template()
    
    def validate_parameters(self, params: Union[IlluminanceParameters, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate parameter values
        
        Args:
            params: Parameters to validate
            
        Returns:
            Dict with validation results
        """
        if isinstance(params, dict):
            # Convert dict to IlluminanceParameters for validation
            param_obj = IlluminanceParameters()
            param_obj = param_obj.update_from_dict(params)
        else:
            param_obj = params
        
        return param_obj.validate()
    
    def format_parameter_summary(self, param_info: Dict[str, Any]) -> str:
        """
        Format parameter information for display
        
        Args:
            param_info: Parsed parameter information
            
        Returns:
            Formatted parameter summary string
        """
        command = self._get_parameter_command()
        return command.format_parameter_summary(param_info)
    
    def format_sensor_data_summary(self, sensor_data: Dict[str, Any]) -> str:
        """
        Format sensor data for display
        
        Args:
            sensor_data: Parsed sensor data
            
        Returns:
            Formatted sensor data summary string
        """
        if "error" in sensor_data:
            return f"Sensor Data Error: {sensor_data['error']}"
        
        lines = [
            f"=== Illuminance Sensor Data ===",
            f"Device ID: {sensor_data.get('device_id', 'Unknown')}",
            f"Sensor ID: {sensor_data.get('sensor_id', 'Unknown')}",
            f"Sequence No: {sensor_data.get('sequence_no', 'Unknown')}",
            f"",
            f"=== Measurement Info ===",
            f"Battery Level: {sensor_data.get('battery_level', 'Unknown')}",
            f"Sampling Period: {sensor_data.get('sampling_period', 'Unknown')}",
            f"Sensor Time: {sensor_data.get('sensor_time_readable', 'Unknown')}",
            f"Sample Count: {sensor_data.get('sample_count', 0)}",
            f"",
            f"=== Illuminance Data ===",
            f"Lux Values: {sensor_data.get('lux_data', [])}",
            f"Average Lux: {sensor_data.get('lux_average', 0.0)} Lux"
        ]
        
        return "\n".join(lines)
    
    def get_command_list(self) -> Dict[str, str]:
        """
        Get list of available commands
        
        Returns:
            Dict mapping command names to descriptions
        """
        return {
            "instant_uplink": "即時センサーデータ取得 (INSTANT_UPLINK)",
            "get_parameter": "パラメータ情報取得 (GET_PARAMETER)",
            "set_parameter": "パラメータ設定 (SET_PARAMETER)", 
            "sensor_dfu": "センサーDFU (SENSOR_DFU)",
            "device_restart": "デバイス再起動 (DEVICE_RESTART)"
        }
    
    def get_module_status(self) -> Dict[str, Any]:
        """
        Get module status information
        
        Returns:
            Dict containing module status
        """
        return {
            "module_type": "illuminance",
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}",
            "available_commands": list(self.get_command_list().keys()),
            "module_info": self.get_module_specific_info()
        }
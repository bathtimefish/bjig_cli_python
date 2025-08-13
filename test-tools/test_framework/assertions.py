"""
BraveJIG Test Assertions

BraveJIG専用のアサーションヘルパー
- プロトコル固有の検証
- データ構造の検証
- タイミング要件の検証
- エラー条件の検証

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import struct
import time
from typing import Dict, Any, List, Optional, Union
from unittest import TestCase


class BraveJIGAssertions:
    """BraveJIG専用アサーション集"""
    
    @staticmethod
    def assert_valid_device_id(device_id: Union[str, int], message: str = ""):
        """有効なデバイスIDかをアサート"""
        if isinstance(device_id, str):
            if device_id.startswith("0x"):
                device_id = int(device_id, 16)
            else:
                device_id = int(device_id, 16)
        
        assert isinstance(device_id, int), f"Device ID must be integer {message}"
        assert 0 <= device_id <= 0xFFFFFFFFFFFFFFFF, f"Device ID out of range: 0x{device_id:X} {message}"
    
    @staticmethod
    def assert_valid_sensor_id(sensor_id: Union[str, int], expected: int = None, message: str = ""):
        """有効なセンサーIDかをアサート"""
        if isinstance(sensor_id, str):
            if sensor_id.startswith("0x"):
                sensor_id = int(sensor_id, 16)
            else:
                sensor_id = int(sensor_id, 16)
        
        assert isinstance(sensor_id, int), f"Sensor ID must be integer {message}"
        assert 0 <= sensor_id <= 0xFFFF, f"Sensor ID out of range: 0x{sensor_id:X} {message}"
        
        if expected is not None:
            assert sensor_id == expected, f"Sensor ID mismatch: 0x{sensor_id:04X} (expected 0x{expected:04X}) {message}"
    
    @staticmethod
    def assert_illuminance_sensor_id(sensor_id: Union[str, int], message: str = ""):
        """照度センサーIDをアサート"""
        BraveJIGAssertions.assert_valid_sensor_id(sensor_id, expected=0x0121, message=message)
    
    @staticmethod
    def assert_command_response(response: Dict[str, Any], expected_command: str = None, message: str = ""):
        """コマンド応答をアサート"""
        assert isinstance(response, dict), f"Response must be dictionary {message}"
        assert "success" in response, f"Response missing 'success' field {message}"
        assert "command" in response, f"Response missing 'command' field {message}"
        
        if expected_command:
            assert response["command"] == expected_command, \
                f"Command mismatch: {response.get('command')} (expected {expected_command}) {message}"
    
    @staticmethod 
    def assert_command_success(response: Dict[str, Any], message: str = ""):
        """コマンド成功をアサート"""
        BraveJIGAssertions.assert_command_response(response, message=message)
        
        success = response.get("success", False)
        error = response.get("error", "No error message")
        
        assert success, f"Command failed: {error} {message}"
    
    @staticmethod
    def assert_command_failure(response: Dict[str, Any], expected_error: str = None, message: str = ""):
        """コマンド失敗をアサート"""
        BraveJIGAssertions.assert_command_response(response, message=message)
        
        success = response.get("success", False)
        assert not success, f"Command should have failed but succeeded {message}"
        
        if expected_error:
            error = response.get("error", "")
            assert expected_error.lower() in error.lower(), \
                f"Expected error '{expected_error}' not found in '{error}' {message}"
    
    @staticmethod
    def assert_downlink_response(response: Dict[str, Any], expected_result: int = 0x00, message: str = ""):
        """Downlink応答をアサート"""
        assert "downlink_response" in response or "response" in response, \
            f"No downlink response found {message}"
        
        downlink = response.get("downlink_response", response.get("response", {}))
        assert downlink.get("success", False), f"Downlink response failed: {downlink.get('result_desc')} {message}"
        
        if "result" in downlink:
            result_hex = downlink["result"]
            result_int = int(result_hex, 16) if isinstance(result_hex, str) else result_hex
            assert result_int == expected_result, \
                f"Unexpected result code: {result_hex} (expected 0x{expected_result:02X}) {message}"
    
    @staticmethod
    def assert_parameter_info(param_info: Dict[str, Any], expected_fields: List[str] = None, message: str = ""):
        """パラメータ情報をアサート"""
        assert isinstance(param_info, dict), f"Parameter info must be dictionary {message}"
        
        if expected_fields is None:
            expected_fields = [
                "timezone", "ble_mode", "tx_power", "advertise_interval",
                "sensor_uplink_interval", "sensor_read_mode", "sampling", 
                "hysteresis_high", "hysteresis_low"
            ]
        
        for field in expected_fields:
            assert field in param_info, f"Parameter field '{field}' missing {message}"
    
    @staticmethod
    def assert_sensor_data(sensor_data: Dict[str, Any], message: str = ""):
        """センサーデータをアサート"""
        assert isinstance(sensor_data, dict), f"Sensor data must be dictionary {message}"
        
        required_fields = ["device_id", "sensor_id", "battery_level", "lux_data"]
        for field in required_fields:
            assert field in sensor_data, f"Sensor data field '{field}' missing {message}"
        
        # Validate lux data
        lux_data = sensor_data.get("lux_data", [])
        assert isinstance(lux_data, list), f"Lux data must be list {message}"
        assert len(lux_data) > 0, f"Lux data is empty {message}"
        
        for lux_value in lux_data:
            assert isinstance(lux_value, (int, float)), f"Invalid lux value: {lux_value} {message}"
            assert 0.0 <= lux_value <= 100000.0, f"Lux value out of range: {lux_value} {message}"
    
    @staticmethod
    def assert_packet_structure(packet: bytes, expected_type: int, min_length: int = 0, message: str = ""):
        """パケット構造をアサート"""
        assert isinstance(packet, bytes), f"Packet must be bytes {message}"
        assert len(packet) >= min_length, f"Packet too short: {len(packet)} bytes (min {min_length}) {message}"
        
        if len(packet) >= 2:
            protocol_version = packet[0]
            packet_type = packet[1]
            
            assert protocol_version == 0x01, f"Invalid protocol version: 0x{protocol_version:02X} {message}"
            assert packet_type == expected_type, f"Invalid packet type: 0x{packet_type:02X} (expected 0x{expected_type:02X}) {message}"
    
    @staticmethod
    def assert_response_time(duration: float, max_time: float, operation: str = "operation", message: str = ""):
        """応答時間をアサート"""
        assert isinstance(duration, (int, float)), f"Duration must be numeric {message}"
        assert duration <= max_time, f"{operation} took {duration:.2f}s, max allowed: {max_time}s {message}"
        assert duration >= 0, f"Invalid negative duration: {duration}s {message}"
    
    @staticmethod
    def assert_parameter_validation(validation_result: Dict[str, Any], should_be_valid: bool = True, 
                                  expected_errors: List[str] = None, message: str = ""):
        """パラメータバリデーション結果をアサート"""
        assert isinstance(validation_result, dict), f"Validation result must be dictionary {message}"
        assert "valid" in validation_result, f"Validation result missing 'valid' field {message}"
        
        is_valid = validation_result.get("valid", False)
        
        if should_be_valid:
            errors = validation_result.get("errors", [])
            assert is_valid, f"Parameter validation failed: {errors} {message}"
        else:
            assert not is_valid, f"Parameter validation should have failed {message}"
            
            if expected_errors:
                errors = validation_result.get("errors", [])
                for expected_error in expected_errors:
                    found = any(expected_error.lower() in error.lower() for error in errors)
                    assert found, f"Expected error '{expected_error}' not found in {errors} {message}"
    
    @staticmethod
    def assert_uplink_timing(test_start: float, uplink_received: float, 
                           max_delay: float = 30.0, message: str = ""):
        """Uplink受信タイミングをアサート"""
        delay = uplink_received - test_start
        assert delay <= max_delay, f"Uplink delay too long: {delay:.2f}s (max {max_delay}s) {message}"
        assert delay >= 0, f"Invalid negative uplink delay: {delay:.2f}s {message}"
    
    @staticmethod
    def assert_battery_level(battery_level: Union[str, int], message: str = ""):
        """バッテリーレベルをアサート"""
        if isinstance(battery_level, str):
            if battery_level.endswith('%'):
                battery_level = int(battery_level[:-1])
            else:
                battery_level = int(battery_level)
        
        assert isinstance(battery_level, int), f"Battery level must be integer {message}"
        assert 0 <= battery_level <= 100, f"Battery level out of range: {battery_level}% {message}"
    
    @staticmethod
    def assert_firmware_version(version: str, message: str = ""):
        """ファームウェアバージョンをアサート"""
        assert isinstance(version, str), f"Firmware version must be string {message}"
        
        # Basic version format validation (e.g., "1.2.3")
        parts = version.split('.')
        assert len(parts) >= 2, f"Invalid version format: {version} {message}"
        
        for part in parts:
            assert part.isdigit(), f"Invalid version part: {part} in {version} {message}"
    
    @staticmethod
    def assert_json_structure(json_data: Union[str, dict], required_keys: List[str] = None, message: str = ""):
        """JSON構造をアサート"""
        if isinstance(json_data, str):
            import json
            try:
                json_data = json.loads(json_data)
            except json.JSONDecodeError as e:
                assert False, f"Invalid JSON: {str(e)} {message}"
        
        assert isinstance(json_data, dict), f"JSON data must be dictionary {message}"
        
        if required_keys:
            for key in required_keys:
                assert key in json_data, f"Required key '{key}' missing from JSON {message}"


class BraveJIGTestCase(TestCase):
    """BraveJIG用テストケース基底クラス"""
    
    def setUp(self):
        """テスト初期化"""
        self.assertions = BraveJIGAssertions()
        self.start_time = time.time()
    
    def tearDown(self):
        """テスト後処理"""
        self.test_duration = time.time() - self.start_time
    
    # Convenience methods that delegate to static assertions
    def assertValidDeviceId(self, device_id, msg=None):
        self.assertions.assert_valid_device_id(device_id, msg or "")
    
    def assertValidSensorId(self, sensor_id, expected=None, msg=None):
        self.assertions.assert_valid_sensor_id(sensor_id, expected, msg or "")
    
    def assertIlluminanceSensorId(self, sensor_id, msg=None):
        self.assertions.assert_illuminance_sensor_id(sensor_id, msg or "")
    
    def assertCommandSuccess(self, response, msg=None):
        self.assertions.assert_command_success(response, msg or "")
    
    def assertCommandFailure(self, response, expected_error=None, msg=None):
        self.assertions.assert_command_failure(response, expected_error, msg or "")
    
    def assertDownlinkResponse(self, response, expected_result=0x00, msg=None):
        self.assertions.assert_downlink_response(response, expected_result, msg or "")
    
    def assertParameterInfo(self, param_info, expected_fields=None, msg=None):
        self.assertions.assert_parameter_info(param_info, expected_fields, msg or "")
    
    def assertSensorData(self, sensor_data, msg=None):
        self.assertions.assert_sensor_data(sensor_data, msg or "")
    
    def assertPacketStructure(self, packet, expected_type, min_length=0, msg=None):
        self.assertions.assert_packet_structure(packet, expected_type, min_length, msg or "")
    
    def assertResponseTime(self, duration, max_time, operation="operation", msg=None):
        self.assertions.assert_response_time(duration, max_time, operation, msg or "")
    
    def assertParameterValidation(self, validation_result, should_be_valid=True, expected_errors=None, msg=None):
        self.assertions.assert_parameter_validation(validation_result, should_be_valid, expected_errors, msg or "")
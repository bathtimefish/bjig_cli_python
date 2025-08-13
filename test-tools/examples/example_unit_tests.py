"""
BraveJIG Unit Test Examples

照度モジュールの単体テスト実装例
新しいテストフレームワークの使用方法を示す

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import unittest
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from tests.test_framework import MockBraveJIGRouter, TestUtilities, BraveJIGTestCase
from tests.test_scenarios.illuminance_scenarios import IlluminanceTestData
from module.illuminance import IlluminanceModule, IlluminanceParameters


class IlluminanceModuleUnitTests(BraveJIGTestCase):
    """照度モジュール単体テストケース"""
    
    def setUp(self):
        """テスト初期化"""
        super().setUp()
        
        # Test configuration
        self.test_device_id = "2468800203400004"
        self.module = IlluminanceModule(self.test_device_id)
        
        # Mock router setup
        self.mock_router = MockBraveJIGRouter()
        self.mock_router.connect("mock_port", 38400)
        self.mock_router.add_mock_device(int(self.test_device_id, 16), sensor_id=0x0121)
        
        # Test utilities
        self.test_utils = TestUtilities()
        self.send_callback, self.receive_callback = self.test_utils.create_mock_callbacks(self.mock_router)
    
    def test_module_initialization(self):
        """モジュール初期化テスト"""
        # Test device info
        device_info = self.module.get_device_info()
        
        self.assertValidDeviceId(device_info["device_id"])
        self.assertIlluminanceSensorId(device_info["sensor_id"])
        self.assertEqual(device_info["module_name"], "illuminance")
    
    def test_parameter_validation_valid_cases(self):
        """パラメータバリデーション - 有効ケース"""
        valid_params = IlluminanceTestData.get_valid_parameters()
        params = IlluminanceParameters(**valid_params)
        
        validation_result = params.validate()
        self.assertParameterValidation(validation_result, should_be_valid=True)
    
    def test_parameter_validation_invalid_cases(self):
        """パラメータバリデーション - 無効ケース"""
        invalid_cases = IlluminanceTestData.get_invalid_parameters()
        
        for case in invalid_cases:
            with self.subTest(case=case["name"]):
                # Create base parameters and apply invalid change
                base_params = IlluminanceTestData.get_valid_parameters()
                base_params.update(case["params"])
                
                params = IlluminanceParameters(**base_params)
                validation_result = params.validate()
                
                self.assertParameterValidation(
                    validation_result, 
                    should_be_valid=False,
                    expected_errors=[case["expected_error"]]
                )
    
    def test_parameter_serialization(self):
        """パラメータシリアライゼーションテスト"""
        params = IlluminanceParameters(**IlluminanceTestData.get_valid_parameters())
        
        # Test serialization
        serialized = params.serialize_to_bytes()
        self.assertEqual(len(serialized), 19, "Serialized parameters should be 19 bytes")
        
        # Test round-trip (serialize -> deserialize)
        mock_sensor_data = b'\x21\x01' + b'\xFF\xFF' + serialized  # Add sensor ID and sequence
        deserialized_params, metadata = IlluminanceParameters.deserialize_from_bytes(mock_sensor_data, offset=4)
        
        # Compare key parameters
        self.assertEqual(params.timezone, deserialized_params.timezone)
        self.assertEqual(params.ble_mode, deserialized_params.ble_mode)
        self.assertEqual(params.sensor_uplink_interval, deserialized_params.sensor_uplink_interval)
    
    def test_instant_uplink_command(self):
        """即時アップリンクコマンドテスト"""
        # Configure mock response
        self.mock_router.simulate_sensor_uplink(int(self.test_device_id, 16), "sensor_data")
        
        # Execute command
        result = self.module.instant_uplink(self.send_callback, self.receive_callback, timeout=5.0)
        
        # Verify result
        self.assertCommandSuccess(result)
        self.assertEqual(result["command"], "instant_uplink")
        
        # Check packet log
        packet_log = self.mock_router.get_packet_log()
        self.assertGreater(len(packet_log), 0, "Should have packet communication")
    
    def test_get_parameter_command(self):
        """パラメータ取得コマンドテスト"""
        # Configure mock to simulate parameter uplink
        self.mock_router.simulate_sensor_uplink(int(self.test_device_id, 16), "parameter_info")
        
        # Execute command
        result = self.module.get_parameter(self.send_callback, self.receive_callback, uplink_timeout=10.0)
        
        # Verify result
        self.assertCommandSuccess(result)
        self.assertIn("parameter_info", result)
        
        # Verify parameter structure
        param_info = result["parameter_info"]
        self.assertParameterInfo(param_info)
    
    def test_set_parameter_workflow(self):
        """パラメータ設定ワークフローテスト"""
        # Setup: Mock current parameters
        device = self.mock_router.devices[int(self.test_device_id, 16)]
        device.parameters["sensor_uplink_interval"] = 60
        
        # Configure mock responses
        self.mock_router.simulate_sensor_uplink(int(self.test_device_id, 16), "parameter_info")
        
        # Execute set parameter
        update_data = {"sensor_uplink_interval": 120}
        result = self.module.set_parameter(update_data, self.send_callback, self.receive_callback, timeout=15.0)
        
        # Verify result
        self.assertCommandSuccess(result)
        self.assertIn("parameter_changes", result)
        self.assertGreater(len(result["parameter_changes"]), 0, "Should have parameter changes")
        
        # Verify the change was applied
        changes = result["parameter_changes"]
        uplink_change = next((c for c in changes if c["field"] == "sensor_uplink_interval"), None)
        self.assertIsNotNone(uplink_change, "Should have uplink interval change")
        self.assertEqual(uplink_change["new_value"], 120)
    
    def test_sensor_data_parsing(self):
        """センサーデータ解析テスト"""
        # Create mock uplink packet with sensor data
        sensor_data_info = IlluminanceTestData.get_mock_sensor_data()[0]
        
        # Simulate uplink reception
        self.mock_router.simulate_sensor_uplink(sensor_data_info["device_id"], "sensor_data")
        
        # Get mock uplink packet
        uplink_packet = self.receive_callback()
        self.assertIsNotNone(uplink_packet, "Should receive uplink packet")
        
        # Parse sensor data
        parsed_data = self.module.parse_sensor_uplink(uplink_packet)
        self.assertIsNotNone(parsed_data, "Should parse sensor data")
        
        # Verify parsed data structure
        self.assertSensorData(parsed_data)
    
    def test_command_timeout_handling(self):
        """コマンドタイムアウト処理テスト"""
        # Configure mock to not respond (timeout scenario)
        self.mock_router.set_response_success_rate(0.0)
        
        # Execute command with short timeout
        result = self.module.get_parameter(self.send_callback, self.receive_callback, uplink_timeout=2.0)
        
        # Verify timeout handling
        self.assertCommandFailure(result)
        self.assertIn("timeout", result.get("error", "").lower())
    
    def test_invalid_device_id_handling(self):
        """無効デバイスID処理テスト"""
        # Create module with invalid device ID format
        with self.assertRaises(ValueError):
            InvalidModule = IlluminanceModule("INVALID_DEVICE_ID")
    
    def test_parameter_template_creation(self):
        """パラメータテンプレート作成テスト"""
        template = self.module.create_parameter_template()
        
        self.assertIsInstance(template, dict)
        
        # Verify template structure
        expected_fields = [
            "timezone", "ble_mode", "tx_power", "advertise_interval",
            "sensor_uplink_interval", "sensor_read_mode", "sampling", 
            "hysteresis_high", "hysteresis_low"
        ]
        
        for field in expected_fields:
            self.assertIn(field, template, f"Template should contain {field}")
            self.assertIn("value", template[field], f"Field {field} should have value")
            self.assertIn("description", template[field], f"Field {field} should have description")
    
    def test_response_time_measurement(self):
        """応答時間測定テスト"""
        # Configure mock for quick response
        self.mock_router.simulate_sensor_uplink(int(self.test_device_id, 16), "parameter_info")
        
        # Measure response time
        self.test_utils.timing.start_timing("get_parameter_test")
        result = self.module.get_parameter(self.send_callback, self.receive_callback, uplink_timeout=10.0)
        duration = self.test_utils.timing.end_timing("get_parameter_test")
        
        # Verify command succeeded and timing is reasonable
        self.assertCommandSuccess(result)
        self.assertResponseTime(duration, 10.0, "get_parameter")  # Should be much faster in mock
    
    def tearDown(self):
        """テスト後処理"""
        if hasattr(self, 'mock_router'):
            self.mock_router.disconnect()
        
        super().tearDown()


class IlluminanceParametersUnitTests(unittest.TestCase):
    """照度パラメータ単体テストケース"""
    
    def test_parameter_creation_with_defaults(self):
        """デフォルト値でのパラメータ作成テスト"""
        params = IlluminanceParameters()
        
        # Verify default values
        self.assertEqual(params.sensor_id, 0x0121)
        self.assertEqual(params.timezone, 0x00)
        self.assertEqual(params.ble_mode, 0x00)
        self.assertEqual(params.advertise_interval, 1000)
        self.assertEqual(params.sensor_uplink_interval, 60)
    
    def test_parameter_update_from_dict(self):
        """辞書からのパラメータ更新テスト"""
        base_params = IlluminanceParameters()
        
        update_data = {
            "sensor_uplink_interval": 120,
            "hysteresis_high": 600.0,
            "hysteresis_low": 500.0
        }
        
        updated_params = base_params.update_from_dict(update_data)
        
        # Verify updates were applied
        self.assertEqual(updated_params.sensor_uplink_interval, 120)
        self.assertEqual(updated_params.hysteresis_high, 600.0)
        self.assertEqual(updated_params.hysteresis_low, 500.0)
        
        # Verify unchanged parameters remain the same
        self.assertEqual(updated_params.timezone, base_params.timezone)
        self.assertEqual(updated_params.ble_mode, base_params.ble_mode)
    
    def test_parameter_json_serialization(self):
        """パラメータJSON化テスト"""
        params = IlluminanceParameters()
        
        # Test to_json method
        json_str = params.to_json()
        self.assertIsInstance(json_str, str)
        
        # Verify it's valid JSON
        import json
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
        
        # Verify key fields are present
        self.assertIn("timezone", parsed)
        self.assertIn("sensor_uplink_interval", parsed)
        self.assertIn("hysteresis_high", parsed)
    
    def test_parameter_display_format(self):
        """パラメータ表示フォーマットテスト"""
        params = IlluminanceParameters()
        display_format = params.to_display_format()
        
        # Verify structure
        for field in ["timezone", "ble_mode", "tx_power"]:
            self.assertIn(field, display_format)
            self.assertIn("value", display_format[field])
            self.assertIn("description", display_format[field])
        
        # Verify specific descriptions
        self.assertEqual(display_format["timezone"]["description"], "JST")
        self.assertEqual(display_format["ble_mode"]["description"], "LongRange")


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)
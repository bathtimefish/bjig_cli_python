"""
BraveJIG Illuminance Module Test Scenarios

照度モジュール用の包括的テストシナリオ定義
- 単体テスト用データとシナリオ
- 統合テスト用シーケンス
- エラーケーステスト
- パフォーマンステスト

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class TestScenario:
    """テストシナリオ定義"""
    name: str
    description: str
    test_type: str  # "unit", "integration", "error", "performance"
    steps: List[Dict[str, Any]]
    expected_outcomes: Dict[str, Any]
    setup_data: Optional[Dict[str, Any]] = None
    cleanup_data: Optional[Dict[str, Any]] = None
    timeout: float = 60.0
    tags: List[str] = field(default_factory=list)


class IlluminanceTestData:
    """照度モジュールテストデータ生成器"""
    
    @staticmethod
    def get_valid_parameters() -> Dict[str, Any]:
        """有効なパラメータセット"""
        return {
            "timezone": 0x00,
            "ble_mode": 0x00,
            "tx_power": 0x00,
            "advertise_interval": 1000,
            "sensor_uplink_interval": 60,
            "sensor_read_mode": 0x00,
            "sampling": 0x00,
            "hysteresis_high": 500.0,
            "hysteresis_low": 400.0
        }
    
    @staticmethod
    def get_parameter_variations() -> List[Dict[str, Any]]:
        """パラメータバリエーション"""
        base_params = IlluminanceTestData.get_valid_parameters()
        
        variations = []
        
        # Timezone variations
        for tz in [0x00, 0x01]:
            params = base_params.copy()
            params["timezone"] = tz
            variations.append(params)
        
        # BLE mode variations
        for mode in [0x00, 0x01]:
            params = base_params.copy()
            params["ble_mode"] = mode
            variations.append(params)
        
        # Tx Power variations
        for power in [0x00, 0x01, 0x02, 0x04, 0x08]:
            params = base_params.copy()
            params["tx_power"] = power
            variations.append(params)
        
        # Interval variations
        for interval in [100, 500, 1000, 2000, 5000]:
            params = base_params.copy()
            params["advertise_interval"] = interval
            variations.append(params)
        
        for interval in [5, 30, 60, 300, 3600]:
            params = base_params.copy()
            params["sensor_uplink_interval"] = interval
            variations.append(params)
        
        # Sensor mode variations
        for mode in [0x00, 0x01, 0x02]:
            params = base_params.copy()
            params["sensor_read_mode"] = mode
            variations.append(params)
        
        # Sampling variations
        for sampling in [0x00, 0x01]:
            params = base_params.copy()
            params["sampling"] = sampling
            variations.append(params)
        
        # Hysteresis variations
        hysteresis_pairs = [
            (100.0, 80.0),
            (500.0, 400.0),
            (1000.0, 800.0),
            (5000.0, 4000.0),
            (10000.0, 8000.0)
        ]
        
        for high, low in hysteresis_pairs:
            params = base_params.copy()
            params["hysteresis_high"] = high
            params["hysteresis_low"] = low
            variations.append(params)
        
        return variations
    
    @staticmethod
    def get_invalid_parameters() -> List[Dict[str, Any]]:
        """無効なパラメータテストケース"""
        return [
            {
                "name": "Invalid Timezone",
                "params": {"timezone": 0x99},
                "expected_error": "timezone must be 0x00 (JST) or 0x01 (UTC)"
            },
            {
                "name": "Invalid BLE Mode",
                "params": {"ble_mode": 0x99},
                "expected_error": "ble_mode must be 0x00 (LongRange) or 0x01 (Legacy)"
            },
            {
                "name": "Invalid Tx Power",
                "params": {"tx_power": 0x99},
                "expected_error": "tx_power must be one of: 0x00-0x08"
            },
            {
                "name": "Advertise Interval Too Low",
                "params": {"advertise_interval": 50},
                "expected_error": "advertise_interval must be 100-10000 ms"
            },
            {
                "name": "Advertise Interval Too High",
                "params": {"advertise_interval": 15000},
                "expected_error": "advertise_interval must be 100-10000 ms"
            },
            {
                "name": "Uplink Interval Too Low",
                "params": {"sensor_uplink_interval": 1},
                "expected_error": "sensor_uplink_interval must be 5-86400 seconds"
            },
            {
                "name": "Uplink Interval Too High",
                "params": {"sensor_uplink_interval": 100000},
                "expected_error": "sensor_uplink_interval must be 5-86400 seconds"
            },
            {
                "name": "Invalid Read Mode",
                "params": {"sensor_read_mode": 0x99},
                "expected_error": "sensor_read_mode must be 0x00, 0x01, or 0x02"
            },
            {
                "name": "Invalid Sampling",
                "params": {"sampling": 0x99},
                "expected_error": "sampling must be 0x00 (1Hz) or 0x01 (2Hz)"
            },
            {
                "name": "Hysteresis High Too Low",
                "params": {"hysteresis_high": 10.0},
                "expected_error": "hysteresis_high must be 40.0-83865.0 Lux"
            },
            {
                "name": "Hysteresis High Too High",
                "params": {"hysteresis_high": 100000.0},
                "expected_error": "hysteresis_high must be 40.0-83865.0 Lux"
            },
            {
                "name": "Hysteresis Low Too Low",
                "params": {"hysteresis_low": 10.0},
                "expected_error": "hysteresis_low must be 40.0-83865.0 Lux"
            },
            {
                "name": "Hysteresis Low Too High",
                "params": {"hysteresis_low": 100000.0},
                "expected_error": "hysteresis_low must be 40.0-83865.0 Lux"
            },
            {
                "name": "Inverted Hysteresis",
                "params": {"hysteresis_high": 400.0, "hysteresis_low": 500.0},
                "expected_error": "hysteresis_low must be less than hysteresis_high"
            }
        ]
    
    @staticmethod
    def get_mock_sensor_data() -> List[Dict[str, Any]]:
        """モックセンサーデータ"""
        return [
            {
                "device_id": 0x2468800203400004,
                "sensor_id": 0x0121,
                "sequence_no": 1,
                "battery_level": 85,
                "sampling_period": 0x00,
                "timestamp": int(time.time()),
                "lux_values": [450.5, 455.2, 448.8]
            },
            {
                "device_id": 0x2468800203400004,
                "sensor_id": 0x0121,
                "sequence_no": 2,
                "battery_level": 83,
                "sampling_period": 0x01,
                "timestamp": int(time.time()) + 60,
                "lux_values": [1200.1, 1198.3, 1205.7, 1201.9]
            },
            {
                "device_id": 0x2468800203400004,
                "sensor_id": 0x0121,
                "sequence_no": 3,
                "battery_level": 20,  # Low battery
                "sampling_period": 0x00,
                "timestamp": int(time.time()) + 120,
                "lux_values": [50.2]
            }
        ]


class IlluminanceTestScenarios:
    """照度モジュールテストシナリオ定義"""
    
    @staticmethod
    def get_unit_test_scenarios() -> List[TestScenario]:
        """単体テストシナリオ"""
        scenarios = []
        
        # Parameter validation scenarios
        scenarios.append(TestScenario(
            name="Parameter Validation - Valid Cases",
            description="Test parameter validation with valid parameter sets",
            test_type="unit",
            steps=[
                {
                    "action": "validate_parameters",
                    "data": IlluminanceTestData.get_valid_parameters(),
                    "expected": {"valid": True}
                }
            ],
            expected_outcomes={"all_validations_pass": True},
            tags=["validation", "parameters"]
        ))
        
        # Invalid parameter scenarios
        for invalid_case in IlluminanceTestData.get_invalid_parameters():
            scenarios.append(TestScenario(
                name=f"Parameter Validation - {invalid_case['name']}",
                description=f"Test parameter validation for {invalid_case['name']}",
                test_type="unit",
                steps=[
                    {
                        "action": "validate_parameters",
                        "data": invalid_case["params"],
                        "expected": {
                            "valid": False,
                            "error_contains": invalid_case["expected_error"]
                        }
                    }
                ],
                expected_outcomes={"validation_fails": True},
                tags=["validation", "parameters", "error"]
            ))
        
        # Packet creation scenarios
        scenarios.append(TestScenario(
            name="Packet Creation - Instant Uplink",
            description="Test instant uplink packet creation",
            test_type="unit",
            steps=[
                {
                    "action": "create_instant_uplink_packet",
                    "data": {"device_id": "2468800203400004"},
                    "expected": {
                        "packet_length": 22,  # Expected packet length
                        "protocol_version": 0x01,
                        "packet_type": 0x00,
                        "sensor_id": 0x0121,
                        "command": 0x00
                    }
                }
            ],
            expected_outcomes={"packet_created": True},
            tags=["packet", "instant_uplink"]
        ))
        
        return scenarios
    
    @staticmethod
    def get_integration_test_scenarios() -> List[TestScenario]:
        """統合テストシナリオ"""
        scenarios = []
        
        # Full parameter workflow
        scenarios.append(TestScenario(
            name="Parameter Management Workflow",
            description="Complete parameter get -> modify -> set -> verify workflow",
            test_type="integration",
            steps=[
                {
                    "action": "get_parameter",
                    "expected": {"success": True, "has_parameter_info": True}
                },
                {
                    "action": "set_parameter",
                    "data": {"sensor_uplink_interval": 120},
                    "expected": {"success": True, "parameter_changed": True}
                },
                {
                    "action": "get_parameter",
                    "expected": {
                        "success": True,
                        "parameter_value": {"sensor_uplink_interval": 120}
                    }
                },
                {
                    "action": "set_parameter",
                    "data": {"sensor_uplink_interval": 60},  # Reset
                    "expected": {"success": True}
                }
            ],
            expected_outcomes={
                "workflow_complete": True,
                "parameters_modified": True,
                "parameters_restored": True
            },
            timeout=180.0,  # Longer timeout for full workflow
            tags=["workflow", "parameters", "integration"]
        ))
        
        # Sensor data acquisition
        scenarios.append(TestScenario(
            name="Sensor Data Acquisition",
            description="Test instant uplink and data parsing",
            test_type="integration",
            steps=[
                {
                    "action": "instant_uplink",
                    "expected": {"success": True, "command_accepted": True}
                },
                {
                    "action": "wait_for_uplink",
                    "timeout": 30.0,
                    "expected": {
                        "uplink_received": True,
                        "sensor_data_valid": True,
                        "has_lux_values": True
                    }
                }
            ],
            expected_outcomes={"sensor_data_received": True},
            timeout=45.0,
            tags=["sensor_data", "uplink", "integration"]
        ))
        
        return scenarios
    
    @staticmethod
    def get_error_test_scenarios() -> List[TestScenario]:
        """エラーケーステストシナリオ"""
        scenarios = []
        
        # Invalid device ID
        scenarios.append(TestScenario(
            name="Invalid Device ID",
            description="Test handling of invalid device ID",
            test_type="error",
            steps=[
                {
                    "action": "get_parameter",
                    "data": {"device_id": "INVALID_ID"},
                    "expected": {"success": False, "error_type": "device_not_found"}
                }
            ],
            expected_outcomes={"error_handled": True},
            tags=["error", "device_id"]
        ))
        
        # Connection timeout
        scenarios.append(TestScenario(
            name="Connection Timeout",
            description="Test handling of connection timeout",
            test_type="error",
            setup_data={"mock_connection_failure": True},
            steps=[
                {
                    "action": "get_parameter",
                    "expected": {"success": False, "error_type": "timeout"}
                }
            ],
            expected_outcomes={"timeout_handled": True},
            tags=["error", "timeout"]
        ))
        
        # Malformed response
        scenarios.append(TestScenario(
            name="Malformed Response",
            description="Test handling of malformed router response",
            test_type="error",
            setup_data={"mock_malformed_response": True},
            steps=[
                {
                    "action": "get_parameter",
                    "expected": {"success": False, "error_type": "parse_error"}
                }
            ],
            expected_outcomes={"parse_error_handled": True},
            tags=["error", "response"]
        ))
        
        return scenarios
    
    @staticmethod
    def get_performance_test_scenarios() -> List[TestScenario]:
        """パフォーマンステストシナリオ"""
        scenarios = []
        
        # Response time test
        scenarios.append(TestScenario(
            name="Command Response Time",
            description="Test command response times are within acceptable limits",
            test_type="performance",
            steps=[
                {
                    "action": "measure_response_time",
                    "command": "get_parameter",
                    "iterations": 10,
                    "expected": {"max_response_time": 15.0}  # 15 seconds max
                },
                {
                    "action": "measure_response_time",
                    "command": "instant_uplink",
                    "iterations": 5,
                    "expected": {"max_response_time": 10.0}  # 10 seconds max
                }
            ],
            expected_outcomes={"response_times_acceptable": True},
            tags=["performance", "timing"]
        ))
        
        # Concurrent operations
        scenarios.append(TestScenario(
            name="Concurrent Operations",
            description="Test behavior under concurrent command execution",
            test_type="performance",
            steps=[
                {
                    "action": "concurrent_commands",
                    "commands": [
                        {"action": "get_parameter"},
                        {"action": "instant_uplink"},
                        {"action": "get_parameter"}
                    ],
                    "expected": {"all_succeed_or_graceful_failure": True}
                }
            ],
            expected_outcomes={"concurrency_handled": True},
            tags=["performance", "concurrency"]
        ))
        
        return scenarios
    
    @staticmethod
    def get_hardware_test_sequences() -> List[Dict[str, Any]]:
        """実機テスト用シーケンス"""
        return [
            {
                "name": "Quick Health Check",
                "description": "Fast health check for basic functionality",
                "commands": [
                    {
                        "name": "Router Version",
                        "args": ["router", "get-version"],
                        "timeout": 10
                    },
                    {
                        "name": "Module Parameter Check",
                        "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                        "timeout": 30
                    }
                ]
            },
            {
                "name": "Comprehensive Parameter Test",
                "description": "Full parameter management testing",
                "commands": [
                    {
                        "name": "Get Initial Parameters",
                        "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                        "timeout": 45
                    },
                    {
                        "name": "Modify Uplink Interval",
                        "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                                "--data", '{"sensor_uplink_interval": 120}'],
                        "timeout": 45
                    },
                    {
                        "name": "Verify Parameter Change",
                        "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                        "timeout": 45
                    },
                    {
                        "name": "Test Hysteresis Change",
                        "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                                "--data", '{"hysteresis_high": 600.0, "hysteresis_low": 500.0}'],
                        "timeout": 45
                    },
                    {
                        "name": "Final Parameter Check",
                        "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                        "timeout": 45
                    },
                    {
                        "name": "Reset to Defaults",
                        "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                                "--data", '{"sensor_uplink_interval": 60, "hysteresis_high": 500.0, "hysteresis_low": 400.0}'],
                        "timeout": 45
                    }
                ]
            },
            {
                "name": "Sensor Data Collection",
                "description": "Test sensor data collection functionality",
                "commands": [
                    {
                        "name": "First Instant Uplink",
                        "args": ["module", "instant-uplink", "--module-id", "2468800203400004"],
                        "timeout": 30
                    },
                    {
                        "name": "Second Instant Uplink",
                        "args": ["module", "instant-uplink", "--module-id", "2468800203400004"],
                        "timeout": 30,
                        "delay": 5  # Wait 5 seconds between commands
                    },
                    {
                        "name": "Third Instant Uplink",
                        "args": ["module", "instant-uplink", "--module-id", "2468800203400004"],
                        "timeout": 30,
                        "delay": 5
                    }
                ]
            },
            {
                "name": "Error Handling Test",
                "description": "Test error conditions and recovery",
                "commands": [
                    {
                        "name": "Invalid Device ID Test",
                        "args": ["module", "get-parameter", "--module-id", "INVALIDDEVICEID"],
                        "timeout": 30,
                        "expected_success": False
                    },
                    {
                        "name": "Recovery Test",
                        "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                        "timeout": 45,
                        "expected_success": True
                    },
                    {
                        "name": "Invalid Parameter Test",
                        "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                                "--data", '{"sensor_uplink_interval": 999999}'],  # Invalid value
                        "timeout": 45,
                        "expected_success": False,
                        "stop_on_failure": False  # Continue even if this fails
                    }
                ]
            }
        ]
    
    @staticmethod
    def get_all_scenarios() -> Dict[str, List[TestScenario]]:
        """全テストシナリオを取得"""
        return {
            "unit": IlluminanceTestScenarios.get_unit_test_scenarios(),
            "integration": IlluminanceTestScenarios.get_integration_test_scenarios(),
            "error": IlluminanceTestScenarios.get_error_test_scenarios(),
            "performance": IlluminanceTestScenarios.get_performance_test_scenarios()
        }
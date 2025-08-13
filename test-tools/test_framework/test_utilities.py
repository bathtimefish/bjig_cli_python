"""
BraveJIG Test Utilities

テスト用ユーティリティクラス
- テストデータ生成
- パケット検証
- タイミング測定
- ログ管理

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import struct
import time
import random
import json
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from unittest.mock import Mock, MagicMock


@dataclass 
class TestPacket:
    """テスト用パケット構造"""
    packet_type: str  # "downlink_request", "downlink_response", "uplink_notification"
    protocol_version: int = 0x01
    data: bytes = b''
    timestamp: float = 0.0
    device_id: Optional[int] = None
    sensor_id: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class TestDataGenerator:
    """テストデータ生成器"""
    
    @staticmethod
    def generate_device_id() -> int:
        """ランダムなデバイスIDを生成"""
        return random.randint(0x1000000000000000, 0xFFFFFFFFFFFFFFFF)
    
    @staticmethod
    def generate_illuminance_parameters(variations: Dict[str, Any] = None) -> Dict[str, Any]:
        """照度センサーパラメータを生成"""
        base_params = {
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
        
        if variations:
            base_params.update(variations)
        
        return base_params
    
    @staticmethod
    def generate_sensor_data(device_id: int, sensor_id: int = 0x0121, 
                           lux_values: List[float] = None) -> Dict[str, Any]:
        """センサーデータを生成"""
        if lux_values is None:
            lux_values = [round(random.uniform(100.0, 1000.0), 2) for _ in range(3)]
        
        return {
            "device_id": device_id,
            "sensor_id": sensor_id,
            "sequence_no": random.randint(1, 65535),
            "battery_level": random.randint(20, 100),
            "sampling_period": 0x00,
            "timestamp": int(time.time()),
            "lux_values": lux_values
        }
    
    @staticmethod
    def generate_invalid_parameters() -> List[Dict[str, Any]]:
        """無効なパラメータのテストケースを生成"""
        return [
            {"timezone": 0x99, "expected_error": "timezone must be 0x00 (JST) or 0x01 (UTC)"},
            {"ble_mode": 0x99, "expected_error": "ble_mode must be 0x00 (LongRange) or 0x01 (Legacy)"},
            {"tx_power": 0x99, "expected_error": "tx_power must be one of: 0x00-0x08"},
            {"advertise_interval": 50, "expected_error": "advertise_interval must be 100-10000 ms"},
            {"advertise_interval": 15000, "expected_error": "advertise_interval must be 100-10000 ms"},
            {"sensor_uplink_interval": 1, "expected_error": "sensor_uplink_interval must be 5-86400 seconds"},
            {"sensor_uplink_interval": 100000, "expected_error": "sensor_uplink_interval must be 5-86400 seconds"},
            {"sensor_read_mode": 0x99, "expected_error": "sensor_read_mode must be 0x00, 0x01, or 0x02"},
            {"sampling": 0x99, "expected_error": "sampling must be 0x00 (1Hz) or 0x01 (2Hz)"},
            {"hysteresis_high": 10.0, "expected_error": "hysteresis_high must be 40.0-83865.0 Lux"},
            {"hysteresis_high": 100000.0, "expected_error": "hysteresis_high must be 40.0-83865.0 Lux"},
            {"hysteresis_low": 10.0, "expected_error": "hysteresis_low must be 40.0-83865.0 Lux"},
            {"hysteresis_low": 100000.0, "expected_error": "hysteresis_low must be 40.0-83865.0 Lux"},
            {"hysteresis_high": 400.0, "hysteresis_low": 500.0, 
             "expected_error": "hysteresis_low must be less than hysteresis_high"}
        ]


class PacketValidator:
    """パケット検証ユーティリティ"""
    
    @staticmethod
    def validate_downlink_request(packet: bytes, expected_device_id: int = None, 
                                expected_sensor_id: int = None, expected_cmd: int = None) -> Dict[str, Any]:
        """Downlinkリクエストパケットを検証"""
        result = {"valid": True, "errors": []}
        
        try:
            if len(packet) < 17:  # Minimum packet size
                result["errors"].append(f"Packet too short: {len(packet)} bytes")
                result["valid"] = False
                return result
            
            # Parse packet header
            protocol_version = packet[0]
            packet_type = packet[1] 
            data_length = struct.unpack('<H', packet[2:4])[0]
            unix_time = struct.unpack('<L', packet[4:8])[0]
            device_id = struct.unpack('<Q', packet[8:16])[0]
            sensor_id = struct.unpack('<H', packet[16:18])[0] if len(packet) >= 18 else None
            
            # Validate fields
            if protocol_version != 0x01:
                result["errors"].append(f"Invalid protocol version: 0x{protocol_version:02X}")
            
            if packet_type != 0x00:
                result["errors"].append(f"Invalid packet type: 0x{packet_type:02X} (expected 0x00)")
            
            if expected_device_id and device_id != expected_device_id:
                result["errors"].append(
                    f"Device ID mismatch: 0x{device_id:016X} (expected 0x{expected_device_id:016X})")
            
            if expected_sensor_id and sensor_id != expected_sensor_id:
                result["errors"].append(
                    f"Sensor ID mismatch: 0x{sensor_id:04X} (expected 0x{expected_sensor_id:04X})")
            
            if len(packet) >= 19:
                cmd = packet[18]
                if expected_cmd is not None and cmd != expected_cmd:
                    result["errors"].append(
                        f"Command mismatch: 0x{cmd:02X} (expected 0x{expected_cmd:02X})")
            
            # Data length validation
            expected_total_length = 17 + data_length  # Header + data
            if len(packet) != expected_total_length:
                result["errors"].append(
                    f"Packet length mismatch: {len(packet)} bytes (expected {expected_total_length})")
            
            result["parsed"] = {
                "protocol_version": f"0x{protocol_version:02X}",
                "packet_type": f"0x{packet_type:02X}",
                "data_length": data_length,
                "unix_time": unix_time,
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}" if sensor_id is not None else None,
                "cmd": f"0x{packet[18]:02X}" if len(packet) >= 19 else None
            }
            
            if result["errors"]:
                result["valid"] = False
            
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Parsing error: {str(e)}")
        
        return result
    
    @staticmethod
    def validate_uplink_notification(packet: bytes, expected_device_id: int = None,
                                   expected_sensor_id: int = None) -> Dict[str, Any]:
        """Uplinknotificationパケットを検証"""
        result = {"valid": True, "errors": []}
        
        try:
            if len(packet) < 21:  # Minimum uplink packet size
                result["errors"].append(f"Uplink packet too short: {len(packet)} bytes")
                result["valid"] = False
                return result
            
            # Parse uplink header
            protocol_version = packet[0]
            packet_type = packet[1]
            unix_time = struct.unpack('<L', packet[4:8])[0]  # Skip reserved field
            device_id = struct.unpack('<Q', packet[8:16])[0]
            sensor_id = struct.unpack('<H', packet[16:18])[0]
            
            # Validate fields
            if protocol_version != 0x01:
                result["errors"].append(f"Invalid protocol version: 0x{protocol_version:02X}")
            
            if packet_type != 0x00:
                result["errors"].append(f"Invalid packet type: 0x{packet_type:02X} (expected 0x00)")
            
            if expected_device_id and device_id != expected_device_id:
                result["errors"].append(
                    f"Device ID mismatch: 0x{device_id:016X} (expected 0x{expected_device_id:016X})")
            
            if expected_sensor_id and sensor_id != expected_sensor_id:
                result["errors"].append(
                    f"Sensor ID mismatch: 0x{sensor_id:04X} (expected 0x{expected_sensor_id:04X})")
            
            result["parsed"] = {
                "protocol_version": f"0x{protocol_version:02X}",
                "packet_type": f"0x{packet_type:02X}",
                "unix_time": unix_time,
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "sensor_data_length": len(packet) - 21
            }
            
            if result["errors"]:
                result["valid"] = False
            
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Parsing error: {str(e)}")
        
        return result


class TimingMeasurement:
    """タイミング測定ユーティリティ"""
    
    def __init__(self):
        self.start_times: Dict[str, float] = {}
        self.measurements: Dict[str, List[float]] = {}
    
    def start_timing(self, name: str):
        """タイミング測定開始"""
        self.start_times[name] = time.time()
    
    def end_timing(self, name: str) -> float:
        """タイミング測定終了"""
        if name not in self.start_times:
            raise ValueError(f"Timing '{name}' not started")
        
        duration = time.time() - self.start_times[name]
        
        if name not in self.measurements:
            self.measurements[name] = []
        self.measurements[name].append(duration)
        
        del self.start_times[name]
        return duration
    
    def get_statistics(self, name: str) -> Dict[str, float]:
        """測定統計を取得"""
        if name not in self.measurements or not self.measurements[name]:
            return {}
        
        measurements = self.measurements[name]
        return {
            "count": len(measurements),
            "min": min(measurements),
            "max": max(measurements),
            "average": sum(measurements) / len(measurements),
            "total": sum(measurements)
        }
    
    def clear_measurements(self, name: str = None):
        """測定データをクリア"""
        if name:
            self.measurements.pop(name, None)
        else:
            self.measurements.clear()


class TestUtilities:
    """テストユーティリティメインクラス"""
    
    def __init__(self):
        self.data_generator = TestDataGenerator()
        self.packet_validator = PacketValidator()
        self.timing = TimingMeasurement()
    
    def create_mock_callbacks(self, mock_router) -> tuple:
        """モックルーター用のコールバック関数を作成"""
        
        def send_callback(data: bytes) -> bool:
            return mock_router.send(data)
        
        def receive_callback() -> Optional[bytes]:
            return mock_router.receive()
        
        return send_callback, receive_callback
    
    def assert_command_success(self, result: Dict[str, Any], command_name: str = "command"):
        """コマンド成功をアサート"""
        assert result.get("success", False), f"{command_name} failed: {result.get('error', 'Unknown error')}"
    
    def assert_command_failure(self, result: Dict[str, Any], expected_error: str = None, 
                             command_name: str = "command"):
        """コマンド失敗をアサート"""
        assert not result.get("success", True), f"{command_name} should have failed but succeeded"
        
        if expected_error:
            error = result.get("error", "")
            assert expected_error in error, f"Expected error '{expected_error}' not found in '{error}'"
    
    def assert_packet_valid(self, packet: bytes, **validation_kwargs):
        """パケット有効性をアサート"""
        validation_result = self.packet_validator.validate_downlink_request(packet, **validation_kwargs)
        assert validation_result["valid"], f"Invalid packet: {validation_result['errors']}"
    
    def assert_response_time(self, duration: float, max_time: float, operation: str = "operation"):
        """応答時間をアサート"""
        assert duration <= max_time, f"{operation} took {duration:.2f}s, max allowed: {max_time}s"
    
    def create_test_scenario(self, name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """テストシナリオを作成"""
        return {
            "name": name,
            "steps": steps,
            "created_at": time.time()
        }
    
    def run_test_scenario(self, scenario: Dict[str, Any], mock_router, 
                         module_instance) -> Dict[str, Any]:
        """テストシナリオを実行"""
        results = {
            "scenario_name": scenario["name"],
            "steps": [],
            "success": True,
            "total_duration": 0.0,
            "errors": []
        }
        
        scenario_start = time.time()
        
        try:
            send_callback, receive_callback = self.create_mock_callbacks(mock_router)
            
            for i, step in enumerate(scenario["steps"]):
                step_name = f"Step {i+1}: {step.get('name', 'Unnamed')}"
                self.timing.start_timing(step_name)
                
                step_result = {
                    "step_number": i + 1,
                    "name": step.get('name', 'Unnamed'),
                    "command": step.get('command'),
                    "success": False,
                    "duration": 0.0,
                    "result": None,
                    "error": None
                }
                
                try:
                    # Execute command based on step configuration
                    command = step.get('command')
                    args = step.get('args', {})
                    
                    if hasattr(module_instance, command):
                        method = getattr(module_instance, command)
                        step_result["result"] = method(send_callback, receive_callback, **args)
                        step_result["success"] = step_result["result"].get("success", False)
                    else:
                        raise ValueError(f"Unknown command: {command}")
                    
                except Exception as e:
                    step_result["error"] = str(e)
                    results["errors"].append(f"{step_name}: {str(e)}")
                    results["success"] = False
                
                step_result["duration"] = self.timing.end_timing(step_name)
                results["steps"].append(step_result)
                
                # Stop on failure if configured
                if not step_result["success"] and step.get("stop_on_failure", True):
                    results["success"] = False
                    break
        
        except Exception as e:
            results["errors"].append(f"Scenario execution error: {str(e)}")
            results["success"] = False
        
        results["total_duration"] = time.time() - scenario_start
        return results
    
    def format_test_report(self, results: Dict[str, Any]) -> str:
        """テスト結果レポートを整形"""
        lines = [
            f"=== Test Scenario: {results['scenario_name']} ===",
            f"Overall Success: {'✅' if results['success'] else '❌'}",
            f"Total Duration: {results['total_duration']:.2f}s",
            f"Steps Completed: {len(results['steps'])}",
            ""
        ]
        
        for step in results["steps"]:
            status = "✅" if step["success"] else "❌"
            lines.append(f"{status} {step['name']} ({step['duration']:.2f}s)")
            if step["error"]:
                lines.append(f"    Error: {step['error']}")
        
        if results["errors"]:
            lines.extend(["", "Errors:"])
            for error in results["errors"]:
                lines.append(f"  - {error}")
        
        return "\n".join(lines)
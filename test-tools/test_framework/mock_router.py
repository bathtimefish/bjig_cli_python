"""
BraveJIG Router Mock Implementation

ルーター通信をモックするクラス
単体テストで実際のハードウェアなしでコマンドをテスト

Features:
- リアルなプロトコル応答シミュレーション
- 設定可能な応答パターン
- エラーケースのシミュレーション
- パケットログ記録
- レスポンス遅延シミュレーション

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import struct
import time
import threading
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import IntEnum
import logging
from unittest.mock import Mock


class MockPacketType(IntEnum):
    """モックパケットタイプ"""
    UPLINK_NOTIFICATION = 0x00
    DOWNLINK_RESPONSE = 0x01
    JIG_INFO_RESPONSE = 0x02


@dataclass
class MockResponse:
    """モック応答定義"""
    packet_type: int
    data: bytes
    delay_ms: float = 0.0
    repeat_count: int = 1
    condition: Optional[Callable] = None


@dataclass
class MockDeviceState:
    """モックデバイスの状態管理"""
    device_id: int = 0x2468800203400004
    sensor_id: int = 0x0121
    connected: bool = True
    battery_level: int = 85
    firmware_version: str = "1.2.3"
    parameters: Dict[str, Any] = field(default_factory=dict)
    sensor_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.parameters:
            self.parameters = {
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
        
        if not self.sensor_data:
            self.sensor_data = {
                "lux_values": [450.5, 455.2, 448.8],
                "sequence_no": 1,
                "sampling_period": 0x00,
                "timestamp": int(time.time())
            }


class MockBraveJIGRouter:
    """
    BraveJIGルーターのモック実装
    
    実際のハードウェア通信を模擬して、
    単体テストでコマンドの動作を検証
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Mock state
        self.is_connected = False
        self.devices: Dict[int, MockDeviceState] = {}
        self.router_info = {
            "version": "1.1.0",
            "device_id": "0x1234567890ABCDEF",
            "scan_mode": 0x01
        }
        
        # Response patterns and logging
        self.response_patterns: Dict[str, List[MockResponse]] = {}
        self.packet_log: List[Dict[str, Any]] = []
        self.auto_responses: Dict[bytes, MockResponse] = {}
        
        # Behavior settings
        self.default_delay = 0.1
        self.connection_success_rate = 1.0
        self.response_success_rate = 1.0
        
        # Initialize default responses
        self._setup_default_responses()
    
    def _setup_default_responses(self):
        """デフォルトの応答パターンを設定"""
        
        # Router version response
        version_data = b"1.1.0\x00"  # Null-terminated string
        self._add_auto_response(
            pattern=b"\x01\x02",  # JIG Info - Get Version
            response=MockResponse(
                packet_type=MockPacketType.JIG_INFO_RESPONSE,
                data=struct.pack("<BB", 0x01, 0x02) + version_data,
                delay_ms=50
            )
        )
        
        # Router device ID response  
        device_id_data = struct.pack("<Q", 0x1234567890ABCDEF)
        self._add_auto_response(
            pattern=b"\x01\x03",  # JIG Info - Get Device ID
            response=MockResponse(
                packet_type=MockPacketType.JIG_INFO_RESPONSE,
                data=struct.pack("<BB", 0x01, 0x03) + device_id_data,
                delay_ms=50
            )
        )
    
    def _add_auto_response(self, pattern: bytes, response: MockResponse):
        """自動応答パターンを追加"""
        self.auto_responses[pattern] = response
    
    def connect(self, port: str, baudrate: int = 38400) -> bool:
        """モック接続"""
        self.logger.info(f"Mock connecting to {port} at {baudrate} baud")
        
        # Simulate connection delay
        time.sleep(0.1)
        
        # Simulate connection failure rate
        import random
        if random.random() > self.connection_success_rate:
            self.logger.error("Mock connection failed")
            return False
        
        self.is_connected = True
        self.logger.info("Mock connection established")
        return True
    
    def disconnect(self):
        """モック切断"""
        self.is_connected = False
        self.logger.info("Mock disconnected")
    
    def send(self, data: bytes) -> bool:
        """データ送信モック"""
        if not self.is_connected:
            return False
        
        # Log sent packet
        self._log_packet("SENT", data)
        
        # Check for auto-responses
        self._check_auto_responses(data)
        
        return True
    
    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """データ受信モック"""
        if not self.is_connected:
            return None
        
        # Check for queued responses
        if hasattr(self, '_response_queue') and self._response_queue:
            response = self._response_queue.pop(0)
            
            # Simulate response delay
            if response.delay_ms > 0:
                time.sleep(response.delay_ms / 1000.0)
            
            self._log_packet("RECEIVED", response.data)
            return response.data
        
        return None
    
    def _check_auto_responses(self, sent_data: bytes):
        """送信データに対する自動応答をチェック"""
        for pattern, response in self.auto_responses.items():
            if pattern in sent_data:
                self._queue_response(response)
                break
    
    def _queue_response(self, response: MockResponse):
        """応答をキューに追加"""
        if not hasattr(self, '_response_queue'):
            self._response_queue = []
        
        for _ in range(response.repeat_count):
            self._response_queue.append(response)
    
    def _log_packet(self, direction: str, data: bytes):
        """パケットログ記録"""
        log_entry = {
            "timestamp": time.time(),
            "direction": direction,
            "data": data,
            "hex": data.hex(' ').upper(),
            "length": len(data)
        }
        self.packet_log.append(log_entry)
        self.logger.debug(f"{direction}: {log_entry['hex']}")
    
    # Device management methods
    def add_mock_device(self, device_id: int, sensor_id: int = 0x0121) -> MockDeviceState:
        """モックデバイスを追加"""
        device = MockDeviceState(device_id=device_id, sensor_id=sensor_id)
        self.devices[device_id] = device
        
        # Setup device-specific responses
        self._setup_device_responses(device)
        
        self.logger.info(f"Added mock device: 0x{device_id:016X}, sensor: 0x{sensor_id:04X}")
        return device
    
    def _setup_device_responses(self, device: MockDeviceState):
        """デバイス固有の応答を設定"""
        device_id_bytes = struct.pack("<Q", device.device_id)
        sensor_id_bytes = struct.pack("<H", device.sensor_id)
        
        # Instant uplink response (Downlink response)
        instant_uplink_response = self._create_downlink_response(
            device_id=device.device_id,
            sensor_id=device.sensor_id,
            cmd=0x00,  # INSTANT_UPLINK
            result=0x00  # Success
        )
        
        # Parameter get response + uplink
        param_get_response = self._create_downlink_response(
            device_id=device.device_id,
            sensor_id=device.sensor_id,
            cmd=0x0D,  # GET_PARAMETER
            result=0x00  # Success
        )
        
        # Register responses for device
        # Note: More sophisticated pattern matching could be implemented
        # For now, using simplified approach
    
    def _create_downlink_response(self, device_id: int, sensor_id: int, cmd: int, result: int) -> bytes:
        """Downlink応答パケットを作成"""
        packet = struct.pack('<BB', 0x01, 0x01)  # Protocol version, Packet type (Downlink response)
        packet += struct.pack('<L', int(time.time()))  # Unix time
        packet += struct.pack('<Q', device_id)  # Device ID
        packet += struct.pack('<H', sensor_id)  # Sensor ID
        packet += struct.pack('<H', 0x0000)  # Order
        packet += struct.pack('<B', cmd)  # Command
        packet += struct.pack('<B', result)  # Result
        return packet
    
    def _create_uplink_notification(self, device_id: int, sensor_id: int, sensor_data: bytes) -> bytes:
        """Uplink通知パケットを作成"""
        packet = struct.pack('<BB', 0x01, 0x00)  # Protocol version, Packet type (Uplink notification)
        packet += struct.pack('<H', 0x0000)  # Reserved
        packet += struct.pack('<L', int(time.time()))  # Unix time
        packet += struct.pack('<Q', device_id)  # Device ID
        packet += struct.pack('<H', sensor_id)  # Sensor ID
        packet += struct.pack('<B', 0x00)  # Notification
        packet += sensor_data
        return packet
    
    def simulate_sensor_uplink(self, device_id: int, uplink_type: str = "sensor_data"):
        """センサーアップリンクをシミュレート"""
        if device_id not in self.devices:
            self.logger.error(f"Device 0x{device_id:016X} not found")
            return
        
        device = self.devices[device_id]
        
        if uplink_type == "sensor_data":
            sensor_data = self._create_illuminance_sensor_data(device)
        elif uplink_type == "parameter_info":
            sensor_data = self._create_parameter_info_data(device)
        else:
            self.logger.error(f"Unknown uplink type: {uplink_type}")
            return
        
        uplink_packet = self._create_uplink_notification(
            device_id=device.device_id,
            sensor_id=device.sensor_id,
            sensor_data=sensor_data
        )
        
        self._queue_response(MockResponse(
            packet_type=MockPacketType.UPLINK_NOTIFICATION,
            data=uplink_packet,
            delay_ms=100
        ))
    
    def _create_illuminance_sensor_data(self, device: MockDeviceState) -> bytes:
        """照度センサーデータを作成"""
        data = struct.pack('<H', device.sensor_id)  # SensorID
        data += struct.pack('<H', device.sensor_data["sequence_no"])  # Sequence No
        data += struct.pack('<B', device.battery_level)  # Battery Level
        data += struct.pack('<B', device.sensor_data["sampling_period"])  # Sampling
        data += struct.pack('<L', device.sensor_data["timestamp"])  # Time
        
        lux_values = device.sensor_data["lux_values"]
        data += struct.pack('<H', len(lux_values))  # Sample Num
        
        for lux_value in lux_values:
            data += struct.pack('<f', float(lux_value))  # LuxData
        
        return data
    
    def _create_parameter_info_data(self, device: MockDeviceState) -> bytes:
        """パラメータ情報データを作成"""
        data = struct.pack('<H', 0x0000)  # SensorID for parameter info
        data += struct.pack('<H', 0xFFFF)  # Sequence No
        data += struct.pack('<H', device.sensor_id)  # Connected SensorID
        
        # FW Version (3 bytes)
        fw_parts = device.firmware_version.split('.')
        data += struct.pack('<BBB', int(fw_parts[0]), int(fw_parts[1]), int(fw_parts[2]))
        
        # Parameters
        params = device.parameters
        data += struct.pack('<B', params["timezone"])
        data += struct.pack('<B', params["ble_mode"])
        data += struct.pack('<B', params["tx_power"])
        data += struct.pack('<H', params["advertise_interval"])
        data += struct.pack('<L', params["sensor_uplink_interval"])
        data += struct.pack('<B', params["sensor_read_mode"])
        data += struct.pack('<B', params["sampling"])
        data += struct.pack('<f', float(params["hysteresis_high"]))
        data += struct.pack('<f', float(params["hysteresis_low"]))
        
        return data
    
    # Configuration methods
    def set_connection_success_rate(self, rate: float):
        """接続成功率を設定 (0.0-1.0)"""
        self.connection_success_rate = max(0.0, min(1.0, rate))
    
    def set_response_success_rate(self, rate: float):
        """応答成功率を設定 (0.0-1.0)"""
        self.response_success_rate = max(0.0, min(1.0, rate))
    
    def set_default_delay(self, delay_ms: float):
        """デフォルト応答遅延を設定"""
        self.default_delay = delay_ms
    
    def clear_packet_log(self):
        """パケットログをクリア"""
        self.packet_log.clear()
    
    def get_packet_log(self) -> List[Dict[str, Any]]:
        """パケットログを取得"""
        return self.packet_log.copy()
    
    def get_packet_log_summary(self) -> Dict[str, Any]:
        """パケットログサマリーを取得"""
        total_packets = len(self.packet_log)
        sent_packets = sum(1 for entry in self.packet_log if entry["direction"] == "SENT")
        received_packets = sum(1 for entry in self.packet_log if entry["direction"] == "RECEIVED")
        
        return {
            "total_packets": total_packets,
            "sent_packets": sent_packets,
            "received_packets": received_packets,
            "total_bytes": sum(entry["length"] for entry in self.packet_log),
            "duration": (self.packet_log[-1]["timestamp"] - self.packet_log[0]["timestamp"]) if self.packet_log else 0.0
        }
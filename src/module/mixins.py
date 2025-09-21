# -*- coding: utf-8 -*-
"""
BraveJIG Module Mixins
共通機能をMixinパターンで提供
"""

import time
import struct
import logging
from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

class UplinkWaitMixin:
    """Uplink待機処理の共通Mixin - 動作確認済み"""
    
    def wait_for_uplink(self,
                       receive_callback: Callable,
                       expected_sensor_id: int,
                       timeout: float = 30.0,
                       uplink_type: str = "sensor_data") -> Optional[bytes]:
        """
        Wait for uplink with specific sensor ID (動作確認済みのパターン)
        
        Args:
            receive_callback: Function to receive data
            expected_sensor_id: Expected sensor ID in uplink
            timeout: Timeout in seconds
            uplink_type: Type description for logging
            
        Returns:
            Uplink data bytes or None if timeout
        """
        self.logger.info(f"Waiting for {uplink_type} uplink from sensor {expected_sensor_id:04X}...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            uplink_data = receive_callback()
            if uplink_data and len(uplink_data) >= 18:
                packet_type = uplink_data[1]
                if packet_type == 0x00:  # Uplink notification
                    sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
                    if sensor_id == expected_sensor_id:
                        self.logger.info(f"{uplink_type.title()} uplink received successfully")
                        return uplink_data
            time.sleep(0.1)
        
        self.logger.warning(f"No {uplink_type} uplink received within {timeout} seconds")
        return None

    def wait_for_sensor_uplink(self, receive_callback, timeout: float = 30.0) -> Optional[bytes]:
        """Wait for illuminance sensor uplink (sensor_id=0x0121)"""
        return self.wait_for_uplink(receive_callback, self.sensor_id, timeout, "illuminance sensor data")
    
    def wait_for_parameter_uplink(self, receive_callback, timeout: float = 30.0) -> Optional[bytes]:
        """Wait for parameter information uplink (sensor_id=0x0000)"""
        return self.wait_for_uplink(receive_callback, 0x0000, timeout, "parameter info")


class ParameterMixin:
    """パラメータ操作の共通Mixin"""
    
    def validate_uplink_data(self, uplink_data: bytes, expected_sensor_id: int = None) -> bool:
        """
        Validate uplink data format and sensor ID
        
        Args:
            uplink_data: Raw uplink data
            expected_sensor_id: Expected sensor ID (optional)
            
        Returns:
            True if valid, False otherwise
        """
        if len(uplink_data) < 18:
            return False
        
        try:
            # Check packet type (should be 0x00 for uplink)
            if uplink_data[1] != 0x00:
                return False
            
            # Check sensor ID if specified
            if expected_sensor_id is not None:
                sensor_id = struct.unpack('<H', uplink_data[16:18])[0]
                return sensor_id == expected_sensor_id
                
            return True
            
        except Exception:
            return False
    
    def extract_device_id_from_uplink(self, uplink_data: bytes) -> Optional[int]:
        """
        Extract device ID from uplink packet (動作確認済み)
        
        Args:
            uplink_data: Raw uplink data
            
        Returns:
            Device ID as integer or None if cannot extract
        """
        if len(uplink_data) < 16:
            return None
        
        try:
            device_id = struct.unpack('<Q', uplink_data[8:16])[0]
            return device_id
        except Exception:
            return None


class ExecutorMixin:
    """Executor共通処理のMixin"""
    
    def suppress_logging(self):
        """ログレベルを抑制（JSON出力時に使用）"""
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger("AsyncSerialMonitor").setLevel(logging.CRITICAL)
        logging.getLogger("core.connection_manager").setLevel(logging.CRITICAL)
    
    def debug_packet_with_time(self, packet_data: bytes, packet_type: str):
        """共通のデバッグ出力関数 - パケットとunix timeを表示"""
        import sys
        from datetime import datetime
        
        try:
            # Unix timeを抽出して日時に変換
            unix_time = struct.unpack('<L', packet_data[4:8])[0]
            formatted_time = datetime.fromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"DEBUG: {packet_type}: {packet_data.hex(' ').upper()}", file=sys.stderr)
            print(f"DEBUG: {packet_type.split()[0]} UNIX TIME: {unix_time} -> {formatted_time}", file=sys.stderr)
        except Exception as e:
            # Unix time解析に失敗した場合はパケットのみ表示
            print(f"DEBUG: {packet_type}: {packet_data.hex(' ').upper()}", file=sys.stderr)
            print(f"DEBUG: Unix time parse error: {e}", file=sys.stderr)
"""
BraveJIG Connection Manager

シリアル通信接続の管理を担当するクラス。
AsyncSerialMonitorとの統合、接続状態管理、データ送信機能を提供。

Author: BraveJIG CLI Development Team
Date: 2025-08-02
"""

import logging
import sys
import os
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor

# Add scripts directory to path for AsyncSerialMonitor import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

try:
    from async_serial_monitor import AsyncSerialMonitor, SerialConnectionError
except ImportError:
    # Fallback for development - create a mock class
    class AsyncSerialMonitor:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def start_monitoring(self): pass
        def stop_monitoring(self): pass
        def send(self, data): return True
        def set_data_callback(self, callback): pass
    
    class SerialConnectionError(Exception): pass


class ConnectionManager:
    """
    BraveJIG シリアル接続管理クラス
    
    AsyncSerialMonitorとの統合による安定したシリアル通信を提供し、
    接続状態の管理とデータ送受信機能を担当する。
    """

    def __init__(self, port: str, baudrate: int = 38400, timeout: float = 10.0):
        """
        接続マネージャーを初期化
        
        Args:
            port: シリアルポートパス (e.g., '/dev/ttyACM0')
            baudrate: 通信ボーレート (default: 38400)
            timeout: 通信タイムアウト秒 (default: 10.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        self._monitor: Optional[AsyncSerialMonitor] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._data_callback: Optional[Callable[[bytes], None]] = None
        
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self):
        """ログ設定を初期化"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def connect(self) -> bool:
        """
        BraveJIGルーターへの接続を確立
        
        Returns:
            bool: 接続成功時True
        """
        try:
            self._monitor = AsyncSerialMonitor(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self._monitor.__enter__()
            
            # データコールバックが設定されている場合は登録
            if self._data_callback:
                self._monitor.set_data_callback(self._data_callback)
            
            self._monitor.start_monitoring()
            
            self.logger.info(f"Connected to BraveJIG router on {self.port}")
            return True
            
        except SerialConnectionError as e:
            self.logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """BraveJIGルーターから切断"""
        if self._monitor:
            try:
                self._monitor.stop_monitoring()
                self._monitor.__exit__(None, None, None)
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self._monitor = None
        
        self.logger.info("Disconnected from BraveJIG router")

    def send_data(self, data: bytes) -> bool:
        """
        データを送信
        
        Args:
            data: 送信するバイトデータ
            
        Returns:
            bool: 送信成功時True
            
        Raises:
            RuntimeError: 未接続時
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to BraveJIG router")
        
        self.logger.debug(f"Sending {len(data)} bytes: {data.hex(' ').upper()}")
        
        return self._monitor.send(data)

    def set_data_callback(self, callback: Callable[[bytes], None]):
        """
        データ受信コールバックを設定
        
        Args:
            callback: データ受信時に呼び出される関数
        """
        self._data_callback = callback
        
        # 既に接続している場合は即座に登録
        if self._monitor:
            self._monitor.set_data_callback(callback)

    def is_connected(self) -> bool:
        """
        接続状態を確認
        
        Returns:
            bool: 接続中の場合True
        """
        return self._monitor is not None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
"""
BraveJIG Command Executor

基本的なコマンド実行とレスポンス待機を担当するクラス。
JIG Infoコマンドやモジュールコマンドの統一的な実行インターフェースを提供。

Author: BraveJIG CLI Development Team  
Date: 2025-08-02
"""

import logging
from typing import Any, Optional, Dict
from concurrent.futures import Future
from dataclasses import dataclass

from protocol.bjig_protocol import BraveJIGProtocol, JigInfoCommand
from .connection_manager import ConnectionManager
from .response_handler import ResponseHandler


@dataclass
class CommandResult:
    """コマンド実行結果"""
    success: bool
    response: Any = None
    error: Optional[str] = None
    raw_data: Optional[bytes] = None
    parameter_info: Optional[Dict[str, Any]] = None


class CommandExecutor:
    """
    BraveJIG コマンド実行クラス
    
    ルーターとモジュールの基本コマンド実行、レスポンス待機、
    および結果の統一的な処理を提供する。
    """

    def __init__(self, connection: ConnectionManager, response_handler: ResponseHandler, 
                 protocol: BraveJIGProtocol, timeout: float = 10.0):
        """
        コマンド実行器を初期化
        
        Args:
            connection: 接続管理インスタンス
            response_handler: レスポンス処理インスタンス
            protocol: 通信プロトコルインスタンス
            timeout: デフォルトタイムアウト秒
        """
        self.connection = connection
        self.response_handler = response_handler
        self.protocol = protocol
        self.timeout = timeout
        
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

    def execute_router_command(self, cmd: JigInfoCommand, **kwargs) -> CommandResult:
        """
        ルーターコマンドを実行
        
        Args:
            cmd: JIG Infoコマンド
            **kwargs: コマンド固有のパラメーター
            
        Returns:
            CommandResult: 実行結果
        """
        try:
            # コマンド別の特別処理
            if cmd == JigInfoCommand.SET_SCAN_MODE_LONG_RANGE or cmd == JigInfoCommand.SET_SCAN_MODE_LEGACY:
                # SET_SCAN_MODEの場合、modeパラメーターからCMDを決定
                mode = kwargs.get('mode')
                if mode is not None:
                    cmd = self.protocol.scan_mode_cmd(mode)
            
            # リクエスト生成
            request = self.protocol.create_jig_info_request(cmd)
            response_key = f"jig_info_{cmd}"
            
            # コマンド送信とレスポンス待機
            response = self._send_and_wait(request, response_key)
            
            return CommandResult(success=True, response=response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    def execute_device_id_command(self, index: Optional[int] = None, remove: bool = False) -> CommandResult:
        """
        Device IDコマンドを実行（取得または削除）
        
        Args:
            index: デバイスインデックス（Noneの場合は全て）
            remove: True の場合は削除、False の場合は取得
            
        Returns:
            CommandResult: 実行結果
        """
        try:
            if remove:
                # デバイスID削除
                if index is None:
                    cmd = JigInfoCommand.REMOVE_DEVICE_ID_ALL
                else:
                    # インデックス範囲チェック
                    if not (0 <= index <= 99):
                        raise ValueError(f"Device index {index} out of range (0-99)")
                    cmd = 0x6C + index
            else:
                # デバイスID取得
                if index is None:
                    cmd = JigInfoCommand.GET_DEVICE_ID_ALL
                else:
                    cmd = self.protocol.cmd_from_device_index(index)
            
            request = self.protocol.create_jig_info_request(cmd)
            response_key = f"jig_info_{cmd}"
            
            response = self._send_and_wait(request, response_key)
            
            return CommandResult(success=True, response=response)
            
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    def execute_module_command(self, module_id: str, command_type: str, **kwargs) -> CommandResult:
        """
        モジュールコマンドを実行
        
        Args:
            module_id: モジュールID
            command_type: コマンドタイプ
            **kwargs: コマンド固有のパラメーター
            
        Returns:
            CommandResult: 実行結果
        """
        try:
            # 各モジュールコマンドの実装は既存のmodule/配下のクラスを利用
            if command_type == "instant_uplink":
                return self._execute_instant_uplink(module_id, **kwargs)
            elif command_type == "get_parameter":
                return self._execute_get_parameter(module_id, **kwargs)
            elif command_type == "set_parameter":
                return self._execute_set_parameter(module_id, **kwargs)
            elif command_type == "restart":
                return self._execute_module_restart(module_id, **kwargs)
            elif command_type == "sensor_dfu":
                return self._execute_sensor_dfu(module_id, **kwargs)
            else:
                return CommandResult(success=False, error=f"Unknown module command type: {command_type}")
                
        except Exception as e:
            return CommandResult(success=False, error=f"Module command execution failed: {str(e)}")

    def _send_and_wait(self, data: bytes, response_key: str, timeout: float = None) -> Any:
        """
        データ送信とレスポンス待機
        
        Args:
            data: 送信データ
            response_key: レスポンスキー
            timeout: タイムアウト秒（Noneの場合はデフォルト使用）
            
        Returns:
            Any: レスポンスオブジェクト
            
        Raises:
            RuntimeError: 接続エラーまたは送信エラー
            TimeoutError: タイムアウト
        """
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to BraveJIG router")
        
        timeout = timeout or self.timeout
        
        # レスポンス待機用Future作成
        future = Future()
        self.response_handler.register_future(response_key, future)
        
        try:
            # データ送信
            if not self.connection.send_data(data):
                raise RuntimeError("Failed to send data")
            
            # レスポンス待機
            return future.result(timeout=timeout)
            
        except Exception as e:
            # エラー時はFutureをクリーンアップ
            if response_key in self.response_handler._response_futures:
                self.response_handler._response_futures.pop(response_key, None)
            raise

    # モジュールコマンド実装（既存コードからの移植）
    def _execute_instant_uplink(self, module_id: str, **kwargs) -> CommandResult:
        """Instant uplink コマンド実行"""
        try:
            from module.illuminance.instant_uplink import InstantUplinkCommand
            
            command = InstantUplinkCommand(module_id)
            
            def send_callback(data: bytes) -> bool:
                return self.connection.send_data(data)
            
            def receive_callback() -> Optional[bytes]:
                # 簡略化された実装 - 実際には適切な非同期処理が必要
                import time
                time.sleep(0.5)
                return None
            
            result = command.execute_instant_uplink(send_callback, receive_callback)
            
            if result.get("success", False):
                return CommandResult(success=True, response=result)
            else:
                return CommandResult(success=False, error=result.get("error", "Instant uplink failed"))
                
        except Exception as e:
            return CommandResult(success=False, error=f"Instant uplink execution failed: {str(e)}")

    def _execute_get_parameter(self, module_id: str, **kwargs) -> CommandResult:
        """Get parameter コマンド実行"""
        try:
            from module.illuminance.get_parameter import GetParameterCommand
            
            command = GetParameterCommand(module_id)
            
            def send_callback(data: bytes) -> bool:
                return self.connection.send_data(data)
            
            def receive_callback() -> Optional[bytes]:
                # 非同期モニタリングを使用してデータを受信
                # 実際の実装では、モニタリングからの最新データを取得する必要がある
                # これは一時的なプレースホルダー実装
                import time
                time.sleep(0.1)
                return None
            
            # パラメータ取得は90秒のタイムアウトが必要
            result = command.execute_get_parameter(send_callback, receive_callback, uplink_timeout=90.0)
            
            if result.get("success", False):
                return CommandResult(success=True, response=result, parameter_info=result.get("parameter_info"))
            else:
                return CommandResult(success=False, error=result.get("error", "Parameter acquisition failed"))
                
        except Exception as e:
            return CommandResult(success=False, error=f"Parameter acquisition failed: {str(e)}")

    def _execute_set_parameter(self, module_id: str, **kwargs) -> CommandResult:
        """Set parameter コマンド実行"""
        try:
            from module.illuminance.set_parameter import SetParameterCommand
            
            command = SetParameterCommand(module_id)
            data = kwargs.get('data', '')
            
            def send_callback(data: bytes) -> bool:
                return self.connection.send_data(data)
            
            def receive_callback() -> Optional[bytes]:
                import time
                time.sleep(0.5)
                return None
            
            result = command.execute_set_parameter(data, send_callback, receive_callback)
            
            if result.get("success", False):
                return CommandResult(success=True, response=result)
            else:
                return CommandResult(success=False, error=result.get("error", "Parameter setting failed"))
                
        except Exception as e:
            return CommandResult(success=False, error=f"Parameter setting failed: {str(e)}")

    def _execute_module_restart(self, module_id: str, **kwargs) -> CommandResult:
        """Module restart コマンド実行"""
        try:
            from module.illuminance.device_restart import DeviceRestartCommand
            
            command = DeviceRestartCommand(module_id)
            
            def send_callback(data: bytes) -> bool:
                return self.connection.send_data(data)
            
            def receive_callback() -> Optional[bytes]:
                import time
                time.sleep(0.5)
                return None
            
            result = command.execute_device_restart(send_callback, receive_callback)
            
            if result.get("success", False):
                return CommandResult(success=True, response=result)
            else:
                return CommandResult(success=False, error=result.get("error", "Device restart failed"))
                
        except Exception as e:
            return CommandResult(success=False, error=f"Device restart failed: {str(e)}")

    def _execute_sensor_dfu(self, module_id: str, **kwargs) -> CommandResult:
        """Sensor DFU コマンド実行"""
        try:
            from module.illuminance.core.sensor_dfu import SensorDfuCommand
            
            command = SensorDfuCommand(module_id)
            firmware_file = kwargs.get('firmware_file', '')
            
            def send_callback(data: bytes) -> bool:
                return self.connection.send_data(data)
            
            def receive_callback() -> Optional[bytes]:
                import time
                time.sleep(0.5)
                return None
            
            def progress_callback(progress: dict) -> None:
                self.logger.info(f"Sensor DFU Progress: {progress['progress_percent']:.1f}% "
                               f"({progress['current_block']}/{progress['total_blocks']} blocks) - {progress['phase']}")
            
            result = command.execute_sensor_dfu(firmware_file, send_callback, receive_callback, progress_callback)
            
            if result.get("success", False):
                return CommandResult(success=True, response=result)
            else:
                return CommandResult(success=False, error=result.get("error", "Sensor DFU failed"))
                
        except Exception as e:
            return CommandResult(success=False, error=f"Sensor DFU failed: {str(e)}")
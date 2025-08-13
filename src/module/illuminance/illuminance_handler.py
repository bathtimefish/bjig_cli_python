"""
BraveJIG Illuminance Sensor Module Handler

照度センサーモジュール用のメインハンドラー
各種コマンドのルーティングと統合管理

Author: BraveJIG CLI Development Team
Date: 2025-08-12
"""

from typing import Dict, Any, Optional
from .handlers.get_parameter_executor import GetParameterExecutor
from .handlers.set_parameter_executor import SetParameterExecutor
from .handlers.device_restart_executor import DeviceRestartExecutor
from .handlers.sensor_dfu_executor import SensorDfuExecutor
from .handlers.instant_uplink_executor import InstantUplinkExecutor


class IlluminanceHandler:
    """
    照度センサーモジュール統合ハンドラー
    
    各コマンドの実行を適切なexecutorに委譲し、
    モジュール全体の整合性を管理
    """
    
    def __init__(self):
        """Initialize handler with executors"""
        self.get_parameter_executor = GetParameterExecutor()
        self.set_parameter_executor = SetParameterExecutor()
        self.device_restart_executor = DeviceRestartExecutor()
        self.sensor_dfu_executor = SensorDfuExecutor()
        self.instant_uplink_executor = InstantUplinkExecutor()
    
    def get_parameter(self, port: str, baud: int, sensor_id: str, module_id: str):
        """
        パラメータ取得コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            sensor_id: センサーID
            module_id: モジュールID
        """
        return self.get_parameter_executor.execute(port, baud, sensor_id, module_id)
    
    def set_parameter(self, port: str, baud: int, sensor_id: str, module_id: str, value: str):
        """
        パラメータ設定コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            sensor_id: センサーID
            module_id: モジュールID
            value: 設定値JSON
        """
        return self.set_parameter_executor.execute(port, baud, sensor_id, module_id, value)
    
    def device_restart(self, port: str, baud: int, module_id: str):
        """
        デバイス再起動コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            module_id: モジュールID
        """
        return self.device_restart_executor.execute(port, baud, module_id)
    
    def sensor_dfu(self, port: str, baud: int, sensor_id: str, module_id: str, firmware_file: str):
        """
        センサーDFUコマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            sensor_id: センサーID
            module_id: モジュールID
            firmware_file: ファームウェアファイルパス
        """
        return self.sensor_dfu_executor.execute(port, baud, sensor_id, module_id, firmware_file)
    
    def instant_uplink(self, port: str, baud: int, module_id: str):
        """
        即時Uplink要求コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            module_id: モジュールID
        """
        return self.instant_uplink_executor.execute(port, baud, module_id)
    
    def get_supported_commands(self) -> Dict[str, str]:
        """
        サポートしているコマンド一覧を取得
        
        Returns:
            コマンド名と説明の辞書
        """
        return {
            "get-parameter": "照度センサーパラメータ取得",
            "set-parameter": "照度センサーパラメータ設定", 
            "instant-uplink": "照度センサー即時Uplink要求",
            "device-restart": "照度センサーデバイス再起動",
            "sensor-dfu": "照度センサーファームウェア更新"
        }
    
    def validate_sensor_id(self, sensor_id: str) -> bool:
        """
        センサーIDの妥当性チェック
        
        Args:
            sensor_id: センサーID
            
        Returns:
            妥当性 (照度センサーは0121固定)
        """
        return sensor_id.upper() == "0121"
    
    def validate_module_id(self, module_id: str) -> bool:
        """
        モジュールIDの妥当性チェック
        
        Args:
            module_id: モジュールID
            
        Returns:
            妥当性 (16桁hex)
        """
        normalized_id = module_id.replace("-", "").replace(":", "").upper()
        return len(normalized_id) == 16 and all(c in "0123456789ABCDEF" for c in normalized_id)
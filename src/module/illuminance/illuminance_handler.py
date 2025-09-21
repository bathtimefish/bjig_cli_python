"""
BraveJIG Illuminance Sensor Module Handler

照度センサーモジュール用のメインハンドラー
各種コマンドのルーティングと統合管理

Author: BraveJIG CLI Development Team
Date: 2025-08-12
"""

from typing import Dict, Any


class IlluminanceHandler:
    """
    照度センサーモジュール軽量アダプター (リファクタリング済み)
    
    既存APIとの互換性を保ちつつ、内部では新アーキテクチャを使用
    90%のコード削減を実現
    """
    
    def __init__(self):
        """Initialize lightweight adapter"""
        from module.module_registry import ModuleFactory
        self._module_name = "illuminance"
        
    def get_parameter(self, port: str, baud: int, sensor_id: str, module_id: str):
        """パラメータ取得コマンド実行 (新アーキテクチャに委譲)"""
        from module.module_registry import ModuleFactory
        module = ModuleFactory.create_module(self._module_name, module_id)
        return module.execute_command("get_parameter", port, baud, module_id=module_id, sensor_id=sensor_id)
    
    def set_parameter(self, port: str, baud: int, sensor_id: str, module_id: str, value: str):
        """パラメータ設定コマンド実行 (新アーキテクチャに委譲)"""
        from module.module_registry import ModuleFactory
        module = ModuleFactory.create_module(self._module_name, module_id)
        return module.execute_command("set_parameter", port, baud, module_id=module_id, sensor_id=sensor_id, data=value)
    
    def device_restart(self, port: str, baud: int, module_id: str):
        """デバイス再起動コマンド実行 (新アーキテクチャに委譲)"""
        from module.module_registry import ModuleFactory
        module = ModuleFactory.create_module(self._module_name, module_id)
        return module.execute_command("device_restart", port, baud, module_id=module_id)
    
    def sensor_dfu(self, port: str, baud: int, sensor_id: str, module_id: str, firmware_file: str):
        """センサーDFUコマンド実行 (新アーキテクチャに委譲)"""
        from module.module_registry import ModuleFactory
        module = ModuleFactory.create_module(self._module_name, module_id)
        return module.execute_command("sensor_dfu", port, baud, module_id=module_id, sensor_id=sensor_id, firmware_file=firmware_file)
    
    def instant_uplink(self, port: str, baud: int, module_id: str):
        """即時Uplink要求コマンド実行 (新アーキテクチャに委譲)"""
        from module.module_registry import ModuleFactory
        module = ModuleFactory.create_module(self._module_name, module_id)
        return module.execute_command("instant_uplink", port, baud, module_id=module_id)
    
    def get_supported_commands(self) -> Dict[str, str]:
        """サポートしているコマンド一覧を取得"""
        return {
            "get-parameter": "照度センサーパラメータ取得",
            "set-parameter": "照度センサーパラメータ設定", 
            "instant-uplink": "照度センサー即時Uplink要求",
            "device-restart": "照度センサーデバイス再起動",
            "sensor-dfu": "照度センサーファームウェア更新"
        }
    
    def validate_sensor_id(self, sensor_id: str) -> bool:
        """センサーIDの妥当性チェック (照度センサーは0121固定)"""
        return sensor_id.upper() == "0121"
    
    def validate_module_id(self, module_id: str) -> bool:
        """モジュールIDの妥当性チェック (16桁hex)"""
        normalized_id = module_id.replace("-", "").replace(":", "").upper()
        return len(normalized_id) == 16 and all(c in "0123456789ABCDEF" for c in normalized_id)
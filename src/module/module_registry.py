# -*- coding: utf-8 -*-
"""
Module Registry & Factory
プラグイン式モジュール管理システム
"""

import importlib
from typing import Dict, Any, Type, Optional
from module.universal_command import UniversalCommand


class ModuleRegistry:
    """
    モジュール登録・管理システム
    動的ローディングとフォールバック機能を提供
    """
    
    _modules: Dict[str, Type] = {}
    _configs: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register_module(cls, name: str, module_class: Type, config: Dict[str, Any]):
        """
        Register a module class and its configuration
        
        Args:
            name: Module name
            module_class: Module class
            config: Module configuration
        """
        cls._modules[name] = module_class
        cls._configs[name] = config
    
    @classmethod
    def get_module_class(cls, name: str) -> Type:
        """
        Get module class by name with dynamic loading fallback
        
        Args:
            name: Module name
            
        Returns:
            Module class
        """
        if name not in cls._modules:
            cls._load_module(name)
        
        return cls._modules.get(name, UniversalCommand)
    
    @classmethod
    def get_module_config(cls, name: str) -> Dict[str, Any]:
        """
        Get module configuration by name
        
        Args:
            name: Module name
            
        Returns:
            Module configuration
        """
        if name not in cls._configs:
            cls._load_module(name)
        
        return cls._configs.get(name, {})
    
    @classmethod
    def _load_module(cls, name: str):
        """
        Load module dynamically with fallback to config-driven approach
        
        Args:
            name: Module name
        """
        try:
            # 1. 専用実装を試行
            module = importlib.import_module(f"module.{name}")
            module_class = getattr(module, f"{name.title()}Module", None)
            
            if module_class:
                # 設定も読み込み
                config_module = importlib.import_module(f"module.{name}.{name}_config")
                config = getattr(config_module, f"get_{name}_config", lambda: {})()
                
                cls._modules[name] = module_class
                cls._configs[name] = config
                return
                
        except ImportError:
            pass
        
        try:
            # 2. 設定ファイルのみからUniversalCommandで動作
            config_module = importlib.import_module(f"module.{name}.{name}_config")
            config = getattr(config_module, f"get_{name}_config", lambda: {})()
            
            cls._modules[name] = UniversalCommand
            cls._configs[name] = config
            
        except ImportError:
            # 3. 完全フォールバック
            cls._modules[name] = UniversalCommand
            cls._configs[name] = {"module_name": name, "sensor_id": 0x0000, "commands": {}}
    
    @classmethod
    def list_available_modules(cls) -> list:
        """List all available modules"""
        return list(cls._modules.keys())
    
    @classmethod
    def is_module_available(cls, name: str) -> bool:
        """Check if module is available"""
        try:
            cls.get_module_class(name)
            return True
        except Exception:
            return False


class ModuleFactory:
    """
    モジュールファクトリー
    設定駆動による動的モジュール作成
    """
    
    @classmethod
    def create_module(cls, module_name: str, device_id: str) -> UniversalCommand:
        """
        Create module instance from configuration
        
        Args:
            module_name: Name of module to create
            device_id: Device ID as hex string
            
        Returns:
            Module instance
        """
        module_class = ModuleRegistry.get_module_class(module_name)
        config = ModuleRegistry.get_module_config(module_name)
        
        if module_class == UniversalCommand:
            # Universal Command使用
            return UniversalCommand(device_id, config)
        else:
            # 専用実装使用
            return module_class(device_id)
    
    @classmethod
    def create_handler(cls, module_name: str) -> Any:
        """
        Create handler for backward compatibility
        
        Args:
            module_name: Name of module
            
        Returns:
            Handler instance or UniversalHandler
        """
        # 既存Handler実装がある場合はそちらを使用
        try:
            module = importlib.import_module(f"module.{module_name}.{module_name}_handler")
            handler_class = getattr(module, f"{module_name.title()}Handler")
            return handler_class()
        except ImportError:
            # フォールバック: UniversalHandlerを作成
            return UniversalHandler(module_name)


class UniversalHandler:
    """
    既存Handler APIとの互換性を提供するアダプター
    """
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.config = ModuleRegistry.get_module_config(module_name)
    
    def instant_uplink(self, port: str, baud: int, module_id: str):
        """Execute instant uplink with existing API"""
        module = ModuleFactory.create_module(self.module_name, module_id)
        return module.execute_command("instant_uplink", port, baud, module_id=module_id)
    
    def get_parameter(self, port: str, baud: int, sensor_id: str, module_id: str):
        """Execute get parameter with existing API"""
        module = ModuleFactory.create_module(self.module_name, module_id)
        return module.execute_command("get_parameter", port, baud, module_id=module_id, sensor_id=sensor_id)
    
    def set_parameter(self, port: str, baud: int, sensor_id: str, module_id: str, data: str):
        """Execute set parameter with existing API"""
        module = ModuleFactory.create_module(self.module_name, module_id)
        return module.execute_command("set_parameter", port, baud, module_id=module_id, sensor_id=sensor_id, data=data)
    
    def device_restart(self, port: str, baud: int, module_id: str):
        """Execute device restart with existing API"""
        module = ModuleFactory.create_module(self.module_name, module_id)
        return module.execute_command("device_restart", port, baud, module_id=module_id)
    
    def sensor_dfu(self, port: str, baud: int, sensor_id: str, module_id: str, firmware_file: str):
        """Execute sensor DFU with existing API"""
        module = ModuleFactory.create_module(self.module_name, module_id)
        return module.execute_command("sensor_dfu", port, baud, module_id=module_id, sensor_id=sensor_id, firmware_file=firmware_file)


# 既知モジュールの事前登録
def register_known_modules():
    """Register known modules at startup"""
    try:
        from module.illuminance.illuminance_config import get_illuminance_config
        ModuleRegistry.register_module("illuminance", UniversalCommand, get_illuminance_config())
    except ImportError:
        pass
    
    # 他のモジュールも同様に追加


# 初期化時に実行
register_known_modules()
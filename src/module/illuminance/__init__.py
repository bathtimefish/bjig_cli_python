"""
BraveJIG Illuminance Module Package

照度センサーモジュール(BJ-MD-LUX-01)の完全実装
全てのコマンドと機能を統一されたインターフェースで提供

Usage:
    from module.illuminance import IlluminanceModule
    
    module = IlluminanceModule("2468800203400004")
    result = module.get_parameter(send_callback, receive_callback)

Author: BraveJIG CLI Development Team  
Date: 2025-08-10
"""

from .illuminance_module import IlluminanceModule
from .illuminance_parameters import IlluminanceParameters
from .base_illuminance import IlluminanceSensorBase, IlluminanceCommand

# Main exports
__all__ = [
    'IlluminanceModule',
    'IlluminanceParameters', 
    'IlluminanceSensorBase',
    'IlluminanceCommand'
]

# Module metadata
MODULE_INFO = {
    "name": "illuminance",
    "model": "BJ-MD-LUX-01",
    "sensor_id": "0x0121",
    "sensor_chip": "OPT3001 (TEXAS INSTRUMENTS)",
    "commands": [
        "instant_uplink",
        "get_parameter",
        "set_parameter",
        "sensor_dfu",
        "device_restart"
    ]
}
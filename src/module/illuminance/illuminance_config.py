# -*- coding: utf-8 -*-
"""
Illuminance Module Configuration
照度センサーモジュールの宣言的設定
"""

from typing import Dict, Any

# 照度センサーモジュール設定
ILLUMINANCE_MODULE_CONFIG = {
    "module_name": "illuminance",
    "sensor_id": 0x0121,
    "model": "BJ-MD-LUX-01",
    "sensor_chip": "OPT3001 (TEXAS INSTRUMENTS)",
    
    # コマンド設定（動作確認済み）
    "commands": {
        "instant_uplink": {
            "cmd": 0x00,
            "sensor_id": 0x0121,  # 照度センサーID使用
            "timeout": 90.0,
            "has_uplink": True,
            "uplink_sensor_id": 0x0121,
            "description": "即時センサーデータ取得 (INSTANT_UPLINK)"
        },
        "get_parameter": {
            "cmd": 0x0D,
            "sensor_id": 0x0000,  # パラメータ取得時は0x0000使用
            "timeout": 30.0,
            "has_uplink": True,
            "uplink_sensor_id": 0x0000,
            "requires_data": True,
            "data": b'\x00',  # Parameter info acquisition request
            "description": "パラメータ情報取得 (GET_PARAMETER)"
        },
        "set_parameter": {
            "cmd": 0x05,
            "sensor_id": 0x0000,  # パラメータ設定時は0x0000使用
            "timeout": 15.0,
            "has_uplink": False,
            "requires_data": True,
            "description": "パラメータ設定 (SET_PARAMETER)"
        },
        "device_restart": {
            "cmd": 0xFD,
            "sensor_id": 0x0000,  # デバイス再起動時は0x0000使用
            "timeout": 10.0,
            "has_uplink": False,
            "description": "デバイス再起動 (DEVICE_RESTART)"
        },
        "sensor_dfu": {
            "cmd": 0x12,
            "sensor_id": 0x0121,  # センサーDFU時は照度センサーID使用
            "timeout": 30.0,
            "has_uplink": False,
            "requires_data": True,
            "description": "センサーDFU (SENSOR_DFU)"
        }
    },
    
    # データパーサー設定
    "data_parsers": {
        "illuminance_sensor": "parse_illuminance_sensor_data",
        "parameter_info": "parse_parameter_info_data"
    },
    
    # モジュール固有情報
    "module_info": {
        "sensor_type": "Illuminance Sensor",
        "measurement_modes": ["瞬時値", "検知", "サンプリング"],
        "lux_range": "40.0-83865.0 Lux",
        "sampling_rates": ["1Hz", "2Hz"]
    }
}

def get_illuminance_config() -> Dict[str, Any]:
    """Get illuminance module configuration"""
    return ILLUMINANCE_MODULE_CONFIG.copy()
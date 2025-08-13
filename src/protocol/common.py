"""
BraveJIG Protocol Common Definitions

共通の定数、列挙型、ユーティリティ関数を定義

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from enum import IntEnum
from typing import Dict, List, Tuple


class SensorType(IntEnum):
    """Sensor type identifiers from proven test scripts"""
    ILLUMINANCE = 0x0121
    ACCELEROMETER = 0x0122
    TEMPERATURE_HUMIDITY = 0x0123
    BAROMETRIC_PRESSURE = 0x0124
    DISTANCE_RANGING = 0x0125


# Real device IDs from proven test scripts
TEST_DEVICES = [
    (0x2468800203400004, SensorType.ILLUMINANCE, "Illuminance"),
    (0x2468800205400011, SensorType.TEMPERATURE_HUMIDITY, "Temperature/Humidity"),
    (0x2468800206400006, SensorType.BAROMETRIC_PRESSURE, "Barometric Pressure"),
    (0x246880020440000F, SensorType.ACCELEROMETER, "Accelerometer"),
    (0x2468800207400001, SensorType.DISTANCE_RANGING, "Distance/Ranging")
]


def cmd_from_device_index(index: int) -> int:
    """Convert device index to JIG Info CMD value (index + 0x03 for indices 0-99)"""
    if 0 <= index <= 99:
        return 0x03 + index
    else:
        raise ValueError(f"Device index {index} out of range (0-99)")


def scan_mode_cmd(mode: int) -> int:
    """Convert scan mode value to SET_SCAN_MODE CMD"""
    from .jiginfo import JigInfoCommand
    if mode == 0:
        return JigInfoCommand.SET_SCAN_MODE_LONG_RANGE
    elif mode == 1:
        return JigInfoCommand.SET_SCAN_MODE_LEGACY
    else:
        raise ValueError(f"Invalid scan mode: {mode} (0=Long Range, 1=Legacy)")


def interpret_error_reason(reason: int) -> str:
    """Interpret error reason code per specs 5-1-5 and observed real hardware behavior"""
    error_reasons = {
        0x01: "不正なリクエスト",
        0x02: "ダウンリンク処理中", 
        0x03: "Reserved",
        0x04: "Reserved",
        0x05: "Reserved",
        0x06: "指定されたインデックスに Device ID が登録されていない",
        0x07: "Device not found"  # From real hardware behavior, not in specs but observed
    }
    return error_reasons.get(reason, f"Unknown error reason: 0x{reason:02x}")
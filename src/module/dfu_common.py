# -*- coding: utf-8 -*-
"""
Common DFU helpers for sensor modules

- dfuDataLength: total .bin size including last 4B CRC (little-endian)
- Final block: do NOT append extra CRC; send remaining firmware bytes as-is

This utility centralizes the 4-block DFU construction to avoid duplication across modules.
"""

from typing import List, Union
import struct


def _to_device_id_int(device_id: Union[int, str]) -> int:
    if isinstance(device_id, int):
        return device_id
    if isinstance(device_id, str):
        return int(device_id, 16)
    raise ValueError(f"Invalid device_id type: {type(device_id)}")


def build_sensor_dfu_blocks(device_id: Union[int, str], sensor_id: int, firmware_data: bytes) -> List[bytes]:
    """
    Build 4-block DFU transfer packets for sensor modules.

    Packet layout (downlink request):
      [0] protocol(1) = 0x01
      [1] packet_type(1) = 0x00 (downlink request)
      [2:4] data_length(2, LE)
      [4:8] unix_time(4, LE)
      [8:16] device_id(8, LE)
      [16:18] sensor_id(2, LE)
      [18] cmd(1) = 0x12
      [19:21] sequence_no(2, LE)
      [21: ...] data

    Blocks:
      - Seq 0x0000: hardwareID(2) + 0xFF*236
      - Seq 0x0001: dfuDataLength(4, LE) + first 234 bytes of firmware
      - Seq 0x0002..: next 238 bytes chunks (continue)
      - Seq 0xFFFF: remaining bytes (no extra CRC appended)
    """
    from lib.datetime_util import get_current_unix_time

    did = _to_device_id_int(device_id)
    fw_size = len(firmware_data)
    blocks: List[bytes] = []

    # Header block (0x0000)
    unix_time = get_current_unix_time()
    data_payload = struct.pack('<H', 0x0000) + (b'\xFF' * 236)
    packet = struct.pack('<BB', 0x01, 0x00)
    packet += struct.pack('<H', len(data_payload))
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', did)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', 0x12)
    packet += struct.pack('<H', 0x0000)
    packet += data_payload
    blocks.append(packet)

    # Second block (0x0001)
    unix_time = get_current_unix_time()
    first_data = firmware_data[:234]
    data_payload = struct.pack('<L', fw_size) + first_data
    if len(first_data) < 234:
        data_payload += b'\xFF' * (234 - len(first_data))
    packet = struct.pack('<BB', 0x01, 0x00)
    packet += struct.pack('<H', len(data_payload))
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', did)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', 0x12)
    packet += struct.pack('<H', 0x0001)
    packet += data_payload
    blocks.append(packet)

    # Continue blocks (0x0002..)
    data_offset = 234
    seq = 0x0002
    while data_offset < fw_size:
        remaining = fw_size - data_offset
        if remaining <= 238:
            break  # final block covers this
        chunk = firmware_data[data_offset:data_offset + 238]
        unix_time = get_current_unix_time()
        data_payload = chunk
        if len(chunk) < 238:
            data_payload += b'\xFF' * (238 - len(chunk))
        packet = struct.pack('<BB', 0x01, 0x00)
        packet += struct.pack('<H', len(data_payload))
        packet += struct.pack('<L', unix_time)
        packet += struct.pack('<Q', did)
        packet += struct.pack('<H', sensor_id)
        packet += struct.pack('<B', 0x12)
        packet += struct.pack('<H', seq)
        packet += data_payload
        blocks.append(packet)
        data_offset += len(chunk)
        seq += 1
        if seq > 0xFFFE:
            break

    # Final block (0xFFFF)
    unix_time = get_current_unix_time()
    final_payload = b''
    if data_offset < fw_size:
        final_payload += firmware_data[data_offset:]
    packet = struct.pack('<BB', 0x01, 0x00)
    packet += struct.pack('<H', len(final_payload))
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', did)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', 0x12)
    packet += struct.pack('<H', 0xFFFF)
    packet += final_payload
    blocks.append(packet)

    return blocks

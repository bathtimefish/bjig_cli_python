"""
BraveJIG Illuminance Sensor DFU Command

センサーDFU(Device Firmware Update)コマンド実装
仕様書 6-3 センサーDFU要求 (CMD: 0x12 - UPDATE_SENSOR_FIRMWARE)

Complex 4-block transfer process:
1. 先頭ブロック (Sequence No: 0x0000) - DFU開始、hardwareID設定
2. 第2ブロック (Sequence No: 0x0001) - DFUデータ長 + DFUデータ開始
3. 継続ブロック (Sequence No: 0x0002~0xXXXX) - DFUデータ継続
4. 最終ブロック (Sequence No: 0xFFFF) - DFUデータ最終 + CRC

Maximum block size: 238 bytes per block (after 5-byte header)

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import struct
import os
import time
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from ..base_illuminance import IlluminanceSensorBase, IlluminanceCommand


class SensorDfuCommand(IlluminanceSensorBase):
    """
    センサーDFUコマンド実装
    
    4段階ブロック転送による複雑なファームウェア更新プロセス
    仕様書 6-3 に基づく正確な実装
    """
    
    MAX_BLOCK_SIZE = 238  # Maximum data bytes per block (excluding 5-byte header)
    
    def __init__(self, device_id: str):
        """
        Initialize sensor DFU command handler
        
        Args:
            device_id: Target device ID as hex string
        """
        super().__init__(device_id)
        self.command = IlluminanceCommand.SENSOR_DFU
        
        # DFU state tracking
        self._firmware_data: Optional[bytes] = None
        self._firmware_size: int = 0
        self._blocks: List[bytes] = []
        self._current_block: int = 0

    def validate_firmware_file(self, firmware_file: str) -> Dict[str, Any]:
        """
        Validate firmware file for DFU process
        
        Args:
            firmware_file: Path to firmware file
            
        Returns:
            Dict containing validation results
        """
        try:
            firmware_path = Path(firmware_file)
            
            # File existence and basic checks
            if not firmware_path.exists():
                return {"valid": False, "error": f"Firmware file not found: {firmware_file}"}
            
            if not firmware_path.is_file():
                return {"valid": False, "error": f"Path is not a file: {firmware_file}"}
            
            # File size validation
            file_size = firmware_path.stat().st_size
            if file_size == 0:
                return {"valid": False, "error": "Firmware file is empty"}
            
            # Check reasonable size limits (e.g., 1MB max for sensor firmware)
            if file_size > 1024 * 1024:
                return {"valid": False, "error": f"Firmware file too large: {file_size} bytes (max: 1MB)"}
            
            # Calculate expected number of blocks
            # First block: hardwareID + reserve (236 bytes data)
            # Second block: dfuDataLength + dfuData (234 bytes data)
            # Continue blocks: dfuData only (238 bytes data each)
            # Final block: remaining dfuData + CRC (variable + 4 bytes)
            
            remaining_after_second = max(0, file_size - 234)  # After second block
            continue_blocks = remaining_after_second // 238
            final_block_size = remaining_after_second % 238
            total_blocks = 2 + continue_blocks + (1 if final_block_size > 0 or remaining_after_second > 0 else 0)
            
            return {
                "valid": True,
                "file_path": str(firmware_path.absolute()),
                "file_name": firmware_path.name, 
                "file_size": file_size,
                "estimated_blocks": total_blocks,
                "transfer_time_estimate": f"{total_blocks * 2} seconds (approx)"
            }
            
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    def prepare_firmware_blocks(self, firmware_file: str) -> Dict[str, Any]:
        """
        Prepare firmware for 4-block DFU transfer
        
        Args:
            firmware_file: Path to firmware file
            
        Returns:
            Dict containing preparation results
        """
        # Validate firmware first
        validation = self.validate_firmware_file(firmware_file)
        if not validation["valid"]:
            return validation
        
        try:
            # Read firmware data
            with open(firmware_file, 'rb') as f:
                self._firmware_data = f.read()
            
            self._firmware_size = len(self._firmware_data)
            
            # Calculate CRC for firmware
            firmware_crc = self._calculate_crc32(self._firmware_data)
            
            # Create blocks
            self._blocks = []
            
            # Block 1: 先頭ブロック (Sequence No: 0x0000)
            block1 = self._create_header_block()
            self._blocks.append(block1)
            
            # Block 2: 第2ブロック (Sequence No: 0x0001) - DFU data length + first data
            block2 = self._create_second_block()
            self._blocks.append(block2)
            
            # Continue blocks: 第3ブロック以降 (Sequence No: 0x0002~0xXXXX)
            continue_blocks = self._create_continue_blocks()
            self._blocks.extend(continue_blocks)
            
            # Final block: 最終ブロック (Sequence No: 0xFFFF)  
            final_block = self._create_final_block(firmware_crc)
            self._blocks.append(final_block)
            
            result = validation.copy()
            result.update({
                "prepared": True,
                "total_blocks": len(self._blocks),
                "firmware_size": self._firmware_size,
                "firmware_crc": f"0x{firmware_crc:08X}",
                "blocks_ready": True
            })
            
            self.logger.info(
                f"Firmware prepared: {validation['file_name']} "
                f"({self._firmware_size} bytes, {len(self._blocks)} blocks, CRC: 0x{firmware_crc:08X})"
            )
            
            return result
            
        except Exception as e:
            return {"valid": True, "prepared": False, "error": f"Preparation failed: {str(e)}"}

    def execute_sensor_dfu(self,
                          firmware_file: str,
                          send_callback: Callable[[bytes], bool],
                          receive_callback: Callable[[], Optional[bytes]],
                          progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Execute complete sensor DFU process
        
        Args:
            firmware_file: Path to firmware file
            send_callback: Function to send data to router
            receive_callback: Function to receive response
            progress_callback: Optional progress update callback
            
        Returns:
            Dict containing complete DFU execution results
        """
        result = {
            "success": False,
            "command": "sensor_dfu",
            "device_id": f"0x{self.device_id:016X}",
            "sensor_id": f"0x{self.sensor_id:04X}",
            "firmware_file": firmware_file
        }
        
        try:
            # Prepare firmware blocks
            preparation = self.prepare_firmware_blocks(firmware_file)
            if not preparation.get("blocks_ready", False):
                result["error"] = preparation.get("error", "Firmware preparation failed")
                result["preparation_details"] = preparation
                return result
            
            result["preparation"] = preparation
            
            # Execute block transfers
            total_blocks = len(self._blocks)
            successful_blocks = 0
            
            self.logger.info(f"Starting sensor DFU: {total_blocks} blocks to transfer")
            
            for block_index, block_data in enumerate(self._blocks):
                # Debug output for block transmission
                block_type = self._get_block_phase_name(block_index)
                sequence_no = self._get_block_sequence_no(block_index)
                
                self.logger.info(f"Sending {block_type} (Sequence: 0x{sequence_no:04X}): {block_data.hex(' ').upper()}")
                
                # Add debug output with time for block transmission
                self._debug_block_packet_with_time(block_data, f"DFU BLOCK {block_index + 1} REQUEST SENT ({block_type})")
                
                block_result = self._transfer_block(
                    block_index, block_data, send_callback, receive_callback
                )
                
                if not block_result["success"]:
                    result["error"] = f"Block {block_index + 1} transfer failed: {block_result['error']}"
                    result["failed_block"] = block_index + 1
                    result["blocks_completed"] = successful_blocks
                    return result
                
                successful_blocks += 1
                
                # Progress callback
                if progress_callback:
                    progress = {
                        "current_block": block_index + 1,
                        "total_blocks": total_blocks,
                        "progress_percent": ((block_index + 1) / total_blocks) * 100,
                        "blocks_remaining": total_blocks - (block_index + 1),
                        "phase": self._get_block_phase_name(block_index)
                    }
                    progress_callback(progress)
                
                # Brief delay between blocks
                time.sleep(1.0)
            
            # DFU Transfer Complete
            result.update({
                "success": True,
                "blocks_completed": successful_blocks,
                "total_blocks": total_blocks,
                "firmware_size": self._firmware_size,
                "message": f"Sensor DFU completed successfully. Transferred {successful_blocks} blocks.",
                "post_dfu_note": {
                    "automatic_restart": True,
                    "restart_waiting_time": "30-60 seconds",
                    "verification_note": "Use get-parameter command after automatic restart to verify firmware version update",
                    "expected_behavior": "Module automatically restarts with new firmware (no manual restart command needed)"
                }
            })
            
            self.logger.info(f"Sensor DFU completed: {successful_blocks}/{total_blocks} blocks transferred")
            self.logger.info("Module will automatically restart with new firmware. Allow 30-60 seconds for restart completion.")
            
        except Exception as e:
            result["error"] = f"Sensor DFU failed: {str(e)}"
            self.logger.error(f"Sensor DFU error: {e}")
        
        return result

    def _create_header_block(self) -> bytes:
        """Create 先頭ブロック (Sequence No: 0x0000)"""
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        
        # DATA部: hardwareID(2バイト) + reserve(236バイト) = 238バイト
        data_payload = struct.pack('<H', 0x0000)             # hardwareID: 0x0000 固定
        data_payload += b'\xFF' * 236                        # Reserve: 0xFF padding
        
        data_length = len(data_payload)
        
        # Build packet according to spec 6-3
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', self.sensor_id)     # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)               # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0x0000)             # Sequence No: 0x0000
        packet += data_payload                          # DATA: hardwareID + reserve
        
        return packet

    def _create_second_block(self) -> bytes:
        """Create 第2ブロック (Sequence No: 0x0001)"""
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        
        # DATA部: dfuDataLength(4バイト) + dfuDataBody(234バイト) = 238バイト
        # dfuDataLength: CRCを含むファームウェア全体サイズ (リトルエンディアン)
        data_payload = struct.pack('<L', self._firmware_size + 4)  # +4 for CRC
        
        # First 234 bytes of firmware data (ビッグエンディアン)
        first_data = self._firmware_data[:234] if len(self._firmware_data) >= 234 else self._firmware_data
        data_payload += first_data
        
        # Pad if necessary to 234 bytes
        if len(first_data) < 234:
            data_payload += b'\xFF' * (234 - len(first_data))
        
        data_length = len(data_payload)
        
        # Build packet according to spec 6-3
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', self.sensor_id)     # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)               # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0x0001)             # Sequence No: 0x0001
        packet += data_payload                          # DATA: dfuDataLength + dfuDataBody
        
        return packet

    def _create_continue_blocks(self) -> List[bytes]:
        """Create 継続ブロック群 (Sequence No: 0x0002~0xXXXX)"""
        from lib.datetime_util import get_current_unix_time
        
        blocks = []
        data_offset = 234  # Start after second block data (234 bytes)
        sequence_no = 0x0002
        
        while data_offset < self._firmware_size:
            remaining = self._firmware_size - data_offset
            block_data_size = min(238, remaining)
            
            # Don't create continue block if this would be the final block
            # (final block is handled separately)
            if remaining <= 238:
                break
            
            unix_time = get_current_unix_time()
            
            # DATA部: dfuDataBody(238バイト)
            # Extract block data (ビッグエンディアン)
            block_data = self._firmware_data[data_offset:data_offset + block_data_size]
            data_payload = block_data
            
            # Pad if necessary (should always be 238 for continue blocks)
            if len(block_data) < 238:
                data_payload += b'\xFF' * (238 - len(block_data))
            
            data_length = len(data_payload)
            
            # Build packet according to spec 6-3
            packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
            packet += struct.pack('<H', data_length)        # Data length
            packet += struct.pack('<L', unix_time)          # Unix time
            packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
            packet += struct.pack('<H', self.sensor_id)     # SensorID: 0x0121
            packet += struct.pack('<B', 0x12)               # CMD: SENSOR_DFU
            packet += struct.pack('<H', sequence_no)        # Sequence No: 0x0002~0xXXXX
            packet += data_payload                          # DATA: dfuDataBody
            
            blocks.append(packet)
            
            data_offset += block_data_size
            sequence_no += 1
            
            # Prevent infinite loop
            if sequence_no > 0xFFFE:
                break
        
        return blocks

    def _create_final_block(self, firmware_crc: int) -> bytes:
        """Create 最終ブロック (Sequence No: 0xFFFF)"""
        from lib.datetime_util import get_current_unix_time
        
        # Calculate remaining data offset after second block and continue blocks
        data_offset = 234  # After second block (234 bytes)
        continue_block_count = 0
        remaining_after_second = self._firmware_size - 234
        if remaining_after_second > 238:
            continue_block_count = (remaining_after_second - 1) // 238  # Integer division
        data_offset += continue_block_count * 238
        
        unix_time = get_current_unix_time()
        
        # DATA部: remaining dfuDataBody + dfuCrc(4バイト)
        data_payload = b''
        
        # Add remaining firmware data (ビッグエンディアン)
        if data_offset < self._firmware_size:
            remaining_data = self._firmware_data[data_offset:]
            data_payload += remaining_data
        
        # Add CRC (リトルエンディアン)
        data_payload += struct.pack('<L', firmware_crc)      # dfuCrc (リトルエンディアン)
        
        data_length = len(data_payload)
        
        # Build packet according to spec 6-3
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', self.sensor_id)     # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)               # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: 0xFFFF
        packet += data_payload                          # DATA: remaining dfuDataBody + dfuCrc
        
        return packet

    def _transfer_block(self, block_index: int, block_data: bytes,
                       send_callback, receive_callback) -> Dict[str, Any]:
        """Transfer a single DFU block and verify response using base class method"""
        result = {"success": False, "block_index": block_index}
        
        try:
            # Use base class method for consistent response handling
            command_result = self.execute_command_with_response(
                block_data, send_callback, receive_callback, 
                timeout=10.0, command_name=f"dfu_block_{block_index + 1}"
            )
            
            result["response"] = command_result.get("response", {})
            result["block_size"] = len(block_data)
            
            if command_result["success"]:
                result["success"] = True
                result["message"] = f"Block {block_index + 1} transferred successfully"
            else:
                result["error"] = f"Block transfer failed: {command_result.get('error', 'Unknown error')}"
            
        except Exception as e:
            result["error"] = f"Block transfer error: {str(e)}"
        
        return result

    def _get_block_phase_name(self, block_index: int) -> str:
        """Get descriptive name for DFU phase"""
        if block_index == 0:
            return "Header Block (DFU Initiation)"
        elif block_index == 1:
            return "Second Block (Data Length + Initial Data)"
        elif block_index == len(self._blocks) - 1:
            return "Final Block (Remaining Data + CRC)"
        else:
            return f"Continue Block {block_index - 1}"
    
    def _get_block_sequence_no(self, block_index: int) -> int:
        """Get sequence number for block"""
        if block_index == 0:
            return 0x0000
        elif block_index == 1:
            return 0x0001
        elif block_index == len(self._blocks) - 1:
            return 0xFFFF
        else:
            return 0x0002 + (block_index - 2)
    
    def _debug_block_packet_with_time(self, packet_data: bytes, packet_type: str):
        """Debug output for DFU block packets with time conversion"""
        import sys
        import struct
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

    def _calculate_crc32(self, data: bytes) -> int:
        """Calculate CRC32 checksum for firmware data"""
        import zlib
        return zlib.crc32(data) & 0xFFFFFFFF

    def _calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16-CCITT checksum for firmware data"""
        crc = 0xFFFF
        polynomial = 0x1021
        
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc <<= 1
                crc &= 0xFFFF
        
        return crc

    def get_dfu_status_summary(self, dfu_result: Dict[str, Any]) -> str:
        """Format DFU result for display"""
        if dfu_result.get("success", False):
            prep = dfu_result.get("preparation", {})
            lines = [
                f"=== Sensor DFU Successful ===",
                f"Device ID: {dfu_result.get('device_id', 'Unknown')}",
                f"Firmware File: {prep.get('file_name', 'Unknown')}",
                f"Firmware Size: {prep.get('file_size', 'Unknown')} bytes",
                f"Blocks Transferred: {dfu_result.get('blocks_completed', 'Unknown')}/{dfu_result.get('total_blocks', 'Unknown')}",
                f"CRC Checksum: {prep.get('firmware_crc', 'Unknown')}",
                f"",
                f"✅ DFU completed successfully!",
                f"   - Module will automatically restart with new firmware",
                f"   - No manual restart command needed",
                f"   - Wait 30-60 seconds for automatic restart completion"
            ]
        else:
            lines = [
                f"=== Sensor DFU Failed ===",
                f"Device ID: {dfu_result.get('device_id', 'Unknown')}",
                f"Error: {dfu_result.get('error', 'Unknown error')}",
                f"Blocks Completed: {dfu_result.get('blocks_completed', 0)}/{dfu_result.get('total_blocks', 'Unknown')}",
                f"",
                f"❌ DFU failed. Device may require manual recovery:",
                f"   - Power cycle the device",
                f"   - Retry DFU operation",
                f"   - Check firmware file integrity",
                f"   - Ensure stable connection during transfer"
            ]
        
        return "\n".join(lines)
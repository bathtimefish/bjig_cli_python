"""
BraveJIG Router DFU (Device Firmware Update) Command

ルーターファームウェア更新コマンドの実装
BraveJIG仕様書 5-2-3. DFU リクエスト に基づく正確な実装

2フェーズDFUプロセス:
Phase 1: DFU開始リクエスト (Type 0x03)
Phase 2: チャンク化ファームウェア転送 (1024バイト単位)

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

import os
import struct
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import time

from protocol.bjig_protocol import BraveJIGProtocol
from protocol.dfu import DfuRequest, DfuResponse, DfuChunk


class DfuCommand:
    """
    Router Device Firmware Update (DFU) command implementation
    
    Implements the complete 2-phase DFU process according to BraveJIG specification:
    
    Phase 1: DFU Initiation
    - Send DFU Request with total firmware size
    - Receive DFU Response (Result=1 for success)
    
    Phase 2: Chunked Firmware Transfer  
    - Split firmware into 1024-byte chunks (last chunk 1-1024 bytes)
    - Send each chunk as [Packet Size (2byte)] + [DFU Image (1-1024byte)]
    - Continue until entire firmware is transferred
    
    Note: This uses USB Protocol Type 0x03, NOT JIG Info commands (Type 0x01)
    """

    def __init__(self, protocol: BraveJIGProtocol):
        """
        Initialize DFU command handler
        
        Args:
            protocol: BraveJIG protocol instance
        """
        self.protocol = protocol
        self.command_name = "dfu"
        
        # DFU state tracking
        self._firmware_data: Optional[bytes] = None
        self._total_size: int = 0
        self._chunks: List[bytes] = []
        self._current_chunk: int = 0
        
        import logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_firmware_file(self, firmware_file: str) -> Dict[str, Any]:
        """
        Validate firmware file for DFU process
        
        Args:
            firmware_file: Path to firmware file
            
        Returns:
            Dict containing validation results
            
        Raises:
            ValueError: If firmware file is invalid
        """
        try:
            firmware_path = Path(firmware_file)
            
            # File existence check
            if not firmware_path.exists():
                raise ValueError(f"Firmware file not found: {firmware_file}")
            
            if not firmware_path.is_file():
                raise ValueError(f"Path is not a file: {firmware_file}")
            
            # File size validation
            file_size = firmware_path.stat().st_size
            if file_size == 0:
                raise ValueError(f"Firmware file is empty: {firmware_file}")
            
            # Check maximum size (4GB limit due to 4-byte Total Length field)
            max_size = 0xFFFFFFFF
            if file_size > max_size:
                raise ValueError(f"Firmware file too large: {file_size} bytes (max: {max_size})")
            
            # File extension warning (not fatal)
            allowed_extensions = ['.bin', '.hex', '.fw']
            if firmware_path.suffix.lower() not in allowed_extensions:
                self.logger.warning(
                    f"Firmware file extension '{firmware_path.suffix}' may not be supported. "
                    f"Recommended: {allowed_extensions}"
                )
            
            return {
                "valid": True,
                "file_path": str(firmware_path.absolute()),
                "file_name": firmware_path.name,
                "file_size": file_size,
                "file_extension": firmware_path.suffix,
                "max_chunks": (file_size + 1023) // 1024  # ceil(file_size / 1024)
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "file_path": firmware_file
            }

    def prepare_firmware(self, firmware_file: str) -> Dict[str, Any]:
        """
        Prepare firmware data for DFU process
        
        Args:
            firmware_file: Path to firmware file
            
        Returns:
            Dict containing preparation results
        """
        # Validate firmware file
        validation = self.validate_firmware_file(firmware_file)
        if not validation["valid"]:
            return validation
        
        try:
            # Read firmware data
            with open(firmware_file, 'rb') as f:
                self._firmware_data = f.read()
            
            self._total_size = len(self._firmware_data)
            
            # Pre-calculate chunks for transfer
            self._chunks = self.protocol.split_firmware_into_chunks(self._firmware_data)
            self._current_chunk = 0
            
            # Calculate checksum for verification
            checksum = self._calculate_checksum(self._firmware_data)
            
            preparation_result = validation.copy()
            preparation_result.update({
                "prepared": True,
                "total_size": self._total_size,
                "chunk_count": len(self._chunks),
                "checksum": checksum,
                "dfu_ready": True
            })
            
            self.logger.info(
                f"Firmware prepared: {validation['file_name']} "
                f"({self._total_size} bytes, {len(self._chunks)} chunks)"
            )
            
            return preparation_result
            
        except Exception as e:
            return {
                "valid": True,
                "prepared": False,
                "error": f"Failed to prepare firmware: {str(e)}",
                "file_path": firmware_file
            }

    def create_dfu_initiation_request(self) -> bytes:
        """
        Create Phase 1 DFU initiation request
        
        Returns:
            bytes: DFU initiation request packet
            
        Raises:
            RuntimeError: If firmware not prepared
        """
        if self._firmware_data is None or self._total_size == 0:
            raise RuntimeError("Firmware not prepared. Call prepare_firmware() first.")
        
        return self.protocol.create_dfu_request(self._total_size)

    def parse_dfu_initiation_response(self, response_data: bytes) -> Dict[str, Any]:
        """
        Parse Phase 1 DFU initiation response
        
        Args:
            response_data: Raw DFU response bytes
            
        Returns:
            Dict containing parsed response information
        """
        try:
            response = self.protocol.parse_dfu_response(response_data)
            
            result_info = {
                "protocol_version": response.protocol_version,
                "packet_type": response.packet_type,
                "unix_time": response.unix_time,
                "result": response.result,
                "success": response.result == 1,
                "raw_data": response_data.hex()
            }
            
            if response.result == 1:
                result_info.update({
                    "status": "dfu_ready",
                    "message": "Router is ready to receive firmware data",
                    "next_phase": "chunk_transfer"
                })
            else:
                result_info.update({
                    "status": "dfu_rejected",
                    "message": "Router rejected DFU initiation request",
                    "next_phase": "abort"
                })
            
            return result_info
            
        except Exception as e:
            return {
                "success": False,
                "status": "parse_error",
                "error": f"Failed to parse DFU response: {str(e)}",
                "raw_data": response_data.hex()
            }

    def get_next_chunk(self) -> Optional[bytes]:
        """
        Get next firmware chunk for transfer
        
        Returns:
            bytes: Next chunk packet or None if all chunks sent
        """
        if self._current_chunk >= len(self._chunks):
            return None
        
        chunk_data = self._chunks[self._current_chunk]
        self._current_chunk += 1
        
        return chunk_data

    def get_transfer_progress(self) -> Dict[str, Any]:
        """
        Get current transfer progress information
        
        Returns:
            Dict containing progress information
        """
        total_chunks = len(self._chunks)
        
        return {
            "current_chunk": self._current_chunk,
            "total_chunks": total_chunks,
            "chunks_remaining": max(0, total_chunks - self._current_chunk),
            "progress_percent": (self._current_chunk / total_chunks * 100) if total_chunks > 0 else 0,
            "bytes_transferred": sum(len(chunk) - 2 for chunk in self._chunks[:self._current_chunk]),  # -2 for packet size header
            "total_bytes": self._total_size,
            "completed": self._current_chunk >= total_chunks
        }

    def execute_dfu_process(self, firmware_file: str, 
                           send_data_callback: Callable[[bytes], bool],
                           receive_data_callback: Callable[[], Optional[bytes]],
                           progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Execute complete DFU process (both phases)
        
        Args:
            firmware_file: Path to firmware file
            send_data_callback: Function to send data to router
            receive_data_callback: Function to receive data from router  
            progress_callback: Optional progress update callback
            
        Returns:
            Dict containing complete DFU execution results
        """
        result = {
            "success": False,
            "phase": "initialization",
            "firmware_file": firmware_file
        }
        
        try:
            # Prepare firmware
            preparation = self.prepare_firmware(firmware_file)
            if not preparation.get("dfu_ready", False):
                result.update({
                    "phase": "preparation_failed",
                    "error": preparation.get("error", "Firmware preparation failed"),
                    "preparation_details": preparation
                })
                return result
            
            result["preparation"] = preparation
            
            # Phase 1: DFU Initiation
            self.logger.info("Starting DFU Phase 1: Initiation Request")
            result["phase"] = "dfu_initiation"
            
            initiation_request = self.create_dfu_initiation_request()
            if not send_data_callback(initiation_request):
                result.update({
                    "error": "Failed to send DFU initiation request",
                    "phase": "send_failed"
                })
                return result
            
            # Wait for DFU initiation response
            time.sleep(0.5)  # Brief delay for router processing
            initiation_response_data = receive_data_callback()
            
            if not initiation_response_data:
                result.update({
                    "error": "No response received for DFU initiation",
                    "phase": "no_response"
                })
                return result
            
            initiation_response = self.parse_dfu_initiation_response(initiation_response_data)
            result["initiation_response"] = initiation_response
            
            if not initiation_response.get("success", False):
                result.update({
                    "error": f"DFU initiation failed: {initiation_response.get('message', 'Unknown error')}",
                    "phase": "initiation_rejected"
                })
                return result
            
            # Phase 2: Chunk Transfer
            self.logger.info("Starting DFU Phase 2: Chunk Transfer")
            result["phase"] = "chunk_transfer"
            
            transfer_results = []
            chunk_number = 0
            
            while True:
                chunk_data = self.get_next_chunk()
                if chunk_data is None:
                    break  # All chunks sent
                
                chunk_number += 1
                
                # Send chunk
                if not send_data_callback(chunk_data):
                    result.update({
                        "error": f"Failed to send chunk {chunk_number}",
                        "phase": "chunk_send_failed",
                        "failed_chunk": chunk_number
                    })
                    return result
                
                transfer_results.append({
                    "chunk_number": chunk_number,
                    "chunk_size": len(chunk_data) - 2,  # -2 for packet size header
                    "success": True
                })
                
                # Progress callback
                if progress_callback:
                    progress_callback(self.get_transfer_progress())
                
                # Brief delay between chunks (adjust as needed)
                time.sleep(0.01)
            
            # DFU Transfer Complete
            result.update({
                "success": True,
                "phase": "completed",
                "transfer_results": transfer_results,
                "final_progress": self.get_transfer_progress(),
                "message": f"DFU completed successfully. Transferred {len(transfer_results)} chunks."
            })
            
            self.logger.info(f"DFU process completed successfully: {len(transfer_results)} chunks transferred")
            
        except Exception as e:
            result.update({
                "error": f"DFU process failed: {str(e)}",
                "phase": "exception"
            })
            self.logger.error(f"DFU process failed: {e}")
        
        return result

    def _calculate_checksum(self, data: bytes) -> str:
        """
        Calculate checksum for firmware data
        
        Args:
            data: Firmware data bytes
            
        Returns:
            str: Hexadecimal checksum string
        """
        # Simple 32-bit checksum - adjust based on BraveJIG specification if needed
        checksum = sum(data) & 0xFFFFFFFF
        return f"0x{checksum:08x}"

    def reset_state(self):
        """Reset DFU command state for new operation"""
        self._firmware_data = None
        self._total_size = 0
        self._chunks = []
        self._current_chunk = 0
"""
BraveJIG DFU Manager

ルーターのDFU（Device Firmware Update）処理を専門的に担当するクラス。
Phase 1（DFU開始）とPhase 2（チャンク転送）の管理、進捗追跡、エラー監視を提供。

Author: BraveJIG CLI Development Team
Date: 2025-08-02
"""

import os
import struct
import time
import logging
from typing import Optional

from protocol.bjig_protocol import BraveJIGProtocol
from protocol.dfu import create_dfu_request
from .connection_manager import ConnectionManager
from .response_handler import ResponseHandler
from .error_tracker import ErrorTracker
from .command_executor import CommandResult


class DfuManager:
    """
    BraveJIG DFU管理クラス
    
    ルーターファームウェア更新の完全な2フェーズDFUプロセスを管理。
    ファームウェア検証、チャンク転送、進捗追跡、エラー検出を提供する。
    """

    def __init__(self, connection: ConnectionManager, response_handler: ResponseHandler,
                 error_tracker: ErrorTracker, protocol: BraveJIGProtocol, timeout: float = 30.0):
        """
        DFUマネージャーを初期化
        
        Args:
            connection: 接続管理インスタンス
            response_handler: レスポンス処理インスタンス  
            error_tracker: エラー追跡インスタンス
            protocol: 通信プロトコルインスタンス
            timeout: DFUタイムアウト秒
        """
        self.connection = connection
        self.response_handler = response_handler
        self.error_tracker = error_tracker
        self.protocol = protocol
        self.timeout = timeout
        
        self.logger = logging.getLogger(__name__)

    def execute_dfu(self, firmware_file: str) -> CommandResult:
        """
        DFU処理を実行
        
        Args:
            firmware_file: ファームウェアファイルパス
            
        Returns:
            CommandResult: DFU実行結果
        """
        try:
            # ファームウェアファイル検証
            if not os.path.exists(firmware_file):
                return CommandResult(success=False, error=f"Firmware file not found: {firmware_file}")
            
            # ファームウェアデータ読み込み
            with open(firmware_file, 'rb') as f:
                firmware_data = f.read()
            
            self.logger.info(f"Starting DFU process: {len(firmware_data)} bytes firmware")
            
            # Phase 1: DFU開始
            dfu_response = self._initiate_dfu(len(firmware_data))
            if not hasattr(dfu_response, 'result') or dfu_response.result != 0x01:
                return CommandResult(success=False, error="DFU initiation failed")
            
            # Phase 2: チャンク転送
            transfer_result = self._transfer_chunks(firmware_data, dfu_response)
            
            return transfer_result
            
        except Exception as e:
            return CommandResult(success=False, error=f"DFU execution failed: {str(e)}")

    def _initiate_dfu(self, firmware_size: int):
        """
        Phase 1: DFU開始処理
        
        Args:
            firmware_size: ファームウェアサイズ
            
        Returns:
            DFU開始レスポンス
            
        Raises:
            RuntimeError: DFU開始失敗時
        """
        self.logger.info("Phase 1: DFU Initiation Request")
        
        # DFU開始リクエスト作成
        dfu_request = create_dfu_request(firmware_size)
        
        # レスポンス待機用Future登録
        from concurrent.futures import Future
        future = Future()
        self.response_handler.register_future("dfu_response", future)
        
        try:
            # DFU開始リクエスト送信
            if not self.connection.send_data(dfu_request):
                raise RuntimeError("Failed to send DFU initiation request")
            
            # レスポンス待機
            response = future.result(timeout=self.timeout)
            
            self.logger.info(f"DFU initiation response: Result=0x{response.result:02X}")
            
            return response
            
        except Exception as e:
            # エラー時はFutureクリーンアップ
            self.response_handler._response_futures.pop("dfu_response", None)
            raise

    def _transfer_chunks(self, firmware_data: bytes, dfu_response) -> CommandResult:
        """
        Phase 2: チャンク転送処理
        
        Args:
            firmware_data: ファームウェアデータ
            dfu_response: DFU開始レスポンス
            
        Returns:
            CommandResult: 転送結果
        """
        try:
            # DFUエラー追跡開始
            self.error_tracker.start_dfu_tracking()
            
            chunk_size = 1024
            total_chunks = (len(firmware_data) + chunk_size - 1) // chunk_size
            
            self.logger.info(f"Phase 2: Starting chunk transfer - {len(firmware_data)} bytes in {total_chunks} chunks")
            
            # チャンク転送ループ
            for chunk_index in range(total_chunks):
                if not self._send_chunk(firmware_data, chunk_index, chunk_size, total_chunks):
                    return CommandResult(success=False, error=f"Failed to send chunk {chunk_index + 1}")
                
                # チャンク間の待機時間
                time.sleep(0.1)
            
            # 最終レスポンス待機
            self.logger.info("Chunk transfer completed, waiting for final router response...")
            time.sleep(2.0)
            
            # DFUエラー追跡停止・確認
            dfu_errors = self.error_tracker.stop_dfu_tracking()
            
            if dfu_errors:
                error_summary = "; ".join(dfu_errors)
                self.logger.error(f"DFU transfer completed with router errors: {error_summary}")
                return CommandResult(success=False, error=f"DFU failed - Router errors: {error_summary}")
            
            self.logger.info("DFU transfer completed successfully with no errors")
            return CommandResult(success=True, response=dfu_response)
            
        except Exception as e:
            # エラー時はDFU追跡停止
            self.error_tracker.stop_dfu_tracking()
            error_msg = f"DFU transfer failed: {str(e)}"
            self.logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)

    def _send_chunk(self, firmware_data: bytes, chunk_index: int, chunk_size: int, total_chunks: int) -> bool:
        """
        単一チャンクを送信
        
        Args:
            firmware_data: ファームウェアデータ
            chunk_index: チャンクインデックス
            chunk_size: チャンクサイズ
            total_chunks: 総チャンク数
            
        Returns:
            bool: 送信成功時True
        """
        start_offset = chunk_index * chunk_size
        end_offset = min(start_offset + chunk_size, len(firmware_data))
        chunk_data = firmware_data[start_offset:end_offset]
        
        # チャンクパケット作成: [Packet Size (2byte)] + [DFU Image (1-1024byte)]
        chunk_packet = struct.pack('<H', len(chunk_data)) + chunk_data
        
        # 詳細ログ出力
        packet_size_field = struct.unpack('<H', chunk_packet[:2])[0]
        self.logger.info(
            f"Chunk {chunk_index + 1}/{total_chunks}: "
            f"DFU Image={len(chunk_data)}B, Packet Size Field={packet_size_field}, "
            f"Total Packet={len(chunk_packet)}B"
        )
        
        # 最初と最後の数チャンクの詳細データをログ出力
        if chunk_index < 3 or chunk_index >= total_chunks - 3:
            data_preview = chunk_packet[:20].hex(' ').upper()
            if len(chunk_packet) > 20:
                data_preview += "..."
            self.logger.info(f"Chunk {chunk_index + 1} data: {data_preview}")
        
        # チャンク送信
        if not self.connection.send_data(chunk_packet):
            self.logger.error(f"Failed to send chunk {chunk_index + 1}")
            return False
        
        # 進捗報告
        progress = (chunk_index + 1) / total_chunks * 100
        self.logger.info(f"DFU Progress: {progress:.1f}% ({chunk_index + 1}/{total_chunks} chunks)")
        
        return True

    def validate_firmware_file(self, firmware_file: str) -> dict:
        """
        ファームウェアファイルを検証
        
        Args:
            firmware_file: ファームウェアファイルパス
            
        Returns:
            dict: 検証結果
        """
        try:
            if not os.path.exists(firmware_file):
                return {"valid": False, "error": f"File not found: {firmware_file}"}
            
            if not os.path.isfile(firmware_file):
                return {"valid": False, "error": f"Path is not a file: {firmware_file}"}
            
            file_size = os.path.getsize(firmware_file)
            if file_size == 0:
                return {"valid": False, "error": "Firmware file is empty"}
            
            # 最大サイズチェック（4GB制限）
            max_size = 0xFFFFFFFF
            if file_size > max_size:
                return {"valid": False, "error": f"File too large: {file_size} bytes (max: {max_size})"}
            
            # チェックサム計算
            with open(firmware_file, 'rb') as f:
                data = f.read()
                checksum = sum(data) & 0xFFFFFFFF
            
            return {
                "valid": True,
                "file_path": os.path.abspath(firmware_file),
                "file_name": os.path.basename(firmware_file),
                "file_size": file_size,
                "chunk_count": (file_size + 1023) // 1024,
                "checksum": f"0x{checksum:08X}"
            }
            
        except Exception as e:
            return {"valid": False, "error": f"Validation failed: {str(e)}"}

    def get_dfu_status(self) -> dict:
        """
        DFU状態情報を取得
        
        Returns:
            dict: DFU状態情報
        """
        return {
            "dfu_tracking_active": self.error_tracker._dfu_tracking_active,
            "dfu_errors": self.error_tracker.get_dfu_errors(),
            "has_errors": self.error_tracker.has_dfu_errors(),
            "timeout": self.timeout
        }
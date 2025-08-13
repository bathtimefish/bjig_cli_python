"""
BraveJIG Error Tracker

エラー通知の追跡と監視を担当するクラス。
特にDFU処理中のエラー検出とログ記録を提供。

Author: BraveJIG CLI Development Team
Date: 2025-08-02
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from protocol.bjig_protocol import ErrorNotification


@dataclass
class ErrorRecord:
    """エラー記録データクラス"""
    timestamp: datetime
    error_type: str
    packet_type: int
    reason: int
    reason_description: str
    context: str = ""
    raw_data: Optional[bytes] = None


class ErrorTracker:
    """
    BraveJIG エラー追跡・監視クラス
    
    ルーターからのエラー通知を追跡し、特にDFU処理中の
    エラー検出と分析機能を提供する。
    """

    def __init__(self):
        """エラートラッカーを初期化"""
        self._error_records: List[ErrorRecord] = []
        self._dfu_errors: List[str] = []
        self._dfu_tracking_active = False
        
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self):
        """ログ設定を初期化"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def start_dfu_tracking(self):
        """DFU処理のエラー追跡を開始"""
        self._dfu_tracking_active = True
        self._dfu_errors.clear()
        self.logger.info("Started DFU error tracking")

    def stop_dfu_tracking(self) -> List[str]:
        """
        DFU処理のエラー追跡を停止
        
        Returns:
            List[str]: 検出されたDFUエラーのリスト
        """
        self._dfu_tracking_active = False
        dfu_errors = self._dfu_errors.copy()
        self.logger.info(f"Stopped DFU error tracking. Detected {len(dfu_errors)} errors")
        return dfu_errors

    def track_error(self, error: ErrorNotification, context: str = ""):
        """
        エラー通知を追跡・記録
        
        Args:
            error: エラー通知オブジェクト
            context: エラーが発生したコンテキスト情報
        """
        from protocol.common import interpret_error_reason
        
        reason_desc = interpret_error_reason(error.reason)
        
        # エラー記録を作成
        error_record = ErrorRecord(
            timestamp=datetime.now(),
            error_type=self._get_error_type(error.packet_type),
            packet_type=error.packet_type,
            reason=error.reason,
            reason_description=reason_desc,
            context=context,
            raw_data=getattr(error, 'raw_data', None)
        )
        
        self._error_records.append(error_record)
        
        # DFU追跡中の場合は専用リストにも追加
        if self._dfu_tracking_active:
            dfu_error_msg = f"DFU Error - Type: 0x{error.packet_type:02X}, Reason: {reason_desc}"
            self._dfu_errors.append(dfu_error_msg)
            self.logger.error(f"DFU ERROR DETECTED: {dfu_error_msg}")
        
        # 一般的なエラーログ
        self.logger.error(
            f"{error_record.error_type} - Reason: {reason_desc} "
            f"(Context: {context})" if context else f"{error_record.error_type} - Reason: {reason_desc}"
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """
        エラーサマリーを取得
        
        Returns:
            Dict[str, Any]: エラー統計とサマリー情報
        """
        total_errors = len(self._error_records)
        
        if total_errors == 0:
            return {
                "total_errors": 0,
                "error_types": {},
                "recent_errors": [],
                "dfu_errors": len(self._dfu_errors)
            }
        
        # エラータイプ別統計
        error_type_counts = {}
        for record in self._error_records:
            error_type_counts[record.error_type] = error_type_counts.get(record.error_type, 0) + 1
        
        # 最近のエラー（最大5件）
        recent_errors = []
        for record in self._error_records[-5:]:
            recent_errors.append({
                "timestamp": record.timestamp.isoformat(),
                "error_type": record.error_type,
                "reason": record.reason_description,
                "context": record.context
            })
        
        return {
            "total_errors": total_errors,
            "error_types": error_type_counts,
            "recent_errors": recent_errors,
            "dfu_errors": len(self._dfu_errors),
            "dfu_tracking_active": self._dfu_tracking_active
        }

    def get_dfu_errors(self) -> List[str]:
        """
        DFU処理中に検出されたエラーのリストを取得
        
        Returns:
            List[str]: DFUエラーメッセージのリスト
        """
        return self._dfu_errors.copy()

    def has_dfu_errors(self) -> bool:
        """
        DFU処理中にエラーが検出されたかチェック
        
        Returns:
            bool: DFUエラーが検出された場合True
        """
        return len(self._dfu_errors) > 0

    def clear_errors(self):
        """全てのエラー記録をクリア"""
        self._error_records.clear()
        self._dfu_errors.clear()
        self.logger.info("Cleared all error records")

    def get_errors_by_type(self, error_type: str) -> List[ErrorRecord]:
        """
        特定のタイプのエラー記録を取得
        
        Args:
            error_type: エラータイプ
            
        Returns:
            List[ErrorRecord]: 該当するエラー記録のリスト
        """
        return [record for record in self._error_records if record.error_type == error_type]

    def _get_error_type(self, packet_type: int) -> str:
        """
        パケットタイプからエラータイプ名を取得
        
        Args:
            packet_type: パケットタイプ
            
        Returns:
            str: エラータイプ名
        """
        error_type_map = {
            0x04: "Legacy Error",
            0xFF: "Router Error Notification"
        }
        
        return error_type_map.get(packet_type, f"Unknown Error (Type: 0x{packet_type:02X})")

    def __len__(self) -> int:
        """エラー記録の総数を取得"""
        return len(self._error_records)
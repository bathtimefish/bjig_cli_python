"""
BraveJIG Response Handler

受信レスポンスの解析と振り分けを担当するクラス。
JIG Info、DFU、エラー通知、Uplinkなど各種レスポンスの適切な処理を提供。

Author: BraveJIG CLI Development Team
Date: 2025-08-02
"""

import logging
from typing import Dict, Any, Callable, Optional
from concurrent.futures import Future

from protocol.bjig_protocol import (
    BraveJIGProtocol, JigInfoResponse, DownlinkResponse, 
    UplinkNotification, ErrorNotification
)
from .error_tracker import ErrorTracker


class ResponseHandler:
    """
    BraveJIG レスポンスハンドラークラス
    
    受信したレスポンスデータの解析、パケットタイプ別の振り分け、
    および適切な処理の実行を担当する。
    """

    def __init__(self, protocol: BraveJIGProtocol, error_tracker: ErrorTracker):
        """
        レスポンスハンドラーを初期化
        
        Args:
            protocol: BraveJIG通信プロトコルインスタンス
            error_tracker: エラー追跡インスタンス
        """
        self.protocol = protocol
        self.error_tracker = error_tracker
        self._response_futures: Dict[str, Future] = {}
        
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

    def handle_response(self, data: bytes):
        """
        受信レスポンスデータを処理
        
        パケットタイプを判定し、適切なハンドラーメソッドに振り分ける。
        
        Args:
            data: 受信した生バイトデータ
        """
        try:
            # パケットタイプを事前確認
            if len(data) < 2:
                self.logger.warning(f"Received packet too short: {len(data)} bytes")
                return
            
            packet_type = data[1]
            
            # Uplink通知は別処理（コマンドレスポンスではない）
            if packet_type == 0x00:
                self._handle_uplink_notification(data)
                return
            
            # コマンドレスポンス処理（JIG Info、Downlink、DFU、Error）
            if packet_type in [0x01, 0x02, 0x03, 0x04, 0xFF]:
                self._handle_command_response(data, packet_type)
            else:
                self.logger.warning(f"Unknown packet type: 0x{packet_type:02X}")
                self.logger.debug(f"Raw data: {data.hex(' ').upper()}")
                
        except Exception as e:
            self.logger.error(f"Error in response handler: {e}")
            self.logger.debug(f"Raw data: {data.hex(' ').upper()}")

    def _handle_command_response(self, data: bytes, packet_type: int):
        """
        コマンドレスポンスを処理
        
        Args:
            data: レスポンスデータ
            packet_type: パケットタイプ
        """
        try:
            self.logger.debug(f"Parsing packet type 0x{packet_type:02X}, length {len(data)} bytes")
            self.logger.debug(f"Raw data: {data.hex(' ').upper()}")
            
            response = self.protocol.parse_response(data)
            self.logger.debug(f"Received command response: {response}")
            
            # レスポンスタイプ別処理
            if isinstance(response, JigInfoResponse):
                self._handle_jig_info_response(response)
            elif isinstance(response, DownlinkResponse):
                self._handle_downlink_response(response)
            elif hasattr(response, 'packet_type') and response.packet_type == 0x03:
                self._handle_dfu_response(response)
            elif isinstance(response, ErrorNotification):
                self._handle_error_notification(response)
            else:
                self.logger.warning(f"Unexpected response type: {type(response)}")
                
        except Exception as e:
            self.logger.error(f"Error parsing command response: {e}")
            self.logger.debug(f"Raw data: {data.hex(' ').upper()}")

    def _handle_jig_info_response(self, response: JigInfoResponse):
        """
        JIG Info レスポンスを処理
        
        Args:
            response: JIG Info レスポンスオブジェクト
        """
        response_key = f"jig_info_{response.cmd}"
        self._complete_future(response_key, response)

    def _handle_downlink_response(self, response: DownlinkResponse):
        """
        Downlink レスポンスを処理
        
        Args:
            response: Downlink レスポンスオブジェクト
        """
        response_key = f"downlink_{response.device_id}_{response.sensor_id}"
        self._complete_future(response_key, response)

    def _handle_dfu_response(self, response):
        """
        DFU レスポンスを処理
        
        Args:
            response: DFU レスポンスオブジェクト
        """
        self._complete_future("dfu_response", response)

    def _handle_uplink_notification(self, data: bytes):
        """
        Uplink 通知を処理（連続的なモジュールからのデータ）
        
        Args:
            data: Uplink通知データ
        """
        try:
            response = self.protocol.parse_response(data)
            if isinstance(response, UplinkNotification):
                device_info = self.protocol.get_device_info(response.device_id)
                device_desc = device_info[1] if device_info else "Unknown"
                
                # デバッグレベルでログ出力（ノイズ減らすため）
                self.logger.debug(
                    f"Uplink from {device_desc} (0x{response.device_id:016x}): "
                    f"Sensor 0x{response.sensor_id:04x}, "
                    f"Data: {response.data.hex()}"
                )
            else:
                self.logger.debug(f"Parsed uplink notification: {response}")
        except Exception as e:
            self.logger.debug(f"Uplink notification parse failed (continuing): {e}")

    def _handle_error_notification(self, error: ErrorNotification):
        """
        エラー通知を処理
        
        Args:
            error: エラー通知オブジェクト
        """
        # エラートラッカーに記録
        self.error_tracker.track_error(error, "Response Handler")
        
        # Type 0xFF エラーの場合はJSON出力も
        if error.packet_type == 0xFF:
            print(error.to_json())
            
            # 最新のFutureをエラーで完了
            if self._response_futures:
                key = next(iter(self._response_futures))
                future = self._response_futures.pop(key)
                if not future.cancelled():
                    reason_desc = self.error_tracker._get_error_type(error.packet_type)
                    future.set_exception(Exception(f"Router error: {reason_desc}"))
        else:
            # Legacy error (packet type 0x04)
            if hasattr(error, 'cmd'):
                key = f"jig_info_{error.cmd}"
                if key in self._response_futures:
                    future = self._response_futures.pop(key)
                    if not future.cancelled():
                        from protocol.common import interpret_error_reason
                        reason_desc = interpret_error_reason(error.reason)
                        future.set_exception(Exception(reason_desc))

    def _complete_future(self, key: str, response: Any):
        """
        待機中のFutureを完了
        
        Args:
            key: レスポンスキー
            response: レスポンスデータ
        """
        if key in self._response_futures:
            future = self._response_futures.pop(key)
            if not future.cancelled():
                future.set_result(response)

    def register_future(self, key: str, future: Future):
        """
        レスポンス待機用Futureを登録
        
        Args:
            key: レスポンスキー
            future: 待機用Future
        """
        self._response_futures[key] = future

    def cancel_all_futures(self):
        """全ての待機中Futureをキャンセル"""
        for future in self._response_futures.values():
            future.cancel()
        self._response_futures.clear()

    def get_pending_futures_count(self) -> int:
        """待機中Futureの数を取得"""
        return len(self._response_futures)
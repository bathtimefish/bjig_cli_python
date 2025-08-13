"""
BraveJIG Illuminance Sensor Instant Uplink Executor

照度センサー即時Uplink要求コマンドの実行フロー実装
get-parameter executorと同じアーキテクチャパターンに統一

Author: BraveJIG CLI Development Team
Date: 2025-08-13
"""

import json
import time
import logging
import struct
from typing import Dict, List, Any, Optional

from core.connection_manager import ConnectionManager
from ..core.instant_uplink import InstantUplinkCommand
from protocol.downlink import UplinkNotification


class InstantUplinkExecutor:
    """
    照度センサー即時Uplink要求コマンドの実行フロー管理
    
    接続管理、デバッグ出力、JSON整形などの実行ロジックを担当
    get-parameterと同じアーキテクチャパターンで実装
    """
    
    def __init__(self):
        """Initialize executor"""
        self.suppress_logging()
    
    def suppress_logging(self):
        """ログレベルを抑制（JSONのみ出力するため）"""
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger("AsyncSerialMonitor").setLevel(logging.CRITICAL)
        logging.getLogger("core.connection_manager").setLevel(logging.CRITICAL)
    
    def debug_packet_with_time(self, packet_data: bytes, packet_type: str):
        """共通のデバッグ出力関数 - パケットとunix timeを表示"""
        import sys
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
    
    def execute(self, port: str, baud: int, module_id: str):
        """
        照度センサー即時Uplink要求コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート  
            module_id: モジュールID (16桁hex)
        """
        try:
            # 実際にルーターに即時Uplink要求を送信
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                error_output = {"error": "Failed to connect to router", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            try:
                # InstantUplinkCommandを作成
                instant_uplink_cmd = InstantUplinkCommand(module_id)
                
                # 受信したデータを保存する変数
                received_data = {"sensor_uplink": None, "downlink_response": None}
                
                def data_callback(data: bytes):
                    """非同期モニタリングからのデータ収集"""
                    if len(data) >= 18:
                        packet_type = data[1]
                        
                        if packet_type == 0x01:  # Downlink response
                            # instant-uplink リクエストのレスポンスかチェック
                            if len(data) >= 19:
                                cmd_byte = data[18] if len(data) > 18 else 0
                                if cmd_byte == 0x00:  # INSTANT_UPLINK
                                    # DEBUG: Downlink response受信
                                    self.debug_packet_with_time(data, "DOWNLINK RESPONSE RECEIVED")
                                    received_data["downlink_response"] = data
                        elif packet_type == 0x00:  # Uplink notification
                            # 照度センサーデータのuplinkかチェック
                            sensor_id_in_packet = struct.unpack('<H', data[16:18])[0]
                            if sensor_id_in_packet == 0x0121:  # 照度センサー
                                # デバイスIDもチェック
                                uplink_device_id = struct.unpack('<Q', data[8:16])[0]
                                uplink_device_id_hex = f"{uplink_device_id:016X}"
                                if uplink_device_id_hex.upper() == module_id.upper():
                                    # DEBUG: Sensor uplink受信
                                    self.debug_packet_with_time(data, "SENSOR UPLINK RECEIVED")
                                    received_data["sensor_uplink"] = data
                
                # データコールバックを設定
                conn.set_data_callback(data_callback)
                
                # 即時Uplink要求を送信
                request_packet = instant_uplink_cmd.create_instant_uplink_request()
                
                # DEBUG: Downlink request送信
                self.debug_packet_with_time(request_packet, "DOWNLINK REQUEST SENT")
                
                if not conn.send_data(request_packet):
                    error_output = {"error": "Failed to send instant uplink request", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                # まずDownlinkレスポンスを待機（10秒）
                start_time = time.time()
                downlink_timeout = 10.0
                
                while (time.time() - start_time) < downlink_timeout:
                    if received_data["downlink_response"]:
                        break
                    time.sleep(0.1)
                
                if not received_data["downlink_response"]:
                    error_output = {"error": "No downlink response received within 10 seconds", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                # 90秒間センサーuplinkを監視
                start_time = time.time()
                uplink_timeout = 90.0
                
                while (time.time() - start_time) < uplink_timeout:
                    if received_data["sensor_uplink"]:
                        # センサーuplinkを解析 - UplinkNotificationとセンサーデータ両方を含む
                        sensor_uplink = received_data["sensor_uplink"]
                        
                        # 1. UplinkNotificationクラスで共通ヘッダを解析
                        try:
                            uplink_notification = UplinkNotification.from_bytes(sensor_uplink)
                            uplink_dict = uplink_notification.to_dict()
                            
                            # 2. センサーデータも解析
                            sensor_data = instant_uplink_cmd.parse_sensor_uplink(sensor_uplink)
                            if sensor_data and "error" not in sensor_data:
                                # 3. 純粋なデータのみを含むJSONを構築（success属性なし）
                                uplink_output = {
                                    "uplink_header": uplink_dict,
                                    "sensor_data": sensor_data
                                }
                                print(json.dumps(uplink_output, indent=2, ensure_ascii=False))
                                return
                            else:
                                # センサーデータ解析失敗でもヘッダ情報は出力
                                uplink_output = {
                                    "uplink_header": uplink_dict,
                                    "sensor_data_error": sensor_data.get("error", "Failed to parse sensor data") if sensor_data else "No sensor data"
                                }
                                print(json.dumps(uplink_output, indent=2, ensure_ascii=False))
                                return
                                
                        except Exception as e:
                            error_output = {"error": f"Failed to parse uplink notification: {str(e)}", "success": False}
                            print(json.dumps(error_output, ensure_ascii=False))
                            return
                    
                    time.sleep(0.1)
                
                # タイムアウト
                error_output = {"error": f"No sensor uplink received within {uplink_timeout} seconds", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                
            finally:
                # 接続を確実に切断
                conn.disconnect()
                
        except Exception as e:
            error_output = {"error": str(e), "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
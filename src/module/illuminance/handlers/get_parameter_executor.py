"""
BraveJIG Illuminance Sensor Get Parameter Executor

照度センサーパラメータ取得コマンドの実行フロー実装
main.pyから抽出した細分化されたexecutor

Author: BraveJIG CLI Development Team
Date: 2025-08-12
"""

import json
import time
import logging
import struct
from typing import Dict, List, Any, Optional

from core.connection_manager import ConnectionManager
from ..core.get_parameter import GetParameterCommand
from protocol.downlink import UplinkNotification


class GetParameterExecutor:
    """
    照度センサーパラメータ取得コマンドの実行フロー管理
    
    接続管理、デバッグ出力、JSON整形などの実行ロジックを担当
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
    
    def execute(self, port: str, baud: int, sensor_id: str, module_id: str):
        """
        照度センサーパラメータ取得コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート  
            sensor_id: センサーID (0121)
            module_id: モジュールID (16桁hex)
        """
        try:
            # 実際にルーターからパラメータを取得
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                error_output = {"error": "Failed to connect to router", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            try:
                # GetParameterCommandを作成
                get_param_cmd = GetParameterCommand(module_id)
                
                # 受信したデータを保存する変数
                received_data = {"parameter_uplink": None, "downlink_response": None}
                
                def data_callback(data: bytes):
                    """非同期モニタリングからのデータ収集"""
                    if len(data) >= 18:
                        packet_type = data[1]
                        
                        if packet_type == 0x01:  # Downlink response
                            # パラメータ取得リクエストのレスポンスかチェック
                            if len(data) >= 19:
                                cmd_byte = data[18] if len(data) > 18 else 0
                                if cmd_byte == 0x0D:  # GET_DEVICE_SETTING
                                    # DEBUG: Downlink response受信
                                    self.debug_packet_with_time(data, "DOWNLINK RESPONSE RECEIVED")
                                    received_data["downlink_response"] = data
                        elif packet_type == 0x00:  # Uplink notification
                            sensor_id_in_packet = struct.unpack('<H', data[16:18])[0]
                            if sensor_id_in_packet == 0x0000:  # Parameter info uplink
                                # デバイスIDもチェック
                                uplink_device_id = struct.unpack('<Q', data[8:16])[0]
                                uplink_device_id_hex = f"{uplink_device_id:016X}"
                                if uplink_device_id_hex.upper() == module_id.upper():
                                    # DEBUG: Parameter uplink受信
                                    self.debug_packet_with_time(data, "PARAMETER UPLINK RECEIVED")
                                    received_data["parameter_uplink"] = data
                
                # データコールバックを設定
                conn.set_data_callback(data_callback)
                
                # パラメータ取得リクエストを送信
                request_packet = get_param_cmd.create_get_parameter_request()
                
                # DEBUG: Downlink request送信
                self.debug_packet_with_time(request_packet, "DOWNLINK REQUEST SENT")
                
                if not conn.send_data(request_packet):
                    error_output = {"error": "Failed to send parameter request", "success": False}
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
                
                # 90秒間パラメータuplinksを監視
                start_time = time.time()
                uplink_timeout = 90.0
                
                while (time.time() - start_time) < uplink_timeout:
                    if received_data["parameter_uplink"]:
                        # パラメータuplinksを解析 - UplinkNotificationと実際のパラメータ両方を含む
                        parameter_uplink = received_data["parameter_uplink"]
                        
                        # 1. UplinkNotificationクラスで共通ヘッダを解析
                        try:
                            uplink_notification = UplinkNotification.from_bytes(parameter_uplink)
                            uplink_dict = uplink_notification.to_dict()
                            
                            # 2. パラメータ情報も解析
                            result = get_param_cmd.parse_parameter_uplink(parameter_uplink)
                            if result and "error" not in result and "_parameters_object" in result:
                                params_obj = result["_parameters_object"]
                                params_dict = params_obj.to_dict()
                                
                                # メタデータ（fw_version, connected_sensor_id）も追加
                                if "fw_version" in result:
                                    params_dict["fw_version"] = result["fw_version"]
                                if "connected_sensor_id" in result:
                                    params_dict["connected_sensor_id"] = result["connected_sensor_id"]
                                
                                # 3. 両方を含む完全なJSONを構築
                                complete_output = {
                                    "uplink_header": uplink_dict,
                                    "parameter_info": params_dict,
                                    "success": True
                                }
                                print(json.dumps(complete_output, indent=2, ensure_ascii=False))
                                return
                            else:
                                # パラメータ解析失敗でもヘッダ情報は出力
                                complete_output = {
                                    "uplink_header": uplink_dict,
                                    "parameter_error": result.get("error", "Failed to parse parameter data"),
                                    "success": False
                                }
                                print(json.dumps(complete_output, indent=2, ensure_ascii=False))
                                return
                                
                        except Exception as e:
                            error_output = {"error": f"Failed to parse uplink notification: {str(e)}", "success": False}
                            print(json.dumps(error_output, ensure_ascii=False))
                            return
                    
                    time.sleep(0.1)
                
                # タイムアウト
                error_output = {"error": f"No parameter uplink received within {uplink_timeout} seconds", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                
            finally:
                # 接続を確実に切断
                conn.disconnect()
                
        except Exception as e:
            error_output = {"error": str(e), "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
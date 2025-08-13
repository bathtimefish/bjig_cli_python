"""
BraveJIG Illuminance Sensor Set Parameter Executor

照度センサーパラメータ設定コマンドの実行フロー実装
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
from ..core.set_parameter import SetParameterCommand
from ..core.get_parameter import GetParameterCommand


class SetParameterExecutor:
    """
    照度センサーパラメータ設定コマンドの実行フロー管理
    
    GET→UPDATE→SET→OUTPUT フローを含む実行ロジックを担当
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
    
    def execute(self, port: str, baud: int, sensor_id: str, module_id: str, value: str):
        """
        照度センサーパラメータ設定コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート  
            sensor_id: センサーID (0121)
            module_id: モジュールID (16桁hex)
            value: 更新パラメータのJSON文字列
        """
        try:
            # 実際にルーターからパラメータを設定
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                error_output = {"error": "Failed to connect to router", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            try:
                # SetParameterCommandを作成
                set_param_cmd = SetParameterCommand(module_id)
                
                # 受信したデータを保存する変数  
                received_data = {"downlink_response": None, "uplink_notifications": []}
                
                def data_callback(data: bytes):
                    """非同期モニタリングからのデータ収集"""
                    if len(data) >= 18:
                        packet_type = data[1]
                        
                        if packet_type == 0x01:  # Downlink response
                            # パラメータ設定リクエストのレスポンスかチェック
                            if len(data) >= 19:
                                cmd_byte = data[18] if len(data) > 18 else 0
                                if cmd_byte == 0x05:  # SET_REGISTER
                                    # DEBUG: Downlink response受信
                                    self.debug_packet_with_time(data, "SET PARAMETER RESPONSE RECEIVED")
                                    received_data["downlink_response"] = data
                        elif packet_type == 0x00:  # Uplink notification
                            # すべてのuplink通知を収集（パラメータ確認用）
                            self.debug_packet_with_time(data, "UPLINK NOTIFICATION RECEIVED")
                            received_data["uplink_notifications"].append(data)
                
                # STEP 1: まずget-parameterで現在の設定を取得
                get_param_cmd = GetParameterCommand(module_id)
                
                # パラメータ取得リクエストを送信
                request_packet = get_param_cmd.create_get_parameter_request()
                self.debug_packet_with_time(request_packet, "GET PARAMETER REQUEST SENT")
                
                if not conn.send_data(request_packet):
                    error_output = {"error": "Failed to send parameter request", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                # Get parameter用のresponse/uplinkを待機
                get_received_data = {"parameter_uplink": None, "downlink_response": None}
                
                def get_data_callback(data: bytes):
                    """Get parameter用データ収集"""
                    if len(data) >= 18:
                        packet_type = data[1]
                        if packet_type == 0x01:  # Downlink response
                            if len(data) >= 19:
                                cmd_byte = data[18] if len(data) > 18 else 0
                                if cmd_byte == 0x0D:  # GET_DEVICE_SETTING
                                    self.debug_packet_with_time(data, "GET PARAMETER RESPONSE RECEIVED")
                                    get_received_data["downlink_response"] = data
                        elif packet_type == 0x00:  # Uplink notification
                            sensor_id_in_packet = struct.unpack('<H', data[16:18])[0]
                            if sensor_id_in_packet == 0x0000:  # Parameter info uplink
                                uplink_device_id = struct.unpack('<Q', data[8:16])[0]
                                uplink_device_id_hex = f"{uplink_device_id:016X}"
                                if uplink_device_id_hex.upper() == module_id.upper():
                                    self.debug_packet_with_time(data, "GET PARAMETER UPLINK RECEIVED")
                                    get_received_data["parameter_uplink"] = data
                
                # Get parameter用のコールバックに切り替え
                conn.set_data_callback(get_data_callback)
                
                # Get parameterのレスポンス/uplink待機
                start_time = time.time()
                timeout_get = 90.0
                
                while (time.time() - start_time) < timeout_get:
                    if get_received_data["parameter_uplink"]:
                        # パラメータを解析
                        result = get_param_cmd.parse_parameter_uplink(get_received_data["parameter_uplink"])
                        if result and "error" not in result and "_parameters_object" in result:
                            current_params_obj = result["_parameters_object"]
                            break
                        else:
                            error_output = {"error": "Failed to parse current parameters", "success": False}
                            print(json.dumps(error_output, ensure_ascii=False))
                            return
                    time.sleep(0.1)
                else:
                    error_output = {"error": "Failed to get current parameters - timeout", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                # STEP 2: パラメータ更新
                try:
                    update_dict = json.loads(value)
                except json.JSONDecodeError as e:
                    error_output = {"error": f"Invalid JSON update data: {str(e)}", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                updated_params_obj = current_params_obj.update_from_dict(update_dict)
                validation_result = updated_params_obj.validate()
                if not validation_result["valid"]:
                    error_output = {"error": f"Parameter validation failed: {validation_result['error']}", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                    
                # STEP 3: Set parameter用のコールバックに戻す
                conn.set_data_callback(data_callback)
                
                # Set parameterリクエストを送信
                set_request_packet = set_param_cmd.create_set_parameter_request(updated_params_obj)
                self.debug_packet_with_time(set_request_packet, "SET PARAMETER REQUEST SENT")
                
                if not conn.send_data(set_request_packet):
                    error_output = {"error": "Failed to send parameter setting request", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                # Set parameterのレスポンス待機
                start_time = time.time()
                timeout_set = 30.0
                
                while (time.time() - start_time) < timeout_set:
                    if received_data["downlink_response"]:
                        # Set parameterのレスポンスにもデバッグ出力を追加（data_callbackで既に出力済みだが、ここでも確認用）
                        # 成功レスポンスを構築
                        result = {
                            "success": True,
                            "command": "set_parameter",
                            "device_id": f"0x{int(module_id, 16):016X}",
                            "current_parameters": current_params_obj.to_dict(),
                            "updated_parameters": updated_params_obj.to_dict(),
                            "parameter_changes": list(update_dict.keys())
                        }
                        break
                    time.sleep(0.1)
                else:
                    error_output = {"error": "Set parameter request timeout", "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    return
                
                if result.get("success", False):
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    error_output = {"error": result.get("error", "Parameter setting failed"), "success": False}
                    print(json.dumps(error_output, ensure_ascii=False))
                    
            finally:
                # 接続を確実に切断
                conn.disconnect()
                
        except Exception as e:
            error_output = {"error": str(e), "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
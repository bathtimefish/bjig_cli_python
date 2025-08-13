"""
BraveJIG Illuminance Sensor Device Restart Executor

照度センサーデバイス再起動コマンドの実行フロー実装
main.pyから抽出した細分化されたexecutor

Author: BraveJIG CLI Development Team
Date: 2025-08-12
"""

import json
import time
import logging
from typing import Dict, Any

from core.connection_manager import ConnectionManager
from ..core.device_restart import DeviceRestartCommand


class DeviceRestartExecutor:
    """
    照度センサーデバイス再起動コマンドの実行フロー管理
    
    接続管理、デバッグ出力、JSON整形などの実行ロジックを担当
    """
    
    def __init__(self):
        """Initialize executor"""
        pass
    
    def debug_packet_with_time(self, packet_data: bytes, packet_type: str):
        """共通のデバッグ出力関数 - パケットとunix timeを表示"""
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
    
    def execute(self, port: str, baud: int, module_id: str):
        """
        照度センサーデバイス再起動コマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート
            module_id: モジュールID (16桁hex)
        """
        # モジュールIDを正規化
        module_id = module_id.replace("-", "").replace(":", "").upper()
        if len(module_id) != 16:
            error_output = {"error": f"Invalid module ID format: {module_id}. Expected 16 hex digits.", "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
            return

        try:
            # 接続確立
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                error_output = {"error": f"Failed to connect to {port}", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return

            # DeviceRestartCommandを作成
            restart_cmd = DeviceRestartCommand(module_id)
            
            # 受信したデータを保存する変数
            received_data = {"downlink_response": None}
            
            def data_callback(data: bytes):
                """非同期モニタリングからのデータ収集"""
                if len(data) >= 18:
                    packet_type = data[1]
                    
                    if packet_type == 0x01:  # Downlink response
                        # デバイス再起動リクエストのレスポンスかチェック
                        if len(data) >= 19:
                            cmd_byte = data[18] if len(data) > 18 else 0
                            if cmd_byte == 0xFD:  # DEVICE_RESTART
                                # DEBUG: Downlink response受信
                                self.debug_packet_with_time(data, "DEVICE RESTART RESPONSE RECEIVED")
                                received_data["downlink_response"] = data
            
            # データコールバックを設定
            conn.set_data_callback(data_callback)
            
            # Device restartリクエストを送信
            restart_request_packet = restart_cmd.create_device_restart_request()
            self.debug_packet_with_time(restart_request_packet, "DEVICE RESTART REQUEST SENT")
            
            if not conn.send_data(restart_request_packet):
                error_output = {"error": "Failed to send device restart request", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            # Downlink responseを待機
            start_time = time.time()
            timeout = 10.0
            
            while (time.time() - start_time) < timeout:
                if received_data["downlink_response"]:
                    break
                time.sleep(0.1)
            
            if not received_data["downlink_response"]:
                error_output = {"error": f"No response received within {timeout} seconds", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return
            
            # Downlink responseを解析
            response_info = restart_cmd.parse_downlink_response(received_data["downlink_response"])
            
            # JSON出力用にresponse_objを除去
            response_info_clean = {k: v for k, v in response_info.items() if k != "response_obj"}
            
            if response_info["success"]:
                # 成功時の出力
                output = {
                    "success": True,
                    "command": "device_restart",
                    "device_id": f"0x{restart_cmd.device_id:016X}",
                    "sensor_id": f"0x{restart_cmd.sensor_id:04X}",
                    "message": "Device restart command completed successfully",
                    "downlink_response": response_info_clean,
                    "restart_info": {
                        "restart_initiated": True,
                        "note": "Device restart command accepted"
                    }
                }
            else:
                # 失敗時の出力
                output = {
                    "success": False,
                    "command": "device_restart", 
                    "device_id": f"0x{restart_cmd.device_id:016X}",
                    "sensor_id": f"0x{restart_cmd.sensor_id:04X}",
                    "error": f"Restart command failed: {response_info['result_desc']}",
                    "downlink_response": response_info_clean
                }
            
            print(json.dumps(output, ensure_ascii=False, indent=2))
            
        except Exception as e:
            error_output = {"error": f"Device restart execution failed: {str(e)}", "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
        finally:
            if 'conn' in locals():
                conn.disconnect()
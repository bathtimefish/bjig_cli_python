"""
BraveJIG Illuminance Sensor DFU Executor

照度センサーDFU (Device Firmware Update) コマンドの実行フロー実装
main.pyから抽出した細分化されたexecutor

Author: BraveJIG CLI Development Team
Date: 2025-08-12
"""

import json
import os
import sys
import struct
from typing import Dict, Any

from core.connection_manager import ConnectionManager
from ..core.sensor_dfu import SensorDfuCommand


class SensorDfuExecutor:
    """
    照度センサーDFUコマンドの実行フロー管理
    
    接続管理、デバッグ出力、JSON整形、プログレス管理などの実行ロジックを担当
    """
    
    def __init__(self):
        """Initialize executor"""
        pass
    
    def debug_packet_with_time(self, packet_data: bytes, packet_type: str):
        """共通のデバッグ出力関数 - パケットとunix timeを表示"""
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
    
    def execute(self, port: str, baud: int, sensor_id: str, module_id: str, firmware_file: str):
        """
        照度センサーDFUコマンド実行
        
        Args:
            port: シリアルポート
            baud: ボーレート  
            sensor_id: センサーID (0121)
            module_id: モジュールID (16桁hex)
            firmware_file: ファームウェアファイルパス
        """
        # モジュールIDを正規化
        module_id = module_id.replace("-", "").replace(":", "").upper()
        if len(module_id) != 16:
            error_output = {"error": f"Invalid module ID format: {module_id}. Expected 16 hex digits.", "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
            return
        
        # ファームウェアファイル存在チェック
        if not os.path.exists(firmware_file):
            error_output = {"error": f"Firmware file not found: {firmware_file}", "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
            return

        try:
            # 接続確立
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                error_output = {"error": f"Failed to connect to {port}", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
                return

            # SensorDfuCommandを作成
            dfu_cmd = SensorDfuCommand(module_id)
            
            # 受信したデータを保存する変数
            received_data = {"downlink_response": None}
            
            def data_callback(data: bytes):
                """非同期モニタリングからのデータ収集"""
                if len(data) >= 18:
                    packet_type = data[1]
                    
                    if packet_type == 0x01:  # Downlink response
                        # センサーDFUリクエストのレスポンスかチェック
                        if len(data) >= 19:
                            cmd_byte = data[18] if len(data) > 18 else 0
                            if cmd_byte == 0x12:  # SENSOR_DFU
                                # DEBUG: Downlink response受信
                                self.debug_packet_with_time(data, "SENSOR DFU RESPONSE RECEIVED")
                                received_data["downlink_response"] = data
            
            # データコールバックを設定
            conn.set_data_callback(data_callback)
            
            def send_callback(data: bytes) -> bool:
                return conn.send_data(data)
            
            def receive_callback() -> bytes:
                response = received_data["downlink_response"]
                received_data["downlink_response"] = None  # Clear after reading
                return response
            
            def progress_callback(progress: dict):
                """プログレス情報をデバッグ出力"""
                progress_msg = f"DFU Progress: Block {progress['current_block']}/{progress['total_blocks']} ({progress['progress_percent']:.1f}%) - {progress['phase']}"
                print(f"DEBUG: {progress_msg}", file=sys.stderr)
            
            # センサーDFU実行（長時間処理のため特別なタイムアウト設定）
            try:
                dfu_result = dfu_cmd.execute_sensor_dfu(
                    firmware_file=firmware_file,
                    send_callback=send_callback, 
                    receive_callback=receive_callback,
                    progress_callback=progress_callback
                )
                
                # JSON出力用にresponse_objを除去
                if "preparation" in dfu_result:
                    prep_clean = {k: v for k, v in dfu_result["preparation"].items() if k != "response_obj"}
                    dfu_result["preparation"] = prep_clean
                
                # DFU成功時の自動再起動に関するガイダンス
                if dfu_result.get("success", False):
                    print(f"DEBUG: DFU completed successfully. Module will automatically restart with new firmware.", file=sys.stderr)
                    print(f"DEBUG: Wait 30-60 seconds for automatic restart completion, then verify firmware version:", file=sys.stderr)
                    print(f"DEBUG: python src/main.py --port {port} --baud {baud} module get-parameter --module-id \"{module_id}\"", file=sys.stderr)
                
                print(json.dumps(dfu_result, ensure_ascii=False, indent=2))
                
            except Exception as dfu_error:
                error_output = {"error": f"DFU execution failed: {str(dfu_error)}", "success": False}
                print(json.dumps(error_output, ensure_ascii=False))
            
        except Exception as e:
            error_output = {"error": f"Sensor DFU execution failed: {str(e)}", "success": False}
            print(json.dumps(error_output, ensure_ascii=False))
        finally:
            if 'conn' in locals():
                conn.disconnect()
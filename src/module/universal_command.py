# -*- coding: utf-8 -*-
"""
Universal Command System
設定駆動による統一コマンド実行システム
"""

import time
import json
import struct
from typing import Dict, Any, Callable, Optional, List
from core.connection_manager import ConnectionManager
from module.base_module import ModuleBase
from module.mixins import UplinkWaitMixin, ParameterMixin, ExecutorMixin


class UniversalCommand(ModuleBase, UplinkWaitMixin, ParameterMixin, ExecutorMixin):
    """
    設定駆動による統一コマンド実行クラス
    動作確認済みのロジックをベースに設計
    """
    
    def __init__(self, device_id: str, module_config: Dict[str, Any]):
        """
        Initialize universal command
        
        Args:
            device_id: Device ID as hex string
            module_config: Module configuration dict
        """
        super().__init__(device_id, module_config["sensor_id"], module_config["module_name"])
        self.config = module_config
    
    def execute_command(self, 
                       command_name: str,
                       port: str,
                       baud: int,
                       **kwargs) -> Dict[str, Any]:
        """
        Execute command using configuration-driven approach
        
        Args:
            command_name: Name of command to execute
            port: Serial port
            baud: Baudrate
            **kwargs: Command-specific parameters
            
        Returns:
            Dict containing execution results
        """
        if command_name not in self.config["commands"]:
            return {
                "success": False,
                "error": f"Unknown command: {command_name}"
            }
        
        cmd_config = self.config["commands"][command_name]
        
        try:
            # 接続管理
            conn = ConnectionManager(port, baud)
            if not conn.connect():
                return {"success": False, "error": "Failed to connect to router"}
            
            try:
                # リクエスト作成
                if command_name == "instant_uplink":
                    return self._execute_instant_uplink(conn, cmd_config, **kwargs)
                elif command_name == "get_parameter":
                    return self._execute_get_parameter(conn, cmd_config, **kwargs)
                elif command_name == "set_parameter":
                    return self._execute_set_parameter(conn, cmd_config, **kwargs)
                elif command_name == "device_restart":
                    return self._execute_device_restart(conn, cmd_config, **kwargs)
                elif command_name == "sensor_dfu":
                    return self._execute_sensor_dfu(conn, cmd_config, **kwargs)
                else:
                    return {"success": False, "error": f"Handler not implemented for: {command_name}"}
                    
            finally:
                conn.disconnect()
                
        except Exception as e:
            return {"success": False, "error": f"Command execution failed: {str(e)}"}
    
    def _execute_instant_uplink(self, conn: ConnectionManager, cmd_config: Dict, **kwargs) -> Dict[str, Any]:
        """Execute instant uplink command (動作確認済みパターン)"""
        self.suppress_logging()
        
        # データコールバック設定
        received_data = {"sensor_uplink": None, "downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                
                if packet_type == 0x01:  # Downlink response
                    if len(data) >= 19:
                        cmd_byte = data[18] if len(data) > 18 else 0
                        if cmd_byte == 0x00:  # INSTANT_UPLINK
                            self.debug_packet_with_time(data, "DOWNLINK RESPONSE RECEIVED")
                            received_data["downlink_response"] = data
                elif packet_type == 0x00:  # Uplink notification
                    sensor_id_in_packet = struct.unpack('<H', data[16:18])[0]
                    if sensor_id_in_packet == cmd_config["uplink_sensor_id"]:
                        uplink_device_id = struct.unpack('<Q', data[8:16])[0]
                        uplink_device_id_hex = f"{uplink_device_id:016X}"
                        module_id = kwargs.get("module_id", f"{self.device_id:016X}")
                        if uplink_device_id_hex.upper() == module_id.upper():
                            self.debug_packet_with_time(data, "SENSOR UPLINK RECEIVED")
                            received_data["sensor_uplink"] = data
        
        conn.set_data_callback(data_callback)
        
        # リクエスト送信
        request_packet = self.create_instant_uplink_request()
        self.debug_packet_with_time(request_packet, "DOWNLINK REQUEST SENT")
        
        if not conn.send_data(request_packet):
            return {"success": False, "error": "Failed to send instant uplink request"}
        
        # Downlinkレスポンス待機
        start_time = time.time()
        while (time.time() - start_time) < 10.0:
            if received_data["downlink_response"]:
                break
            time.sleep(0.1)
        
        if not received_data["downlink_response"]:
            return {"success": False, "error": "No downlink response received within 10 seconds"}
        
        # Uplink待機
        start_time = time.time()
        while (time.time() - start_time) < cmd_config["timeout"]:
            if received_data["sensor_uplink"]:
                # センサーデータ解析
                sensor_uplink = received_data["sensor_uplink"]
                try:
                    from protocol.downlink import UplinkNotification
                    uplink_notification = UplinkNotification.from_bytes(sensor_uplink)
                    uplink_dict = uplink_notification.to_dict()
                    
                    # センサーデータ解析（動作確認済みパターン）
                    sensor_data = self._parse_illuminance_sensor_data(sensor_uplink)
                    if sensor_data and "error" not in sensor_data:
                        return {
                            "uplink_header": uplink_dict,
                            "sensor_data": sensor_data
                        }
                    else:
                        return {
                            "uplink_header": uplink_dict,
                            "sensor_data_error": sensor_data.get("error", "Failed to parse sensor data") if sensor_data else "No sensor data"
                        }
                        
                except Exception as e:
                    return {"success": False, "error": f"Failed to parse uplink notification: {str(e)}"}
            
            time.sleep(0.1)
        
        return {"success": False, "error": f"No sensor uplink received within {cmd_config['timeout']} seconds"}
    
    def _execute_get_parameter(self, conn: ConnectionManager, cmd_config: Dict, **kwargs) -> Dict[str, Any]:
        """Execute get parameter command (動作確認済みパターン)"""
        # データコールバック設定（parameter uplink用）
        received_data = {"parameter_uplink": None, "downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                
                if packet_type == 0x01:  # Downlink response
                    received_data["downlink_response"] = data
                elif packet_type == 0x00:  # Uplink notification
                    sensor_id_in_packet = struct.unpack('<H', data[16:18])[0]
                    if sensor_id_in_packet == 0x0000:  # Parameter info
                        uplink_device_id = struct.unpack('<Q', data[8:16])[0]
                        uplink_device_id_hex = f"{uplink_device_id:016X}"
                        module_id = kwargs.get("module_id", f"{self.device_id:016X}")
                        if uplink_device_id_hex.upper() == module_id.upper():
                            received_data["parameter_uplink"] = data
        
        conn.set_data_callback(data_callback)
        
        # リクエスト送信
        request_packet = self.create_get_parameter_request()
        
        if not conn.send_data(request_packet):
            return {"success": False, "error": "Failed to send get parameter request"}
        
        # Downlinkレスポンス待機
        start_time = time.time()
        while (time.time() - start_time) < 10.0:
            if received_data["downlink_response"]:
                break
            time.sleep(0.1)
        
        if not received_data["downlink_response"]:
            return {"success": False, "error": "No downlink response received"}
        
        # Parameter uplink待機
        start_time = time.time()
        while (time.time() - start_time) < cmd_config["timeout"]:
            if received_data["parameter_uplink"]:
                # パラメータ情報解析
                parameter_data = self._parse_parameter_info_data(received_data["parameter_uplink"])
                return {
                    "success": True,
                    "parameter_info": parameter_data
                }
            
            time.sleep(0.1)
        
        return {"success": False, "error": f"No parameter uplink received within {cmd_config['timeout']} seconds"}
    
    def _execute_set_parameter(self, conn: ConnectionManager, cmd_config: Dict, **kwargs) -> Dict[str, Any]:
        """Execute set parameter command"""
        # パラメータデータが必要
        param_data = kwargs.get("data")
        if not param_data:
            return {"success": False, "error": "Parameter data required for set_parameter"}
        
        # パラメータデータが文字列の場合は、IlluminanceParametersで処理
        if isinstance(param_data, str):
            try:
                import json
                from module.illuminance.illuminance_parameters import IlluminanceParameters
                
                update_dict = json.loads(param_data)
                
                # 現在のパラメータを取得（必要な手順）
                current_result = self._execute_get_parameter(conn, self.config["commands"]["get_parameter"], **kwargs)
                if not current_result.get("success"):
                    return {"success": False, "error": "Failed to get current parameters before update"}
                
                param_info = current_result["parameter_info"]
                
                # 現在のパラメータから IlluminanceParameters オブジェクトを再構築
                current_params = IlluminanceParameters()
                for key in ['timezone', 'ble_mode', 'tx_power', 'advertise_interval', 
                           'sensor_uplink_interval', 'sensor_read_mode', 'sampling',
                           'hysteresis_high', 'hysteresis_low']:
                    if key in param_info:
                        value = param_info[key]
                        # 辞書形式の場合は value キーから値を取得
                        if isinstance(value, dict) and 'value' in value:
                            value = value['value']
                        setattr(current_params, key, value)
                
                # 更新を適用
                updated_params = current_params.update_from_dict(update_dict)
                param_bytes = updated_params.serialize_to_bytes()
                
            except Exception as e:
                return {"success": False, "error": f"Parameter processing failed: {str(e)}"}
        else:
            param_bytes = param_data
        
        # リクエスト送信
        request_packet = self.create_set_parameter_request(param_bytes)
        
        if not conn.send_data(request_packet):
            return {"success": False, "error": "Failed to send set parameter request"}
        
        # レスポンス待機
        received_data = {"downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                if packet_type == 0x01:  # Downlink response
                    received_data["downlink_response"] = data
        
        conn.set_data_callback(data_callback)
        
        # Downlinkレスポンス待機
        import time
        start_time = time.time()
        while (time.time() - start_time) < cmd_config["timeout"]:
            if received_data["downlink_response"]:
                return {
                    "success": True,
                    "message": "Parameter update request sent successfully",
                    "updated_parameters": update_dict
                }
            time.sleep(0.1)
        
        return {"success": False, "error": "No response received for set parameter"}
    
    def _execute_device_restart(self, conn: ConnectionManager, cmd_config: Dict, **kwargs) -> Dict[str, Any]:
        """Execute device restart command"""
        request_packet = self.create_device_restart_request()
        
        print(f"DEBUG: RESTART REQUEST SENT: {request_packet.hex(' ').upper()}")
        
        if not conn.send_data(request_packet):
            return {"success": False, "error": "Failed to send device restart request"}
        
        # レスポンス待機
        received_data = {"downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                print(f"DEBUG: RESTART RESPONSE RECEIVED: {data.hex(' ').upper()}")
                
                # 最優先: CMD=0xFDの成功レスポンス即座検出
                if packet_type == 0x01 and len(data) >= 20:
                    payload = data[16:]
                    if len(payload) >= 4 and payload[2] == 0xFD and payload[3] == 0x00:
                        print("DEBUG: RESTART SUCCESS RESPONSE DETECTED!")
                        received_data["downlink_response"] = data
                        print("DEBUG: RESTART COMMAND RESPONSE DETECTED!")
                        return
                
                # packet_type == 0x00 もdownlinkレスポンスとして検証
                if packet_type == 0x01 or packet_type == 0x00:
                    # レスポンス内容を詳細に解析
                    try:
                        import struct
                        protocol_version = data[0]
                        packet_type_val = data[1]
                        data_length = struct.unpack('<H', data[2:4])[0]
                        unix_time = struct.unpack('<L', data[4:8])[0]
                        device_id = struct.unpack('<Q', data[8:16])[0]
                        
                        print(f"DEBUG: RESTART RESPONSE - Protocol: {protocol_version:02X}, Type: {packet_type_val:02X}, Length: {data_length}")
                        print(f"DEBUG: RESTART RESPONSE - Device ID: {device_id:016X}")
                        
                        # パケットの構造をさらに詳しく解析
                        if len(data) > 16:
                            payload_start = 16
                            payload = data[payload_start:]
                            print(f"DEBUG: RESTART RESPONSE - Payload: {payload.hex(' ').upper()}")
                            
                            # CMD応答かどうかチェック
                            if len(payload) >= 6:
                                sensor_id = struct.unpack('<H', payload[0:2])[0]
                                cmd_type = payload[2]
                                status = payload[3] if len(payload) > 3 else None
                                status_str = f"{status:02X}" if status is not None else "N/A"
                                print(f"DEBUG: RESTART RESPONSE - Sensor ID: {sensor_id:04X}, CMD: {cmd_type:02X}, Status: {status_str}")
                                
                                # device_restart コマンドの応答 (CMD=0xFD) かチェック
                                if cmd_type == 0xFD:
                                    received_data["downlink_response"] = data
                                    print("DEBUG: RESTART COMMAND RESPONSE DETECTED!")
                                    
                    except Exception as e:
                        print(f"DEBUG: RESTART RESPONSE PARSE ERROR: {e}")
        
        conn.set_data_callback(data_callback)
        
        # Downlinkレスポンス待機
        import time
        start_time = time.time()
        while (time.time() - start_time) < cmd_config["timeout"]:
            if received_data["downlink_response"]:
                return {
                    "success": True,
                    "message": "Device restart request sent successfully and response received",
                    "response_data": received_data["downlink_response"].hex(' ').upper()
                }
            time.sleep(0.1)
        
        # レスポンス待機
        received_data = {"downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                print(f"DEBUG: RESTART RESPONSE RECEIVED: {data.hex(' ').upper()}")
                
                # 最優先: CMD=0xFDの成功レスポンス即座検出
                if packet_type == 0x01 and len(data) >= 20:
                    payload = data[16:]
                    if len(payload) >= 4 and payload[2] == 0xFD and payload[3] == 0x00:
                        print("DEBUG: RESTART SUCCESS RESPONSE DETECTED!")
                        received_data["downlink_response"] = data
                        print("DEBUG: RESTART COMMAND RESPONSE DETECTED!")
                        return
                
                # packet_type == 0x00 もdownlinkレスポンスとして検証
                if packet_type == 0x01 or packet_type == 0x00:
                    # レスポンス内容を詳細に解析
                    try:
                        import struct
                        protocol_version = data[0]
                        packet_type_val = data[1]
                        data_length = struct.unpack('<H', data[2:4])[0]
                        unix_time = struct.unpack('<L', data[4:8])[0]
                        device_id = struct.unpack('<Q', data[8:16])[0]
                        
                        print(f"DEBUG: RESTART RESPONSE - Protocol: {protocol_version:02X}, Type: {packet_type_val:02X}, Length: {data_length}")
                        print(f"DEBUG: RESTART RESPONSE - Device ID: {device_id:016X}")
                        
                        # パケットの構造をさらに詳しく解析
                        if len(data) > 16:
                            payload_start = 16
                            payload = data[payload_start:]
                            print(f"DEBUG: RESTART RESPONSE - Payload: {payload.hex(' ').upper()}")
                            
                            # CMD応答かどうかチェック
                            if len(payload) >= 6:
                                sensor_id = struct.unpack('<H', payload[0:2])[0]
                                cmd_type = payload[2]
                                status = payload[3] if len(payload) > 3 else None
                                status_str = f"{status:02X}" if status is not None else "N/A"
                                print(f"DEBUG: RESTART RESPONSE - Sensor ID: {sensor_id:04X}, CMD: {cmd_type:02X}, Status: {status_str}")
                                
                                # device_restart コマンドの応答 (CMD=0xFD) かチェック
                                if cmd_type == 0xFD:
                                    received_data["downlink_response"] = data
                                    print("DEBUG: RESTART COMMAND RESPONSE DETECTED!")
                                    
                    except Exception as e:
                        print(f"DEBUG: RESTART RESPONSE PARSE ERROR: {e}")
        
        conn.set_data_callback(data_callback)
        
        # Downlinkレスポンス待機
        import time
        start_time = time.time()
        while (time.time() - start_time) < cmd_config["timeout"]:
            if received_data["downlink_response"]:
                return {
                    "success": True,
                    "message": "Device restart request sent successfully and response received",
                    "response_data": received_data["downlink_response"].hex(' ').upper()
                }
            time.sleep(0.1)
        
        return {"success": False, "error": "No response received for device restart"}

    def _execute_sensor_dfu(self, conn: ConnectionManager, cmd_config: Dict, **kwargs) -> Dict[str, Any]:
        """Execute sensor DFU command with proper 4-block transfer process"""
        firmware_file = kwargs.get("firmware_file")
        if not firmware_file:
            return {"success": False, "error": "Firmware file required for sensor DFU"}
        
        # ファームウェアファイルの存在確認
        import os
        if not os.path.exists(firmware_file):
            return {"success": False, "error": f"Firmware file not found: {firmware_file}"}
        
        # ファームウェアファイル読み込み
        try:
            with open(firmware_file, 'rb') as f:
                firmware_data = f.read()
            print(f"DEBUG: SENSOR DFU - Loaded firmware file: {firmware_file} ({len(firmware_data)} bytes)")
        except Exception as e:
            return {"success": False, "error": f"Failed to read firmware file: {str(e)}"}
        
        # Create DFU blocks using legacy logic
        try:
            blocks = self._create_dfu_blocks(firmware_data)
            print(f"DEBUG: SENSOR DFU - Created {len(blocks)} blocks for transfer")
        except Exception as e:
            return {"success": False, "error": f"Failed to create DFU blocks: {str(e)}"}
        
        # Execute 4-block transfer process
        total_blocks = len(blocks)
        successful_blocks = 0
        received_data = {"downlink_response": None}
        
        def data_callback(data: bytes):
            if len(data) >= 18:
                packet_type = data[1]
                print(f"DEBUG: SENSOR DFU RESPONSE RECEIVED: {data.hex(' ').upper()}")
                
                # sensor DFU成功レスポンスを検出
                if packet_type == 0x01 and len(data) >= 20:
                    payload = data[16:]
                    if len(payload) >= 4 and payload[2] == 0x12:
                        print(f"DEBUG: SENSOR DFU SUCCESS RESPONSE DETECTED (Status: {payload[3]:02X})!")
                        received_data["downlink_response"] = data
                        print("DEBUG: SENSOR DFU COMMAND RESPONSE DETECTED!")
                        return
        
        conn.set_data_callback(data_callback)
        
        # Transfer each block
        for block_index, block_data in enumerate(blocks):
            block_type = self._get_block_phase_name(block_index, total_blocks)
            sequence_no = self._get_block_sequence_no(block_index, total_blocks)
            
            print(f"DEBUG: SENSOR DFU - Sending {block_type} (Seq: 0x{sequence_no:04X})")
            print(f"DEBUG: SENSOR DFU BLOCK {block_index + 1} REQUEST SENT: {block_data.hex(' ').upper()}")
            
            # Reset response flag
            received_data["downlink_response"] = None
            
            # Send block
            if not conn.send_data(block_data):
                return {
                    "success": False, 
                    "error": f"Failed to send block {block_index + 1}/{total_blocks}",
                    "blocks_completed": successful_blocks
                }
            
            # Wait for response
            import time
            start_time = time.time()
            timeout = 15.0  # 15 seconds per block
            
            while (time.time() - start_time) < timeout:
                if received_data["downlink_response"]:
                    break
                time.sleep(0.1)
            
            if not received_data["downlink_response"]:
                return {
                    "success": False,
                    "error": f"No response received for block {block_index + 1}/{total_blocks}",
                    "blocks_completed": successful_blocks
                }
            
            successful_blocks += 1
            print(f"DEBUG: SENSOR DFU - Block {block_index + 1}/{total_blocks} completed successfully")
            
            # Brief delay between blocks
            time.sleep(1.0)
        
        return {
            "success": True,
            "message": "Sensor DFU completed successfully",
            "firmware_file": firmware_file,
            "firmware_size": len(firmware_data),
            "blocks_completed": successful_blocks,
            "total_blocks": total_blocks,
            "post_dfu_note": "Module will automatically restart with new firmware. Allow 30-60 seconds for restart completion."
        }

    def _create_dfu_blocks(self, firmware_data: bytes) -> List[bytes]:
        """Create 4-block DFU transfer packets based on legacy implementation"""
        blocks = []
        firmware_size = len(firmware_data)
        firmware_crc = self._calculate_crc32(firmware_data)
        
        # Block 1: 先頭ブロック (Sequence No: 0x0000) - Header block
        blocks.append(self._create_header_block())
        
        # Block 2: 第2ブロック (Sequence No: 0x0001) - Data length + first data
        blocks.append(self._create_second_block(firmware_data, firmware_size))
        
        # Continue blocks: 継続ブロック (Sequence No: 0x0002~0xXXXX)
        continue_blocks = self._create_continue_blocks(firmware_data)
        blocks.extend(continue_blocks)
        
        # Final block: 最終ブロック (Sequence No: 0xFFFF) - Final data + CRC
        blocks.append(self._create_final_block(firmware_data, firmware_crc))
        
        return blocks
    
    def _create_header_block(self) -> bytes:
        """Create 先頭ブロック (Sequence No: 0x0000)"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        device_id_int = self.device_id if isinstance(self.device_id, int) else int(self.device_id, 16)
        
        # DATA部: hardwareID(2バイト) + reserve(236バイト) = 238バイト
        data_payload = struct.pack('<H', 0x0000)  # hardwareID: 0x0000 固定
        data_payload += b'\xFF' * 236             # Reserve: 0xFF padding
        
        data_length = len(data_payload)
        
        # Build packet according to spec 6-3
        packet = struct.pack('<BB', 0x01, 0x00)     # Protocol version, Packet type
        packet += struct.pack('<H', data_length)    # Data length
        packet += struct.pack('<L', unix_time)      # Unix time
        packet += struct.pack('<Q', device_id_int)  # Device ID
        packet += struct.pack('<H', 0x0121)         # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)           # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0x0000)         # Sequence No: 0x0000
        packet += data_payload                      # DATA: hardwareID + reserve
        
        return packet
    
    def _create_second_block(self, firmware_data: bytes, firmware_size: int) -> bytes:
        """Create 第2ブロック (Sequence No: 0x0001)"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        unix_time = get_current_unix_time()
        device_id_int = self.device_id if isinstance(self.device_id, int) else int(self.device_id, 16)
        
        # DATA部: dfuDataLength(4バイト) + dfuDataBody(234バイト) = 238バイト
        data_payload = struct.pack('<L', firmware_size + 4)  # +4 for CRC
        
        # First 234 bytes of firmware data
        first_data = firmware_data[:234] if len(firmware_data) >= 234 else firmware_data
        data_payload += first_data
        
        # Pad if necessary to 234 bytes
        if len(first_data) < 234:
            data_payload += b'\xFF' * (234 - len(first_data))
        
        data_length = len(data_payload)
        
        # Build packet
        packet = struct.pack('<BB', 0x01, 0x00)     # Protocol version, Packet type
        packet += struct.pack('<H', data_length)    # Data length
        packet += struct.pack('<L', unix_time)      # Unix time
        packet += struct.pack('<Q', device_id_int)  # Device ID
        packet += struct.pack('<H', 0x0121)         # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)           # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0x0001)         # Sequence No: 0x0001
        packet += data_payload                      # DATA: dfuDataLength + dfuDataBody
        
        return packet
    
    def _create_continue_blocks(self, firmware_data: bytes) -> List[bytes]:
        """Create 継続ブロック群 (Sequence No: 0x0002~0xXXXX)"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        blocks = []
        data_offset = 234  # Start after second block data (234 bytes)
        sequence_no = 0x0002
        firmware_size = len(firmware_data)
        device_id_int = self.device_id if isinstance(self.device_id, int) else int(self.device_id, 16)
        
        while data_offset < firmware_size:
            remaining = firmware_size - data_offset
            
            # Don't create continue block if this would be the final block
            if remaining <= 238:
                break
                
            block_data_size = min(238, remaining)
            unix_time = get_current_unix_time()
            
            # DATA部: dfuDataBody(238バイト)
            block_data = firmware_data[data_offset:data_offset + block_data_size]
            data_payload = block_data
            
            # Pad if necessary (should always be 238 for continue blocks)
            if len(block_data) < 238:
                data_payload += b'\xFF' * (238 - len(block_data))
            
            data_length = len(data_payload)
            
            # Build packet
            packet = struct.pack('<BB', 0x01, 0x00)     # Protocol version, Packet type
            packet += struct.pack('<H', data_length)    # Data length
            packet += struct.pack('<L', unix_time)      # Unix time
            packet += struct.pack('<Q', device_id_int)  # Device ID
            packet += struct.pack('<H', 0x0121)         # SensorID: 0x0121
            packet += struct.pack('<B', 0x12)           # CMD: SENSOR_DFU
            packet += struct.pack('<H', sequence_no)    # Sequence No: 0x0002~0xXXXX
            packet += data_payload                      # DATA: dfuDataBody
            
            blocks.append(packet)
            
            data_offset += block_data_size
            sequence_no += 1
            
            # Prevent infinite loop
            if sequence_no > 0xFFFE:
                break
        
        return blocks
    
    def _create_final_block(self, firmware_data: bytes, firmware_crc: int) -> bytes:
        """Create 最終ブロック (Sequence No: 0xFFFF)"""
        from lib.datetime_util import get_current_unix_time
        import struct
        
        # Calculate remaining data offset after second block and continue blocks
        data_offset = 234  # After second block (234 bytes)
        firmware_size = len(firmware_data)
        remaining_after_second = firmware_size - 234
        
        if remaining_after_second > 238:
            continue_block_count = (remaining_after_second - 1) // 238
            data_offset += continue_block_count * 238
        
        unix_time = get_current_unix_time()
        device_id_int = self.device_id if isinstance(self.device_id, int) else int(self.device_id, 16)
        
        # DATA部: remaining dfuDataBody + dfuCrc(4バイト)
        data_payload = b''
        
        # Add remaining firmware data
        if data_offset < firmware_size:
            remaining_data = firmware_data[data_offset:]
            data_payload += remaining_data
        
        # Add CRC (little endian)
        data_payload += struct.pack('<L', firmware_crc)
        
        data_length = len(data_payload)
        
        # Build packet
        packet = struct.pack('<BB', 0x01, 0x00)     # Protocol version, Packet type
        packet += struct.pack('<H', data_length)    # Data length
        packet += struct.pack('<L', unix_time)      # Unix time
        packet += struct.pack('<Q', device_id_int)  # Device ID
        packet += struct.pack('<H', 0x0121)         # SensorID: 0x0121
        packet += struct.pack('<B', 0x12)           # CMD: SENSOR_DFU
        packet += struct.pack('<H', 0xFFFF)         # Sequence No: 0xFFFF
        packet += data_payload                      # DATA: remaining dfuDataBody + dfuCrc
        
        return packet
    
    def _get_block_phase_name(self, block_index: int, total_blocks: int) -> str:
        """Get descriptive name for DFU phase"""
        if block_index == 0:
            return "Header Block"
        elif block_index == 1:
            return "Second Block"
        elif block_index == total_blocks - 1:
            return "Final Block"
        else:
            return f"Continue Block {block_index - 1}"
    
    def _get_block_sequence_no(self, block_index: int, total_blocks: int) -> int:
        """Get sequence number for block"""
        if block_index == 0:
            return 0x0000
        elif block_index == 1:
            return 0x0001
        elif block_index == total_blocks - 1:
            return 0xFFFF
        else:
            return 0x0002 + (block_index - 2)
    
    def _calculate_crc32(self, data: bytes) -> int:
        """Calculate CRC32 checksum for firmware data"""
        import zlib
        return zlib.crc32(data) & 0xFFFFFFFF
    
    # === データパーサー (動作確認済みロジック) ===
    
    def _parse_illuminance_sensor_data(self, uplink_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse illuminance sensor data (動作確認済み)"""
        try:
            # 既存の動作確認済みロジックを使用
            from module.illuminance.core.instant_uplink import InstantUplinkCommand
            temp_cmd = InstantUplinkCommand(f"{self.device_id:016X}")
            return temp_cmd.parse_sensor_uplink(uplink_data)
        except Exception as e:
            return {"error": f"Failed to parse illuminance sensor data: {str(e)}"}
    
    def _parse_parameter_info_data(self, uplink_data: bytes) -> Dict[str, Any]:
        """Parse parameter info data (動作確認済み)"""
        try:
            # 既存の動作確認済みロジックを使用
            from module.illuminance.core.get_parameter import GetParameterCommand
            temp_cmd = GetParameterCommand(f"{self.device_id:016X}")
            return temp_cmd.parse_parameter_uplink(uplink_data)
        except Exception as e:
            return {"error": f"Failed to parse parameter info: {str(e)}"}

    def get_module_specific_info(self) -> Dict[str, Any]:
        """Get module-specific information from config"""
        return self.config.get("module_info", {})

    def create_parameter_structure(self) -> Any:
        """Create parameter structure from config"""
        # 設定から動的に作成（将来の拡張用）
        if self.config["module_name"] == "illuminance":
            from module.illuminance.illuminance_parameters import IlluminanceParameters
            return IlluminanceParameters()
        
        return None

    
    def create_get_parameter_request(self) -> bytes:
        """Create get parameter request packet"""
        import struct
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        data_payload = struct.pack('<B', 0x00)  # DATA: Parameter info acquisition request
        data_length = len(data_payload)
        
        # Build packet according to spec 6-4 - use SensorID 0x0000 NOT 0x0121
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit (spec 6-4)
        packet += struct.pack('<B', 0x0D)               # CMD: GET_DEVICE_SETTING
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += data_payload                          # DATA: 0x00
        
        return packet

    def create_set_parameter_request(self, param_data: bytes) -> bytes:
        """Create set parameter request packet"""
        import struct
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        data_length = len(param_data)
        
        # Build packet according to spec - use SensorID 0x0000
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', data_length)        # Data length
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', self.device_id)     # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit
        packet += struct.pack('<B', 0x05)               # CMD: SET_REGISTER
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        packet += param_data                            # DATA: Parameter data
        
        return packet

    def create_device_restart_request(self) -> bytes:
        """Create device restart request packet"""
        import struct
        from lib.datetime_util import get_current_unix_time
        
        unix_time = get_current_unix_time()
        
        # Convert device_id safely to integer
        print(f"DEBUG: device_id type: {type(self.device_id)}, value: {self.device_id}")
        if isinstance(self.device_id, str):
            device_id_int = int(self.device_id, 16)
        elif isinstance(self.device_id, int):
            device_id_int = self.device_id
        else:
            raise ValueError(f"Invalid device_id type: {type(self.device_id)}, value: {self.device_id}")
        
        print(f"DEBUG: device_id_int: {device_id_int:016X}")
        
        # Build packet according to illuminance module spec - CMD 0xFD for device restart
        packet = struct.pack('<BB', 0x01, 0x00)         # Protocol version, Packet type (downlink request)
        packet += struct.pack('<H', 0x00)               # Data length (0 bytes)
        packet += struct.pack('<L', unix_time)          # Unix time
        packet += struct.pack('<Q', device_id_int)      # Device ID (little-endian)
        packet += struct.pack('<H', 0x0000)             # SensorID: End device main unit
        packet += struct.pack('<B', 0xFD)               # CMD: DEVICE_RESTART (illuminance module spec)
        packet += struct.pack('<H', 0xFFFF)             # Sequence No: Fixed
        # No DATA for device restart
        
        return packet

    def create_sensor_dfu_request(self, firmware_data: bytes) -> bytes:
        """Legacy method - replaced by 4-block transfer process"""
        raise NotImplementedError("Use _create_dfu_blocks() for proper 4-block transfer process")

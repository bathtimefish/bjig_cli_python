#!/usr/bin/env python3
"""
Complete Parameter Acquisition Test

Send parameter acquisition request and monitor for both downlink response
and subsequent parameter information uplink in real-time.
"""

import time
import struct
import json
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage
downlink_response = None
parameter_uplink = None
downlink_received = False
parameter_received = False
test_failed = False

def create_truly_correct_illuminance_request(device_id: int) -> bytes:
    """Create correct illuminance sensor parameter acquisition request"""
    protocol_version = 0x01
    packet_type = 0x00  # Downlink request
    unix_time = int(time.time())
    sensor_id = 0x0000  # Correct: 0x0000 fixed for parameter acquisition
    cmd = 0x0D  # GET_DEVICE_SETTING
    order = 0xFFFF
    data = bytes([0x00])  # 1 byte only
    data_length = len(data)  # 1
    
    # Build complete downlink request packet
    packet = struct.pack('<BB', protocol_version, packet_type)
    packet += struct.pack('<H', data_length)
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', device_id)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', cmd)
    packet += struct.pack('<H', order)
    packet += data
    
    return packet

def parse_parameter_information(data: bytes) -> dict:
    """Parse parameter information uplink according to illuminance spec 5-2"""
    try:
        if len(data) < 21:
            return {"error": "Packet too short for uplink"}
        
        # Verify this is an uplink notification (Type: 0x00)
        packet_type = data[1]
        if packet_type != 0x00:
            return {"error": f"Not uplink notification, got type 0x{packet_type:02X}"}
        
        # Verify sensor ID is 0x0000 (parameter information identifier)
        sensor_id = struct.unpack('<H', data[16:18])[0]
        if sensor_id != 0x0000:
            return {"error": f"Not parameter info, sensor ID is 0x{sensor_id:04X}"}
        
        print(f"\n🎯 Parameter Information Uplink Detected!")
        print(f"   Raw HEX: {data.hex(' ').upper()}")
        
        # Parse common uplink header
        data_length = struct.unpack('<H', data[2:4])[0]
        unix_time = struct.unpack('<L', data[4:8])[0]
        device_id = struct.unpack('<Q', data[8:16])[0]
        rssi = data[18] if data[18] < 128 else data[18] - 256
        order = struct.unpack('<H', data[19:21])[0]
        
        # Sensor data starts at index 21
        sensor_data = data[21:]
        
        print(f"   Type: 0x{packet_type:02X} (UPLINK_NOTIFICATION)")
        print(f"   Sensor ID: 0x{sensor_id:04X} (Parameter Information)")
        print(f"   Device ID: 0x{device_id:016X}")
        print(f"   Data Length: {data_length} bytes")
        print(f"   Sensor Data: {len(sensor_data)} bytes")
        print(f"   Sensor Data HEX: {sensor_data.hex(' ').upper()}")
        
        # Debug: Show byte-by-byte breakdown according to your analysis
        print(f"   📊 Analysis: The sensor data starts directly with illuminance sensor parameters")
        print(f"   📊 Your correct specification (offset 0, no parameter header):")
        if len(sensor_data) >= 24:
            print(f"      SensorID: {sensor_data[0:2].hex(' ').upper()} = 0x{struct.unpack('<H', sensor_data[0:2])[0]:04X}")
            print(f"      FW Version: {sensor_data[2:5].hex(' ').upper()} = {sensor_data[2]}.{sensor_data[3]}.{sensor_data[4]}")  
            print(f"      Timezone: {sensor_data[5:6].hex(' ').upper()} = {sensor_data[5]}")
            print(f"      BLE Mode: {sensor_data[6:7].hex(' ').upper()} = {sensor_data[6]}")
            print(f"      Tx Power: {sensor_data[7:8].hex(' ').upper()} = {sensor_data[7]}")
            print(f"      Advertise Interval: {sensor_data[8:10].hex(' ').upper()} = {struct.unpack('<H', sensor_data[8:10])[0]}")
            print(f"      Sensor Uplink Interval: {sensor_data[10:14].hex(' ').upper()} = {struct.unpack('<L', sensor_data[10:14])[0]} seconds")
            print(f"      Sensor Read Mode: {sensor_data[14:15].hex(' ').upper()} = {sensor_data[14]}")
            print(f"      Sampling: {sensor_data[15:16].hex(' ').upper()} = {sensor_data[15]}")
            print(f"      HysteresisHigh: {sensor_data[16:20].hex(' ').upper()} = {struct.unpack('<f', sensor_data[16:20])[0]:.2f} lux")
            if len(sensor_data) >= 24:
                print(f"      HysteresisLow: {sensor_data[20:24].hex(' ').upper()} = {struct.unpack('<f', sensor_data[20:24])[0]:.2f} lux")
        
        result = {
            "packet_info": {
                "type": "PARAMETER_INFORMATION_UPLINK",
                "device_id": f"0x{device_id:016X}",
                "sensor_id": f"0x{sensor_id:04X}",
                "unix_time": unix_time,
                "timestamp": datetime.fromtimestamp(unix_time).isoformat(),
                "rssi": f"{rssi} dBm",
                "order": order,
                "data_length": data_length,
                "sensor_data_length": len(sensor_data),
                "raw_packet": data.hex(' ').upper(),
                "sensor_data_hex": sensor_data.hex(' ').upper()
            }
        }
        
        # Based on analysis: The sensor data directly contains illuminance parameters
        # No Parameter Information header - starts directly with Sensor Data
        # Structure: [SensorID(2)][FW Ver(3)][TimeZone(1)][BLE Mode(1)][Tx Power(1)][Adv Interval(2)][Uplink Interval(4)][Read Mode(1)][Sampling(1)][HysteresisHigh(4)][HysteresisLow(4)]
        
        if len(sensor_data) < 24:
            result["error"] = f"Insufficient sensor data for parameter parsing (got {len(sensor_data)}, need 24)"
            return result
        
        offset = 0
        
        # Parse directly as Sensor Data according to your correct analysis
        sensor_data_info = {}
        
        # SensorID (2 bytes) - 0x0121 (illuminance sensor)
        if offset + 2 <= len(sensor_data):
            illuminance_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            sensor_data_info["sensor_id"] = {
                "value": f"0x{illuminance_sensor_id:04X}",
                "decimal": illuminance_sensor_id,
                "name": "Illuminance" if illuminance_sensor_id == 0x0121 else f"Other(0x{illuminance_sensor_id:04X})",
                "expected": "0x0121",
                "valid": illuminance_sensor_id == 0x0121,
                "description": "照度モジュールのSensorID",
                "raw_bytes": sensor_data[offset:offset+2].hex(' ').upper()
            }
            offset += 2
        
        # FW Version (3 bytes)
        if offset + 3 <= len(sensor_data):
            fw_bytes = sensor_data[offset:offset+3]
            fw_version = f"{fw_bytes[0]}.{fw_bytes[1]}.{fw_bytes[2]}"
            sensor_data_info["fw_version"] = {
                "value": fw_version,
                "major": fw_bytes[0],
                "minor": fw_bytes[1],
                "patch": fw_bytes[2],
                "raw_bytes": fw_bytes.hex(' ').upper(),
                "description": "本製品のFWバージョン"
            }
            offset += 3
        
        # TimeZone (1 byte)
        if offset + 1 <= len(sensor_data):
            timezone = sensor_data[offset]
            sensor_data_info["timezone"] = {
                "value": timezone,
                "hex": f"0x{timezone:02X}",
                "description": "タイムゾーン設定",
                "raw_bytes": f"{timezone:02X}"
            }
            offset += 1
        
        # BLE Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            ble_mode = sensor_data[offset]
            sensor_data_info["ble_mode"] = {
                "value": ble_mode,
                "hex": f"0x{ble_mode:02X}",
                "description": "Bluetooth LE通信モードの設定情報",
                "raw_bytes": f"{ble_mode:02X}"
            }
            offset += 1
        
        # Tx Power (1 byte)
        if offset + 1 <= len(sensor_data):
            tx_power = sensor_data[offset]
            sensor_data_info["tx_power"] = {
                "value": tx_power,
                "hex": f"0x{tx_power:02X}",
                "description": "Bluetooth LE通信の送信電波出力",
                "raw_bytes": f"{tx_power:02X}"
            }
            offset += 1
        
        # Advertise Interval (2 bytes, little endian)
        if offset + 2 <= len(sensor_data):
            adv_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
            sensor_data_info["advertise_interval"] = {
                "value": adv_interval,
                "hex": f"0x{adv_interval:04X}",
                "raw_bytes": sensor_data[offset:offset+2].hex(' ').upper(),
                "description": "Advertiseを発信する間隔",
                "encoding": "リトルエンディアン"
            }
            offset += 2
        
        # Sensor Uplink Interval (4 bytes, little endian)
        if offset + 4 <= len(sensor_data):
            uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
            sensor_data_info["sensor_uplink_interval"] = {
                "value": uplink_interval,
                "unit": "seconds",
                "hex": f"0x{uplink_interval:08X}",
                "raw_bytes": sensor_data[offset:offset+4].hex(' ').upper(),
                "description": "Sensor情報データをUplinkする間隔",
                "encoding": "リトルエンディアン"
            }
            offset += 4
        
        # Sensor Read Mode (1 byte)
        if offset + 1 <= len(sensor_data):
            read_mode = sensor_data[offset]
            sensor_data_info["sensor_read_mode"] = {
                "value": read_mode,
                "hex": f"0x{read_mode:02X}",
                "description": "計測モード",
                "raw_bytes": f"{read_mode:02X}"
            }
            offset += 1
        
        # Sampling (1 byte)
        if offset + 1 <= len(sensor_data):
            sampling = sensor_data[offset]
            sensor_data_info["sampling"] = {
                "value": sampling,
                "hex": f"0x{sampling:02X}",
                "description": "サンプリング周期",
                "raw_bytes": f"{sampling:02X}"
            }
            offset += 1
        
        # HysteresisHigh (4 bytes, little endian, IEEE 754 Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_high_bytes = sensor_data[offset:offset+4]
            hysteresis_high = struct.unpack('<f', hysteresis_high_bytes)[0]
            sensor_data_info["hysteresis_high"] = {
                "value": hysteresis_high,
                "unit": "Lux",
                "hex": f"0x{struct.unpack('<L', hysteresis_high_bytes)[0]:08X}",
                "raw_bytes": hysteresis_high_bytes.hex(' ').upper(),
                "description": "ヒステリシス(High):照度(Lux)",
                "encoding": "リトルエンディアン IEEE 754 Float"
            }
            offset += 4
        
        # HysteresisLow (4 bytes, little endian, IEEE 754 Float)
        if offset + 4 <= len(sensor_data):
            hysteresis_low_bytes = sensor_data[offset:offset+4]
            hysteresis_low = struct.unpack('<f', hysteresis_low_bytes)[0]
            sensor_data_info["hysteresis_low"] = {
                "value": hysteresis_low,
                "unit": "Lux",
                "hex": f"0x{struct.unpack('<L', hysteresis_low_bytes)[0]:08X}",
                "raw_bytes": hysteresis_low_bytes.hex(' ').upper(),
                "description": "ヒステリシス(Low):照度(Lux)",
                "encoding": "リトルエンディアン IEEE 754 Float"
            }
            offset += 4
        
        # Check for remaining data
        if offset < len(sensor_data):
            remaining_data = sensor_data[offset:]
            sensor_data_info["remaining_data"] = {
                "length": len(remaining_data),
                "raw_bytes": remaining_data.hex(' ').upper(),
                "description": "仕様書に記載されていない追加データ"
            }
        
        result["sensor_data"] = sensor_data_info
        
        # Validation summary
        result["validation"] = {
            "valid_parameter_uplink": True,
            "sensor_id_valid": sensor_data_info.get("sensor_id", {}).get("valid", False),
            "sufficient_data_length": len(sensor_data) >= 24
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Parameter parsing error: {e}", "raw": data.hex(' ').upper()}

def parse_downlink_response(data: bytes) -> dict:
    """Parse downlink response"""
    try:
        if len(data) < 20:
            return {"error": "Response too short"}
        
        protocol_version = data[0]
        packet_type = data[1]
        unix_time = struct.unpack('<L', data[2:6])[0]
        device_id = struct.unpack('<Q', data[6:14])[0]
        sensor_id = struct.unpack('<H', data[14:16])[0]
        order = struct.unpack('<H', data[16:18])[0]
        cmd = data[18]
        result = data[19]
        
        return {
            "raw_hex": data.hex(' ').upper(),
            "protocol_version": f"0x{protocol_version:02X}",
            "type": f"0x{packet_type:02X}",
            "unix_time": unix_time,
            "timestamp": datetime.fromtimestamp(unix_time).isoformat(),
            "device_id": f"0x{device_id:016X}",
            "sensor_id": f"0x{sensor_id:04X}",
            "order": order,
            "cmd": f"0x{cmd:02X}",
            "result": f"0x{result:02X}",
            "result_desc": get_result_description(result),
            "success": result == 0x00
        }
        
    except Exception as e:
        return {"error": f"Parse error: {e}"}

def get_result_description(result: int) -> str:
    """Get result code description"""
    descriptions = {
        0x00: "Success",
        0x01: "Invalid Sensor ID",
        0x02: "Unsupported CMD",
        0x03: "Parameter out of range",
        0x04: "Connection failed",
        0x05: "Timeout",
        0x07: "Device not found",
        0x08: "Router busy",
        0x09: "Module busy"
    }
    return descriptions.get(result, f"Unknown(0x{result:02X})")

def on_data_received(data: bytes):
    """Callback for received data - strict sequential processing"""
    global downlink_response, parameter_uplink, downlink_received, parameter_received, test_failed
    
    if len(data) < 2:
        return
    
    packet_type = data[1]
    
    if packet_type == 0x01:  # Downlink response
        print(f"\n✅ STEP 2: DOWNLINK RESPONSE RECEIVED!")
        print(f"   Raw HEX: {data.hex(' ').upper()}")
        
        downlink_response = parse_downlink_response(data)
        downlink_received = True
        
        if downlink_response.get('success', False):
            print(f"   Result: {downlink_response.get('result_desc', 'Unknown')} ✅")
            print(f"   ✅ Parameter acquisition request successful!")
            print(f"   ⏳ Now waiting for parameter information uplink (SensorID: 0x0000)...")
        else:
            # Step 3: Error handling
            print(f"\n❌ STEP 3: ERROR IN DOWNLINK RESPONSE!")
            print(f"   Result: {downlink_response.get('result_desc', 'Unknown')} ❌")
            print(f"   Error Code: {downlink_response.get('result', 'Unknown')}")
            print(f"   ❌ Test failed due to downlink error - terminating")
            test_failed = True
        
    elif packet_type == 0x00:  # Uplink notification
        # Only process parameter uplink if downlink was successful
        if not downlink_received:
            print(f"📦 Uplink received before downlink response (ignoring)")
            return
            
        if test_failed:
            print(f"📦 Uplink received after downlink error (ignoring)")
            return
            
        sensor_id = struct.unpack('<H', data[16:18])[0] if len(data) >= 18 else 0
        
        if sensor_id == 0x0000:  # Parameter information uplink
            print(f"\n🎯 STEP 4: PARAMETER INFORMATION UPLINK RECEIVED!")
            print(f"   SensorID: 0x{sensor_id:04X} ✅")
            parameter_uplink = parse_parameter_information(data)
            parameter_received = True
        else:
            print(f"📦 Other sensor uplink: 0x{sensor_id:04X} (ignoring)")

def main():
    """Main test function with strict sequential processing"""
    global downlink_received, parameter_received, test_failed
    
    print("🔬 Complete Parameter Acquisition Test")
    print("=" * 50)
    print("Processing steps:")
    print("  1. Send parameter acquisition downlink request")
    print("  2. Receive success downlink response")
    print("  3. If error received, display error and terminate")
    print("  4. Receive parameter information uplink (SensorID: 0x0000)")
    print()
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    # Known illuminance sensor device ID
    illuminance_device_id = 0x2468800203400004
    
    print(f"🎯 Target: Illuminance Sensor (0x{illuminance_device_id:016X})")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            # Step 1: Send parameter acquisition request
            request_packet = create_truly_correct_illuminance_request(illuminance_device_id)
            print(f"\n📤 STEP 1: SENDING PARAMETER ACQUISITION REQUEST")
            print(f"   Request HEX: {request_packet.hex(' ').upper()}")
            
            if monitor.send(request_packet):
                print(f"   ✅ Request sent successfully")
            else:
                print(f"   ❌ Failed to send request")
                return False
            
            print(f"\n⏳ Waiting for sequential responses...")
            
            # Wait for downlink response first
            start_time = time.time()
            while not downlink_received and not test_failed and (time.time() - start_time) < 30:
                time.sleep(0.1)
            
            # Check if downlink failed
            if test_failed:
                print(f"\n❌ TEST TERMINATED DUE TO DOWNLINK ERROR")
                return False
            
            if not downlink_received:
                print(f"\n❌ No downlink response received within 30 seconds")
                return False
            
            # Now wait for parameter uplink
            print(f"\n⏳ Waiting for parameter uplink (max 30 seconds)...")
            start_time = time.time()
            while not parameter_received and (time.time() - start_time) < 30:
                time.sleep(0.1)
            
            # Final results
            print(f"\n" + "=" * 70)
            print(f"📊 FINAL TEST RESULTS")
            print(f"=" * 70)
            
            # Step 2/3 Results
            if downlink_response:
                print(f"\n✅ STEP 2: DOWNLINK RESPONSE")
                print(f"   HEX: {downlink_response.get('raw_hex', 'Unknown')}")
                print(f"   Result: {downlink_response.get('result_desc', 'Unknown')}")
                print(f"   Success: {downlink_response.get('success', False)}")
                
                if not downlink_response.get('success', False):
                    print(f"   ❌ Test failed at step 3 - downlink error")
                    return False
            else:
                print(f"\n❌ STEP 2: No downlink response received")
                return False
            
            # Step 4 Results
            if parameter_uplink:
                print(f"\n🎯 STEP 4: PARAMETER INFORMATION UPLINK")
                print(f"   HEX: {parameter_uplink.get('packet_info', {}).get('raw_packet', 'Unknown')}")
                print(f"   Sensor Data HEX: {parameter_uplink.get('packet_info', {}).get('sensor_data_hex', 'Unknown')}")
                
                # Output complete JSON
                json_output = json.dumps(parameter_uplink, ensure_ascii=False, indent=2)
                print(f"\n📄 COMPLETE PARAMETER INFORMATION JSON:")
                print(f"=" * 70)
                print(json_output)
                
                print(f"\n✅ ALL STEPS COMPLETED SUCCESSFULLY!")
                return True
            else:
                print(f"\n⚠️  STEP 4: No parameter information uplink received")
                print(f"   Downlink was successful but parameter data not received")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
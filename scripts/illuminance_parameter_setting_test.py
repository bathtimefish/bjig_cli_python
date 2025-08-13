#!/usr/bin/env python3
"""
Illuminance Parameter Setting Test

Complete parameter setting flow: GET → MODIFY → SET
Generic parameter modification with validation.
Example: Change Advertise Interval to 10 seconds
"""

import time
import struct
import json
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage
current_parameters = None
setting_response = None
get_response_received = False
set_response_received = False
test_failed = False

def create_parameter_get_request(device_id: int) -> bytes:
    """Create parameter acquisition request (CMD: 0x0D)"""
    protocol_version = 0x01
    packet_type = 0x00  # Downlink request
    unix_time = int(time.time())
    sensor_id = 0x0000  # Fixed for parameter acquisition
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

def create_parameter_set_request(device_id: int, param_data: bytes) -> bytes:
    """Create parameter setting request (CMD: 0x05) according to spec 6-2"""
    protocol_version = 0x01
    packet_type = 0x00  # Downlink request
    unix_time = int(time.time())
    sensor_id = 0x0000  # End device main unit (spec 6-2 requirement)
    cmd = 0x05  # SET_REGISTER (SET_PARAMETER)
    order = 0xFFFF  # Fixed value according to spec 6-2
    data_length = len(param_data)
    
    # Build complete downlink request packet
    packet = struct.pack('<BB', protocol_version, packet_type)
    packet += struct.pack('<H', data_length)
    packet += struct.pack('<L', unix_time)
    packet += struct.pack('<Q', device_id)
    packet += struct.pack('<H', sensor_id)
    packet += struct.pack('<B', cmd)
    packet += struct.pack('<H', order)
    packet += param_data
    
    return packet

def parse_parameter_information(data: bytes) -> dict:
    """Parse parameter information uplink"""
    try:
        if len(data) < 21:
            return {"error": "Packet too short for uplink"}
        
        packet_type = data[1]
        if packet_type != 0x00:
            return {"error": f"Not uplink notification, got type 0x{packet_type:02X}"}
        
        sensor_id = struct.unpack('<H', data[16:18])[0]
        if sensor_id != 0x0000:
            return {"error": f"Not parameter info, sensor ID is 0x{sensor_id:04X}"}
        
        # Sensor data starts at index 21
        sensor_data = data[21:]
        
        if len(sensor_data) < 24:
            return {"error": f"Insufficient sensor data (got {len(sensor_data)}, need 24)"}
        
        # Parse sensor data according to confirmed structure
        offset = 0
        sensor_data_info = {}
        
        # SensorID (2 bytes)
        illuminance_sensor_id = struct.unpack('<H', sensor_data[offset:offset+2])[0]
        sensor_data_info["sensor_id"] = {
            "value": illuminance_sensor_id,
            "hex": f"0x{illuminance_sensor_id:04X}",
            "raw_bytes": sensor_data[offset:offset+2]
        }
        offset += 2
        
        # FW Version (3 bytes)
        fw_bytes = sensor_data[offset:offset+3]
        sensor_data_info["fw_version"] = {
            "value": f"{fw_bytes[0]}.{fw_bytes[1]}.{fw_bytes[2]}",
            "major": fw_bytes[0],
            "minor": fw_bytes[1],
            "patch": fw_bytes[2],
            "raw_bytes": fw_bytes
        }
        offset += 3
        
        # TimeZone (1 byte)
        timezone = sensor_data[offset]
        sensor_data_info["timezone"] = {
            "value": timezone,
            "raw_bytes": sensor_data[offset:offset+1]
        }
        offset += 1
        
        # BLE Mode (1 byte)
        ble_mode = sensor_data[offset]
        sensor_data_info["ble_mode"] = {
            "value": ble_mode,
            "raw_bytes": sensor_data[offset:offset+1]
        }
        offset += 1
        
        # Tx Power (1 byte)
        tx_power = sensor_data[offset]
        sensor_data_info["tx_power"] = {
            "value": tx_power,
            "raw_bytes": sensor_data[offset:offset+1]
        }
        offset += 1
        
        # Advertise Interval (2 bytes, little endian)
        adv_interval = struct.unpack('<H', sensor_data[offset:offset+2])[0]
        sensor_data_info["advertise_interval"] = {
            "value": adv_interval,
            "raw_bytes": sensor_data[offset:offset+2]
        }
        offset += 2
        
        # Sensor Uplink Interval (4 bytes, little endian)
        uplink_interval = struct.unpack('<L', sensor_data[offset:offset+4])[0]
        sensor_data_info["sensor_uplink_interval"] = {
            "value": uplink_interval,
            "raw_bytes": sensor_data[offset:offset+4]
        }
        offset += 4
        
        # Sensor Read Mode (1 byte)
        read_mode = sensor_data[offset]
        sensor_data_info["sensor_read_mode"] = {
            "value": read_mode,
            "raw_bytes": sensor_data[offset:offset+1]
        }
        offset += 1
        
        # Sampling (1 byte)
        sampling = sensor_data[offset]
        sensor_data_info["sampling"] = {
            "value": sampling,
            "raw_bytes": sensor_data[offset:offset+1]
        }
        offset += 1
        
        # HysteresisHigh (4 bytes, little endian, IEEE 754 Float)
        hysteresis_high_bytes = sensor_data[offset:offset+4]
        hysteresis_high = struct.unpack('<f', hysteresis_high_bytes)[0]
        sensor_data_info["hysteresis_high"] = {
            "value": hysteresis_high,
            "raw_bytes": hysteresis_high_bytes
        }
        offset += 4
        
        # HysteresisLow (4 bytes, little endian, IEEE 754 Float)
        hysteresis_low_bytes = sensor_data[offset:offset+4]
        hysteresis_low = struct.unpack('<f', hysteresis_low_bytes)[0]
        sensor_data_info["hysteresis_low"] = {
            "value": hysteresis_low,
            "raw_bytes": hysteresis_low_bytes
        }
        offset += 4
        
        return sensor_data_info
        
    except Exception as e:
        return {"error": f"Parameter parsing error: {e}"}

def validate_parameter_value(parameter_name: str, value: any) -> bool:
    """Validate parameter value according to spec"""
    
    validation_rules = {
        "advertise_interval": {
            "type": int,
            "min": 0,
            "max": 65535,
            "unit": "milliseconds"
        },
        "sensor_uplink_interval": {
            "type": int,
            "min": 1,
            "max": 4294967295,
            "unit": "seconds"
        },
        "timezone": {
            "type": int,
            "min": 0,
            "max": 255
        },
        "ble_mode": {
            "type": int,
            "min": 0,
            "max": 255
        },
        "tx_power": {
            "type": int,
            "min": 0,
            "max": 255
        },
        "sensor_read_mode": {
            "type": int,
            "min": 0,
            "max": 255
        },
        "sampling": {
            "type": int,
            "min": 0,
            "max": 255
        },
        "hysteresis_high": {
            "type": float,
            "min": 0.0,
            "max": 100000.0,
            "unit": "lux"
        },
        "hysteresis_low": {
            "type": float,
            "min": 0.0,
            "max": 100000.0,
            "unit": "lux"
        }
    }
    
    if parameter_name not in validation_rules:
        raise ValueError(f"Unknown parameter: {parameter_name}")
    
    rules = validation_rules[parameter_name]
    
    # Type check
    if not isinstance(value, rules["type"]):
        raise TypeError(f"Parameter '{parameter_name}' must be {rules['type'].__name__}")
    
    # Range check
    if "min" in rules and value < rules["min"]:
        raise ValueError(f"Parameter '{parameter_name}' must be >= {rules['min']}")
    
    if "max" in rules and value > rules["max"]:
        raise ValueError(f"Parameter '{parameter_name}' must be <= {rules['max']}")
    
    return True

def update_parameter(param_structure: dict, parameter_name: str, new_value: any) -> dict:
    """
    Update any parameter in the structure
    
    Args:
        param_structure: Current parameter structure
        parameter_name: Parameter name to update
        new_value: New value to set
    
    Returns:
        Updated parameter structure
    """
    if parameter_name not in param_structure:
        raise ValueError(f"Parameter '{parameter_name}' not found in structure")
    
    # Validate parameter value
    validate_parameter_value(parameter_name, new_value)
    
    # Update the parameter
    param_structure[parameter_name]["value"] = new_value
    
    print(f"   ✅ Updated {parameter_name}: {new_value}")
    
    return param_structure

def update_multiple_parameters(param_structure: dict, updates: dict) -> dict:
    """
    Update multiple parameters at once
    
    Args:
        param_structure: Current parameter structure
        updates: Dictionary of {parameter_name: new_value}
    
    Returns:
        Updated parameter structure
    """
    for param_name, new_value in updates.items():
        param_structure = update_parameter(param_structure, param_name, new_value)
    
    return param_structure

def serialize_parameter_structure(param_structure: dict) -> bytes:
    """Convert parameter structure to bytes according to spec 6-2 DATA format"""
    try:
        # Build parameter data according to spec 6-2 (19 bytes total)
        data = b''
        
        # SensorID (2 bytes) - 0x0121 fixed for illuminance sensor
        sensor_id = param_structure["sensor_id"]["value"]
        data += struct.pack('<H', sensor_id)
        
        # TimeZone (1 byte)
        data += struct.pack('<B', param_structure["timezone"]["value"])
        
        # BLE Mode (1 byte)
        data += struct.pack('<B', param_structure["ble_mode"]["value"])
        
        # Tx Power (1 byte)
        data += struct.pack('<B', param_structure["tx_power"]["value"])
        
        # Advertise Interval (2 bytes, little endian)
        data += struct.pack('<H', param_structure["advertise_interval"]["value"])
        
        # Sensor Uplink Interval (4 bytes, little endian)
        data += struct.pack('<L', param_structure["sensor_uplink_interval"]["value"])
        
        # Sensor Read Mode (1 byte)
        data += struct.pack('<B', param_structure["sensor_read_mode"]["value"])
        
        # Sampling (1 byte)
        data += struct.pack('<B', param_structure["sampling"]["value"])
        
        # HysteresisHigh (4 bytes, little endian, IEEE 754 Float)
        data += struct.pack('<f', param_structure["hysteresis_high"]["value"])
        
        # HysteresisLow (4 bytes, little endian, IEEE 754 Float)
        data += struct.pack('<f', param_structure["hysteresis_low"]["value"])
        
        print(f"   📊 Serialized parameter data: {data.hex(' ').upper()}")
        print(f"   📊 Data length: {len(data)} bytes (spec 6-2 format)")
        
        return data
        
    except Exception as e:
        raise Exception(f"Failed to serialize parameter structure: {e}")

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
            "cmd_name": get_cmd_name(cmd),
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

def get_cmd_name(cmd: int) -> str:
    """Get command name"""
    commands = {
        0x00: "IMMEDIATE_UPLINK",
        0x05: "SET_PARAMETER",
        0x06: "GET_PARAMETER",
        0x07: "SENSOR_DFU",
        0x08: "DEVICE_RESET",
        0x0D: "GET_DEVICE_SETTING"
    }
    return commands.get(cmd, f"UNKNOWN(0x{cmd:02X})")

def on_data_received(data: bytes):
    """Callback for received data - handles both GET and SET phases"""
    global current_parameters, setting_response, get_response_received, set_response_received, test_failed
    
    if len(data) < 2:
        return
    
    packet_type = data[1]
    
    if packet_type == 0x01:  # Downlink response
        response = parse_downlink_response(data)
        cmd = data[18] if len(data) > 18 else 0
        
        if cmd == 0x0D:  # GET_DEVICE_SETTING response
            print(f"\n✅ STEP 2: GET PARAMETER DOWNLINK RESPONSE")
            print(f"   HEX: {response.get('raw_hex', 'Unknown')}")
            print(f"   Result: {response.get('result_desc', 'Unknown')}")
            
            if response.get('success', False):
                print(f"   ✅ Parameter acquisition successful!")
                print(f"   ⏳ Waiting for parameter information uplink...")
            else:
                print(f"   ❌ Parameter acquisition failed: {response.get('result_desc', 'Unknown')}")
                test_failed = True
        
        elif cmd == 0x05:  # SET_PARAMETER response
            print(f"\n✅ STEP 9: SET PARAMETER DOWNLINK RESPONSE")
            print(f"   HEX: {response.get('raw_hex', 'Unknown')}")
            print(f"   Result: {response.get('result_desc', 'Unknown')}")
            
            setting_response = response
            set_response_received = True
            
            if not response.get('success', False):
                print(f"   ❌ Parameter setting failed: {response.get('result_desc', 'Unknown')}")
                test_failed = True
        
    elif packet_type == 0x00:  # Uplink notification
        if not get_response_received:  # Still in GET phase
            sensor_id = struct.unpack('<H', data[16:18])[0] if len(data) >= 18 else 0
            
            if sensor_id == 0x0000:  # Parameter information uplink
                print(f"\n🎯 STEP 4: PARAMETER INFORMATION UPLINK")
                print(f"   Raw HEX: {data.hex(' ').upper()}")
                
                current_parameters = parse_parameter_information(data)
                get_response_received = True
                
                if "error" in current_parameters:
                    print(f"   ❌ Parameter parsing failed: {current_parameters['error']}")
                    test_failed = True
                else:
                    print(f"   ✅ Parameter information received and parsed")
            else:
                print(f"📦 Other sensor uplink: 0x{sensor_id:04X} (ignoring)")

def main():
    """Main parameter setting test function"""
    global get_response_received, set_response_received, test_failed
    
    # Initialize change tracking
    change_info = {}
    
    print("🔧 Illuminance Parameter Setting Test")
    print("=" * 55)
    print("Complete flow: GET → MODIFY → SET")
    print("Example: Change Sensor Uplink Interval to 10 seconds")
    print()
    print("Processing steps:")
    print("  1. Send parameter acquisition request (CMD: 0x0D)")
    print("  2. Receive success downlink response")
    print("  3. Handle errors if any")
    print("  4. Receive parameter information uplink (SensorID: 0x0000)")
    print("  5-7. Modify parameter structure")
    print("  8. Send parameter setting request (CMD: 0x05)")
    print("  9-10. Verify setting response")
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
            
            # PHASE 1: GET CURRENT PARAMETERS (Steps 1-4)
            print(f"\n🔍 PHASE 1: GET CURRENT PARAMETERS")
            print(f"=" * 50)
            
            # Step 1: Send parameter acquisition request
            request_packet = create_parameter_get_request(illuminance_device_id)
            print(f"\n📤 STEP 1: SENDING PARAMETER GET REQUEST")
            print(f"   Request HEX: {request_packet.hex(' ').upper()}")
            
            if monitor.send(request_packet):
                print(f"   ✅ Request sent successfully")
            else:
                print(f"   ❌ Failed to send request")
                return False
            
            # Wait for GET phase completion
            start_time = time.time()
            while not get_response_received and not test_failed and (time.time() - start_time) < 30:
                time.sleep(0.1)
            
            if test_failed:
                print(f"\n❌ GET phase failed")
                return False
            
            if not get_response_received or not current_parameters:
                print(f"\n❌ Failed to get current parameters")
                return False
            
            print(f"\n✅ GET phase completed successfully")
            
            # PHASE 2: MODIFY PARAMETERS (Steps 5-7)
            print(f"\n🔧 PHASE 2: MODIFY PARAMETERS")
            print(f"=" * 50)
            
            print(f"\n📊 STEP 5-6: Current parameter values:")
            for param_name, param_info in current_parameters.items():
                if isinstance(param_info, dict) and "value" in param_info:
                    print(f"   {param_name}: {param_info['value']}")
            
            print(f"\n🔄 STEP 7: Modifying parameters...")
            
            try:
                # Change Sensor Uplink Interval to 10 seconds
                parameter_name = "sensor_uplink_interval"
                old_value = current_parameters[parameter_name]["value"]
                new_value = 10
                
                print(f"   🔄 Changing {parameter_name}: {old_value} → {new_value}")
                modified_params = update_parameter(current_parameters, parameter_name, new_value)
                
                # Store change info for final log
                change_info = {
                    "parameter_name": parameter_name,
                    "old_value": old_value,
                    "new_value": new_value
                }
                
            except (ValueError, TypeError) as e:
                print(f"❌ Parameter modification failed: {e}")
                return False
            
            # PHASE 3: SET PARAMETERS (Steps 8-10)
            print(f"\n📤 PHASE 3: SET PARAMETERS")
            print(f"=" * 50)
            
            # Step 8: Send parameter setting request
            try:
                param_data = serialize_parameter_structure(modified_params)
                set_request_packet = create_parameter_set_request(illuminance_device_id, param_data)
                
                print(f"\n📤 STEP 8: SENDING PARAMETER SET REQUEST")
                print(f"   Parameter Data HEX: {param_data.hex(' ').upper()}")
                print(f"   Full Request HEX: {set_request_packet.hex(' ').upper()}")
                
                if monitor.send(set_request_packet):
                    print(f"   ✅ Set request sent successfully")
                else:
                    print(f"   ❌ Failed to send set request")
                    return False
                
            except Exception as e:
                print(f"❌ Failed to create set request: {e}")
                return False
            
            # Wait for SET phase completion
            start_time = time.time()
            while not set_response_received and not test_failed and (time.time() - start_time) < 30:
                time.sleep(0.1)
            
            # Final results
            print(f"\n" + "=" * 70)
            print(f"📊 FINAL TEST RESULTS")
            print(f"=" * 70)
            
            if test_failed:
                print(f"\n❌ TEST FAILED")
                return False
            
            if setting_response and setting_response.get('success', False):
                print(f"\n✅ PARAMETER SETTING SUCCESSFUL!")
                print(f"   Command: {setting_response.get('cmd_name', 'Unknown')}")
                print(f"   Result: {setting_response.get('result_desc', 'Unknown')}")
                print(f"   Response HEX: {setting_response.get('raw_hex', 'Unknown')}")
                
                # Success log message
                print(f"\n📝 Updated sensor module: {change_info['parameter_name']}, {change_info['old_value']} to {change_info['new_value']}")
                print(f"🎉 Sensor Uplink Interval successfully changed to 10 seconds!")
                return True
            else:
                print(f"\n❌ PARAMETER SETTING FAILED")
                if setting_response:
                    print(f"   Error: {setting_response.get('result_desc', 'Unknown')}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
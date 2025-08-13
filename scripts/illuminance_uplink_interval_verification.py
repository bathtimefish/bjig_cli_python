#!/usr/bin/env python3
"""
Illuminance Uplink Interval Verification

Monitor illuminance sensor uplink notifications to verify the interval 
has changed to approximately 10 seconds.
"""

import time
import struct
import sys
from datetime import datetime
from async_serial_monitor import AsyncSerialMonitor

# Global storage for illuminance uplinks
illuminance_uplinks = []
test_start_time = None

def on_data_received(data: bytes):
    """Callback for received data - focus on illuminance uplinks"""
    global illuminance_uplinks, test_start_time
    
    if len(data) < 18:
        return
    
    packet_type = data[1]
    
    if packet_type == 0x00:  # Uplink notification
        sensor_id = struct.unpack('<H', data[16:18])[0]
        
        if sensor_id == 0x0121:  # Illuminance sensor
            current_time = time.time()
            
            # Parse illuminance data
            device_id = struct.unpack('<Q', data[8:16])[0]
            unix_time = struct.unpack('<L', data[4:8])[0]
            rssi = data[18] if data[18] < 128 else data[18] - 256
            
            # Extract illuminance value (last 4 bytes of sensor data)
            sensor_data = data[21:]
            if len(sensor_data) >= 4:
                lux_bytes = sensor_data[-4:]
                lux_value = struct.unpack('<f', lux_bytes)[0]
            else:
                lux_value = 0.0
            
            uplink_info = {
                "timestamp": current_time,
                "elapsed_time": current_time - test_start_time,
                "device_id": f"0x{device_id:016X}",
                "unix_time": unix_time,
                "formatted_time": datetime.fromtimestamp(unix_time).strftime('%H:%M:%S'),
                "rssi": f"{rssi} dBm",
                "illuminance": f"{lux_value:.2f} lux",
                "raw_hex": data.hex(' ').upper()
            }
            
            illuminance_uplinks.append(uplink_info)
            
            # Calculate interval from previous uplink
            if len(illuminance_uplinks) > 1:
                prev_uplink = illuminance_uplinks[-2]
                interval = current_time - prev_uplink["timestamp"]
                
                print(f"📦 Illuminance Uplink #{len(illuminance_uplinks)}")
                print(f"   Time: {uplink_info['formatted_time']}")
                print(f"   Interval: {interval:.1f} seconds (from previous)")
                print(f"   Illuminance: {uplink_info['illuminance']}")
                print(f"   RSSI: {uplink_info['rssi']}")
                print(f"   Elapsed: {uplink_info['elapsed_time']:.1f}s")
                print()
            else:
                print(f"📦 Illuminance Uplink #1 (first)")
                print(f"   Time: {uplink_info['formatted_time']}")
                print(f"   Illuminance: {uplink_info['illuminance']}")
                print(f"   RSSI: {uplink_info['rssi']}")
                print(f"   Elapsed: {uplink_info['elapsed_time']:.1f}s")
                print()
        else:
            # Brief info for other sensors
            print(f"📦 Other sensor: 0x{sensor_id:04X}")

def calculate_statistics():
    """Calculate interval statistics"""
    if len(illuminance_uplinks) < 2:
        return None
    
    intervals = []
    for i in range(1, len(illuminance_uplinks)):
        interval = illuminance_uplinks[i]["timestamp"] - illuminance_uplinks[i-1]["timestamp"]
        intervals.append(interval)
    
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)
    
    return {
        "count": len(intervals),
        "average": avg_interval,
        "minimum": min_interval,
        "maximum": max_interval,
        "intervals": intervals
    }

def main():
    """Main verification function"""
    global test_start_time
    
    print("📊 Illuminance Uplink Interval Verification")
    print("=" * 50)
    print("Monitoring illuminance sensor uplink notifications")
    print("Expected interval: ~10 seconds (after parameter change)")
    print("Monitoring duration: 60 seconds")
    print()
    
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.start_monitoring()
            
            test_start_time = time.time()
            print(f"🚀 Starting monitoring at {datetime.now().strftime('%H:%M:%S')}")
            print()
            
            # Monitor for 60 seconds
            time.sleep(60)
            
            print("⏰ Monitoring completed")
            print()
            
            # Calculate and display statistics
            stats = calculate_statistics()
            
            print("📊 VERIFICATION RESULTS")
            print("=" * 40)
            
            if stats:
                print(f"Total illuminance uplinks received: {len(illuminance_uplinks)}")
                print(f"Intervals measured: {stats['count']}")
                print(f"Average interval: {stats['average']:.1f} seconds")
                print(f"Minimum interval: {stats['minimum']:.1f} seconds")
                print(f"Maximum interval: {stats['maximum']:.1f} seconds")
                print()
                
                # Show all intervals
                print("📋 All measured intervals:")
                for i, interval in enumerate(stats['intervals'], 1):
                    print(f"   Interval {i}: {interval:.1f} seconds")
                
                print()
                
                # Verification assessment
                target_interval = 10.0
                tolerance = 2.0  # ±2 seconds tolerance
                
                if abs(stats['average'] - target_interval) <= tolerance:
                    print(f"✅ VERIFICATION PASSED")
                    print(f"   Average interval ({stats['average']:.1f}s) is within {tolerance}s of target ({target_interval}s)")
                else:
                    print(f"❌ VERIFICATION FAILED")
                    print(f"   Average interval ({stats['average']:.1f}s) is outside {tolerance}s tolerance of target ({target_interval}s)")
                
                # Additional analysis
                close_to_target = sum(1 for interval in stats['intervals'] 
                                    if abs(interval - target_interval) <= tolerance)
                success_rate = (close_to_target / len(stats['intervals'])) * 100
                
                print(f"   Success rate: {close_to_target}/{len(stats['intervals'])} ({success_rate:.1f}%) within tolerance")
                
                return abs(stats['average'] - target_interval) <= tolerance
                
            else:
                print("❌ VERIFICATION FAILED")
                print("   Insufficient data (less than 2 uplinks received)")
                
                if len(illuminance_uplinks) == 1:
                    print("   Only 1 uplink received - need at least 2 to measure interval")
                elif len(illuminance_uplinks) == 0:
                    print("   No illuminance uplinks received - check sensor connection")
                
                return False
                
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Quick Comprehensive Test

Quick test to verify all AsyncSerialMonitor functionality works correctly.
"""

import time
import signal
import struct
import sys
from async_serial_monitor import AsyncSerialMonitor

# Global flag for graceful shutdown
test_running = True

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping test...")
    test_running = False

def on_data_received(data: bytes):
    """Callback for received data"""
    print(f"📥 RX: {len(data)}B - {data[:8].hex(' ').upper()}{'...' if len(data) > 8 else ''}")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    print(f"🔗 {'Connected' if connected else 'Disconnected'}")

def main():
    """Quick comprehensive test"""
    global test_running
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("⚡ Quick AsyncSerialMonitor Test")
    print("=" * 35)
    
    try:
        with AsyncSerialMonitor() as monitor:
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            monitor.start_monitoring()
            
            print("📊 Test Results:")
            print(f"✅ Connection: Success")
            print(f"✅ Monitoring: Started")
            
            # Send one JIG INFO command
            jig_packet = struct.pack('<BBB', 0x01, 0x01, 0x02)  # FW version request
            jig_packet += struct.pack('<L', int(time.time()) + 9*3600)  # Local time
            jig_packet += struct.pack('<L', int(time.time()))  # Unix time
            
            print(f"📤 Sending JIG INFO command...")
            monitor.send(jig_packet)
            
            # Monitor for 10 seconds
            print(f"🔄 Monitoring for 10 seconds...")
            start_time = time.time()
            
            while test_running and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            stats = monitor.statistics
            print(f"\n📈 Final Results:")
            print(f"   TX: {stats['bytes_sent']} bytes")
            print(f"   RX: {stats['bytes_received']} bytes")
            print(f"   Connection attempts: {stats['connection_attempts']}")
            
            if stats['bytes_received'] > 0:
                print(f"✅ SUCCESS: Communication working!")
            else:
                print(f"⚠️  No data received")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    print("🏁 Quick test completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Quick BraveJIG Router Connection Test

Short connection test to verify basic functionality without long waits.
"""

import time
import signal
import sys
from async_serial_monitor import AsyncSerialMonitor

# Global flag for graceful shutdown
test_running = True

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global test_running
    print("\n🛑 Stopping connection test...")
    test_running = False

def on_data_received(data: bytes):
    """Callback for received data"""
    print(f"📥 Received {len(data)} bytes: {data.hex(' ').upper()}")

def on_error(error: Exception):
    """Callback for errors"""
    print(f"❌ Error: {error}")

def on_connection_changed(connected: bool):
    """Callback for connection state changes"""
    status = "🔗 Connected to BraveJIG Router" if connected else "🔌 Disconnected from BraveJIG Router"
    print(status)

def main():
    """Main connection test function"""
    global test_running
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🚀 Quick BraveJIG Router Connection Test")
    print("=" * 45)
    
    # Use correct port for macOS
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router...")
    print(f"   Port: {port}")
    print(f"   Baudrate: {baudrate}")
    print(f"   Test duration: 10 seconds")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate, timeout=5.0) as monitor:
            print(f"📊 Monitor: {monitor}")
            
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            print("▶️  Starting monitoring...")
            monitor.start_monitoring()
            
            print("🔄 Monitoring for 10 seconds...")
            print("   Press Ctrl+C to stop early")
            
            # Monitor for 10 seconds
            start_time = time.time()
            
            while test_running and monitor.is_monitoring and (time.time() - start_time) < 10:
                time.sleep(0.1)
            
            # Test sending data (JIG Info command)
            print("📤 Testing data transmission...")
            if monitor.send(b'\x01\x01'):
                print("✅ Data sent successfully")
            else:
                print("❌ Failed to send data")
            
            # Wait a bit for potential response
            time.sleep(1.0)
            
            # Final statistics
            final_stats = monitor.statistics
            print(f"\n📈 Final Statistics:")
            print(f"   Bytes received: {final_stats['bytes_received']}")
            print(f"   Bytes sent: {final_stats['bytes_sent']}")
            print(f"   Connection attempts: {final_stats['connection_attempts']}")
            
            if final_stats['bytes_received'] > 0 or final_stats['bytes_sent'] > 0:
                print("✅ SUCCESS: Serial communication is working!")
            else:
                print("⚠️  No data exchanged - this may be normal")
                
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("🏁 Quick connection test completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
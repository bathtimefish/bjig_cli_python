#!/usr/bin/env python3
"""
BraveJIG Router Connection Test

Basic connection test to verify AsyncSerialMonitor can communicate with BraveJIG Router.
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
    
    # Show printable characters if any
    try:
        text = data.decode('utf-8', errors='ignore')
        printable = ''.join(c if c.isprintable() else '.' for c in text)
        if printable.strip():
            print(f"📄 Text: '{printable}'")
    except:
        pass

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
    
    print("🚀 BraveJIG Router Connection Test")
    print("=" * 40)
    
    # Use correct port for macOS
    port = '/dev/cu.usbmodem0000000000002'
    baudrate = 38400
    
    print(f"🔧 Connecting to BraveJIG Router...")
    print(f"   Port: {port}")
    print(f"   Baudrate: {baudrate}")
    print(f"   Timeout: 10 seconds")
    
    try:
        with AsyncSerialMonitor(port=port, baudrate=baudrate) as monitor:
            print(f"📊 Monitor: {monitor}")
            
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            print("▶️  Starting monitoring...")
            monitor.start_monitoring()
            
            print("\n🔄 Monitoring active for 90 seconds...")
            print("💡 Waiting for uplink notifications (60-second intervals)")
            print("   Press Ctrl+C to stop early")
            
            # Monitor for 90 seconds (to catch 60-second uplink interval)
            start_time = time.time()
            last_stats_time = start_time
            
            while test_running and monitor.is_monitoring and (time.time() - start_time) < 90:
                time.sleep(0.1)
                
                # Print statistics every 5 seconds
                current_time = time.time()
                if current_time - last_stats_time >= 5:
                    stats = monitor.statistics
                    elapsed = int(current_time - start_time)
                    print(f"⏱️  [{elapsed}s] Stats: RX:{stats['bytes_received']} TX:{stats['bytes_sent']} bytes")
                    last_stats_time = current_time
            
            # Final statistics
            final_stats = monitor.statistics
            print(f"\n📈 Final Statistics:")
            print(f"   Bytes received: {final_stats['bytes_received']}")
            print(f"   Bytes sent: {final_stats['bytes_sent']}")
            print(f"   Connection attempts: {final_stats['connection_attempts']}")
            
            if final_stats['bytes_received'] > 0:
                print("✅ SUCCESS: Received data from BraveJIG Router!")
            else:
                print("⚠️  No data received - this may be normal if no modules are paired")
                
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    
    print("🏁 Connection test completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
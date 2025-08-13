"""
Basic usage example for AsyncSerialMonitor

This example demonstrates the fundamental usage of AsyncSerialMonitor
for simple serial communication monitoring and command transmission.
"""

import sys
import time
import signal
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from async_serial_monitor import AsyncSerialMonitor
from exceptions import AsyncSerialMonitorError


def setup_logging():
    """Setup logging for the example"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def on_data_received(data: bytes):
    """Callback function for received data"""
    print(f"📥 Received {len(data)} bytes: {data.hex(' ').upper()}")
    
    # Try to decode as text if possible
    try:
        text = data.decode('utf-8', errors='ignore')
        if text.isprintable():
            print(f"📄 Text: {repr(text)}")
    except:
        pass


def on_error(error: Exception):
    """Callback function for errors"""
    print(f"❌ Error: {error}")


def on_connection_changed(connected: bool):
    """Callback function for connection state changes"""
    status = "🔗 Connected" if connected else "🔌 Disconnected"
    print(f"{status}")


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Stopping monitor...")
    global monitor_running
    monitor_running = False


def main():
    """Main function demonstrating basic usage"""
    setup_logging()
    
    print("🚀 AsyncSerialMonitor Basic Usage Example")
    print("=" * 50)
    
    # Setup signal handler for graceful shutdown
    global monitor_running
    monitor_running = True
    signal.signal(signal.SIGINT, signal_handler)
    
    # List available serial ports
    print("📋 Available serial ports:")
    ports = AsyncSerialMonitor.list_serial_ports()
    for i, port in enumerate(ports):
        print(f"  {i+1}. {port}")
    
    if not ports:
        print("⚠️  No serial ports found!")
        return
    
    # Create monitor with default settings (can be customized)
    port = '/dev/tty.usbmodem0000000000002'  # Default for BraveJIG
    print(f"\n🔧 Creating monitor for {port}")
    
    try:
        # Using context manager for automatic cleanup
        with AsyncSerialMonitor(port=port) as monitor:
            print(f"📊 Monitor: {monitor}")
            
            # Set up callbacks
            monitor.set_data_callback(on_data_received)
            monitor.set_error_callback(on_error)
            monitor.set_connection_callback(on_connection_changed)
            
            # Start monitoring
            print("▶️  Starting monitoring...")
            monitor.start_monitoring()
            
            # Send some test data
            test_commands = [
                b'\x01\x01\x02\x12\x34\x56\x78',  # Example command 1
                b'\x01\x00\x00\x00',              # Example command 2
            ]
            
            for i, cmd in enumerate(test_commands):
                print(f"📤 Sending test command {i+1}: {cmd.hex(' ').upper()}")
                if monitor.send(cmd):
                    print("✅ Command queued successfully")
                else:
                    print("❌ Failed to queue command")
                time.sleep(2)
            
            # Main loop
            print("\n🔄 Monitoring active. Press Ctrl+C to stop...")
            print("💡 You can connect to the serial port from another terminal")
            print("   to send data and see it received here.")
            
            while monitor_running and monitor.is_monitoring:
                time.sleep(0.1)
                
                # Print statistics every 10 seconds
                if int(time.time()) % 10 == 0:
                    stats = monitor.statistics
                    print(f"📈 Stats: RX:{stats['bytes_received']} TX:{stats['bytes_sent']} bytes")
                    time.sleep(1)  # Avoid printing multiple times
            
    except AsyncSerialMonitorError as e:
        print(f"❌ AsyncSerialMonitor error: {e}")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
    finally:
        print("🏁 Example finished")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
BraveJIG CLI Test Runner

This script provides automated testing capabilities for the BraveJIG CLI tool.
It can run individual commands or test sequences while monitoring the results.

Usage:
    python3 test_runner.py [options] <test_type>

Examples:
    # Test all router commands
    python3 test_runner.py router_basic
    
    # Test illuminance sensor commands
    python3 test_runner.py illuminance_basic --module-id 001122334455667788
    
    # Run single command
    python3 test_runner.py single --command "router get-version"
"""

import sys
import os
import subprocess
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))


class BraveJIGTestRunner:
    """Automated test runner for BraveJIG CLI commands"""
    
    def __init__(self, cli_device: str = "/tmp/bjig_cli", baudrate: int = 38400):
        self.cli_device = cli_device
        self.baudrate = baudrate
        self.main_script = os.path.join(os.path.dirname(__file__), '..', 'src', 'main.py')
        
        # Test results
        self.results = []
        
    def run_command(self, command_args: List[str], timeout: float = 30.0) -> Dict[str, Any]:
        """Run a single CLI command and capture results"""
        full_command = [
            'python3', self.main_script,
            '--port', self.cli_device,
            '--baud', str(self.baudrate)
        ] + command_args
        
        result = {
            'command': ' '.join(command_args),
            'full_command': ' '.join(full_command),
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'return_code': None,
            'stdout': '',
            'stderr': '',
            'duration': 0.0
        }
        
        print(f"🧪 Running: {result['command']}")
        
        start_time = time.time()
        
        try:
            process = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result['return_code'] = process.returncode
            result['stdout'] = process.stdout
            result['stderr'] = process.stderr
            result['success'] = (process.returncode == 0)
            result['duration'] = time.time() - start_time
            
            # Print results
            if result['success']:
                print(f"  ✅ Success ({result['duration']:.2f}s)")
                if result['stdout'].strip():
                    print(f"  📄 Output:")
                    for line in result['stdout'].strip().split('\\n'):
                        print(f"    {line}")
            else:
                print(f"  ❌ Failed ({result['duration']:.2f}s) - Return code: {result['return_code']}")
                if result['stderr'].strip():
                    print(f"  🚨 Error:")
                    for line in result['stderr'].strip().split('\\n'):
                        print(f"    {line}")
            
        except subprocess.TimeoutExpired:
            result['error'] = f"Command timed out after {timeout} seconds"
            result['duration'] = timeout
            print(f"  ⏰ Timeout after {timeout}s")
            
        except Exception as e:
            result['error'] = str(e)
            result['duration'] = time.time() - start_time
            print(f"  💥 Exception: {e}")
        
        print()
        self.results.append(result)
        return result
    
    def test_router_basic(self) -> bool:
        """Test basic router commands"""
        print("=== Router Basic Commands Test ===")
        
        commands = [
            ['router', 'get-version'],
            ['router', 'get-device-id'],
            ['router', 'get-scan-mode'],
            ['router', 'keep-alive'],
        ]
        
        all_success = True
        for cmd in commands:
            result = self.run_command(cmd)
            if not result['success']:
                all_success = False
        
        return all_success
    
    def test_router_advanced(self) -> bool:
        """Test advanced router commands"""
        print("=== Router Advanced Commands Test ===")
        
        commands = [
            ['router', 'stop'],
            ['router', 'start'], 
            ['router', 'set-scan-mode', '1'],
            ['router', 'get-scan-mode'],
            ['router', 'set-scan-mode', '0'],
            ['router', 'get-device-id', '0'],
        ]
        
        all_success = True
        for cmd in commands:
            result = self.run_command(cmd)
            if not result['success']:
                all_success = False
            time.sleep(1)  # Delay between advanced commands
        
        return all_success
    
    def test_illuminance_basic(self, module_id: str = "001122334455667788") -> bool:
        """Test basic illuminance sensor commands"""
        print("=== Illuminance Sensor Basic Commands Test ===")
        
        commands = [
            ['module', 'instant-uplink', '--module-id', module_id],
            ['module', 'get-parameter', '--module-id', module_id],
        ]
        
        all_success = True
        for cmd in commands:
            result = self.run_command(cmd, timeout=45.0)  # Longer timeout for module commands
            if not result['success']:
                all_success = False
            time.sleep(2)  # Delay between module commands
        
        return all_success
    
    def test_illuminance_advanced(self, module_id: str = "001122334455667788") -> bool:
        """Test advanced illuminance sensor commands"""
        print("=== Illuminance Sensor Advanced Commands Test ===")
        
        # Test parameter setting with sample data
        test_parameters = {
            "timezone": 1,  # Change to UTC
            "advertise_interval": 2000,  # 2 seconds
            "hysteresis_high": 1000.0,
            "hysteresis_low": 800.0
        }
        
        import json
        param_json = json.dumps(test_parameters)
        
        commands = [
            ['module', 'set-parameter', '--sensor-id', '0121', '--module-id', module_id, '--data', param_json],
            ['module', 'get-parameter', '--module-id', module_id],  # Verify changes
            ['module', 'restart', '--module-id', module_id],
        ]
        
        all_success = True
        for cmd in commands:
            result = self.run_command(cmd, timeout=60.0)  # Even longer timeout for parameter operations
            if not result['success']:
                all_success = False
            time.sleep(3)  # Longer delay for advanced operations
        
        return all_success
    
    def test_single_command(self, command: str) -> bool:
        """Test a single command specified by user"""
        print("=== Single Command Test ===")
        
        # Parse command string into argument list
        args = command.split()
        result = self.run_command(args)
        
        return result['success']
    
    def test_monitor_mode(self, duration: float = 10.0) -> bool:
        """Test monitor mode for a specified duration"""
        print(f"=== Monitor Mode Test ({duration}s) ===")
        
        # Start monitor in background
        monitor_cmd = [
            'python3', self.main_script,
            '--port', self.cli_device,
            '--baud', str(self.baudrate),
            'monitor'
        ]
        
        print(f"🔍 Starting monitor for {duration} seconds...")
        
        try:
            process = subprocess.Popen(
                monitor_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Let it run for specified duration
            time.sleep(duration)
            
            # Terminate monitor
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            print(f"  ✅ Monitor ran for {duration}s")
            if stdout.strip():
                print("  📄 Monitor output:")
                for line in stdout.strip().split('\\n')[:10]:  # Show first 10 lines
                    print(f"    {line}")
                if len(stdout.strip().split('\\n')) > 10:
                    print("    ... (truncated)")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Monitor test failed: {e}")
            return False
    
    def print_summary(self):
        """Print test results summary"""
        print("=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - successful_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        
        if failed_tests > 0:
            print("\\nFailed Tests:")
            for result in self.results:
                if not result['success']:
                    print(f"  ❌ {result['command']}")
                    if 'error' in result:
                        print(f"     Error: {result['error']}")
                    elif result['stderr']:
                        print(f"     stderr: {result['stderr'][:100]}...")
        
        total_duration = sum(r['duration'] for r in self.results)
        print(f"\\nTotal Duration: {total_duration:.2f}s")
        print("=" * 60)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='BraveJIG CLI Test Runner')
    parser.add_argument('test_type', choices=[
        'router_basic', 'router_advanced', 'illuminance_basic', 
        'illuminance_advanced', 'single', 'monitor', 'all'
    ], help='Type of test to run')
    
    parser.add_argument('--device', default='/tmp/bjig_cli', 
                       help='CLI device path (default: /tmp/bjig_cli)')
    parser.add_argument('--baudrate', type=int, default=38400,
                       help='Baudrate (default: 38400)')
    parser.add_argument('--module-id', default='001122334455667788',
                       help='Module ID for sensor tests')
    parser.add_argument('--command', help='Single command to run (for single test type)')
    parser.add_argument('--duration', type=float, default=10.0,
                       help='Duration for monitor test (default: 10s)')
    
    args = parser.parse_args()
    
    # Check if CLI device exists
    if not os.path.exists(args.device):
        print(f"Error: CLI device {args.device} not found")
        print("Please run setup_test_environment.sh first")
        sys.exit(1)
    
    runner = BraveJIGTestRunner(args.device, args.baudrate)
    
    print(f"BraveJIG CLI Test Runner")
    print(f"Device: {args.device} | Baudrate: {args.baudrate}")
    print(f"Test Type: {args.test_type}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    success = False
    
    try:
        if args.test_type == 'router_basic':
            success = runner.test_router_basic()
        elif args.test_type == 'router_advanced':
            success = runner.test_router_advanced()
        elif args.test_type == 'illuminance_basic':
            success = runner.test_illuminance_basic(args.module_id)
        elif args.test_type == 'illuminance_advanced':
            success = runner.test_illuminance_advanced(args.module_id)
        elif args.test_type == 'single':
            if not args.command:
                print("Error: --command required for single test type")
                sys.exit(1)
            success = runner.test_single_command(args.command)
        elif args.test_type == 'monitor':
            success = runner.test_monitor_mode(args.duration)
        elif args.test_type == 'all':
            success = True
            success &= runner.test_router_basic()
            success &= runner.test_illuminance_basic(args.module_id)
            # Add more comprehensive tests as needed
        
    except KeyboardInterrupt:
        print("\\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"🚨 Test runner error: {e}")
    
    finally:
        runner.print_summary()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
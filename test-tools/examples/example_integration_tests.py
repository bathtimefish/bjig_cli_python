"""
BraveJIG Integration Test Examples

実機テスト環境を使用した統合テスト例
socatテスト環境の使用方法を示す

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import os
import sys
import time
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from tests.integration import IntegratedTestRunner, SocatTestConfig
from tests.hardware.test_helpers import HardwareTestRunner, HardwareTestConfig
from tests.test_scenarios.illuminance_scenarios import IlluminanceTestScenarios


def run_socat_integration_tests():
    """Socat統合テストの実行例"""
    print("=== BraveJIG Socat Integration Test Example ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test configuration
    config = SocatTestConfig(
        physical_device="/dev/ttyACM0",  # Adjust for your system
        baudrate=38400,
        test_results_dir="/tmp/bjig_integration_test_results"
    )
    
    # Create test runner
    runner = IntegratedTestRunner(config)
    
    try:
        # Setup test environment
        print("Setting up socat test environment...")
        if not runner.setup_environment():
            print("❌ Failed to setup test environment")
            return False
        
        print("✅ Test environment ready!")
        print(f"Monitor PTY: {config.monitor_pty}")
        print(f"CLI PTY: {config.cli_pty}")
        
        # Run basic router tests
        print("\n--- Running Basic Router Tests ---")
        router_result = runner.run_test_sequence("Basic Router Tests", [
            {"name": "Get Router Version", "args": ["router", "get-version"], "timeout": 10},
            {"name": "Get Device ID", "args": ["router", "get-device-id"], "timeout": 10},
            {"name": "Keep Alive", "args": ["router", "keep-alive"], "timeout": 10}
        ])
        
        print(f"Router tests: {'✅ PASSED' if router_result['success'] else '❌ FAILED'}")
        print(f"Commands executed: {len(router_result['commands'])}")
        print(f"Total packets captured: {router_result['total_packets']}")
        
        # Run illuminance module tests
        print("\n--- Running Illuminance Module Tests ---")
        module_result = runner.run_test_sequence("Illuminance Module Tests", [
            {
                "name": "Get Parameters",
                "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                "timeout": 45
            },
            {
                "name": "Instant Uplink",
                "args": ["module", "instant-uplink", "--module-id", "2468800203400004"],
                "timeout": 30
            },
            {
                "name": "Set Parameter Test",
                "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                        "--data", '{"sensor_uplink_interval": 120}'],
                "timeout": 45
            }
        ])
        
        print(f"Module tests: {'✅ PASSED' if module_result['success'] else '❌ FAILED'}")
        print(f"Commands executed: {len(module_result['commands'])}")
        print(f"Total packets captured: {module_result['total_packets']}")
        
        # Save detailed results
        results_file = runner.save_test_results()
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Show packet summary
        packet_log = runner.monitor.get_packet_log()
        if packet_log:
            print(f"\n--- Packet Communication Summary ---")
            print(f"Total packets: {len(packet_log)}")
            
            uplink_count = sum(1 for p in packet_log if p['direction'] == 'UPLINK')
            downlink_count = sum(1 for p in packet_log if p['direction'] == 'DOWNLINK_RESPONSE')
            
            print(f"Uplink packets: {uplink_count}")
            print(f"Downlink responses: {downlink_count}")
            
            # Show recent packets
            print("\nRecent packets:")
            for packet in packet_log[-5:]:  # Last 5 packets
                timestamp = time.strftime("%H:%M:%S", time.localtime(packet['timestamp']))
                direction = packet['direction']
                summary = packet['parsed'].get('summary', 'Unknown')
                print(f"  {timestamp} - {direction}: {summary}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False
    finally:
        # Cleanup
        print("\nCleaning up test environment...")
        runner.cleanup_environment()
        print("✅ Cleanup complete")


def run_hardware_tests():
    """実機テスト実行例"""
    print("=== BraveJIG Hardware Test Example ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test configuration
    config = HardwareTestConfig(
        # port will be auto-detected
        baudrate=38400,
        command_timeout=45.0,
        retry_count=2,
        test_output_dir="/tmp/bjig_hardware_test_results"
    )
    
    # Create test runner
    runner = HardwareTestRunner(config)
    
    try:
        # Setup test environment
        print("Setting up hardware test environment...")
        setup_result = runner.setup_test_environment()
        
        if not setup_result["success"]:
            print(f"❌ Failed to setup: {setup_result.get('error', 'Unknown error')}")
            return False
        
        print("✅ Hardware test environment ready!")
        print(f"Using router at: {setup_result['test_config']['port']}")
        
        # Show detected devices
        if setup_result["detected_devices"]:
            print("\nDetected devices:")
            for i, device in enumerate(setup_result["detected_devices"]):
                status = "✅" if device.get("connectivity", {}).get("connected", False) else "❌"
                print(f"  {i+1}. {device['port']} - {device['description']} {status}")
        
        # Run basic test suite
        print("\n--- Running Basic Hardware Tests ---")
        basic_results = runner.run_hardware_tests("router_basic")
        
        print(f"Basic tests: {'✅ PASSED' if basic_results['summary']['failed'] == 0 else '❌ FAILED'}")
        print(f"Tests: {basic_results['summary']['passed']}/{basic_results['summary']['total']} passed")
        print(f"Duration: {basic_results['summary']['duration']:.2f}s")
        
        # Run illuminance tests if available
        print("\n--- Running Illuminance Hardware Tests ---")
        try:
            illuminance_results = runner.run_hardware_tests("illuminance_basic")
            
            print(f"Illuminance tests: {'✅ PASSED' if illuminance_results['summary']['failed'] == 0 else '❌ FAILED'}")
            print(f"Tests: {illuminance_results['summary']['passed']}/{illuminance_results['summary']['total']} passed")
            print(f"Duration: {illuminance_results['summary']['duration']:.2f}s")
            
        except Exception as e:
            print(f"⚠️ Illuminance tests failed: {str(e)}")
        
        # Generate reports
        print("\n--- Generating Test Reports ---")
        if hasattr(runner, 'test_history') and runner.command_runner.test_history:
            # Create a summary report
            total_commands = len(runner.command_runner.test_history)
            successful_commands = sum(1 for r in runner.command_runner.test_history if r['success'])
            
            print(f"Total commands executed: {total_commands}")
            print(f"Successful commands: {successful_commands}")
            print(f"Success rate: {(successful_commands/total_commands)*100:.1f}%")
            
            # Show any failures
            failures = [r for r in runner.command_runner.test_history if not r['success']]
            if failures:
                print("\nCommand failures:")
                for failure in failures:
                    print(f"  - {failure['command']}: {failure.get('final_result', {}).get('error', 'Unknown error')}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        logging.exception("Detailed error:")
        return False


def run_scenario_based_tests():
    """シナリオベーステスト実行例"""
    print("=== BraveJIG Scenario-Based Test Example ===")
    
    # Get predefined test scenarios
    all_scenarios = IlluminanceTestScenarios.get_all_scenarios()
    
    print("Available test scenario categories:")
    for category, scenarios in all_scenarios.items():
        print(f"  - {category}: {len(scenarios)} scenarios")
    
    # Example: Run unit test scenarios with mock
    print("\n--- Running Unit Test Scenarios ---")
    unit_scenarios = all_scenarios["unit"]
    
    for scenario in unit_scenarios[:3]:  # Run first 3 scenarios
        print(f"\nRunning scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"Type: {scenario.test_type}")
        print(f"Steps: {len(scenario.steps)}")
        print(f"Tags: {', '.join(scenario.tags)}")
        
        # In a real implementation, you would execute the scenario steps
        # For this example, we'll just show the structure
        for i, step in enumerate(scenario.steps):
            print(f"  Step {i+1}: {step.get('action', 'Unknown action')}")
    
    # Example: Show hardware test sequences
    print("\n--- Available Hardware Test Sequences ---")
    hardware_sequences = IlluminanceTestScenarios.get_hardware_test_sequences()
    
    for sequence in hardware_sequences:
        print(f"\nSequence: {sequence['name']}")
        print(f"Description: {sequence['description']}")
        print(f"Commands: {len(sequence['commands'])}")
        
        for i, cmd in enumerate(sequence['commands']):
            timeout = cmd.get('timeout', 30)
            print(f"  {i+1}. {cmd['name']} (timeout: {timeout}s)")


def main():
    """メイン実行関数"""
    print("BraveJIG Integration Test Examples")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
    else:
        print("Available test types:")
        print("  socat      - Run socat integration tests")
        print("  hardware   - Run hardware tests")
        print("  scenarios  - Show scenario examples")
        print()
        test_type = input("Select test type (or press Enter for scenarios): ").strip().lower()
        if not test_type:
            test_type = "scenarios"
    
    if test_type == "socat":
        success = run_socat_integration_tests()
    elif test_type == "hardware":
        success = run_hardware_tests()
    elif test_type == "scenarios":
        run_scenario_based_tests()
        success = True
    else:
        print(f"Unknown test type: {test_type}")
        success = False
    
    if success:
        print("\n🎉 Test example completed successfully!")
    else:
        print("\n💥 Test example failed!")
    
    return success


if __name__ == '__main__':
    main()
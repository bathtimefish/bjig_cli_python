"""
BraveJIG Hardware Test Helpers

実機テスト用ヘルパー関数とユーティリティ
- デバイス検出と接続管理
- コマンド実行とレスポンス検証
- テスト環境の自動セットアップ
- ログ収集とレポート生成

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import os
import sys
import time
import serial
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HardwareTestConfig:
    """実機テスト設定"""
    # Serial connection settings
    port: Optional[str] = None  # Auto-detect if None
    baudrate: int = 38400
    timeout: float = 5.0
    
    # Test device information
    router_device_id: Optional[str] = None
    test_module_devices: Dict[str, str] = field(default_factory=dict)  # module_type -> device_id
    
    # Test execution settings
    command_timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    
    # Logging and output
    log_level: str = "INFO"
    test_output_dir: str = "/tmp/bjig_hardware_tests"
    save_raw_logs: bool = True
    generate_reports: bool = True


class SerialDeviceDetector:
    """シリアルデバイス検出器"""
    
    @staticmethod
    def detect_bjig_routers() -> List[Dict[str, str]]:
        """BraveJIGルーターを検出"""
        potential_devices = []
        
        try:
            import serial.tools.list_ports
            
            # List all serial ports
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                device_info = {
                    "port": port.device,
                    "description": port.description or "",
                    "hwid": port.hwid or "",
                    "manufacturer": port.manufacturer or "",
                    "product": port.product or "",
                    "serial_number": port.serial_number or ""
                }
                
                # Check for BraveJIG router characteristics
                # (This would be refined based on actual hardware characteristics)
                if SerialDeviceDetector._is_likely_bjig_router(device_info):
                    potential_devices.append(device_info)
            
        except ImportError:
            # Fallback for systems without pyserial tools
            logging.warning("pyserial tools not available, falling back to basic detection")
            potential_devices = SerialDeviceDetector._basic_device_detection()
        
        return potential_devices
    
    @staticmethod
    def _is_likely_bjig_router(device_info: Dict[str, str]) -> bool:
        """デバイス情報からBraveJIGルーターの可能性を判定"""
        # Common patterns for USB-to-serial adapters used in BraveJIG routers
        likely_patterns = [
            "USB",
            "Serial",
            "UART", 
            "CDC",
            "ACM",
            "CH340",
            "CP210",
            "FT232"
        ]
        
        device_text = " ".join([
            device_info.get("description", ""),
            device_info.get("manufacturer", ""),
            device_info.get("product", "")
        ]).upper()
        
        return any(pattern.upper() in device_text for pattern in likely_patterns)
    
    @staticmethod
    def _basic_device_detection() -> List[Dict[str, str]]:
        """基本的なデバイス検出（フォールバック）"""
        devices = []
        
        # Common serial device paths
        potential_paths = [
            "/dev/ttyACM*",
            "/dev/ttyUSB*", 
            "/dev/cu.usbmodem*",
            "/dev/cu.usbserial*"
        ]
        
        import glob
        for pattern in potential_paths:
            for device_path in glob.glob(pattern):
                devices.append({
                    "port": device_path,
                    "description": f"Serial device at {device_path}",
                    "hwid": "",
                    "manufacturer": "",
                    "product": "",
                    "serial_number": ""
                })
        
        return devices
    
    @staticmethod
    def test_router_connectivity(port: str, baudrate: int = 38400, timeout: float = 5.0) -> Dict[str, Any]:
        """ルーター接続性をテスト"""
        result = {
            "port": port,
            "connected": False,
            "router_version": None,
            "device_id": None,
            "error": None
        }
        
        try:
            with serial.Serial(port, baudrate, timeout=timeout) as ser:
                # Clear buffers
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                
                # Send version request (JIG Info command)
                version_cmd = bytes([0x01, 0x02])  # Protocol version 1, Get Version
                ser.write(version_cmd)
                
                # Wait for response
                time.sleep(0.5)
                response = ser.read(ser.in_waiting or 64)
                
                if response:
                    result["connected"] = True
                    # Parse version response (simplified)
                    if len(response) >= 4:
                        result["router_version"] = "Connected"  # Simplified
                
        except Exception as e:
            result["error"] = str(e)
        
        return result


class HardwareCommandRunner:
    """実機コマンド実行器"""
    
    def __init__(self, config: HardwareTestConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.test_history: List[Dict[str, Any]] = []
        
        # Ensure output directory exists
        os.makedirs(self.config.test_output_dir, exist_ok=True)
    
    def run_cli_command(self, command_args: List[str], **kwargs) -> Dict[str, Any]:
        """CLIコマンドを実行"""
        # Merge kwargs with config defaults
        timeout = kwargs.get("timeout", self.config.command_timeout)
        retry_count = kwargs.get("retry_count", self.config.retry_count)
        port = kwargs.get("port", self.config.port)
        baudrate = kwargs.get("baudrate", self.config.baudrate)
        
        if not port:
            # Auto-detect port
            routers = SerialDeviceDetector.detect_bjig_routers()
            if not routers:
                return {
                    "success": False,
                    "error": "No BraveJIG router devices found",
                    "command": " ".join(command_args)
                }
            port = routers[0]["port"]
            self.logger.info(f"Auto-detected router at: {port}")
        
        # Build full command
        main_script = self._find_main_script()
        full_command = [
            sys.executable, main_script,
            "--port", port,
            "--baud", str(baudrate)
        ] + command_args
        
        result = {
            "command": " ".join(command_args),
            "full_command": " ".join(full_command),
            "port": port,
            "success": False,
            "attempts": [],
            "final_result": None
        }
        
        # Execute with retries
        for attempt in range(retry_count):
            attempt_result = self._execute_single_attempt(full_command, timeout, attempt + 1)
            result["attempts"].append(attempt_result)
            
            if attempt_result["success"]:
                result["success"] = True
                result["final_result"] = attempt_result
                break
            
            # Wait before retry
            if attempt < retry_count - 1:
                time.sleep(self.config.retry_delay)
        
        # Use last attempt as final result if no success
        if not result["success"]:
            result["final_result"] = result["attempts"][-1] if result["attempts"] else None
        
        # Add to history
        self.test_history.append(result)
        
        return result
    
    def _execute_single_attempt(self, command: List[str], timeout: float, attempt: int) -> Dict[str, Any]:
        """単一コマンド実行試行"""
        attempt_result = {
            "attempt": attempt,
            "timestamp": time.time(),
            "success": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "duration": 0.0,
            "error": None
        }
        
        self.logger.info(f"Attempt {attempt}: {' '.join(command)}")
        
        start_time = time.time()
        
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            attempt_result["return_code"] = process.returncode
            attempt_result["stdout"] = process.stdout
            attempt_result["stderr"] = process.stderr
            attempt_result["success"] = (process.returncode == 0)
            
        except subprocess.TimeoutExpired:
            attempt_result["error"] = f"Command timed out after {timeout} seconds"
        except Exception as e:
            attempt_result["error"] = str(e)
        
        attempt_result["duration"] = time.time() - start_time
        
        # Log result
        if attempt_result["success"]:
            self.logger.info(f"  ✅ Success ({attempt_result['duration']:.2f}s)")
        else:
            error_msg = attempt_result["error"] or f"Return code: {attempt_result['return_code']}"
            self.logger.warning(f"  ❌ Failed ({attempt_result['duration']:.2f}s): {error_msg}")
        
        return attempt_result
    
    def _find_main_script(self) -> str:
        """メインスクリプトを検索"""
        # Try relative paths from test location
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'main.py'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'main.py'),
            'src/main.py',
            'main.py'
        ]
        
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path
        
        raise FileNotFoundError("Could not find main.py script")
    
    def run_test_suite(self, suite_name: str, test_commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """テストスイートを実行"""
        suite_result = {
            "suite_name": suite_name,
            "start_time": time.time(),
            "commands": [],
            "summary": {
                "total": len(test_commands),
                "passed": 0,
                "failed": 0,
                "duration": 0.0
            }
        }
        
        self.logger.info(f"Running test suite: {suite_name} ({len(test_commands)} commands)")
        
        for i, cmd_config in enumerate(test_commands):
            self.logger.info(f"Test {i+1}/{len(test_commands)}: {cmd_config.get('name', 'Unnamed')}")
            
            command_args = cmd_config["args"]
            result = self.run_cli_command(command_args, **cmd_config.get("options", {}))
            
            result["test_name"] = cmd_config.get("name", f"Test {i+1}")
            result["expected_success"] = cmd_config.get("expected_success", True)
            
            # Evaluate test result
            test_passed = (result["success"] == result["expected_success"])
            result["test_passed"] = test_passed
            
            if test_passed:
                suite_result["summary"]["passed"] += 1
            else:
                suite_result["summary"]["failed"] += 1
            
            suite_result["commands"].append(result)
            
            # Check if we should stop on failure
            if not test_passed and cmd_config.get("stop_on_failure", False):
                self.logger.error(f"Test suite stopped due to failure at test {i+1}")
                break
        
        suite_result["end_time"] = time.time()
        suite_result["summary"]["duration"] = suite_result["end_time"] - suite_result["start_time"]
        
        # Log summary
        summary = suite_result["summary"]
        status = "✅" if summary["failed"] == 0 else "❌"
        self.logger.info(
            f"{status} Test suite '{suite_name}' completed: "
            f"{summary['passed']}/{summary['total']} passed "
            f"({summary['duration']:.2f}s)"
        )
        
        return suite_result
    
    def generate_test_report(self, results: Dict[str, Any], format: str = "text") -> str:
        """テストレポートを生成"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        if format == "text":
            return self._generate_text_report(results, timestamp)
        elif format == "json":
            return self._generate_json_report(results, timestamp)
        elif format == "html":
            return self._generate_html_report(results, timestamp)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_text_report(self, results: Dict[str, Any], timestamp: str) -> str:
        """テキストレポートを生成"""
        filename = f"test_report_{timestamp}.txt"
        filepath = os.path.join(self.config.test_output_dir, filename)
        
        lines = [
            f"BraveJIG Hardware Test Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Suite: {results['suite_name']}",
            "=" * 60,
            ""
        ]
        
        # Summary
        summary = results["summary"]
        lines.extend([
            f"SUMMARY:",
            f"  Total Tests: {summary['total']}",
            f"  Passed: {summary['passed']}",
            f"  Failed: {summary['failed']}",
            f"  Duration: {summary['duration']:.2f}s",
            ""
        ])
        
        # Individual test results
        lines.append("TEST DETAILS:")
        for i, cmd_result in enumerate(results["commands"]):
            status = "PASS" if cmd_result["test_passed"] else "FAIL"
            lines.extend([
                f"  {i+1}. {cmd_result['test_name']}: {status}",
                f"     Command: {cmd_result['command']}",
                f"     Success: {cmd_result['success']}",
                f"     Attempts: {len(cmd_result['attempts'])}",
                ""
            ])
            
            if not cmd_result["test_passed"] and cmd_result["final_result"]:
                final = cmd_result["final_result"]
                if final.get("error"):
                    lines.append(f"     Error: {final['error']}")
                if final.get("stderr"):
                    lines.append(f"     Stderr: {final['stderr'][:200]}...")
                lines.append("")
        
        # Write report
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        self.logger.info(f"Text report saved: {filepath}")
        return filepath
    
    def _generate_json_report(self, results: Dict[str, Any], timestamp: str) -> str:
        """JSONレポートを生成"""
        filename = f"test_report_{timestamp}.json"
        filepath = os.path.join(self.config.test_output_dir, filename)
        
        import json
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"JSON report saved: {filepath}")
        return filepath
    
    def _generate_html_report(self, results: Dict[str, Any], timestamp: str) -> str:
        """HTMLレポートを生成（簡易版）"""
        filename = f"test_report_{timestamp}.html"
        filepath = os.path.join(self.config.test_output_dir, filename)
        
        # Simple HTML template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BraveJIG Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .summary {{ background-color: #f0f0f0; padding: 20px; margin-bottom: 20px; }}
                .pass {{ color: green; }}
                .fail {{ color: red; }}
                .test-item {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <h1>BraveJIG Hardware Test Report</h1>
            <p>Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Suite: {results['suite_name']}</p>
                <p>Total Tests: {results['summary']['total']}</p>
                <p>Passed: <span class="pass">{results['summary']['passed']}</span></p>
                <p>Failed: <span class="fail">{results['summary']['failed']}</span></p>
                <p>Duration: {results['summary']['duration']:.2f}s</p>
            </div>
            
            <h2>Test Details</h2>
        """
        
        for i, cmd_result in enumerate(results["commands"]):
            status_class = "pass" if cmd_result["test_passed"] else "fail"
            status_text = "PASS" if cmd_result["test_passed"] else "FAIL"
            
            html_content += f"""
            <div class="test-item">
                <h3>{i+1}. {cmd_result['test_name']}: <span class="{status_class}">{status_text}</span></h3>
                <p><strong>Command:</strong> {cmd_result['command']}</p>
                <p><strong>Success:</strong> {cmd_result['success']}</p>
                <p><strong>Attempts:</strong> {len(cmd_result['attempts'])}</p>
            """
            
            if not cmd_result["test_passed"] and cmd_result["final_result"]:
                final = cmd_result["final_result"]
                if final.get("error"):
                    html_content += f"<p><strong>Error:</strong> {final['error']}</p>"
            
            html_content += "</div>"
        
        html_content += """
            </body>
            </html>
        """
        
        with open(filepath, 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML report saved: {filepath}")
        return filepath


class HardwareTestRunner:
    """実機テストランナーメインクラス"""
    
    def __init__(self, config: HardwareTestConfig = None):
        self.config = config or HardwareTestConfig()
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize components
        self.command_runner = HardwareCommandRunner(self.config)
        self.device_detector = SerialDeviceDetector()
    
    def setup_test_environment(self) -> Dict[str, Any]:
        """テスト環境をセットアップ"""
        setup_result = {
            "success": False,
            "detected_devices": [],
            "selected_router": None,
            "test_config": None
        }
        
        self.logger.info("Setting up hardware test environment...")
        
        # Detect BraveJIG routers
        detected_routers = self.device_detector.detect_bjig_routers()
        setup_result["detected_devices"] = detected_routers
        
        if not detected_routers:
            setup_result["error"] = "No BraveJIG router devices detected"
            return setup_result
        
        # Test connectivity for each detected device
        working_routers = []
        for device in detected_routers:
            connectivity = self.device_detector.test_router_connectivity(
                device["port"], self.config.baudrate, self.config.timeout
            )
            device["connectivity"] = connectivity
            
            if connectivity["connected"]:
                working_routers.append(device)
        
        if not working_routers:
            setup_result["error"] = "No working BraveJIG routers found"
            return setup_result
        
        # Select the first working router
        selected_router = working_routers[0]
        setup_result["selected_router"] = selected_router
        
        # Update config with detected router
        if not self.config.port:
            self.config.port = selected_router["port"]
        
        setup_result["success"] = True
        setup_result["test_config"] = {
            "port": self.config.port,
            "baudrate": self.config.baudrate,
            "timeout": self.config.timeout
        }
        
        self.logger.info(f"Test environment ready with router at: {self.config.port}")
        return setup_result
    
    def run_hardware_tests(self, test_suite_name: str = "default") -> Dict[str, Any]:
        """実機テストを実行"""
        # Define test suites
        test_suites = self.get_predefined_test_suites()
        
        if test_suite_name not in test_suites:
            available = ", ".join(test_suites.keys())
            raise ValueError(f"Unknown test suite: {test_suite_name}. Available: {available}")
        
        test_commands = test_suites[test_suite_name]
        
        # Run the test suite
        results = self.command_runner.run_test_suite(test_suite_name, test_commands)
        
        # Generate reports
        if self.config.generate_reports:
            text_report = self.command_runner.generate_test_report(results, "text")
            json_report = self.command_runner.generate_test_report(results, "json")
            
            results["reports"] = {
                "text": text_report,
                "json": json_report
            }
        
        return results
    
    def get_predefined_test_suites(self) -> Dict[str, List[Dict[str, Any]]]:
        """定義済みテストスイートを取得"""
        return {
            "router_basic": [
                {
                    "name": "Get Router Version",
                    "args": ["router", "get-version"],
                    "expected_success": True
                },
                {
                    "name": "Get Router Device ID", 
                    "args": ["router", "get-device-id"],
                    "expected_success": True
                },
                {
                    "name": "Router Keep Alive",
                    "args": ["router", "keep-alive"],
                    "expected_success": True
                }
            ],
            
            "illuminance_basic": [
                {
                    "name": "Illuminance Get Parameter",
                    "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                    "expected_success": True,
                    "options": {"timeout": 45}  # Longer timeout for parameter uplink
                },
                {
                    "name": "Illuminance Instant Uplink",
                    "args": ["module", "instant-uplink", "--module-id", "2468800203400004"],
                    "expected_success": True,
                    "options": {"timeout": 30}
                }
            ],
            
            "illuminance_advanced": [
                {
                    "name": "Get Current Parameters",
                    "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                    "expected_success": True,
                    "options": {"timeout": 45}
                },
                {
                    "name": "Set Parameter (Uplink Interval)",
                    "args": ["module", "set-parameter", "--module-id", "2468800203400004", 
                            "--data", '{"sensor_uplink_interval": 120}'],
                    "expected_success": True,
                    "options": {"timeout": 45}
                },
                {
                    "name": "Verify Parameter Change",
                    "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                    "expected_success": True,
                    "options": {"timeout": 45}
                },
                {
                    "name": "Reset Parameters",
                    "args": ["module", "set-parameter", "--module-id", "2468800203400004",
                            "--data", '{"sensor_uplink_interval": 60}'],
                    "expected_success": True,
                    "options": {"timeout": 45}
                }
            ],
            
            "default": [
                {
                    "name": "Router Version Check",
                    "args": ["router", "get-version"],
                    "expected_success": True
                },
                {
                    "name": "Basic Module Test",
                    "args": ["module", "get-parameter", "--module-id", "2468800203400004"],
                    "expected_success": True,
                    "options": {"timeout": 45}
                }
            ]
        }
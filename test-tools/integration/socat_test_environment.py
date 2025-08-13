"""
BraveJIG Socat Integration Test Environment

socatを利用したリアルタイム通信監視統合テスト環境
- 物理JIGルーターへの2系統接続
- コマンド送信とリアルタイム監視の並行実行
- プロトコル解析とテスト自動化

Author: BraveJIG CLI Development Team
Date: 2025-08-10
"""

import os
import sys
import subprocess
import time
import threading
import signal
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SocatTestConfig:
    """Socatテスト環境設定"""
    physical_device: str = "/dev/ttyACM0"
    baudrate: int = 38400
    monitor_pty: str = "/tmp/bjig_monitor"
    cli_pty: str = "/tmp/bjig_cli"
    socat_log_file: str = "/tmp/bjig_socat.log"
    monitor_log_file: str = "/tmp/bjig_monitor.log"
    test_results_dir: str = "/tmp/bjig_test_results"


class SocatProcessManager:
    """Socatプロセス管理"""
    
    def __init__(self, config: SocatTestConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.socat_process: Optional[subprocess.Popen] = None
        self.monitor_process: Optional[subprocess.Popen] = None
        
    def start_socat_bridge(self) -> bool:
        """Socatブリッジを開始"""
        try:
            # Kill existing socat processes
            self._cleanup_existing_processes()
            
            # Remove old PTY files
            self._remove_pty_files()
            
            # Validate physical device
            if not os.path.exists(self.config.physical_device):
                self.logger.error(f"Physical device not found: {self.config.physical_device}")
                return False
            
            # Start socat bridge
            socat_cmd = [
                "socat",
                f"{self.config.physical_device},{self.config.baudrate},raw,echo=0",
                f"PTY,link={self.config.monitor_pty},raw,echo=0,waitslave",
                f"PTY,link={self.config.cli_pty},raw,echo=0,waitslave"
            ]
            
            self.logger.info(f"Starting socat bridge: {' '.join(socat_cmd)}")
            
            # Start socat process
            self.socat_process = subprocess.Popen(
                socat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait for PTY files to be created
            max_wait = 10  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                if (os.path.exists(self.config.monitor_pty) and 
                    os.path.exists(self.config.cli_pty)):
                    self.logger.info("Socat bridge established successfully")
                    return True
                time.sleep(0.1)
            
            self.logger.error("Timeout waiting for PTY files to be created")
            self._stop_socat_bridge()
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to start socat bridge: {str(e)}")
            return False
    
    def _cleanup_existing_processes(self):
        """既存のsocatプロセスをクリーンアップ"""
        try:
            # Find and kill existing socat processes for our PTYs
            result = subprocess.run(
                ["pgrep", "-f", f"socat.*{self.config.monitor_pty}"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            self.logger.info(f"Killed existing socat process: {pid}")
                        except ProcessLookupError:
                            pass  # Process already dead
        except Exception as e:
            self.logger.warning(f"Error cleaning up processes: {str(e)}")
    
    def _remove_pty_files(self):
        """古いPTYファイルを削除"""
        for pty_file in [self.config.monitor_pty, self.config.cli_pty]:
            try:
                if os.path.exists(pty_file):
                    os.remove(pty_file)
                    self.logger.debug(f"Removed old PTY file: {pty_file}")
            except Exception as e:
                self.logger.warning(f"Error removing PTY file {pty_file}: {str(e)}")
    
    def _stop_socat_bridge(self):
        """Socatブリッジを停止"""
        if self.socat_process:
            try:
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(self.socat_process.pid), signal.SIGTERM)
                
                # Wait for process to terminate
                try:
                    self.socat_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't respond to SIGTERM
                    os.killpg(os.getpgid(self.socat_process.pid), signal.SIGKILL)
                    self.socat_process.wait()
                
                self.logger.info("Socat bridge stopped")
            except Exception as e:
                self.logger.error(f"Error stopping socat bridge: {str(e)}")
            finally:
                self.socat_process = None
    
    def stop_environment(self):
        """テスト環境全体を停止"""
        self._stop_socat_bridge()
        self._remove_pty_files()
    
    def is_running(self) -> bool:
        """Socatブリッジが動作中かチェック"""
        return (self.socat_process is not None and 
                self.socat_process.poll() is None and
                os.path.exists(self.config.monitor_pty) and
                os.path.exists(self.config.cli_pty))


class RealtimeProtocolMonitor:
    """リアルタイムプロトコル監視"""
    
    def __init__(self, config: SocatTestConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_monitoring = False
        self.packet_log: List[Dict[str, Any]] = []
        self.event_callbacks: List[Callable] = []
        
        # Create results directory
        os.makedirs(self.config.test_results_dir, exist_ok=True)
    
    def start_monitoring(self) -> bool:
        """プロトコル監視を開始"""
        if self.is_monitoring:
            self.logger.warning("Monitor already running")
            return True
        
        if not os.path.exists(self.config.monitor_pty):
            self.logger.error(f"Monitor PTY not found: {self.config.monitor_pty}")
            return False
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("Real-time protocol monitoring started")
        return True
    
    def stop_monitoring(self):
        """プロトコル監視を停止"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("Protocol monitoring stopped")
    
    def _monitor_loop(self):
        """監視ループ（別スレッドで実行）"""
        try:
            with open(self.config.monitor_pty, 'rb') as monitor_port:
                buffer = b''
                
                while self.is_monitoring:
                    try:
                        # Read data with timeout
                        data = os.read(monitor_port.fileno(), 1024)
                        if data:
                            buffer += data
                            
                            # Process complete packets
                            while buffer:
                                packet, remaining = self._extract_packet(buffer)
                                if packet:
                                    self._process_packet(packet)
                                    buffer = remaining
                                else:
                                    break
                        
                        time.sleep(0.001)  # Small delay to prevent busy waiting
                        
                    except OSError:
                        # Handle read timeout or other OS errors
                        time.sleep(0.01)
                        continue
                        
        except Exception as e:
            self.logger.error(f"Monitor loop error: {str(e)}")
    
    def _extract_packet(self, buffer: bytes) -> Tuple[Optional[bytes], bytes]:
        """バッファから完全なパケットを抽出"""
        if len(buffer) < 2:
            return None, buffer
        
        # BraveJIGプロトコルのパケット解析
        protocol_version = buffer[0]
        packet_type = buffer[1]
        
        if protocol_version != 0x01:
            # Invalid protocol version, skip this byte
            return None, buffer[1:]
        
        try:
            if packet_type == 0x00:  # Uplink notification
                if len(buffer) < 21:  # Minimum uplink size
                    return None, buffer
                
                # Extract sensor data length (assuming it follows standard format)
                # This is a simplified extraction - real implementation would be more robust
                min_packet_size = 21  # Basic uplink header
                if len(buffer) >= min_packet_size:
                    # For now, assume fixed-size packets or extract based on content
                    # In a real implementation, you'd parse the actual data length
                    packet_size = min(len(buffer), min_packet_size + 50)  # Reasonable max
                    return buffer[:packet_size], buffer[packet_size:]
                    
            elif packet_type == 0x01:  # Downlink response
                min_size = 20  # Minimum downlink response size
                if len(buffer) >= min_size:
                    return buffer[:min_size], buffer[min_size:]
                    
            elif packet_type == 0x02:  # JIG Info response
                if len(buffer) < 4:
                    return None, buffer
                    
                # JIG Info responses have variable length
                # Parse based on command type
                if len(buffer) >= 4:
                    # Simple heuristic - take what we have up to reasonable limit
                    packet_size = min(len(buffer), 64)  # Reasonable max for JIG Info
                    return buffer[:packet_size], buffer[packet_size:]
            
            # Unknown packet type or insufficient data
            return None, buffer
            
        except Exception as e:
            self.logger.error(f"Packet extraction error: {str(e)}")
            return None, buffer[1:]  # Skip one byte and try again
    
    def _process_packet(self, packet: bytes):
        """パケットを処理して記録"""
        timestamp = time.time()
        
        packet_info = {
            "timestamp": timestamp,
            "raw_data": packet.hex(' ').upper(),
            "length": len(packet),
            "direction": self._determine_direction(packet),
            "parsed": self._parse_packet(packet)
        }
        
        # Add to log
        self.packet_log.append(packet_info)
        
        # Log to console (optional)
        direction = packet_info["direction"]
        parsed = packet_info["parsed"]
        self.logger.info(f"{direction}: {parsed.get('summary', 'Unknown packet')}")
        
        # Notify callbacks
        for callback in self.event_callbacks:
            try:
                callback(packet_info)
            except Exception as e:
                self.logger.error(f"Callback error: {str(e)}")
    
    def _determine_direction(self, packet: bytes) -> str:
        """パケット方向を判定（簡易版）"""
        if len(packet) < 2:
            return "UNKNOWN"
        
        packet_type = packet[1]
        
        if packet_type == 0x00:
            return "UPLINK"
        elif packet_type == 0x01:
            return "DOWNLINK_RESPONSE"
        elif packet_type == 0x02:
            return "JIG_INFO_RESPONSE"
        else:
            return "UNKNOWN"
    
    def _parse_packet(self, packet: bytes) -> Dict[str, Any]:
        """パケットを解析（簡易版）"""
        parsed = {"type": "unknown", "summary": "Unknown packet"}
        
        try:
            if len(packet) < 2:
                return parsed
            
            protocol_version = packet[0]
            packet_type = packet[1]
            
            parsed["protocol_version"] = f"0x{protocol_version:02X}"
            parsed["packet_type"] = f"0x{packet_type:02X}"
            
            if packet_type == 0x00:  # Uplink
                parsed["type"] = "uplink"
                if len(packet) >= 18:
                    sensor_id = struct.unpack('<H', packet[16:18])[0]
                    parsed["sensor_id"] = f"0x{sensor_id:04X}"
                    
                    if sensor_id == 0x0121:
                        parsed["summary"] = "Illuminance sensor uplink"
                    elif sensor_id == 0x0000:
                        parsed["summary"] = "Parameter info uplink"
                    else:
                        parsed["summary"] = f"Sensor uplink (ID: {sensor_id:04X})"
                        
            elif packet_type == 0x01:  # Downlink response
                parsed["type"] = "downlink_response"
                if len(packet) >= 20:
                    result = packet[19]
                    parsed["result"] = f"0x{result:02X}"
                    parsed["summary"] = f"Downlink response ({'Success' if result == 0 else 'Error'})"
                    
            elif packet_type == 0x02:  # JIG Info response
                parsed["type"] = "jig_info_response"
                parsed["summary"] = "JIG Info response"
                
        except Exception as e:
            parsed["error"] = str(e)
        
        return parsed
    
    def add_event_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """イベントコールバックを追加"""
        self.event_callbacks.append(callback)
    
    def get_packet_log(self) -> List[Dict[str, Any]]:
        """パケットログを取得"""
        return self.packet_log.copy()
    
    def clear_packet_log(self):
        """パケットログをクリア"""
        self.packet_log.clear()
    
    def save_packet_log(self, filename: str = None) -> str:
        """パケットログをファイルに保存"""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"packet_log_{timestamp}.json"
        
        filepath = os.path.join(self.config.test_results_dir, filename)
        
        import json
        with open(filepath, 'w') as f:
            json.dump(self.packet_log, f, indent=2, default=str)
        
        self.logger.info(f"Packet log saved to: {filepath}")
        return filepath


class IntegratedTestRunner:
    """統合テストランナー"""
    
    def __init__(self, config: SocatTestConfig = None):
        self.config = config or SocatTestConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.socat_manager = SocatProcessManager(self.config)
        self.monitor = RealtimeProtocolMonitor(self.config)
        self.test_results: List[Dict[str, Any]] = []
    
    def setup_environment(self) -> bool:
        """テスト環境をセットアップ"""
        self.logger.info("Setting up integrated test environment...")
        
        # Start socat bridge
        if not self.socat_manager.start_socat_bridge():
            self.logger.error("Failed to start socat bridge")
            return False
        
        # Give some time for the bridge to stabilize
        time.sleep(1)
        
        # Start monitoring
        if not self.monitor.start_monitoring():
            self.logger.error("Failed to start monitoring")
            self.cleanup_environment()
            return False
        
        self.logger.info("Integrated test environment ready")
        return True
    
    def cleanup_environment(self):
        """テスト環境をクリーンアップ"""
        self.logger.info("Cleaning up test environment...")
        
        self.monitor.stop_monitoring()
        self.socat_manager.stop_environment()
        
        # Save final logs
        if self.monitor.packet_log:
            log_file = self.monitor.save_packet_log()
            self.logger.info(f"Final packet log saved: {log_file}")
    
    def run_cli_command(self, command_args: List[str], timeout: float = 30.0) -> Dict[str, Any]:
        """CLIコマンドを実行（監視付き）"""
        if not self.socat_manager.is_running():
            raise RuntimeError("Test environment not running")
        
        # Clear packet log for this test
        self.monitor.clear_packet_log()
        
        # Build full command
        main_script = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'main.py')
        full_command = [
            'python3', main_script,
            '--port', self.config.cli_pty,
            '--baud', str(self.config.baudrate)
        ] + command_args
        
        result = {
            'command': ' '.join(command_args),
            'success': False,
            'return_code': None,
            'stdout': '',
            'stderr': '',
            'duration': 0.0,
            'packet_count': 0,
            'packets': []
        }
        
        self.logger.info(f"Running command: {result['command']}")
        
        start_time = time.time()
        
        try:
            # Execute command
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
            
            # Wait a bit for any remaining packets
            time.sleep(0.5)
            
            # Collect packet information
            result['packets'] = self.monitor.get_packet_log()
            result['packet_count'] = len(result['packets'])
            
            # Add to test results
            self.test_results.append(result)
            
            # Log results
            status = "✅" if result['success'] else "❌"
            self.logger.info(
                f"{status} Command completed ({result['duration']:.2f}s, {result['packet_count']} packets)")
            
            if result['success'] and result['stdout']:
                for line in result['stdout'].strip().split('\n'):
                    self.logger.info(f"  📄 {line}")
            
            if not result['success'] and result['stderr']:
                for line in result['stderr'].strip().split('\n'):
                    self.logger.error(f"  🚨 {line}")
        
        except subprocess.TimeoutExpired:
            result['error'] = f"Command timed out after {timeout} seconds"
            result['duration'] = timeout
            self.logger.error(f"⏰ Command timed out after {timeout}s")
        
        return result
    
    def run_test_sequence(self, test_name: str, commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """テストシーケンスを実行"""
        self.logger.info(f"Running test sequence: {test_name}")
        
        sequence_result = {
            "test_name": test_name,
            "start_time": time.time(),
            "commands": [],
            "success": True,
            "total_packets": 0,
            "total_duration": 0.0
        }
        
        for i, cmd_config in enumerate(commands):
            cmd_args = cmd_config.get("args", [])
            timeout = cmd_config.get("timeout", 30.0)
            name = cmd_config.get("name", f"Command {i+1}")
            
            self.logger.info(f"  Step {i+1}: {name}")
            
            cmd_result = self.run_cli_command(cmd_args, timeout)
            cmd_result["step_name"] = name
            
            sequence_result["commands"].append(cmd_result)
            sequence_result["total_packets"] += cmd_result["packet_count"]
            
            if not cmd_result["success"]:
                sequence_result["success"] = False
                
                # Check if we should stop on failure
                if cmd_config.get("stop_on_failure", True):
                    self.logger.error(f"Test sequence failed at step {i+1}")
                    break
            
            # Inter-command delay
            delay = cmd_config.get("delay", 0.0)
            if delay > 0:
                time.sleep(delay)
        
        sequence_result["end_time"] = time.time()
        sequence_result["total_duration"] = sequence_result["end_time"] - sequence_result["start_time"]
        
        # Log summary
        status = "✅" if sequence_result["success"] else "❌"
        self.logger.info(
            f"{status} Test sequence '{test_name}' completed: "
            f"{sequence_result['total_duration']:.2f}s, "
            f"{sequence_result['total_packets']} packets, "
            f"{len([c for c in sequence_result['commands'] if c['success']])}/{len(sequence_result['commands'])} passed"
        )
        
        return sequence_result
    
    def save_test_results(self, filename: str = None) -> str:
        """テスト結果を保存"""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"test_results_{timestamp}.json"
        
        filepath = os.path.join(self.config.test_results_dir, filename)
        
        import json
        with open(filepath, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        self.logger.info(f"Test results saved to: {filepath}")
        return filepath


def run_socat_test_environment():
    """Socatテスト環境の実行例"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test runner
    config = SocatTestConfig()
    runner = IntegratedTestRunner(config)
    
    try:
        # Setup environment
        if not runner.setup_environment():
            print("Failed to setup test environment")
            return
        
        print("Test environment ready!")
        print(f"Monitor PTY: {config.monitor_pty}")
        print(f"CLI PTY: {config.cli_pty}")
        print("You can now run commands in another terminal or use the test sequences")
        
        # Example: Run basic router tests
        router_tests = [
            {"name": "Get Version", "args": ["router", "get-version"], "timeout": 10},
            {"name": "Get Device ID", "args": ["router", "get-device-id"], "timeout": 10},
            {"name": "Keep Alive", "args": ["router", "keep-alive"], "timeout": 10}
        ]
        
        result = runner.run_test_sequence("Basic Router Tests", router_tests)
        print(f"\nTest sequence result: {result['success']}")
        
        # Save results
        results_file = runner.save_test_results()
        print(f"Results saved to: {results_file}")
        
        # Keep environment running for manual testing
        print("\nPress Enter to stop the test environment...")
        input()
        
    finally:
        runner.cleanup_environment()


if __name__ == "__main__":
    run_socat_test_environment()
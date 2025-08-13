"""
BraveJIG Router Command Base Classes

このモジュールは、全てのルーターコマンドの共通基盤を提供します。
BraveJIG仕様書に基づくJIG Info Request/Response パターンを統一的に実装します。

Key features:
- 統一的なコマンドインターフェース
- JIG Info プロトコルの共通処理
- エラーハンドリングとレスポンス解析
- 結果のJSON出力サポート

Author: BraveJIG CLI Development Team
Date: 2025-07-31
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Union
import json
import logging

from protocol.bjig_protocol import (
    BraveJIGProtocol, JigInfoResponse, ErrorNotification, 
    JigInfoCommand
)


@dataclass
class CommandResult:
    """Router command execution result"""
    success: bool
    command_name: str
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    raw_response: Optional[bytes] = None

    def to_json(self) -> str:
        """Convert result to JSON string"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return asdict(self)


class BaseRouterCommand(ABC):
    """
    Base class for all BraveJIG router commands
    
    This class provides common functionality for JIG Info request/response
    handling based on the BraveJIG router specification.
    """

    def __init__(self, protocol: BraveJIGProtocol):
        """
        Initialize base router command
        
        Args:
            protocol: BraveJIG protocol instance for request/response handling
        """
        self.protocol = protocol
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    @abstractmethod
    def command_name(self) -> str:
        """Command name for identification and logging"""
        pass

    @property
    @abstractmethod
    def jig_info_cmd(self) -> JigInfoCommand:
        """JIG Info command code for this operation"""
        pass

    def create_request(self, **kwargs) -> bytes:
        """
        Create JIG Info request for this command
        
        Args:
            **kwargs: Command-specific parameters
            
        Returns:
            bytes: Encoded JIG Info request packet
        """
        cmd_code = self.get_command_code(**kwargs)
        return self.protocol.create_jig_info_request(cmd_code)

    def get_command_code(self, **kwargs) -> int:
        """
        Get the specific command code for this request
        
        Base implementation returns the default command code.
        Override in subclasses for commands with variable codes.
        
        Args:
            **kwargs: Command-specific parameters
            
        Returns:
            int: JIG Info command code
        """
        return self.jig_info_cmd

    def parse_response(self, response_data: bytes) -> CommandResult:
        """
        Parse JIG Info response data
        
        Args:
            response_data: Raw response bytes from router
            
        Returns:
            CommandResult: Parsed command result
        """
        try:
            response = self.protocol.parse_response(response_data)
            
            if isinstance(response, ErrorNotification):
                return self._handle_error_response(response)
            elif isinstance(response, JigInfoResponse):
                return self._handle_success_response(response)
            else:
                return CommandResult(
                    success=False,
                    command_name=self.command_name,
                    error_message=f"Unexpected response type: {type(response)}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to parse response: {e}")
            return CommandResult(
                success=False,
                command_name=self.command_name,
                error_message=f"Response parsing error: {str(e)}",
                raw_response=response_data
            )

    def _handle_error_response(self, error: ErrorNotification) -> CommandResult:
        """Handle error notification response"""
        error_reason = self.protocol.interpret_error_reason(error.reason)
        
        return CommandResult(
            success=False,
            command_name=self.command_name,
            error_message=f"Router error: {error_reason} (Code: 0x{error.reason:02x})",
            response_data={
                "error_type": "router_error",
                "error_code": error.reason,
                "error_description": error_reason,
                "cmd": error.cmd,
                "local_time": error.local_time,
                "unix_time": error.unix_time
            }
        )

    def _handle_success_response(self, response: JigInfoResponse) -> CommandResult:
        """
        Handle successful JIG Info response
        
        Base implementation provides common response handling.
        Override in subclasses for command-specific response processing.
        
        Args:
            response: JIG Info response object
            
        Returns:
            CommandResult: Parsed success result
        """
        response_data = self.process_response_data(response)
        
        return CommandResult(
            success=True,
            command_name=self.command_name,
            response_data=response_data
        )

    @abstractmethod
    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """
        Process command-specific response data
        
        This method should be implemented by each command to extract
        and format the relevant data from the JIG Info response.
        
        Args:
            response: JIG Info response object
            
        Returns:
            Dict[str, Any]: Processed response data
        """
        pass

    def execute(self, **kwargs) -> CommandResult:
        """
        Execute the router command
        
        This is a convenience method that combines request creation
        and response parsing. For actual communication, use the
        request/response methods separately with a communication layer.
        
        Args:
            **kwargs: Command-specific parameters
            
        Returns:
            CommandResult: Command execution result
        """
        try:
            request_data = self.create_request(**kwargs)
            self.logger.info(f"Created {self.command_name} request: {request_data.hex()}")
            
            # Note: Actual communication would happen here
            # This is just a placeholder for the command structure
            return CommandResult(
                success=True,
                command_name=self.command_name,
                response_data={
                    "message": f"{self.command_name} request created successfully",
                    "request_size": len(request_data),
                    "command_code": self.get_command_code(**kwargs)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to execute {self.command_name}: {e}")
            return CommandResult(
                success=False,
                command_name=self.command_name,
                error_message=f"Command execution error: {str(e)}"
            )

    def format_output(self, result: CommandResult, output_format: str = "json") -> str:
        """
        Format command result for output
        
        Args:
            result: Command execution result
            output_format: Output format ("json", "text")
            
        Returns:
            str: Formatted output string
        """
        if output_format.lower() == "json":
            return result.to_json()
        else:
            # Text format
            if result.success:
                return f"{self.command_name} completed successfully"
            else:
                return f"{self.command_name} failed: {result.error_message}"


class SimpleRouterCommand(BaseRouterCommand):
    """
    Base class for simple router commands with no additional parameters
    
    This class is suitable for commands like router_start, router_stop,
    get_version, keep_alive that don't require additional parameters.
    """

    def process_response_data(self, response: JigInfoResponse) -> Dict[str, Any]:
        """Default response processing for simple commands"""
        return {
            "command": self.command_name,
            "protocol_version": response.protocol_version,
            "packet_type": response.packet_type,
            "cmd": response.cmd,
            "local_time": response.local_time,
            "unix_time": response.unix_time,
            "data": response.data.hex() if response.data else None,
            "data_length": len(response.data) if response.data else 0
        }


class ParameterizedRouterCommand(BaseRouterCommand):
    """
    Base class for router commands that require additional parameters
    
    This class is suitable for commands like get_device_id, set_scan_mode
    that require additional parameters and have variable command codes.
    """

    @abstractmethod
    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate command parameters
        
        Args:
            **kwargs: Command parameters to validate
            
        Returns:
            bool: True if parameters are valid
            
        Raises:
            ValueError: If parameters are invalid
        """
        pass

    def create_request(self, **kwargs) -> bytes:
        """Create request with parameter validation"""
        if not self.validate_parameters(**kwargs):
            raise ValueError(f"Invalid parameters for {self.command_name}")
        
        return super().create_request(**kwargs)
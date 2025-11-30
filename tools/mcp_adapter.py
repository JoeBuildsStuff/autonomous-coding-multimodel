"""
MCP Adapter for Browser Automation
===================================

Adapter that spawns and communicates with MCP servers via stdio.
This allows non-Claude providers (OpenAI, Grok) to use MCP tools
like puppeteer-mcp-server for browser automation.

MCP (Model Context Protocol) is Anthropic's open protocol for tool communication.
This adapter implements the client side of the protocol.
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Optional
from pathlib import Path


class MCPError(Exception):
    """Error from MCP communication."""
    pass


class MCPAdapter:
    """
    Adapter to communicate with MCP servers via stdio.
    
    Spawns the MCP server as a subprocess and communicates using
    JSON-RPC over stdin/stdout.
    
    Example usage:
        adapter = MCPAdapter("npx", ["puppeteer-mcp-server"])
        await adapter.start()
        result = await adapter.call_tool("puppeteer_navigate", {"url": "https://example.com"})
        await adapter.stop()
    """
    
    def __init__(
        self,
        command: str,
        args: list[str],
        working_dir: Optional[Path] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the MCP adapter.
        
        Args:
            command: The command to run (e.g., "npx")
            args: Arguments to pass to the command (e.g., ["puppeteer-mcp-server"])
            working_dir: Optional working directory for the subprocess
            timeout: Timeout for MCP requests in seconds
        """
        self.command = command
        self.args = args
        self.working_dir = working_dir
        self.timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._initialized = False
        self._lock = asyncio.Lock()
    
    @property
    def is_running(self) -> bool:
        """Check if the MCP server process is running."""
        return self._process is not None and self._process.poll() is None
    
    async def start(self) -> None:
        """
        Start the MCP server process and initialize the connection.
        
        Raises:
            MCPError: If the server fails to start or initialize
        """
        if self.is_running:
            return
        
        try:
            # Start the MCP server process
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                cwd=self.working_dir,
            )
            
            # Send initialize request per MCP protocol
            response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": False
                    }
                },
                "clientInfo": {
                    "name": "autonomous-coding-multimodel",
                    "version": "1.0.0"
                }
            })
            
            if "error" in response:
                raise MCPError(f"MCP initialization failed: {response['error']}")
            
            # Send initialized notification
            await self._send_notification("notifications/initialized", {})
            
            self._initialized = True
            
        except FileNotFoundError:
            raise MCPError(
                f"MCP server command not found: {self.command}\n"
                "Make sure npx is available (comes with Node.js)."
            )
        except Exception as e:
            await self.stop()
            raise MCPError(f"Failed to start MCP server: {e}")
    
    async def stop(self) -> None:
        """Stop the MCP server process gracefully."""
        if self._process:
            try:
                # Try graceful shutdown
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                
                # Wait briefly for graceful exit
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self._process = None
                self._initialized = False
    
    async def list_tools(self) -> list[dict]:
        """
        List available tools from the MCP server.
        
        Returns:
            List of tool definitions
        """
        response = await self._send_request("tools/list", {})
        
        if "error" in response:
            raise MCPError(f"Failed to list tools: {response['error']}")
        
        return response.get("result", {}).get("tools", [])
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """
        Call an MCP tool and return the result.
        
        Args:
            tool_name: Name of the tool (with or without mcp__puppeteer__ prefix)
            arguments: Tool arguments
            
        Returns:
            Dict with the tool result or error
        """
        # Remove the mcp__puppeteer__ prefix if present
        if tool_name.startswith("mcp__puppeteer__"):
            tool_name = tool_name.replace("mcp__puppeteer__", "")
        
        # Also handle the puppeteer_ prefix used in OpenAI tool definitions
        if tool_name.startswith("puppeteer_"):
            # Keep as-is - this matches the MCP server's tool names
            pass
        
        try:
            response = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            if "error" in response:
                return {"error": f"MCP error: {response['error'].get('message', str(response['error']))}"}
            
            result = response.get("result", {})
            
            # MCP returns content as a list of content blocks
            content = result.get("content", [])
            if content:
                # Extract text content
                text_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        # For screenshots, return base64 data info
                        text_parts.append(f"[Image: {block.get('mimeType', 'image/png')}]")
                
                return {"result": "\n".join(text_parts)}
            
            return {"result": str(result)}
            
        except Exception as e:
            return {"error": f"MCP communication failed: {str(e)}"}
    
    async def health_check(self) -> bool:
        """
        Check if the MCP server is responsive.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self.is_running:
            return False
        
        try:
            # Try listing tools as a health check
            await self.list_tools()
            return True
        except Exception:
            return False
    
    async def _send_request(self, method: str, params: dict) -> dict:
        """
        Send a JSON-RPC request and wait for response.
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            Response dict
        """
        async with self._lock:
            if not self._process or not self._process.stdin or not self._process.stdout:
                raise MCPError("MCP server not running")
            
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params
            }
            
            request_line = json.dumps(request) + "\n"
            
            # Write request to stdin
            try:
                self._process.stdin.write(request_line)
                self._process.stdin.flush()
            except BrokenPipeError:
                raise MCPError("MCP server connection broken")
            
            # Read response from stdout with timeout
            try:
                response_line = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self._process.stdout.readline
                    ),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                raise MCPError(f"MCP request timed out after {self.timeout}s")
            
            if not response_line:
                # Check for errors in stderr
                if self._process.stderr:
                    stderr = self._process.stderr.read()
                    if stderr:
                        raise MCPError(f"MCP server error: {stderr}")
                raise MCPError("MCP server closed connection")
            
            try:
                return json.loads(response_line)
            except json.JSONDecodeError as e:
                raise MCPError(f"Invalid JSON response from MCP server: {e}")
    
    async def _send_notification(self, method: str, params: dict) -> None:
        """
        Send a JSON-RPC notification (no response expected).
        
        Args:
            method: RPC method name
            params: Method parameters
        """
        async with self._lock:
            if not self._process or not self._process.stdin:
                raise MCPError("MCP server not running")
            
            notification = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params
            }
            
            notification_line = json.dumps(notification) + "\n"
            
            try:
                self._process.stdin.write(notification_line)
                self._process.stdin.flush()
            except BrokenPipeError:
                raise MCPError("MCP server connection broken")
    
    async def __aenter__(self) -> "MCPAdapter":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


class PuppeteerMCPAdapter(MCPAdapter):
    """
    Specialized MCP adapter for the puppeteer-mcp-server.
    
    Provides convenience methods for common browser operations.
    """
    
    def __init__(
        self,
        working_dir: Optional[Path] = None,
        timeout: float = 60.0,  # Browser ops may take longer
    ):
        """
        Initialize the Puppeteer MCP adapter.
        
        Args:
            working_dir: Optional working directory
            timeout: Timeout for operations in seconds
        """
        super().__init__(
            command="npx",
            args=["puppeteer-mcp-server"],
            working_dir=working_dir,
            timeout=timeout,
        )
    
    async def connect_to_chrome(
        self,
        target_url: Optional[str] = None,
        debug_port: int = 9222,
    ) -> dict[str, Any]:
        """
        Connect to an existing Chrome instance with remote debugging.
        
        Args:
            target_url: Optional URL of the target tab
            debug_port: Chrome debugging port (default: 9222)
            
        Returns:
            Connection result
        """
        args = {}
        if target_url:
            args["targetUrl"] = target_url
        if debug_port != 9222:
            args["debugPort"] = debug_port
        
        return await self.call_tool("puppeteer_connect_active_tab", args)
    
    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
        return await self.call_tool("puppeteer_navigate", {"url": url})
    
    async def screenshot(
        self,
        name: str,
        selector: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> dict[str, Any]:
        """Take a screenshot."""
        args = {"name": name}
        if selector:
            args["selector"] = selector
        if width:
            args["width"] = width
        if height:
            args["height"] = height
        return await self.call_tool("puppeteer_screenshot", args)
    
    async def click(self, selector: str) -> dict[str, Any]:
        """Click an element."""
        return await self.call_tool("puppeteer_click", {"selector": selector})
    
    async def fill(self, selector: str, value: str) -> dict[str, Any]:
        """Fill an input field."""
        return await self.call_tool("puppeteer_fill", {
            "selector": selector,
            "value": value
        })
    
    async def select(self, selector: str, value: str) -> dict[str, Any]:
        """Select a dropdown option."""
        return await self.call_tool("puppeteer_select", {
            "selector": selector,
            "value": value
        })
    
    async def hover(self, selector: str) -> dict[str, Any]:
        """Hover over an element."""
        return await self.call_tool("puppeteer_hover", {"selector": selector})
    
    async def evaluate(self, script: str) -> dict[str, Any]:
        """Execute JavaScript in the browser."""
        return await self.call_tool("puppeteer_evaluate", {"script": script})

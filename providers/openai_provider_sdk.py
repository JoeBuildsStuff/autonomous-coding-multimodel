"""
OpenAI Provider using OpenAI Agents SDK
======================================

Refactored provider that uses the OpenAI Agents SDK for simplified
agent loop, tool management, and MCP integration.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator, Any, List, Optional

from agents import Agent, Runner, ItemHelpers
from agents.mcp import MCPServerStdio
from openai.types.responses import ResponseTextDeltaEvent

from .base import (
    BaseProvider,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from tools.executor import ToolExecutor
from tools.sdk_tools import SDK_TOOLS, set_executor
from tools.mcp_adapter import MCPError


# System prompt for coding tasks
SYSTEM_PROMPT = """You are an expert full-stack developer building a production-quality web application.

You have access to tools to read, write, and edit files, search for files and content, run bash commands, and control a browser.

Browser Tools:
- puppeteer_navigate: Navigate to a URL
- puppeteer_click: Click an element by CSS selector
- puppeteer_fill: Fill an input field
- puppeteer_screenshot: Take a screenshot
- puppeteer_evaluate: Execute JavaScript in the browser
- puppeteer_connect_active_tab: Connect to an existing Chrome instance

When working on tasks:
1. Read existing files to understand the codebase before making changes
2. Make targeted edits when possible rather than rewriting entire files
3. Use bash commands to run npm, git, and other development tools
4. Test your changes by running the application when appropriate
5. Use browser tools to verify the UI and test user interactions

Always explain what you're doing and why before using tools."""


class OpenAIProvider(BaseProvider):
    """
    Provider for OpenAI models using the OpenAI Agents SDK.
    
    Uses the SDK's Agent + Runner for simplified agent loop and tool management.
    Browser automation via puppeteer-mcp-server is enabled by default.
    """
    
    def __init__(
        self,
        model: str,
        project_dir: Path,
        enable_browser: bool = True,
        chrome_debug_port: int = 9222,
    ):
        super().__init__(model, project_dir)
        self._agent: Optional[Agent] = None
        self._tool_executor: Optional[ToolExecutor] = None
        self._mcp_server: Optional[MCPServerStdio] = None
        self._current_message: Optional[str] = None
        self._enable_browser = enable_browser
        self._chrome_debug_port = chrome_debug_port
        self._browser_available = False
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "OPENAI_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "gpt-5-nano"
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        return [
            "gpt-5-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "o1",
            "o1-mini",
        ]
    
    async def __aenter__(self) -> "OpenAIProvider":
        """Enter async context."""
        # Create tool executor
        self._tool_executor = ToolExecutor(self.project_dir)
        
        # Set executor for SDK tools
        set_executor(self._tool_executor)
        
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize MCP server for browser tools (default ON)
        mcp_servers = []
        if self._enable_browser:
            try:
                self._mcp_server = MCPServerStdio(
                    name="Puppeteer MCP Server",
                    params={
                        "command": "npx",
                        "args": ["-y", "puppeteer-mcp-server"],
                    },
                    cache_tools_list=True,
                )
                await self._mcp_server.__aenter__()
                mcp_servers.append(self._mcp_server)
                self._browser_available = True
            except Exception as e:
                # Log warning but continue - browser tools just won't be available
                print(f"   - Warning: Browser tools unavailable ({e})")
                print(f"   - Make sure Node.js/npx is installed")
                self._mcp_server = None
                self._browser_available = False
        
        # Create agent with tools and MCP servers
        self._agent = Agent(
            name="Coding Assistant",
            instructions=SYSTEM_PROMPT,
            tools=SDK_TOOLS,
            mcp_servers=mcp_servers,
            model=self.model,
        )
        
        # Count tools
        tool_count = len(SDK_TOOLS)
        if self._browser_available and self._mcp_server:
            # Tools will be discovered automatically by SDK
            # Rough estimate: add 8 for typical browser tools
            tool_count += 8
        
        print(f"Initialized OpenAIProvider (SDK)")
        print(f"   - Model: {self.model}")
        print(f"   - Project directory: {self.project_dir.resolve()}")
        print(f"   - Tools: {tool_count} available (via SDK)")
        if self._browser_available:
            print(f"   - MCP servers: puppeteer (browser automation)")
        print()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        # Stop MCP server if running
        if self._mcp_server:
            try:
                await self._mcp_server.__aexit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
            self._mcp_server = None
        
        self._agent = None
        self._tool_executor = None
        self._browser_available = False
    
    async def query(self, message: str) -> None:
        """Send a query and prepare for response streaming."""
        if not self._agent:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        self._current_message = message
    
    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Execute the agentic loop with tool use using the SDK.
        
        Converts SDK streaming events to our message format.
        """
        if not self._agent or not self._current_message:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        # Use SDK's streaming runner
        result = Runner.run_streamed(self._agent, input=self._current_message)
        
        # Track current message blocks
        current_text_blocks = []
        current_tool_use_blocks = []
        pending_tool_results = []
        
        async for event in result.stream_events():
            # Handle different event types
            if event.type == "run_item_stream_event":
                item = event.item
                
                if item.type == "message_output_item":
                    # Text output from the agent
                    text_content = ItemHelpers.text_message_output(item)
                    if text_content:
                        current_text_blocks.append(TextBlock(text=text_content))
                
                elif item.type == "tool_call_item":
                    # Tool is being called
                    # Extract tool call details from raw_item
                    raw_item = getattr(item, "raw_item", None)
                    if raw_item:
                        # Extract name, id, and arguments from raw_item
                        tool_name = getattr(raw_item, "name", "unknown")
                        tool_id = getattr(raw_item, "id", None) or getattr(raw_item, "call_id", "unknown")
                        
                        # Extract input/arguments - different types have different field names
                        tool_input = {}
                        if hasattr(raw_item, "arguments"):
                            args = raw_item.arguments
                            if isinstance(args, str):
                                try:
                                    tool_input = json.loads(args)
                                except json.JSONDecodeError:
                                    tool_input = {"raw": args}
                            elif isinstance(args, dict):
                                tool_input = args
                        elif hasattr(raw_item, "input"):
                            tool_input = raw_item.input
                    else:
                        # Fallback if raw_item is not available
                        tool_name = "unknown"
                        tool_id = ""
                        tool_input = {}
                    
                    current_tool_use_blocks.append(ToolUseBlock(
                        name=tool_name,
                        input=tool_input,
                        id=tool_id,
                    ))
                
                elif item.type == "tool_call_output_item":
                    # Tool execution completed
                    tool_id = getattr(item, "tool_call_id", "")
                    output = getattr(item, "output", "")
                    is_error = getattr(item, "is_error", False)
                    
                    # Check if we should yield previous blocks first
                    if current_text_blocks or current_tool_use_blocks:
                        content_blocks = current_text_blocks + current_tool_use_blocks
                        yield AssistantMessage(content=content_blocks)
                        current_text_blocks = []
                        current_tool_use_blocks = []
                    
                    # Yield tool result
                    yield UserMessage(content=[
                        ToolResultBlock(
                            content=str(output),
                            tool_use_id=tool_id,
                            is_error=is_error,
                        )
                    ])
            
            elif event.type == "raw_response_event":
                # Handle raw text deltas for streaming text
                if isinstance(event.data, ResponseTextDeltaEvent):
                    delta = event.data.delta
                    if delta:
                        # Accumulate text deltas
                        if current_text_blocks:
                            current_text_blocks[-1].text += delta
                        else:
                            current_text_blocks.append(TextBlock(text=delta))
        
        # Yield any remaining blocks
        if current_text_blocks or current_tool_use_blocks:
            content_blocks = current_text_blocks + current_tool_use_blocks
            yield AssistantMessage(content=content_blocks)
        
        # Clear the current message
        self._current_message = None


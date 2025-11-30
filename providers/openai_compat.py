"""
OpenAI-Compatible Base Provider
===============================

Base implementation for providers using the OpenAI API format,
including OpenAI and Grok.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator, Any, List, Optional
from abc import abstractmethod

from openai import OpenAI

from .base import (
    BaseProvider,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from tools import (
    get_tool_definitions,
    get_all_tool_definitions,
    ToolExecutor,
    PuppeteerMCPAdapter,
    MCPError,
)


# System prompt for coding tasks
SYSTEM_PROMPT = """You are an expert full-stack developer building a production-quality web application.

You have access to tools to read, write, and edit files, search for files and content, and run bash commands.

When working on tasks:
1. Read existing files to understand the codebase before making changes
2. Make targeted edits when possible rather than rewriting entire files
3. Use bash commands to run npm, git, and other development tools
4. Test your changes by running the application when appropriate

Always explain what you're doing and why before using tools."""


# Extended system prompt when browser tools are enabled
SYSTEM_PROMPT_WITH_BROWSER = """You are an expert full-stack developer building a production-quality web application.

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


class OpenAICompatibleProvider(BaseProvider):
    """
    Base provider for OpenAI-compatible APIs.
    
    Implements the agentic loop with tool use for APIs that follow
    the OpenAI chat completions format.
    
    Subclasses must implement:
    - _create_client(): Return configured OpenAI client
    - get_required_env_var(): Return env var name for API key
    - get_default_model(): Return default model identifier
    """
    
    def __init__(
        self,
        model: str,
        project_dir: Path,
        enable_browser: bool = False,
        chrome_debug_port: int = 9222,
    ):
        """
        Initialize the provider.
        
        Args:
            model: Model identifier
            project_dir: Project directory for sandboxing
            enable_browser: Whether to enable browser automation tools
            chrome_debug_port: Chrome debugging port for browser connection
        """
        super().__init__(model, project_dir)
        self._client: OpenAI | None = None
        self._tool_executor: ToolExecutor | None = None
        self._mcp_adapter: Optional[PuppeteerMCPAdapter] = None
        self._messages: List[dict] = []
        self._pending_response: List[Any] | None = None
        self._enable_browser = enable_browser
        self._chrome_debug_port = chrome_debug_port
    
    @abstractmethod
    def _create_client(self) -> OpenAI:
        """Create and return the OpenAI client. Override in subclasses."""
        pass
    
    async def __aenter__(self) -> "OpenAICompatibleProvider":
        """Enter async context."""
        self._client = self._create_client()
        self._tool_executor = ToolExecutor(self.project_dir)
        self._messages = []
        
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize MCP adapter for browser tools if enabled
        if self._enable_browser:
            try:
                self._mcp_adapter = PuppeteerMCPAdapter(
                    working_dir=self.project_dir
                )
                await self._mcp_adapter.start()
                self._tool_executor.set_mcp_adapter(self._mcp_adapter)
                
                print(f"   - Browser tools: enabled (puppeteer-mcp-server)")
                print(f"   - Chrome debug port: {self._chrome_debug_port}")
            except MCPError as e:
                print(f"   - Browser tools: failed to start ({e})")
                self._mcp_adapter = None
        
        tool_count = len(get_all_tool_definitions(include_browser=self._enable_browser))
        
        print(f"Initialized {self.__class__.__name__}")
        print(f"   - Model: {self.model}")
        print(f"   - Project directory: {self.project_dir.resolve()}")
        print(f"   - Tools: {tool_count} available")
        if self._enable_browser and not self._mcp_adapter:
            print(f"   - Note: Browser tools requested but not available")
        print()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        # Stop MCP adapter if running
        if self._mcp_adapter:
            await self._mcp_adapter.stop()
            self._mcp_adapter = None
        
        self._client = None
        self._tool_executor = None
        self._messages = []
        self._pending_response = None
    
    async def query(self, message: str) -> None:
        """
        Send a query and prepare for response streaming.
        
        The actual API call and tool execution loop happens in receive_response().
        """
        if not self._client:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        # Add system message if this is the first message
        if not self._messages:
            system_prompt = (
                SYSTEM_PROMPT_WITH_BROWSER if self._enable_browser
                else SYSTEM_PROMPT
            )
            self._messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add the user message
        self._messages.append({
            "role": "user",
            "content": message
        })
        
        # Signal that we have a pending query
        self._pending_response = []
    
    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Execute the agentic loop with tool use.
        
        This method handles the full conversation loop:
        1. Send messages to the model
        2. If model requests tools, execute them
        3. Send tool results back to model
        4. Repeat until model gives final response
        """
        if not self._client or not self._tool_executor:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        max_iterations = 100  # Safety limit
        iteration = 0
        
        # Get tool definitions including browser tools if enabled
        tools = get_all_tool_definitions(include_browser=self._enable_browser)
        
        while iteration < max_iterations:
            iteration += 1
            
            # Make API call
            response = self._client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                tools=tools,
                tool_choice="auto",
            )
            
            assistant_message = response.choices[0].message
            
            # Add assistant message to history
            self._messages.append(assistant_message.model_dump())
            
            # Convert to our message format and yield
            content_blocks = []
            
            # Handle text content
            if assistant_message.content:
                content_blocks.append(TextBlock(text=assistant_message.content))
            
            # Handle tool calls
            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    content_blocks.append(ToolUseBlock(
                        name=tool_call.function.name,
                        input=json.loads(tool_call.function.arguments),
                        id=tool_call.id,
                    ))
            
            if content_blocks:
                yield AssistantMessage(content=content_blocks)
            
            # If no tool calls, we're done
            if not assistant_message.tool_calls:
                break
            
            # Execute tools and collect results
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Use async execution for browser tools
                result = await self._tool_executor.execute_async(tool_name, tool_args)
                
                # Format result for API
                if "error" in result:
                    result_content = f"Error: {result['error']}"
                    is_error = True
                else:
                    result_content = result.get("result", "")
                    is_error = False
                
                # Add to message history
                self._messages.append({
                    "role": "tool",
                    "content": result_content,
                    "tool_call_id": tool_call.id,
                })
                
                tool_results.append(ToolResultBlock(
                    content=result_content,
                    tool_use_id=tool_call.id,
                    is_error=is_error,
                ))
            
            # Yield tool results
            if tool_results:
                yield UserMessage(content=tool_results)
        
        if iteration >= max_iterations:
            yield AssistantMessage(content=[
                TextBlock(text="\n[Warning: Maximum iterations reached]")
            ])

"""
Grok Provider
=============

Provider implementation for xAI's Grok models via OpenAI-compatible API.

Models:
- grok-4-1-fast-reasoning: Best tool-calling model, 2M context, reasoning enabled
- grok-4-1-fast-non-reasoning: Best tool-calling model, 2M context, no reasoning (faster)
- grok-4-fast-reasoning: SOTA cost-efficiency, 2M context, reasoning enabled
- grok-4-fast-non-reasoning: SOTA cost-efficiency, 2M context, no reasoning
- grok-4: Flagship model, 256K context
- grok-3: Previous gen flagship, 131K context
- grok-3-mini: Smaller model, supports reasoning_effort parameter

Note: Only grok-3-mini supports the reasoning_effort parameter.
Other models use -reasoning/-non-reasoning model variants instead.

Browser automation via puppeteer-mcp-server is enabled by default.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator, Any, List, Optional

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


# System prompt for coding tasks (includes browser tools by default)
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


class GrokProvider(BaseProvider):
    """
    Provider for xAI's Grok models.
    
    Uses the OpenAI-compatible API at api.x.ai.
    
    Browser automation via puppeteer-mcp-server is enabled by default.
    """
    
    def __init__(
        self,
        model: str,
        project_dir: Path,
        enable_browser: bool = True,  # Default ON like original repo
        chrome_debug_port: int = 9222,
    ):
        super().__init__(model, project_dir)
        self._client: OpenAI | None = None
        self._tool_executor: ToolExecutor | None = None
        self._mcp_adapter: Optional[PuppeteerMCPAdapter] = None
        self._messages: List[dict] = []
        self._enable_browser = enable_browser
        self._chrome_debug_port = chrome_debug_port
        self._browser_available = False  # Track if browser tools actually started
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "XAI_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "grok-4-1-fast-reasoning"
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        return [
            # Grok 4.1 Fast - best tool-calling model, 2M context
            "grok-4-1-fast-reasoning",      # Reasoning enabled (default)
            "grok-4-1-fast-non-reasoning",  # Non-reasoning (faster)
            # Grok 4 Fast - SOTA cost-efficiency, 2M context
            "grok-4-fast-reasoning",
            "grok-4-fast-non-reasoning",
            # Grok 4 - flagship model, 256K context
            "grok-4",
            # Grok 3 models
            "grok-3",
            "grok-3-mini",  # Only model that supports reasoning_effort parameter
        ]
    
    @property
    def _is_grok3_mini(self) -> bool:
        """Check if this is grok-3-mini which supports reasoning_effort parameter."""
        return "grok-3-mini" in self.model.lower()
    
    @property
    def _is_reasoning_variant(self) -> bool:
        """Check if this is a reasoning variant (for display purposes)."""
        return "reasoning" in self.model.lower() and "non-reasoning" not in self.model.lower()
    
    def _create_client(self) -> OpenAI:
        """Create Grok client using OpenAI SDK with custom base URL."""
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            raise ValueError(
                "XAI_API_KEY environment variable not set.\n"
                "Get your API key from: https://console.x.ai/"
            )
        
        return OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
    
    async def __aenter__(self) -> "GrokProvider":
        """Enter async context."""
        self._client = self._create_client()
        self._tool_executor = ToolExecutor(self.project_dir)
        self._messages = []
        
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize MCP adapter for browser tools (default ON)
        if self._enable_browser:
            try:
                self._mcp_adapter = PuppeteerMCPAdapter(
                    working_dir=self.project_dir
                )
                await self._mcp_adapter.start()
                self._tool_executor.set_mcp_adapter(self._mcp_adapter)
                self._browser_available = True
            except MCPError as e:
                # Log warning but continue - browser tools just won't be available
                print(f"   - Warning: Browser tools unavailable ({e})")
                print(f"   - Make sure Node.js/npx is installed")
                self._mcp_adapter = None
                self._browser_available = False
        
        # Count tools (include browser if available)
        tool_count = len(get_all_tool_definitions(include_browser=self._browser_available))
        
        print(f"Initialized GrokProvider")
        print(f"   - Model: {self.model}")
        if self._is_reasoning_variant:
            print(f"   - Mode: reasoning enabled")
        elif "non-reasoning" in self.model.lower():
            print(f"   - Mode: non-reasoning (faster)")
        if self._is_grok3_mini:
            print(f"   - Reasoning effort: medium")
        print(f"   - Project directory: {self.project_dir.resolve()}")
        print(f"   - Tools: {tool_count} available")
        if self._browser_available:
            print(f"   - MCP servers: puppeteer (browser automation)")
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
        self._browser_available = False
    
    async def query(self, message: str) -> None:
        """Send a query and prepare for response streaming."""
        if not self._client:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        # Add system message if this is the first message
        if not self._messages:
            self._messages.append({
                "role": "system",
                "content": SYSTEM_PROMPT
            })
        
        # Add the user message
        self._messages.append({
            "role": "user",
            "content": message
        })
    
    async def receive_response(self) -> AsyncIterator[Any]:
        """Execute the agentic loop with tool use."""
        if not self._client or not self._tool_executor:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        max_iterations = 100
        iteration = 0
        
        # Get tools including browser if available
        tools = get_all_tool_definitions(include_browser=self._browser_available)
        
        while iteration < max_iterations:
            iteration += 1
            
            # Build API call parameters
            api_params = {
                "model": self.model,
                "messages": self._messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            
            # Add reasoning effort ONLY for grok-3-mini (other models don't support it)
            # Grok 4.x models use -reasoning/-non-reasoning model variants instead
            if self._is_grok3_mini:
                api_params["reasoning_effort"] = "medium"
            
            # Make API call
            response = self._client.chat.completions.create(**api_params)
            
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

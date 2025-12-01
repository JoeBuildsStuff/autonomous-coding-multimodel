"""
OpenAI Provider
===============

Provider implementation for OpenAI models (GPT-4, GPT-5, etc.).
Supports both the chat completions API and the newer responses API for GPT-5 models.
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


class OpenAIProvider(BaseProvider):
    """
    Provider for OpenAI models.
    
    Uses the responses API for GPT-5 models (with reasoning support)
    and falls back to chat completions for older models.
    
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
        self._use_responses_api = model.startswith("gpt-5")
        self._enable_browser = enable_browser
        self._chrome_debug_port = chrome_debug_port
        self._browser_available = False  # Track if browser tools actually started
    
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
    
    def _create_client(self) -> OpenAI:
        """Create OpenAI client."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set.\n"
                "Get your API key from: https://platform.openai.com/api-keys"
            )
        
        return OpenAI(api_key=api_key)
    
    async def __aenter__(self) -> "OpenAIProvider":
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
        
        print(f"Initialized OpenAIProvider")
        print(f"   - Model: {self.model}")
        print(f"   - API: {'responses' if self._use_responses_api else 'chat.completions'}")
        if self._use_responses_api:
            print(f"   - Reasoning: medium effort")
            print(f"   - Verbosity: medium")
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
        
        if self._use_responses_api:
            async for msg in self._receive_response_responses_api():
                yield msg
        else:
            async for msg in self._receive_response_chat_api():
                yield msg
    
    async def _receive_response_responses_api(self) -> AsyncIterator[Any]:
        """Handle GPT-5 models using the responses API with reasoning."""
        max_iterations = 100
        iteration = 0
        
        # Get tools including browser if available
        tool_defs = get_all_tool_definitions(include_browser=self._browser_available)
        
        # Convert tools to the responses API format
        tools = []
        for tool_def in tool_defs:
            tools.append({
                "type": "function",
                "name": tool_def["function"]["name"],
                "description": tool_def["function"]["description"],
                "parameters": tool_def["function"]["parameters"],
            })
        
        while iteration < max_iterations:
            iteration += 1
            
            # Build input from messages
            input_messages = []
            for msg in self._messages:
                if msg["role"] == "system":
                    input_messages.append({
                        "role": "system",
                        "content": msg["content"]
                    })
                elif msg["role"] == "user":
                    input_messages.append({
                        "role": "user",
                        "content": msg["content"]
                    })
                elif msg["role"] == "assistant":
                    input_messages.append({
                        "role": "assistant",
                        "content": msg.get("content", "")
                    })
                elif msg["role"] == "tool":
                    input_messages.append({
                        "role": "tool",
                        "content": msg["content"],
                        "tool_call_id": msg.get("tool_call_id", "")
                    })
            
            # Make API call using responses endpoint
            response = self._client.responses.create(
                model=self.model,
                input=input_messages,
                text={
                    "format": {"type": "text"},
                    "verbosity": "medium"
                },
                reasoning={
                    "effort": "medium"
                },
                tools=tools if tools else [],
                store=True,
                include=[
                    "reasoning.encrypted_content",
                ]
            )
            
            # Process response
            content_blocks = []
            tool_calls = []
            
            # Handle the response output
            for output_item in response.output:
                if output_item.type == "message":
                    for content in output_item.content:
                        if content.type == "text":
                            content_blocks.append(TextBlock(text=content.text))
                elif output_item.type == "function_call":
                    tool_calls.append({
                        "id": output_item.call_id,
                        "name": output_item.name,
                        "arguments": output_item.arguments
                    })
                    content_blocks.append(ToolUseBlock(
                        name=output_item.name,
                        input=json.loads(output_item.arguments) if output_item.arguments else {},
                        id=output_item.call_id,
                    ))
            
            # Add assistant response to history
            self._messages.append({
                "role": "assistant",
                "content": "".join(b.text for b in content_blocks if isinstance(b, TextBlock)),
                "tool_calls": tool_calls
            })
            
            if content_blocks:
                yield AssistantMessage(content=content_blocks)
            
            # If no tool calls, we're done
            if not tool_calls:
                break
            
            # Execute tools and collect results
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = json.loads(tool_call["arguments"]) if tool_call["arguments"] else {}
                
                # Use async execution for browser tools
                result = await self._tool_executor.execute_async(tool_name, tool_args)
                
                if "error" in result:
                    result_content = f"Error: {result['error']}"
                    is_error = True
                else:
                    result_content = result.get("result", "")
                    is_error = False
                
                self._messages.append({
                    "role": "tool",
                    "content": result_content,
                    "tool_call_id": tool_call["id"],
                })
                
                tool_results.append(ToolResultBlock(
                    content=result_content,
                    tool_use_id=tool_call["id"],
                    is_error=is_error,
                ))
            
            if tool_results:
                yield UserMessage(content=tool_results)
        
        if iteration >= max_iterations:
            yield AssistantMessage(content=[
                TextBlock(text="\n[Warning: Maximum iterations reached]")
            ])
    
    async def _receive_response_chat_api(self) -> AsyncIterator[Any]:
        """Handle older models using the chat completions API."""
        max_iterations = 100
        iteration = 0
        
        # Get tools including browser if available
        tools = get_all_tool_definitions(include_browser=self._browser_available)
        
        while iteration < max_iterations:
            iteration += 1
            
            response = self._client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                tools=tools,
                tool_choice="auto",
            )
            
            assistant_message = response.choices[0].message
            self._messages.append(assistant_message.model_dump())
            
            content_blocks = []
            
            if assistant_message.content:
                content_blocks.append(TextBlock(text=assistant_message.content))
            
            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    content_blocks.append(ToolUseBlock(
                        name=tool_call.function.name,
                        input=json.loads(tool_call.function.arguments),
                        id=tool_call.id,
                    ))
            
            if content_blocks:
                yield AssistantMessage(content=content_blocks)
            
            if not assistant_message.tool_calls:
                break
            
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Use async execution for browser tools
                result = await self._tool_executor.execute_async(tool_name, tool_args)
                
                if "error" in result:
                    result_content = f"Error: {result['error']}"
                    is_error = True
                else:
                    result_content = result.get("result", "")
                    is_error = False
                
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
            
            if tool_results:
                yield UserMessage(content=tool_results)
        
        if iteration >= max_iterations:
            yield AssistantMessage(content=[
                TextBlock(text="\n[Warning: Maximum iterations reached]")
            ])

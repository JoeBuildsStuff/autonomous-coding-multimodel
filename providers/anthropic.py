"""
Anthropic Provider
==================

Provider implementation for Anthropic's Claude models using the Claude Agent SDK.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator, Any, List

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

from .base import (
    BaseProvider,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from security import bash_security_hook


# Puppeteer MCP tools for browser automation
PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]


class AnthropicProvider(BaseProvider):
    """
    Provider for Anthropic's Claude models via the Claude Agent SDK.
    
    This provider wraps the Claude SDK client and provides the full
    feature set including sandboxing, MCP tools, and security hooks.
    """
    
    def __init__(self, model: str, project_dir: Path):
        super().__init__(model, project_dir)
        self._client: ClaudeSDKClient | None = None
        self._current_query: str | None = None
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "ANTHROPIC_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "claude-haiku-4-5-20250514"
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        return [
            "claude-haiku-4-5-20250514",
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]
    
    def _create_client(self) -> ClaudeSDKClient:
        """Create and configure the Claude SDK client."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set.\n"
                "Get your API key from: https://console.anthropic.com/"
            )
        
        # Create comprehensive security settings
        security_settings = {
            "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [
                    "Read(./**)",
                    "Write(./**)",
                    "Edit(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                    "Bash(*)",
                    *PUPPETEER_TOOLS,
                ],
            },
        }
        
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Write settings file
        settings_file = self.project_dir / ".claude_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)
        
        print(f"Created security settings at {settings_file}")
        print("   - Sandbox enabled (OS-level bash isolation)")
        print(f"   - Filesystem restricted to: {self.project_dir.resolve()}")
        print("   - Bash commands restricted to allowlist (see security.py)")
        print("   - MCP servers: puppeteer (browser automation)")
        print()
        
        return ClaudeSDKClient(
            options=ClaudeCodeOptions(
                model=self.model,
                system_prompt="You are an expert full-stack developer building a production-quality web application.",
                allowed_tools=[
                    *BUILTIN_TOOLS,
                    *PUPPETEER_TOOLS,
                ],
                mcp_servers={
                    "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
                },
                hooks={
                    "PreToolUse": [
                        HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                    ],
                },
                max_turns=1000,
                cwd=str(self.project_dir.resolve()),
                settings=str(settings_file.resolve()),
            )
        )
    
    async def __aenter__(self) -> "AnthropicProvider":
        """Enter async context - create and enter SDK client."""
        self._client = self._create_client()
        await self._client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - cleanup SDK client."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None
    
    async def query(self, message: str) -> None:
        """Send a query to Claude."""
        if not self._client:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        self._current_query = message
        await self._client.query(message)
    
    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Receive streaming response from Claude.
        
        Converts SDK message types to our standardized types.
        """
        if not self._client:
            raise RuntimeError("Provider not initialized. Use 'async with' context manager.")
        
        async for msg in self._client.receive_response():
            msg_type = type(msg).__name__
            
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                # Convert SDK blocks to our types
                content_blocks = []
                for block in msg.content:
                    block_type = type(block).__name__
                    
                    if block_type == "TextBlock" and hasattr(block, "text"):
                        content_blocks.append(TextBlock(text=block.text))
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        content_blocks.append(ToolUseBlock(
                            name=block.name,
                            input=getattr(block, "input", {}),
                            id=getattr(block, "id", ""),
                        ))
                
                yield AssistantMessage(content=content_blocks)
            
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                # Convert tool results
                content_blocks = []
                for block in msg.content:
                    block_type = type(block).__name__
                    
                    if block_type == "ToolResultBlock":
                        content_blocks.append(ToolResultBlock(
                            content=str(getattr(block, "content", "")),
                            tool_use_id=getattr(block, "tool_use_id", ""),
                            is_error=getattr(block, "is_error", False),
                        ))
                
                if content_blocks:
                    yield UserMessage(content=content_blocks)

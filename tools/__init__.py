"""
Tools Package
=============

Tool definitions and executor for OpenAI-compatible providers.
Includes both filesystem/bash tools and browser automation tools.
"""

from .definitions import TOOL_DEFINITIONS, get_tool_definitions, get_tool_names
from .browser_definitions import (
    BROWSER_TOOL_DEFINITIONS,
    BROWSER_TOOL_NAMES,
    get_browser_tool_definitions,
    get_browser_tool_names,
    is_browser_tool,
)
from .executor import ToolExecutor, SecurityError
from .mcp_adapter import MCPAdapter, MCPError, PuppeteerMCPAdapter
from .sdk_tools import SDK_TOOLS, set_executor

__all__ = [
    # Core tool definitions
    "TOOL_DEFINITIONS",
    "get_tool_definitions",
    "get_tool_names",
    # Browser tool definitions
    "BROWSER_TOOL_DEFINITIONS",
    "BROWSER_TOOL_NAMES",
    "get_browser_tool_definitions",
    "get_browser_tool_names",
    "is_browser_tool",
    # Combined tool helper
    "get_all_tool_definitions",
    # Executor
    "ToolExecutor",
    "SecurityError",
    # MCP adapter
    "MCPAdapter",
    "MCPError",
    "PuppeteerMCPAdapter",
    # SDK tools (for OpenAI Agents SDK)
    "SDK_TOOLS",
    "set_executor",
]


def get_all_tool_definitions(include_browser: bool = False) -> list[dict]:
    """
    Get all tool definitions, optionally including browser tools.
    
    Args:
        include_browser: Whether to include browser automation tools
        
    Returns:
        List of tool definitions in OpenAI format
    """
    tools = list(TOOL_DEFINITIONS)
    if include_browser:
        tools.extend(BROWSER_TOOL_DEFINITIONS)
    return tools

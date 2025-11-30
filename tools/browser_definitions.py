"""
Browser Tool Definitions for OpenAI-Compatible Providers
=========================================================

Defines OpenAI-style function schemas for browser automation tools.
These tools map to the puppeteer-mcp-server's capabilities.
"""

BROWSER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "puppeteer_connect_active_tab",
            "description": (
                "Connect to an existing Chrome instance with remote debugging enabled. "
                "Chrome must be started with --remote-debugging-port flag. "
                "Use this to connect to a browser that's already running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "targetUrl": {
                        "type": "string",
                        "description": "Optional URL of the target tab to connect to",
                    },
                    "debugPort": {
                        "type": "number",
                        "description": "Chrome debugging port (default: 9222)",
                        "default": 9222,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_navigate",
            "description": "Navigate the browser to a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_screenshot",
            "description": (
                "Take a screenshot of the current page or a specific element. "
                "Returns the screenshot as a base64-encoded image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the screenshot file",
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector for element to screenshot",
                    },
                    "width": {
                        "type": "number",
                        "description": "Width in pixels (default: 800)",
                    },
                    "height": {
                        "type": "number",
                        "description": "Height in pixels (default: 600)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_click",
            "description": "Click an element on the page using a CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for element to click",
                    },
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_fill",
            "description": "Fill out an input field with text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input field",
                    },
                    "value": {
                        "type": "string",
                        "description": "Text value to fill in",
                    },
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_select",
            "description": "Select an option from a dropdown/select element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the select element",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value of the option to select",
                    },
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_hover",
            "description": "Hover the mouse over an element on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for element to hover over",
                    },
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_evaluate",
            "description": (
                "Execute JavaScript code in the browser console. "
                "Returns the result of the script execution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "JavaScript code to execute",
                    },
                },
                "required": ["script"],
            },
        },
    },
]


# List of browser tool names
BROWSER_TOOL_NAMES = [
    tool["function"]["name"] for tool in BROWSER_TOOL_DEFINITIONS
]


def get_browser_tool_definitions() -> list[dict]:
    """Return the list of browser tool definitions."""
    return BROWSER_TOOL_DEFINITIONS


def get_browser_tool_names() -> list[str]:
    """Return list of browser tool names."""
    return BROWSER_TOOL_NAMES


def is_browser_tool(tool_name: str) -> bool:
    """Check if a tool name is a browser tool."""
    # Handle both prefixed and unprefixed names
    if tool_name.startswith("mcp__puppeteer__"):
        tool_name = tool_name.replace("mcp__puppeteer__", "")
    return tool_name in BROWSER_TOOL_NAMES

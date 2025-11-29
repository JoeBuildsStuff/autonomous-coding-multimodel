"""
Tool Definitions for OpenAI-Compatible Providers
================================================

Defines OpenAI-style function schemas that mirror the Claude CLI tools.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file. Supports optional offset/limit to "
                "page through very large files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file (within the project directory)",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Optional 0-based line number to start reading from",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Optional number of lines to read starting at offset",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates parents if needed and overwrites the entire file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file (within the project directory)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace existing text within a file. The target string must exist; "
                "set replace_all true to update every occurrence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to replace",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Set true to replace every occurrence (default replaces first only)",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "List files or directories matching a glob pattern within the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (supports ** for recursion)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional directory to scope the search (defaults to project root)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": (
                "Search file contents using ripgrep-compatible options. Supports line "
                "context, glob/type filters, and output throttling."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex or literal pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search (default '.')",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Optional glob passed to rg --glob",
                    },
                    "type": {
                        "type": "string",
                        "description": "Optional ripgrep file type filter (e.g. 'ts', 'py')",
                    },
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                        "description": "Choose detailed content, file list, or counts",
                    },
                    "-A": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of lines to show after each match",
                    },
                    "-B": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of lines to show before each match",
                    },
                    "-C": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of lines to show before and after each match",
                    },
                    "-n": {
                        "type": "boolean",
                        "description": "Show line numbers (default true for content mode)",
                    },
                    "-i": {
                        "type": "boolean",
                        "description": "Case-insensitive search",
                    },
                    "head_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Limit output lines/entries (similar to piping through head)",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Skip this many output lines before applying head_limit",
                    },
                    "multiline": {
                        "type": "boolean",
                        "description": "Enable multiline dotall mode (rg -U --multiline-dotall)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Execute a bash command from the project root. Commands are validated "
                "against the same allowlist used by the Claude CLI demo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run (e.g. 'npm install', 'git status')",
                    }
                },
                "required": ["command"],
            },
        },
    },
]


def get_tool_definitions() -> list[dict]:
    """Return the list of tool definitions."""
    return TOOL_DEFINITIONS


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [tool["function"]["name"] for tool in TOOL_DEFINITIONS]

"""
Tool Definitions for OpenAI-Compatible Providers
================================================

Defines tools in OpenAI function calling format for use with
OpenAI, Grok, and other compatible APIs.
"""

# Tool definitions in OpenAI function calling format
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path. Use this to examine existing code, configuration files, or any text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the file to read (relative to project directory)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file at the specified path. Creates the file if it doesn't exist, or overwrites if it does. Use this to create new files or completely replace file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the file to write (relative to project directory)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Make a targeted edit to a file by replacing a specific string with new content. Use this for surgical edits rather than rewriting entire files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the file to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace (must match exactly)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory. Returns file and directory names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the directory to list (use '.' for current directory)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files matching a glob pattern. Useful for finding files by name or extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match (e.g., '**/*.py' for all Python files)"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "Search for a pattern in file contents using grep-like functionality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The text pattern to search for"
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory or file to search in (use '.' for entire project)"
                    },
                    "include": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py')"
                    }
                },
                "required": ["pattern", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command. Only certain commands are allowed for security: ls, cat, head, tail, wc, grep, cp, mkdir, chmod, pwd, npm, node, git, ps, lsof, sleep, pkill (dev processes only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
]


def get_tool_definitions() -> list[dict]:
    """Return the list of tool definitions."""
    return TOOL_DEFINITIONS


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [tool["function"]["name"] for tool in TOOL_DEFINITIONS]

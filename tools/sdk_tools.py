"""
SDK-based Tool Definitions using OpenAI Agents SDK
==================================================

These tools use the @function_tool decorator for automatic schema generation.
They wrap the existing ToolExecutor for backward compatibility.
"""

from typing import Annotated, Optional
from pathlib import Path

from agents import function_tool

from security import validate_bash_command
from .executor import ToolExecutor


# Global executor instance (set by provider)
_executor: Optional[ToolExecutor] = None


def set_executor(executor: ToolExecutor) -> None:
    """Set the global tool executor instance."""
    global _executor
    _executor = executor


@function_tool
def read_file(
    path: Annotated[str, "Relative path to the file (within the project directory)"],
    offset: Annotated[Optional[int], "Optional 0-based line number to start reading from"] = 0,
    limit: Annotated[Optional[int], "Optional number of lines to read starting at offset"] = None,
) -> str:
    """Read the contents of a file. Supports optional offset/limit to page through very large files."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    result = _executor.execute("read_file", {
        "path": path,
        "offset": offset,
        "limit": limit,
    })
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


@function_tool
def write_file(
    path: Annotated[str, "Relative path to the file (within the project directory)"],
    content: Annotated[str, "Content to write"],
) -> str:
    """Write content to a file. Creates parents if needed and overwrites the entire file."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    result = _executor.execute("write_file", {
        "path": path,
        "content": content,
    })
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


@function_tool
def edit_file(
    path: Annotated[str, "Relative path to the file"],
    old_string: Annotated[str, "Exact text to replace"],
    new_string: Annotated[str, "Replacement text"],
    replace_all: Annotated[Optional[bool], "Set true to replace every occurrence (default replaces first only)"] = False,
) -> str:
    """Replace existing text within a file. The target string must exist; set replace_all true to update every occurrence."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    result = _executor.execute("edit_file", {
        "path": path,
        "old_string": old_string,
        "new_string": new_string,
        "replace_all": replace_all,
    })
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


@function_tool
def glob_search(
    pattern: Annotated[str, "Glob pattern (supports ** for recursion)"],
    path: Annotated[Optional[str], "Optional directory to scope the search (defaults to project root)"] = None,
) -> str:
    """List files or directories matching a glob pattern within the sandbox."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    result = _executor.execute("glob_search", {
        "pattern": pattern,
        "path": path,
    })
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


@function_tool
def grep_search(
    pattern: Annotated[str, "Regex or literal pattern to search for"],
    path: Annotated[Optional[str], "File or directory to search (default '.')"] = None,
    glob: Annotated[Optional[str], "Optional glob passed to rg --glob"] = None,
    type: Annotated[Optional[str], "Optional ripgrep file type filter (e.g. 'ts', 'py')"] = None,
    output_mode: Annotated[Optional[str], "Choose detailed content, file list, or counts"] = None,
    before: Annotated[Optional[int], "Number of lines to show before each match"] = None,
    after: Annotated[Optional[int], "Number of lines to show after each match"] = None,
    context: Annotated[Optional[int], "Number of lines to show before and after each match"] = None,
    line_numbers: Annotated[Optional[bool], "Show line numbers (default true for content mode)"] = None,
    ignore_case: Annotated[Optional[bool], "Case-insensitive search"] = None,
    head_limit: Annotated[Optional[int], "Limit output lines/entries (similar to piping through head)"] = None,
    offset: Annotated[Optional[int], "Skip this many output lines before applying head_limit"] = None,
    multiline: Annotated[Optional[bool], "Enable multiline dotall mode (rg -U --multiline-dotall)"] = None,
) -> str:
    """Search file contents using ripgrep-compatible options. Supports line context, glob/type filters, and output throttling."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    # Map parameter names to executor format
    args = {
        "pattern": pattern,
        "path": path,
        "glob": glob,
        "type": type,
        "output_mode": output_mode or "files_with_matches",
        "-B": before,
        "-A": after,
        "-C": context,
        "-n": line_numbers,
        "-i": ignore_case,
        "head_limit": head_limit,
        "offset": offset,
        "multiline": multiline or False,
    }
    
    result = _executor.execute("grep_search", args)
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


@function_tool
def bash(
    command: Annotated[str, "Command to run (e.g. 'npm install', 'git status')"],
) -> str:
    """Execute a bash command from the project root. Commands are validated against the same allowlist used by the Claude CLI demo."""
    if not _executor:
        return "Error: Tool executor not initialized"
    
    # Validate command first
    is_allowed, reason = validate_bash_command(command)
    if not is_allowed:
        return f"Error: Command blocked: {reason}"
    
    result = _executor.execute("bash", {
        "command": command,
    })
    
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("result", "")


# Export all tools as a list
SDK_TOOLS = [
    read_file,
    write_file,
    edit_file,
    glob_search,
    grep_search,
    bash,
]



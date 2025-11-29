"""
Tool Executor for OpenAI-Compatible Providers
==============================================

Executes tools on behalf of non-Claude providers that don't have
built-in tool execution capabilities.
"""

import glob
import os
import subprocess
from pathlib import Path
from typing import Any

from security import validate_bash_command


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


class ToolExecutor:
    """
    Executes tools in a sandboxed environment.
    
    All file operations are restricted to the project directory.
    Bash commands are validated against a security allowlist.
    """
    
    def __init__(self, project_dir: Path):
        """
        Initialize the tool executor.
        
        Args:
            project_dir: The project directory (all operations are sandboxed here)
        """
        self.project_dir = project_dir.resolve()
    
    def execute(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """
        Execute a tool and return the result.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Dict with 'result' or 'error' key
        """
        try:
            if tool_name == "read_file":
                return self._read_file(arguments["path"])
            elif tool_name == "write_file":
                return self._write_file(arguments["path"], arguments["content"])
            elif tool_name == "edit_file":
                return self._edit_file(
                    arguments["path"],
                    arguments["old_string"],
                    arguments["new_string"]
                )
            elif tool_name == "list_directory":
                return self._list_directory(arguments["path"])
            elif tool_name == "search_files":
                return self._search_files(arguments["pattern"])
            elif tool_name == "search_content":
                return self._search_content(
                    arguments["pattern"],
                    arguments["path"],
                    arguments.get("include")
                )
            elif tool_name == "bash":
                return self._run_bash(arguments["command"])
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except SecurityError as e:
            return {"error": f"Security violation: {str(e)}"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve a path, ensuring it's within the project directory.
        
        Args:
            path: Relative path to validate
            
        Returns:
            Resolved absolute path
            
        Raises:
            SecurityError: If path escapes the project directory
        """
        # Resolve the path relative to project directory
        resolved = (self.project_dir / path).resolve()
        
        # Check that resolved path is within project directory
        try:
            resolved.relative_to(self.project_dir)
        except ValueError:
            raise SecurityError(f"Path escape attempt blocked: {path}")
        
        return resolved
    
    def _read_file(self, path: str) -> dict[str, Any]:
        """Read a file's contents."""
        file_path = self._validate_path(path)
        
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        
        if not file_path.is_file():
            return {"error": f"Not a file: {path}"}
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return {"result": content}
        except UnicodeDecodeError:
            return {"error": f"Cannot read binary file: {path}"}
    
    def _write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a file."""
        file_path = self._validate_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(content, encoding="utf-8")
        return {"result": f"Successfully wrote {len(content)} bytes to {path}"}
    
    def _edit_file(self, path: str, old_string: str, new_string: str) -> dict[str, Any]:
        """Make a targeted edit to a file."""
        file_path = self._validate_path(path)
        
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        
        content = file_path.read_text(encoding="utf-8")
        
        # Check that old_string exists exactly once
        count = content.count(old_string)
        if count == 0:
            return {"error": f"String not found in file: {old_string[:100]}..."}
        if count > 1:
            return {"error": f"String found {count} times, must be unique for safe editing"}
        
        # Perform the replacement
        new_content = content.replace(old_string, new_string)
        file_path.write_text(new_content, encoding="utf-8")
        
        return {"result": f"Successfully edited {path}"}
    
    def _list_directory(self, path: str) -> dict[str, Any]:
        """List directory contents."""
        dir_path = self._validate_path(path)
        
        if not dir_path.exists():
            return {"error": f"Directory not found: {path}"}
        
        if not dir_path.is_dir():
            return {"error": f"Not a directory: {path}"}
        
        entries = []
        for entry in sorted(dir_path.iterdir()):
            entry_type = "dir" if entry.is_dir() else "file"
            entries.append(f"[{entry_type}] {entry.name}")
        
        return {"result": "\n".join(entries) if entries else "(empty directory)"}
    
    def _search_files(self, pattern: str) -> dict[str, Any]:
        """Search for files matching a glob pattern."""
        # Use glob from project directory
        old_cwd = os.getcwd()
        try:
            os.chdir(self.project_dir)
            matches = glob.glob(pattern, recursive=True)
            
            if not matches:
                return {"result": "No files found matching pattern"}
            
            return {"result": "\n".join(sorted(matches))}
        finally:
            os.chdir(old_cwd)
    
    def _search_content(
        self, 
        pattern: str, 
        path: str, 
        include: str | None = None
    ) -> dict[str, Any]:
        """Search for pattern in file contents."""
        search_path = self._validate_path(path)
        
        if not search_path.exists():
            return {"error": f"Path not found: {path}"}
        
        results = []
        
        # Determine files to search
        if search_path.is_file():
            files = [search_path]
        else:
            if include:
                files = list(search_path.rglob(include))
            else:
                files = [f for f in search_path.rglob("*") if f.is_file()]
        
        # Search each file
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern in line:
                        rel_path = file_path.relative_to(self.project_dir)
                        results.append(f"{rel_path}:{i}: {line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files and permission errors
                continue
        
        if not results:
            return {"result": "No matches found"}
        
        # Limit results to prevent overwhelming output
        if len(results) > 100:
            results = results[:100]
            results.append(f"... and more (showing first 100 matches)")
        
        return {"result": "\n".join(results)}
    
    def _run_bash(self, command: str) -> dict[str, Any]:
        """
        Run a bash command with security validation.
        
        Commands are validated against the allowlist before execution.
        """
        # Validate command against security allowlist
        is_allowed, reason = validate_bash_command(command)
        if not is_allowed:
            return {"error": f"Command blocked: {reason}"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            
            return {"result": output if output.strip() else "(no output)"}
            
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 5 minutes"}
        except Exception as e:
            return {"error": f"Command execution failed: {str(e)}"}

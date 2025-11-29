"""
Tool Executor for OpenAI-Compatible Providers
==============================================

Executes tools on behalf of non-Claude providers that don't have
built-in tool execution capabilities.
"""

import glob
import os
import shutil
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
                return self._read_file(
                    path=arguments["path"],
                    offset=arguments.get("offset"),
                    limit=arguments.get("limit"),
                )
            if tool_name == "write_file":
                return self._write_file(arguments["path"], arguments["content"])
            if tool_name == "edit_file":
                return self._edit_file(
                    path=arguments["path"],
                    old_string=arguments["old_string"],
                    new_string=arguments["new_string"],
                    replace_all=arguments.get("replace_all", False),
                )
            if tool_name == "glob_search":
                return self._glob_search(arguments["pattern"], arguments.get("path"))
            if tool_name == "grep_search":
                return self._grep_search(
                    pattern=arguments["pattern"],
                    path=arguments.get("path"),
                    glob_pattern=arguments.get("glob"),
                    file_type=arguments.get("type"),
                    output_mode=arguments.get("output_mode", "files_with_matches"),
                    before=arguments.get("-B"),
                    after=arguments.get("-A"),
                    context=arguments.get("-C"),
                    line_numbers=arguments.get("-n"),
                    ignore_case=arguments.get("-i"),
                    head_limit=arguments.get("head_limit"),
                    offset=arguments.get("offset"),
                    multiline=arguments.get("multiline", False),
                )
            if tool_name == "bash":
                return self._run_bash(arguments["command"])
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
    
    def _read_file(self, path: str, offset: int | None, limit: int | None) -> dict[str, Any]:
        """Read a file's contents with optional pagination."""
        file_path = self._validate_path(path)
        
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        
        if not file_path.is_file():
            return {"error": f"Not a file: {path}"}
        
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"error": f"Cannot read binary file: {path}"}
        
        if offset is not None and offset < 0:
            return {"error": "Offset must be zero or positive"}
        if limit is not None and limit < 1:
            return {"error": "Limit must be positive"}

        if offset is None and limit is None:
            return {"result": content}
        
        lines = content.splitlines()
        total_lines = len(lines)
        start = max(offset or 0, 0)
        if total_lines == 0:
            if start == 0:
                return {"result": "[lines 0-0 of 0] (file is empty)"}
            return {"error": "Offset beyond end of file (file is empty)"}
        if start >= total_lines:
            return {
                "error": f"Offset {start} beyond end of file (total {total_lines} lines)"
            }
        end = start + limit if limit else total_lines
        selected = lines[start:end]
        header = f"[lines {start + 1}-{min(end, total_lines)} of {total_lines}]\n"
        return {"result": header + "\n".join(selected)}
    
    def _write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a file."""
        file_path = self._validate_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(content, encoding="utf-8")
        return {"result": f"Successfully wrote {len(content)} bytes to {path}"}
    
    def _edit_file(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> dict[str, Any]:
        """Make a targeted edit to a file."""
        file_path = self._validate_path(path)
        
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        
        content = file_path.read_text(encoding="utf-8")
        
        occurrences = content.count(old_string)
        if occurrences == 0:
            preview = old_string[:100] + ("..." if len(old_string) > 100 else "")
            return {"error": f"String not found in file: {preview}"}
        
        if not replace_all:
            new_content = content.replace(old_string, new_string, 1)
            replaced = 1
        else:
            new_content = content.replace(old_string, new_string)
            replaced = occurrences
        
        file_path.write_text(new_content, encoding="utf-8")
        return {"result": f"Replaced {replaced} occurrence(s) in {path}"}
    
    def _glob_search(self, pattern: str, path: str | None) -> dict[str, Any]:
        """Search for files/directories matching a glob pattern."""
        base_dir = self.project_dir if not path else self._validate_path(path)
        if not base_dir.exists():
            return {"error": f"Directory not found: {path or '.'}"}
        if not base_dir.is_dir():
            return {"error": f"Not a directory: {path or '.'}"}

        matches: list[str] = []
        for entry in glob.iglob(pattern, root_dir=str(base_dir), recursive=True):
            full_path = (base_dir / entry).resolve()
            try:
                rel_path = full_path.relative_to(self.project_dir)
            except ValueError:
                # Ignore entries that somehow escape the sandbox
                continue
            matched = str(rel_path)
            if not matched:
                matched = "."
            matches.append(matched)

        if not matches:
            return {"result": "No matches found"}

        matches = sorted(set(matches))
        return {"result": "\n".join(matches)}

    def _grep_search(
        self,
        pattern: str,
        path: str | None,
        glob_pattern: str | None,
        file_type: str | None,
        output_mode: str,
        before: int | None,
        after: int | None,
        context: int | None,
        line_numbers: bool | None,
        ignore_case: bool | None,
        head_limit: int | None,
        offset: int | None,
        multiline: bool,
    ) -> dict[str, Any]:
        """Search file contents using ripgrep."""
        if shutil.which("rg") is None:
            return {"error": "ripgrep (rg) is not installed"}

        if head_limit is not None and head_limit < 1:
            return {"error": "head_limit must be positive"}
        if offset is not None and offset < 0:
            return {"error": "offset must be zero or positive"}

        target_path = self._validate_path(path or ".")
        relative_target = "."
        try:
            relative_target = str(target_path.relative_to(self.project_dir)) or "."
        except ValueError:
            # Should not happen due to _validate_path, but guard anyway
            relative_target = str(target_path)

        cmd = ["rg", "--color", "never"]

        if glob_pattern:
            cmd.extend(["--glob", glob_pattern])
        if file_type:
            cmd.extend(["--type", file_type])
        if context is not None:
            cmd.extend(["-C", str(context)])
        else:
            if before is not None:
                cmd.extend(["-B", str(before)])
            if after is not None:
                cmd.extend(["-A", str(after)])

        effective_mode = output_mode or "files_with_matches"
        if effective_mode not in {"content", "files_with_matches", "count"}:
            return {"error": f"Invalid output_mode: {effective_mode}"}
        if effective_mode == "files_with_matches":
            cmd.append("-l")
        elif effective_mode == "count":
            cmd.append("-c")
        else:
            # content mode
            show_numbers = line_numbers
            if show_numbers is None:
                show_numbers = True
            if show_numbers:
                cmd.append("-n")

        if ignore_case:
            cmd.append("-i")
        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])

        cmd.append(pattern)
        cmd.append(relative_target)

        result = subprocess.run(
            cmd,
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode not in (0, 1):
            return {"error": stderr or f"rg failed with exit code {result.returncode}"}

        if result.returncode == 1 and not stdout:
            return {"result": "No matches found"}

        lines = stdout.splitlines()
        start = max(offset or 0, 0)
        if start >= len(lines):
            return {"error": "Offset skips all output"}
        end = start + head_limit if head_limit else len(lines)
        sliced = lines[start:end]
        if head_limit and len(lines) > end:
            sliced.append("... (results truncated)")

        output = "\n".join(sliced)
        if stderr:
            output = f"{output}\n[stderr]: {stderr}"
        return {"result": output or "(no output)"}
    
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

"""
Base Provider Abstract Class
============================

Defines the interface that all LLM providers must implement.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional, List, Any


@dataclass
class TextBlock:
    """A block of text content from the model."""
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    """A tool use request from the model."""
    name: str
    input: dict
    id: str
    type: str = "tool_use"


@dataclass
class ToolResultBlock:
    """Result from executing a tool."""
    content: str
    tool_use_id: str
    is_error: bool = False
    type: str = "tool_result"


@dataclass
class AssistantMessage:
    """Message from the assistant."""
    content: List[Any]  # List of TextBlock or ToolUseBlock
    role: str = "assistant"


@dataclass
class UserMessage:
    """Message from the user or tool results."""
    content: List[Any]  # List of ToolResultBlock
    role: str = "user"


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement this interface to work with the
    autonomous coding agent.
    """
    
    def __init__(self, model: str, project_dir: Path, verbose: bool = False):
        """
        Initialize the provider.
        
        Args:
            model: The model identifier to use
            project_dir: Directory for the project (used for sandboxing)
            verbose: Whether to log full JSON responses to file (for debugging)
        """
        self.model = model
        self.project_dir = project_dir
        self.verbose = verbose
        self._verbose_log_file: Optional[Path] = None
        if self.verbose:
            self._init_verbose_logging()
    
    @abstractmethod
    async def __aenter__(self) -> "BaseProvider":
        """Async context manager entry."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        pass
    
    @abstractmethod
    async def query(self, message: str) -> None:
        """
        Send a query to the model.
        
        Args:
            message: The prompt/message to send
        """
        pass
    
    @abstractmethod
    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Receive streaming response from the model.
        
        Yields:
            AssistantMessage or UserMessage objects representing
            the conversation flow including tool use and results.
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_required_env_var(cls) -> str:
        """
        Return the required environment variable name for API key.
        
        Returns:
            Name of the environment variable (e.g., "ANTHROPIC_API_KEY")
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_default_model(cls) -> str:
        """
        Return the default model for this provider.
        
        Returns:
            Model identifier string
        """
        pass
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """
        Return list of available models for this provider.
        
        Override in subclasses to provide model listings.
        
        Returns:
            List of model identifier strings
        """
        return [cls.get_default_model()]
    
    def _init_verbose_logging(self) -> None:
        """Initialize verbose logging to a markdown file in the logs directory."""
        if not self.verbose:
            return
        
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create log file name based on model name (sanitize for filename)
        model_safe = self.model.replace("/", "-").replace(" ", "-").replace(":", "-")
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        log_filename = f"{model_safe}-verbose-{timestamp}.md"
        self._verbose_log_file = logs_dir / log_filename
        
        # Write initial header to log file
        with open(self._verbose_log_file, "w", encoding="utf-8") as f:
            f.write(f"# Verbose Log: {self.model}\n\n")
            f.write(f"**Started:** {datetime.now().isoformat()}\n")
            f.write(f"**Project Directory:** {self.project_dir.resolve()}\n\n")
            f.write("---\n\n")
    
    def _print_verbose_json(self, title: str, data: Any) -> None:
        """
        Log JSON data to markdown file in verbose mode with nice formatting.
        
        Args:
            title: Title/header for the JSON output
            data: Data to log (will be converted to JSON)
        """
        if not self.verbose or not self._verbose_log_file:
            return
        
        try:
            # Always convert through _object_to_dict for consistent handling
            data = self._object_to_dict(data)
            
            # Format with nice indentation
            json_str = json.dumps(data, indent=4, default=str, ensure_ascii=False)
            
            # Write to log file with markdown formatting
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._verbose_log_file, "a", encoding="utf-8") as f:
                f.write(f"## {title}\n\n")
                f.write(f"**Timestamp:** {timestamp}\n\n")
                f.write("```json\n")
                f.write(json_str)
                f.write("\n```\n\n")
                f.write("---\n\n")
        except Exception as e:
            # Fallback logging
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._verbose_log_file, "a", encoding="utf-8") as f:
                f.write(f"## {title} (Error)\n\n")
                f.write(f"**Timestamp:** {timestamp}\n\n")
                f.write(f"**Error:** {str(e)}\n\n")
                f.write(f"**Raw data:**\n\n```\n{str(data)}\n```\n\n")
                f.write("---\n\n")
    
    def _object_to_dict(self, obj: Any) -> Any:
        """
        Recursively convert an object to a dictionary with better handling of SDK objects.
        
        Args:
            obj: Object to convert
            
        Returns:
            Dictionary representation of the object
        """
        # Handle None
        if obj is None:
            return None
        
        # Handle primitives
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # Handle dict
        if isinstance(obj, dict):
            return {k: self._object_to_dict(v) for k, v in obj.items()}
        
        # Handle list/tuple
        if isinstance(obj, (list, tuple)):
            return [self._object_to_dict(item) for item in obj]
        
        # Try Pydantic model_dump first (most reliable)
        if hasattr(obj, "model_dump"):
            try:
                dumped = obj.model_dump()
                if isinstance(dumped, dict):
                    return self._object_to_dict(dumped)
            except Exception:
                pass
        
        # Special handling for SDK event objects - extract key attributes
        obj_type = type(obj).__name__
        result = {"_object_type": obj_type}
        
        # Common attributes to extract from SDK objects
        common_attrs = [
            "type", "id", "name", "content", "data", "item", "response", 
            "output", "status", "role", "model", "created_at", "error",
            "instructions", "metadata", "object", "temperature", "tool_choice",
            "tools", "output_index", "sequence_number", "delta", "text",
            "function", "arguments", "tool_call_id", "is_error", "summary"
        ]
        
        # Try to extract attributes
        extracted = False
        for attr in common_attrs:
            if hasattr(obj, attr):
                try:
                    value = getattr(obj, attr)
                    # Skip None values to keep output clean
                    if value is not None:
                        result[attr] = self._object_to_dict(value)
                        extracted = True
                except Exception:
                    pass
        
        # If we extracted some attributes, return them
        if extracted and len(result) > 1:  # More than just _object_type
            return result
        
        # Try to extract from __dict__ if available
        if hasattr(obj, "__dict__"):
            result = {}
            for k, v in obj.__dict__.items():
                # Skip private/internal attributes and callables
                if k.startswith("_") or callable(v):
                    continue
                try:
                    converted = self._object_to_dict(v)
                    # Only include if it's meaningful (not empty dict/list)
                    if converted is not None and converted != {} and converted != []:
                        result[k] = converted
                except Exception:
                    # If conversion fails, try to get a string representation
                    try:
                        result[k] = str(v)[:200]  # Limit length
                    except Exception:
                        pass
            if result:
                return result
        
        # Last resort: create a summary from string representation
        obj_str = str(obj)
        if len(obj_str) > 1000:
            # For very long strings, create a summary
            summary = {
                "_object_type": obj_type,
                "_summary": obj_str[:500] + f"\n... (truncated, {len(obj_str)} chars total)"
            }
            # Try to extract a few key attributes even from string
            for attr in ["id", "type", "name", "status"]:
                if hasattr(obj, attr):
                    try:
                        summary[attr] = getattr(obj, attr)
                    except Exception:
                        pass
            return summary
        
        return obj_str

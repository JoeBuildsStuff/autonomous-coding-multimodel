"""
Base Provider Abstract Class
============================

Defines the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
    
    def __init__(self, model: str, project_dir: Path):
        """
        Initialize the provider.
        
        Args:
            model: The model identifier to use
            project_dir: Directory for the project (used for sandboxing)
        """
        self.model = model
        self.project_dir = project_dir
    
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

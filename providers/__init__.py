"""
Providers Package
=================

Multi-model provider abstraction for the autonomous coding agent.

Supported providers:
- anthropic: Claude models via Claude Agent SDK (full features)
- openai: OpenAI models (GPT-4, GPT-5 with reasoning support)
- grok: xAI Grok models via OpenAI-compatible API (with reasoning support)

Browser automation via puppeteer-mcp-server is enabled by default for all providers.
"""

from pathlib import Path
from typing import Dict, Type

from .base import (
    BaseProvider,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from .anthropic import AnthropicProvider
from .openai_provider import OpenAIProvider
from .grok_provider import GrokProvider


# Registry of available providers
PROVIDERS: Dict[str, Type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "grok": GrokProvider,
}


def get_provider(
    provider_name: str,
    model: str,
    project_dir: Path,
    enable_browser: bool = True,  # Default ON like original repo
    chrome_debug_port: int = 9222,
) -> BaseProvider:
    """
    Factory function to create a provider instance.
    
    Args:
        provider_name: Name of the provider (anthropic, openai, grok)
        model: Model identifier to use
        project_dir: Project directory for sandboxing
        enable_browser: Whether to enable browser automation tools (default: True)
        chrome_debug_port: Chrome debugging port for browser connection
        
    Returns:
        Configured provider instance
        
    Raises:
        ValueError: If provider_name is not recognized
    """
    if provider_name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(
            f"Unknown provider: {provider_name}\n"
            f"Available providers: {available}"
        )
    
    provider_class = PROVIDERS[provider_name]
    
    # Anthropic provider doesn't need extra browser flags (handled via MCP config)
    if provider_name == "anthropic":
        return provider_class(model=model, project_dir=project_dir)
    
    # OpenAI and Grok providers support browser flags
    return provider_class(
        model=model,
        project_dir=project_dir,
        enable_browser=enable_browser,
        chrome_debug_port=chrome_debug_port,
    )


def get_default_model(provider_name: str) -> str:
    """
    Get the default model for a provider.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        Default model identifier string
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDERS[provider_name].get_default_model()


def get_required_env_var(provider_name: str) -> str:
    """
    Get the required environment variable for a provider.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        Environment variable name (e.g., "ANTHROPIC_API_KEY")
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDERS[provider_name].get_required_env_var()


def get_available_providers() -> list[str]:
    """Return list of available provider names."""
    return list(PROVIDERS.keys())


def get_available_models(provider_name: str) -> list[str]:
    """
    Get list of available models for a provider.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        List of model identifier strings
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}")
    return PROVIDERS[provider_name].get_available_models()


def supports_browser_tools(provider_name: str) -> bool:
    """
    Check if a provider supports browser automation tools.
    
    All providers support browser tools:
    - Anthropic/Claude has built-in MCP support
    - OpenAI and Grok use the MCP adapter
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        True if browser tools are supported
    """
    return provider_name in PROVIDERS


__all__ = [
    # Factory functions
    "get_provider",
    "get_default_model",
    "get_required_env_var",
    "get_available_providers",
    "get_available_models",
    "supports_browser_tools",
    # Base types
    "BaseProvider",
    "AssistantMessage",
    "UserMessage",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    # Provider classes
    "AnthropicProvider",
    "OpenAIProvider",
    "GrokProvider",
    # Registry
    "PROVIDERS",
]

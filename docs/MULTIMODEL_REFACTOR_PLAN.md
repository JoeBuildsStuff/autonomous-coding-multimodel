# Multi-Model Refactoring Plan

**Status: ✅ IMPLEMENTED**

This document outlines the plan that was used to refactor the autonomous coding agent to support multiple LLM providers beyond Anthropic, including OpenAI-compatible endpoints like Grok.

## Current Architecture

```
autonomous_agent_demo.py  →  agent.py  →  client.py  →  Claude Agent SDK
                                              ↓
                                        security.py (bash hooks)
```

**Current limitations:**
- `client.py` is tightly coupled to `ClaudeSDKClient` and `claude_code_sdk`
- API key check is hardcoded for `ANTHROPIC_API_KEY`
- Model selection assumes Anthropic models only
- No abstraction layer for different providers

## Target Architecture

```
autonomous_agent_demo.py
        ↓
    agent.py
        ↓
  providers/
    ├── base.py          # Abstract base class for all providers
    ├── anthropic.py     # Claude via Claude Agent SDK
    ├── openai.py        # OpenAI models (GPT-4, etc.)
    └── grok.py          # Grok via OpenAI-compatible API (x.ai)
        ↓
    security.py (shared bash hooks - where applicable)
```

## Provider Selection

Users will specify both provider and model via CLI:

```bash
# Anthropic (default - uses Claude Agent SDK)
python autonomous_agent_demo.py --provider anthropic --model claude-sonnet-4-5-20250929

# OpenAI
python autonomous_agent_demo.py --provider openai --model gpt-4o

# Grok (via x.ai OpenAI-compatible endpoint)
python autonomous_agent_demo.py --provider grok --model grok-4-1-fast-reasoning
```

## Implementation Plan

### Phase 1: Create Provider Abstraction Layer

#### 1.1 Create `providers/base.py`

Define an abstract base class that all providers must implement:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator, Any

class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: str, project_dir: Path):
        self.model = model
        self.project_dir = project_dir
    
    @abstractmethod
    async def __aenter__(self):
        """Async context manager entry."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    @abstractmethod
    async def query(self, message: str) -> None:
        """Send a query to the model."""
        pass
    
    @abstractmethod
    async def receive_response(self) -> AsyncIterator[Any]:
        """Receive streaming response from the model."""
        pass
    
    @classmethod
    @abstractmethod
    def get_required_env_var(cls) -> str:
        """Return the required environment variable name for API key."""
        pass
    
    @classmethod
    @abstractmethod
    def get_default_model(cls) -> str:
        """Return the default model for this provider."""
        pass
```

#### 1.2 Create `providers/anthropic.py`

Wrap the existing Claude SDK client:

```python
from pathlib import Path
from .base import BaseProvider
from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
# ... (move existing client.py logic here)

class AnthropicProvider(BaseProvider):
    """Provider for Anthropic's Claude models via Claude Agent SDK."""
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "ANTHROPIC_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "claude-sonnet-4-5-20250929"
    
    # ... implement abstract methods wrapping ClaudeSDKClient
```

#### 1.3 Create `providers/openai_provider.py`

Implement OpenAI-compatible provider with tool use:

```python
from openai import OpenAI
from .base import BaseProvider

class OpenAIProvider(BaseProvider):
    """Provider for OpenAI models."""
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "OPENAI_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "gpt-4o"
    
    # ... implement abstract methods with OpenAI client
```

#### 1.4 Create `providers/grok.py`

Implement Grok provider (OpenAI-compatible with different base URL):

```python
from openai import OpenAI
from .base import BaseProvider

class GrokProvider(BaseProvider):
    """Provider for xAI's Grok models via OpenAI-compatible API."""
    
    def __init__(self, model: str, project_dir: Path):
        super().__init__(model, project_dir)
        self.client = OpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
        )
    
    @classmethod
    def get_required_env_var(cls) -> str:
        return "XAI_API_KEY"
    
    @classmethod
    def get_default_model(cls) -> str:
        return "grok-4-1-fast-reasoning"
```

#### 1.5 Create `providers/__init__.py`

Factory function to get the right provider:

```python
from .base import BaseProvider
from .anthropic import AnthropicProvider
from .openai_provider import OpenAIProvider
from .grok import GrokProvider

PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "grok": GrokProvider,
}

def get_provider(provider_name: str, model: str, project_dir: Path) -> BaseProvider:
    """Factory function to create a provider instance."""
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")
    
    provider_class = PROVIDERS[provider_name]
    return provider_class(model=model, project_dir=project_dir)

def get_default_model(provider_name: str) -> str:
    """Get the default model for a provider."""
    return PROVIDERS[provider_name].get_default_model()

def get_required_env_var(provider_name: str) -> str:
    """Get the required environment variable for a provider."""
    return PROVIDERS[provider_name].get_required_env_var()
```

### Phase 2: Implement Tool Use for OpenAI-Compatible Providers

The Claude Agent SDK handles tool use automatically. For OpenAI-compatible providers, we need to implement our own tool execution loop.

#### 2.1 Create `tools/definitions.py`

Define tools in OpenAI function calling format:

```python
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    # ... bash, glob, grep, etc.
]
```

#### 2.2 Create `tools/executor.py`

Tool execution logic:

```python
from pathlib import Path
from security import validate_bash_command

class ToolExecutor:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
    
    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return the result."""
        if tool_name == "read_file":
            return self._read_file(arguments["path"])
        elif tool_name == "write_file":
            return self._write_file(arguments["path"], arguments["content"])
        elif tool_name == "bash":
            return self._run_bash(arguments["command"])
        # ... etc
    
    def _run_bash(self, command: str) -> dict:
        """Run bash command with security validation."""
        is_allowed, message = validate_bash_command(command)
        if not is_allowed:
            return {"error": f"Command blocked: {message}"}
        # Execute command...
```

### Phase 3: Update Entry Points

#### 3.1 Update `autonomous_agent_demo.py`

Add provider selection:

```python
parser.add_argument(
    "--provider",
    type=str,
    default="anthropic",
    choices=["anthropic", "openai", "grok"],
    help="LLM provider to use (default: anthropic)",
)

# Update API key check to be provider-aware
env_var = get_required_env_var(args.provider)
if not os.environ.get(env_var):
    print(f"Error: {env_var} environment variable not set")
    return
```

#### 3.2 Update `agent.py`

Use provider abstraction instead of direct Claude SDK:

```python
from providers import get_provider

async def run_autonomous_agent(
    project_dir: Path,
    provider_name: str,
    model: str,
    max_iterations: Optional[int] = None,
) -> None:
    # ...
    provider = get_provider(provider_name, model, project_dir)
    
    async with provider:
        status, response = await run_agent_session(provider, prompt, project_dir)
```

### Phase 4: Security Considerations

#### 4.1 Shared Security Layer

The existing `security.py` bash allowlist should work for all providers. However:

- **Anthropic provider**: Uses Claude SDK's hook system (existing implementation)
- **OpenAI/Grok providers**: Security validation happens in `ToolExecutor` before command execution

#### 4.2 Filesystem Sandboxing

- Anthropic provider uses Claude SDK's built-in sandboxing
- OpenAI/Grok providers need manual path validation in `ToolExecutor`:

```python
def _validate_path(self, path: str) -> Path:
    """Ensure path is within project directory."""
    resolved = (self.project_dir / path).resolve()
    if not str(resolved).startswith(str(self.project_dir.resolve())):
        raise SecurityError(f"Path escape attempt: {path}")
    return resolved
```

### Phase 5: Configuration & Environment

#### 5.1 Update `.env` template

```env
# Anthropic (for Claude models)
ANTHROPIC_API_KEY=your-anthropic-key

# OpenAI (for GPT models)
OPENAI_API_KEY=your-openai-key

# xAI (for Grok models)
XAI_API_KEY=your-xai-key
```

#### 5.2 Update `requirements.txt`

```
claude-code-sdk>=0.1.0
openai>=1.0.0
python-dotenv>=1.0.0
```

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `providers/__init__.py` | CREATE | Provider factory and registry |
| `providers/base.py` | CREATE | Abstract base class |
| `providers/anthropic.py` | CREATE | Claude SDK wrapper (from client.py) |
| `providers/openai_provider.py` | CREATE | OpenAI provider |
| `providers/grok.py` | CREATE | Grok provider |
| `tools/__init__.py` | CREATE | Tools package |
| `tools/definitions.py` | CREATE | Tool definitions (OpenAI format) |
| `tools/executor.py` | CREATE | Tool execution logic |
| `client.py` | DELETE | Logic moves to providers/anthropic.py |
| `agent.py` | MODIFY | Use provider abstraction |
| `autonomous_agent_demo.py` | MODIFY | Add --provider argument |
| `security.py` | MODIFY | Add `validate_bash_command()` function |
| `requirements.txt` | MODIFY | Add openai dependency |
| `.env.example` | CREATE | Template for all API keys |
| `README.md` | MODIFY | Document multi-provider usage |

## Migration Path

1. **Phase 1**: Create provider abstraction without breaking existing functionality
2. **Phase 2**: Implement OpenAI/Grok providers with tool use
3. **Phase 3**: Update CLI and entry points
4. **Phase 4**: Test all providers thoroughly
5. **Phase 5**: Update documentation

## Testing Strategy

```bash
# Test Anthropic (should work exactly as before)
python autonomous_agent_demo.py --provider anthropic --project-dir ./test_anthropic

# Test OpenAI
python autonomous_agent_demo.py --provider openai --model gpt-4o --project-dir ./test_openai

# Test Grok
python autonomous_agent_demo.py --provider grok --project-dir ./test_grok
```

## Open Questions

1. **Tool parity**: Should OpenAI/Grok providers support MCP tools like Puppeteer? Initial implementation could skip MCP and focus on core file/bash tools.

2. **Streaming**: The Claude SDK provides streaming responses. OpenAI also supports streaming. Should we standardize on streaming for all providers?

3. **Context window management**: Different models have different context limits. Should we add provider-specific context management?

4. **Cost tracking**: Different providers have different pricing. Should we add token/cost tracking?

## Next Steps

1. Review and approve this plan
2. Create the `providers/` directory structure
3. Implement `BaseProvider` and `AnthropicProvider` first (no behavior change)
4. Add OpenAI and Grok providers
5. Update CLI and agent.py
6. Test thoroughly
7. Update documentation

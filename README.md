# Autonomous Coding Agent Demo

A minimal harness demonstrating long-running autonomous coding with multiple LLM providers. This demo implements a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions.

## Supported Providers

| Provider | Default Model | Features |
|----------|---------------|----------|
| **Anthropic** (default) | claude-haiku-4-5 | Full Claude Agent SDK with sandbox, MCP tools, security hooks |
| **OpenAI** | gpt-5-nano | Tool use + reasoning (medium effort/verbosity) |
| **Grok** | grok-4-1-fast-reasoning | Tool use + reasoning (medium effort) |

## Prerequisites

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Set API keys** (only need the one for your chosen provider):

```bash
# For Claude models
export ANTHROPIC_API_KEY='your-anthropic-key'

# For OpenAI models
export OPENAI_API_KEY='your-openai-key'

# For Grok models
export XAI_API_KEY='your-xai-key'
```

Or copy `.env.example` to `.env` and fill in your keys.

## Quick Start

```bash
# Using Claude (default)
python autonomous_agent_demo.py --project-dir ./my_project

# Using OpenAI GPT-4o
python autonomous_agent_demo.py --provider openai --model gpt-4o --project-dir ./my_project

# Using Grok
python autonomous_agent_demo.py --provider grok --project-dir ./my_project

# Limit iterations for testing
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3

# List available models for a provider
python autonomous_agent_demo.py --provider openai --list-models
```

## Important Timing Expectations

> **Warning: This demo takes a long time to run!**

- **First session (initialization):** The agent generates a `feature_list.json` with 200 test cases. This takes several minutes and may appear to hang - this is normal.

- **Subsequent sessions:** Each coding iteration can take **5-15 minutes** depending on complexity and model.

- **Full app:** Building all 200 features typically requires **many hours** of total runtime across multiple sessions.

**Tip:** Modify `prompts/initializer_prompt.md` to reduce the feature count (e.g., 20-50 features) for faster demos.

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (Session 1):** Reads `app_spec.txt`, creates `feature_list.json` with test cases, sets up project structure, and initializes git.

2. **Coding Agent (Sessions 2+):** Picks up where the previous session left off, implements features one by one, and marks them as passing.

### Session Management

- Each session runs with a fresh context window
- Progress is persisted via `feature_list.json` and git commits
- The agent auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run the same command to resume

## Security Model

Defense-in-depth security approach:

**For Anthropic (Claude) provider:**
- OS-level sandbox via Claude Agent SDK
- Filesystem restricted to project directory
- Bash commands validated via security hooks

**For OpenAI/Grok providers:**
- Filesystem operations sandboxed to project directory
- Bash command allowlist (see `security.py`)
- Path traversal protection

### Allowed Bash Commands

```
ls, cat, head, tail, wc, grep    # File inspection
cp, mkdir, chmod                  # File operations
pwd                               # Directory
npm, node                         # Node.js development
git                               # Version control
ps, lsof, sleep, pkill           # Process management (restricted)
```

## Project Structure

```
autonomous-coding-multimodel/
├── autonomous_agent_demo.py  # Main entry point
├── agent.py                  # Agent session logic
├── providers/                # LLM provider implementations
│   ├── __init__.py          # Provider factory
│   ├── base.py              # Abstract base class
│   ├── anthropic.py         # Claude via Agent SDK
│   ├── openai_compat.py     # OpenAI-compatible base
│   ├── openai_provider.py   # OpenAI models
│   └── grok_provider.py     # Grok models
├── tools/                    # Tool execution for non-Claude providers
│   ├── __init__.py
│   ├── definitions.py       # Tool definitions (OpenAI format)
│   └── executor.py          # Sandboxed tool execution
├── security.py              # Bash command validation
├── progress.py              # Progress tracking
├── prompts.py               # Prompt loading
├── prompts/
│   ├── app_spec.txt         # Application specification
│   ├── initializer_prompt.md
│   └── coding_prompt.md
├── requirements.txt
└── .env.example             # API key template
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--provider` | LLM provider (anthropic, openai, grok) | `anthropic` |
| `--model` | Model to use | Provider's default |
| `--project-dir` | Directory for the project | `./autonomous_demo_project` |
| `--max-iterations` | Max agent iterations | Unlimited |
| `--list-models` | List models for provider | - |

## Customization

### Changing the Application

Edit `prompts/app_spec.txt` to specify a different application to build.

### Adjusting Feature Count

Edit `prompts/initializer_prompt.md` and change the "200 features" requirement to a smaller number.

### Adding New Providers

1. Create a new provider class in `providers/`
2. Extend `BaseProvider` (for custom implementation) or `OpenAICompatibleProvider` (for OpenAI-like APIs)
3. Register in `providers/__init__.py`

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

## Provider Differences

| Feature | Anthropic | OpenAI | Grok |
|---------|-----------|--------|------|
| Sandbox | OS-level (Docker) | Path validation | Path validation |
| MCP Tools | ✅ Puppeteer | ❌ | ❌ |
| Security Hooks | ✅ Pre-tool | Manual validation | Manual validation |
| Streaming | ✅ | Coming soon | Coming soon |

## Troubleshooting

**"Command blocked by security hook"**
The agent tried to run a disallowed command. Add it to `ALLOWED_COMMANDS` in `security.py` if needed.

**"API key not set"**
Set the appropriate environment variable for your provider.

**"Unknown provider"**
Check available providers with `--provider` choices.

**Model errors**
Use `--list-models` to see available models for your provider.

## License

Internal Anthropic use.

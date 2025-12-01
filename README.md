# Autonomous Coding Agent Demo

A minimal harness demonstrating long-running autonomous coding with multiple LLM providers. This demo implements a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions.

**Browser automation via puppeteer-mcp-server is enabled by default for all providers.**

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

**Node.js required** for browser automation (npx auto-downloads puppeteer-mcp-server):

```bash
# Check if Node.js is installed
node --version
npx --version
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

# Disable browser tools
python autonomous_agent_demo.py --provider openai --no-browser --project-dir ./my_project

# Limit iterations for testing
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3

# List available models for a provider
python autonomous_agent_demo.py --provider openai --list-models

# Enable verbose mode to log full JSON responses to file (for debugging)
python autonomous_agent_demo.py --provider openai --verbose --project-dir ./my_project
# Verbose logs are saved to logs/{model-name}-verbose-{timestamp}.md
```

## Important Timing Expectations

> **Warning: This demo takes a long time to run!**

- **First session (initialization):** The agent generates a `feature_list.json` with 50 test cases. This takes several minutes and may appear to hang - this is normal.

- **Subsequent sessions:** Each coding iteration can take **5-15 minutes** depending on complexity and model.

- **Full app:** Building all 50 features typically requires **many hours** of total runtime across multiple sessions.

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

## Browser Automation

**Browser tools are enabled by default for all providers**, matching the behavior of the original Anthropic-only demo. The puppeteer-mcp-server is automatically downloaded via `npx` on first use.

### Available Browser Tools

| Tool | Description |
|------|-------------|
| `puppeteer_navigate` | Navigate to a URL |
| `puppeteer_click` | Click an element by CSS selector |
| `puppeteer_fill` | Fill an input field |
| `puppeteer_screenshot` | Take a screenshot |
| `puppeteer_select` | Select a dropdown option |
| `puppeteer_hover` | Hover over an element |
| `puppeteer_evaluate` | Execute JavaScript in the browser |
| `puppeteer_connect_active_tab` | Connect to existing Chrome instance |

### Requirements

Browser tools require Node.js/npx to be installed. The puppeteer-mcp-server package is automatically downloaded via `npx` when first needed.

If Node.js is not available, the agent will log a warning and continue without browser tools.

### Connecting to Existing Chrome

To use `puppeteer_connect_active_tab`, start Chrome with remote debugging:

```bash
# Using the helper script
./scripts/start_chrome_debug.sh

# Or manually on macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Or with a custom port
python autonomous_agent_demo.py --chrome-debug-port=9223 --project-dir ./my_project
```

### Disabling Browser Tools

If you don't need browser automation:

```bash
python autonomous_agent_demo.py --no-browser --project-dir ./my_project
```

## Security Model

Defense-in-depth security approach:

**For Anthropic (Claude) provider:**
- OS-level sandbox via Claude Agent SDK
- Filesystem restricted to project directory
- Bash commands validated via security hooks
- MCP tools (including Puppeteer) sandboxed

**For OpenAI/Grok providers:**
- Filesystem operations sandboxed to project directory
- Bash command allowlist (see `security.py`)
- Path traversal protection
- MCP adapter for browser tools

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
│   ├── openai_provider.py   # OpenAI models (uses Agents SDK)
│   └── grok_provider.py     # Grok models
├── tools/                    # Tool execution for non-Claude providers
│   ├── __init__.py
│   ├── definitions.py       # Core tool definitions (OpenAI format)
│   ├── browser_definitions.py # Browser tool definitions
│   ├── executor.py          # Sandboxed tool execution
│   └── mcp_adapter.py       # MCP protocol adapter
├── scripts/
│   └── start_chrome_debug.sh # Helper to start Chrome with debugging
├── security.py              # Bash command validation
├── progress.py              # Progress tracking
├── prompts.py               # Prompt loading
├── prompts/
│   ├── app_spec.txt         # Application specification
│   ├── initializer_prompt.md
│   └── coding_prompt.md
├── docs/
│   ├── MULTIMODEL_REFACTOR_PLAN.md
│   ├── PUPPETEER_INTEGRATION_PLAN.md
│   └── tools.md
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
| `--no-browser` | Disable browser automation | Enabled by default |
| `--chrome-debug-port` | Chrome debugging port | `9222` |
| `--verbose` | Log full JSON responses to markdown file in logs/ directory (for debugging) | Disabled |

## Customization

### Changing the Application

Edit `prompts/app_spec.txt` to specify a different application to build.

### Adjusting Feature Count

Edit `prompts/initializer_prompt.md` and change the "50 features" requirement to a smaller number.

### Adding New Providers

1. Create a new provider class in `providers/`
2. Extend `BaseProvider` and implement the required methods
3. Register in `providers/__init__.py`

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

## Provider Differences

| Feature | Anthropic | OpenAI | Grok |
|---------|-----------|--------|------|
| Sandbox | OS-level (Docker) | Path validation | Path validation |
| Browser Tools | ✅ Built-in MCP | ✅ MCP Adapter | ✅ MCP Adapter |
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

**"Warning: Browser tools unavailable"**
Make sure Node.js and npx are installed. The puppeteer-mcp-server is auto-downloaded via npx.

**"MCP server error" or "MCP communication failed"**
- Check that Node.js/npx is installed: `npx --version`
- Try running `npx puppeteer-mcp-server` manually to see error messages
- Ensure Chrome is installed if using headless browser features

**"Port 9222 is already in use"**
- Chrome may already be running with debugging
- Use a different port: `--chrome-debug-port=9223`
- Or close existing Chrome instances

## License

Internal Anthropic use.

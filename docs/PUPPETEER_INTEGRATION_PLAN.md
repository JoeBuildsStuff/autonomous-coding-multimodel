# Puppeteer Tooling Integration Plan

## Goals
- Ensure the Anthropic (Claude) provider in the multimodel harness launches the Puppeteer MCP server exactly like the original demo so browser automation keeps working out of the box.
- Provide a path for OpenAI/Grok providers to access the same browser tooling, either through the MCP server or by reusing its code directly.
- Maintain the existing security posture (sandboxed file access + bash allowlist) regardless of provider.

## Current State
- **Original repo** (`claude-quickstarts/autonomous-coding`) uses `ClaudeSDKClient` and sets `mcp_servers={"puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}}`, so Claude automatically spawns the MCP server locally and exposes `mcp__puppeteer__*` tools.
- **Multimodel repo** currently exposes filesystem + bash tools through `tools/definitions.py` and `tools/executor.py`, but only the Anthropic provider has a built-in MCP environment. OpenAI/Grok providers have no browser automation today.

## Available Puppeteer MCP Tools

The `puppeteer-mcp-server` (located at `/Users/josephtaylor/CodeProjects3/puppeteer-mcp-server`) exposes these 8 tools:

| Tool Name | Description | Required Parameters |
|-----------|-------------|---------------------|
| `puppeteer_connect_active_tab` | Connect to existing Chrome with remote debugging | None (optional: `targetUrl`, `debugPort`) |
| `puppeteer_navigate` | Navigate to a URL | `url` |
| `puppeteer_screenshot` | Take screenshot of page/element | `name` (optional: `selector`, `width`, `height`) |
| `puppeteer_click` | Click an element | `selector` |
| `puppeteer_fill` | Fill an input field | `selector`, `value` |
| `puppeteer_select` | Select dropdown option | `selector`, `value` |
| `puppeteer_hover` | Hover over element | `selector` |
| `puppeteer_evaluate` | Execute JavaScript in browser | `script` |

---

## Phase 1 – Parity for Anthropic Provider

### Status: ✅ COMPLETE

The Anthropic provider (`providers/anthropic.py`) already mirrors the original `client.py` configuration:

- ✅ `PUPPETEER_TOOLS` list defined with all 8 tools (including `puppeteer_connect_active_tab`)
- ✅ `mcp_servers` configured: `{"puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}}`
- ✅ `.claude_settings.json` includes Puppeteer allow rules
- ✅ Security hooks for bash command validation

### Verification Test
```bash
python autonomous_agent_demo.py --provider anthropic --project-dir ./test_puppeteer
# Agent should be able to call mcp__puppeteer__puppeteer_navigate to open localhost:3000
```

---

## Phase 2 – Adapter for OpenAI/Grok Providers

### Status: ✅ COMPLETE

### Implementation

Created an MCP stdio adapter that spawns the puppeteer-mcp-server and proxies tool calls:

**File: `tools/mcp_adapter.py`**
- `MCPAdapter` class for generic MCP server communication via stdio
- `PuppeteerMCPAdapter` specialized for puppeteer-mcp-server
- JSON-RPC protocol implementation for MCP communication
- Async/await support for non-blocking tool execution

**File: `tools/browser_definitions.py`**
- OpenAI-format tool definitions for all 8 browser tools
- Helper functions: `get_browser_tool_definitions()`, `is_browser_tool()`

**File: `tools/executor.py`**
- Updated to handle browser tools via MCP adapter
- Added `execute_async()` method for async tool execution
- `set_mcp_adapter()` method to inject the adapter

**Files: `providers/openai_provider.py`, `providers/grok_provider.py`**
- Added `enable_browser` and `chrome_debug_port` constructor parameters
- Initialize MCP adapter on `__aenter__` if browser enabled
- Clean shutdown on `__aexit__`
- Use async tool execution for browser operations

**File: `providers/__init__.py`**
- Updated `get_provider()` to pass browser flags
- Added `supports_browser_tools()` helper

### Chrome Lifecycle Helper

**File: `scripts/start_chrome_debug.sh`**
- Helper script to start Chrome with remote debugging
- Auto-detects Chrome location on macOS/Linux/Windows
- Creates temporary user profile for clean debugging session
- Usage: `./scripts/start_chrome_debug.sh [port]`

### Usage

```bash
# Enable browser tools for OpenAI
python autonomous_agent_demo.py --provider openai --enable-browser --project-dir ./test

# With custom Chrome debug port
python autonomous_agent_demo.py --provider grok --enable-browser --chrome-debug-port 9223 --project-dir ./test

# Start Chrome with debugging first (optional, for connect_active_tab)
./scripts/start_chrome_debug.sh
```

---

## Phase 3 – Hardening & DX Improvements

### Status: ✅ COMPLETE

### Configuration Options

CLI flags added to `autonomous_agent_demo.py`:
- `--enable-browser`: Enable browser automation tools
- `--chrome-debug-port`: Chrome remote debugging port (default: 9222)

`.env.example` updated with:
- `ENABLE_BROWSER_TOOLS`
- `CHROME_DEBUG_PORT`
- `PUPPETEER_MCP_COMMAND` / `PUPPETEER_MCP_ARGS`

### Error Handling

`MCPAdapter` includes:
- `MCPError` exception class for MCP-specific errors
- Health check via `health_check()` method
- Graceful shutdown in `stop()`
- Timeout handling for requests
- Connection broken detection

### Documentation

README.md updated with:
- Browser automation section
- Available browser tools table
- Chrome setup instructions
- Troubleshooting guide for browser issues

---

## Implementation Checklist

### Phase 1 ✅
- [x] PUPPETEER_TOOLS includes all 8 tools
- [x] mcp_servers configured in Anthropic provider
- [x] Security settings include Puppeteer permissions

### Phase 2 ✅
- [x] Create `tools/mcp_adapter.py`
- [x] Create `tools/browser_definitions.py`
- [x] Update `tools/__init__.py` to export browser tools
- [x] Update `tools/executor.py` to handle browser tool calls
- [x] Update `OpenAIProvider` with `--enable-browser` flag
- [x] Update `GrokProvider` with `--enable-browser` flag
- [x] Create `scripts/start_chrome_debug.sh`

### Phase 3 ✅
- [x] Add CLI flags for browser configuration
- [x] Add `.env` variables for MCP configuration
- [x] Implement health check for MCP adapter
- [x] Add error handling and logging
- [x] Update README with browser tool documentation

### Future Improvements (Optional)
- [ ] Add integration test for browser tools
- [ ] Test in headless environment (document fallback)
- [ ] Add streaming support for browser tool results
- [ ] Consider Playwright alternative for better cross-browser support

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    autonomous_agent_demo.py                      │
│                         (CLI entry point)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          agent.py                                │
│                    (session management)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Anthropic     │   │     OpenAI      │   │      Grok       │
│   Provider      │   │    Provider     │   │    Provider     │
│                 │   │                 │   │                 │
│ Built-in MCP    │   │ MCP Adapter     │   │ MCP Adapter     │
│ (puppeteer)     │   │ (if enabled)    │   │ (if enabled)    │
└─────────────────┘   └─────────────────┘   └─────────────────┘
          │                     │                     │
          │                     ▼                     │
          │           ┌─────────────────┐             │
          │           │  ToolExecutor   │◄────────────┘
          │           │                 │
          │           │ - File tools    │
          │           │ - Bash tools    │
          │           │ - Browser tools │
          │           │   (via adapter) │
          │           └─────────────────┘
          │                     │
          │                     ▼
          │           ┌─────────────────┐
          │           │   MCPAdapter    │
          │           │                 │
          │           │ JSON-RPC stdio  │
          │           └─────────────────┘
          │                     │
          ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    puppeteer-mcp-server                          │
│                    (npm package)                                 │
│                                                                  │
│  puppeteer_navigate | puppeteer_click | puppeteer_fill | ...    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Chrome Browser                           │
│                   (headless or with debugging)                   │
└─────────────────────────────────────────────────────────────────┘
```

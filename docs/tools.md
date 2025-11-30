# Claude SDK Tool Behaviors (Original Demo)

This document summarizes how the Anthropic-only prototype wires up the Claude Agent SDK tools so we can mirror or extend the behavior in the multi-provider refactor.

## Execution pipeline

- `client.py` registers the SDK built-ins plus Puppeteer MCP tools via `ClaudeCodeOptions.allowed_tools` and mirrors the list in `.claude_settings.json`, which constrains filesystem and bash access to the project directory (`claude-quickstarts/autonomous-coding/client.py:18-121`).
- File-based tools (`Read`, `Write`, `Edit`, `Glob`, `Grep`) do not have local handlers—the CLI executes them directly using the schemas published in `sdk-tools.d.ts` under the Claude CLI install (`~/.nvm/.../@anthropic-ai/claude-code/sdk-tools.d.ts`). Those schemas describe the arguments/behavior we need to be compatible with.
- Only `Bash` gets custom logic: the Python side registers `bash_security_hook` for the `PreToolUse` event so every bash invocation is validated before it reaches the CLI sandbox (`claude-quickstarts/autonomous-coding/security.py:1-205,220-366`).

## Built-in file tools

Information below is taken from `sdk-tools.d.ts` and the surrounding comments.

### `Read` (`FileReadInput`, `sdk-tools.d.ts:120-132`)
- Required: absolute `file_path` within the allowed workspace.
- Optional pagination knobs: `offset` (line number to start at) and `limit` (line count to read). SDK uses them to avoid pulling massive files into context. No chunking logic exists in repo; CLI performs the slicing.

### `Write` (`FileWriteInput`, `sdk-tools.d.ts:134-141`)
- Required: absolute `file_path` and full-file `content`. The SDK overwrites the target file; there is no append mode.
- Because `permissions.allow` only whitelists `./**`, the CLI refuses writes outside the project dir even if the agent supplies an absolute path.

### `Edit` (`FileEditInput`, `sdk-tools.d.ts:102-118`)
- Required: `file_path`, `old_string`, `new_string`.
- Optional `replace_all` toggles single replacement vs. global patch. CLI enforces `old_string != new_string` and fails if the target text is missing.

### `Glob` (`GlobInput`, `sdk-tools.d.ts:144-152`)
- Required pattern follows standard glob semantics.
- Optional `path` overrides the search root; leaving it blank defaults to the sandbox working directory. Comments explicitly warn not to send the literal string `"undefined"`.

### `Grep` (`GrepInput`, `sdk-tools.d.ts:154-215`)
- Wraps `rg` with structured flags: regex `pattern`, optional `path`, `glob` filter, and `type` (maps to `rg --type`).
- Output modes: `content`, `files_with_matches`, or `count`; context flags (`-A`, `-B`, `-C`), line numbers (`-n` default true when in content mode), case-insensitive (`-i`), multiline, plus `head_limit`/`offset` to throttle results. The CLI enforces which combinations apply to which mode.

## Bash tool & shell lifecycle

### `Bash` (`BashInput`, `sdk-tools.d.ts:35-76`)
- Takes raw `command`, optional `timeout`, `description`, `run_in_background`, and `dangerouslyDisableSandbox` (must stay false in this demo).
- Execution order:
  1. SDK calls `bash_security_hook` before hitting the CLI. The hook tokenizes the command, ensures every executable belongs to `ALLOWED_COMMANDS`, and runs extra validation for `pkill`, `chmod`, and `./init.sh` (`security.py:18-205,220-366`).
  2. If allowed, the CLI runs the command inside its OS-level sandbox rooted at the project directory (set via `ClaudeCodeOptions.cwd`).
  3. Background commands return a `bash_id`; foregound commands stream stdout/stderr inline.

### `BashOutput` (`sdk-tools.d.ts:77-91`)
- Lets the agent read incremental output from a background shell by supplying the `bash_id`. Optional `filter` accepts a regex so the SDK only forwards matching lines.

### `KillShell` (`sdk-tools.d.ts:216-222`)
- Terminates a background shell by ID. Not exposed in `allowed_tools` here, but part of the CLI schema for long-lived sessions.

## Puppeteer MCP tools

Configured in `client.py` as `mcp__puppeteer__*` tool IDs (`client.py:18-27,106-111`). The Python SDK spawns `npx puppeteer-mcp-server`, and each tool maps to a browser automation primitive:

- `puppeteer_navigate` – load a URL and wait for DOM readiness.
- `puppeteer_screenshot` – capture the current page state (full or selector-based).
- `puppeteer_click`, `puppeteer_hover`, `puppeteer_fill`, `puppeteer_select` – basic interaction APIs mirroring Puppeteer’s page helpers.
- `puppeteer_evaluate` – run arbitrary JS in the page context.

Because they originate from MCP, the CLI handles permissions; the Python side simply whitelists the tool IDs and lets the external MCP server enforce any per-command validation.

## Key takeaways for the refactor

1. Maintain parity with the CLI schemas so OpenAI/Grok tools accept the same arguments (especially `Grep`/`Bash` where there are many structured options).
2. Preserve the defense-in-depth stack: filesystem allowlist via settings, path validation in provider layer, and pre-tool hooks for bash commands.
3. Treat Puppeteer tools as opaque RPC calls; reproducing them outside the Claude SDK would mean either reusing the MCP server or reimplementing equivalent browser tooling (e.g., Playwright) with similar commands.

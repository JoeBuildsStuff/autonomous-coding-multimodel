"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
from pathlib import Path
from typing import Optional

from providers import (
    get_provider,
    get_default_model,
    BaseProvider,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from progress import print_session_header, print_progress_summary
from prompts import get_initializer_prompt, get_coding_prompt, copy_spec_to_project


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    provider: BaseProvider,
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using the given provider.

    Args:
        provider: The LLM provider to use
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    print("Sending prompt to agent...\n")

    try:
        # Send the query
        await provider.query(message)

        # Collect response text and show tool use
        response_text = ""
        async for msg in provider.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]", flush=True)
                        input_str = str(block.input)
                        if len(input_str) > 200:
                            print(f"   Input: {input_str[:200]}...", flush=True)
                        else:
                            print(f"   Input: {input_str}", flush=True)

            elif isinstance(msg, UserMessage):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        # Check if command was blocked
                        if "blocked" in block.content.lower():
                            print(f"   [BLOCKED] {block.content}", flush=True)
                        elif block.is_error:
                            # Show errors (truncated)
                            error_str = block.content[:500]
                            print(f"   [Error] {error_str}", flush=True)
                        else:
                            # Tool succeeded - just show brief confirmation
                            print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        print(f"Error during agent session: {e}")
        return "error", str(e)


async def run_autonomous_agent(
    project_dir: Path,
    provider_name: str,
    model: str | None = None,
    max_iterations: Optional[int] = None,
    enable_browser: bool = False,
    chrome_debug_port: int = 9222,
    verbose: bool = False,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        provider_name: Name of the LLM provider to use
        model: Model to use (defaults to provider's default)
        max_iterations: Maximum number of iterations (None for unlimited)
        enable_browser: Whether to enable browser automation tools
        chrome_debug_port: Chrome debugging port for browser connection
        verbose: Whether to print full JSON responses from the provider
    """
    # Use default model if not specified
    if model is None:
        model = get_default_model(provider_name)
    
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nProvider: {provider_name}")
    print(f"Model: {model}")
    print(f"Project directory: {project_dir}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    if enable_browser:
        print(f"Browser tools: Enabled (Chrome debug port: {chrome_debug_port})")
    if verbose:
        print("Verbose mode: Enabled (full JSON responses will be logged to file)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    tests_file = project_dir / "feature_list.json"
    is_first_run = not tests_file.exists()

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()
        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is generating 200 detailed test cases.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project")
        print_progress_summary(project_dir)

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_first_run)

        # Create provider (fresh context for each session)
        provider = get_provider(
            provider_name,
            model,
            project_dir,
            enable_browser=enable_browser,
            chrome_debug_port=chrome_debug_port,
            verbose=verbose,
        )

        # Choose prompt based on session type
        if is_first_run:
            prompt = get_initializer_prompt()
            is_first_run = False  # Only use initializer once
        else:
            prompt = get_coding_prompt()

        # Run session with async context manager
        async with provider:
            status, response = await run_agent_session(provider, prompt, project_dir)

        # Handle status
        if status == "continue":
            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            print("\nSession encountered an error")
            print("Will retry with a fresh session...")
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        # Small delay between sessions
        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")

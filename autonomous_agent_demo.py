#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with multiple LLM providers.
This script implements the two-agent pattern (initializer + coding agent) and
supports Anthropic (Claude), OpenAI, and Grok models.

Example Usage:
    # Using Claude (default)
    python autonomous_agent_demo.py --project-dir ./my_project
    
    # Using OpenAI
    python autonomous_agent_demo.py --provider openai --model gpt-4o --project-dir ./my_project
    
    # Using Grok
    python autonomous_agent_demo.py --provider grok --project-dir ./my_project
"""

import argparse
import asyncio
import os
from pathlib import Path

from agent import run_autonomous_agent
from providers import (
    get_available_providers,
    get_default_model,
    get_required_env_var,
    get_available_models,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Multi-model agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh project with Claude (default)
  python autonomous_agent_demo.py --project-dir ./my_app

  # Use OpenAI GPT-4o
  python autonomous_agent_demo.py --provider openai --model gpt-4o --project-dir ./my_app

  # Use Grok
  python autonomous_agent_demo.py --provider grok --project-dir ./my_app

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir ./my_app --max-iterations 3

  # List available models for a provider
  python autonomous_agent_demo.py --provider openai --list-models

Environment Variables:
  ANTHROPIC_API_KEY    For Claude models (anthropic provider)
  OPENAI_API_KEY       For GPT models (openai provider)
  XAI_API_KEY          For Grok models (grok provider)
        """,
    )

    parser.add_argument(
        "--provider",
        type=str,
        default="anthropic",
        choices=get_available_providers(),
        help="LLM provider to use (default: anthropic)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (defaults to provider's default model)",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project (default: generations/autonomous_demo_project)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models for the selected provider and exit",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Handle --list-models
    if args.list_models:
        print(f"\nAvailable models for '{args.provider}' provider:")
        print("-" * 40)
        default = get_default_model(args.provider)
        for model in get_available_models(args.provider):
            marker = " (default)" if model == default else ""
            print(f"  {model}{marker}")
        print()
        return

    # Check for required API key
    env_var = get_required_env_var(args.provider)
    if not os.environ.get(env_var):
        print(f"Error: {env_var} environment variable not set")
        print()
        
        # Provide helpful instructions based on provider
        if args.provider == "anthropic":
            print("Get your API key from: https://console.anthropic.com/")
        elif args.provider == "openai":
            print("Get your API key from: https://platform.openai.com/api-keys")
        elif args.provider == "grok":
            print("Get your API key from: https://console.x.ai/")
        
        print(f"\nThen set it:")
        print(f"  export {env_var}='your-api-key-here'")
        return

    # Automatically place projects in generations/ directory unless already specified
    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/"):
        if project_dir.is_absolute():
            pass  # Use absolute paths as-is
        else:
            project_dir = Path("generations") / project_dir

    # Use default model if not specified
    model = args.model or get_default_model(args.provider)

    # Run the agent
    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                provider_name=args.provider,
                model=model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()

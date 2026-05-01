"""Typer CLI entry point."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from .agent import run_agent
from .providers import get_provider

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def run(
    folder: Path = typer.Argument(..., help="Folder containing one .py and one .xlsx"),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help="LLM provider: 'gemini' or 'claude'. Defaults to LLM_PROVIDER env var.",
    ),
    budget: float = typer.Option(
        0.50, "--budget", "-b", help="Hard cap on USD spend per run."
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Skip the human Q&A step (uses sensible defaults). Useful for CI.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Where to write the generated .md file."
    ),
) -> None:
    """Document a folder of production work as a single Markdown file."""
    load_dotenv()
    p = get_provider(provider)
    console.print(
        f"[dim]Provider:[/dim] [bold]{p.name}[/bold]  "
        f"[dim]Budget:[/dim] [bold]${budget:.2f}[/bold]  "
        f"[dim]Folder:[/dim] [bold]{folder}[/bold]"
    )
    result = run_agent(
        folder,
        provider=p,
        budget_usd=budget,
        interactive=not non_interactive,
        output_dir=output_dir,
    )
    raise typer.Exit(0 if result.output_path.exists() else 1)


@app.command()
def info() -> None:
    """Print configured providers and pricing."""
    load_dotenv()
    console.print("Configured environment:")
    console.print(f"  LLM_PROVIDER:      {os.environ.get('LLM_PROVIDER', '(unset)')}")
    console.print(
        f"  GEMINI_API_KEY:    {'set' if os.environ.get('GEMINI_API_KEY') else 'NOT SET'}"
    )
    console.print(
        f"  ANTHROPIC_API_KEY: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET'}"
    )


if __name__ == "__main__":
    app()

from __future__ import annotations

import socket
import webbrowser
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console

from prreviewbot.web.app import create_app

app = typer.Typer(add_completion=False, help="PRreviewBot - local PR review & suggestion bot.")
console = Console()


def _pick_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    # fallback: ask OS for free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port (auto-fallback if busy)"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser"),
    data_dir: Optional[Path] = typer.Option(None, help="Config dir (defaults to ~/.prreviewbot)"),
):
    """Start the local web UI."""
    chosen_port = _pick_port(port)
    url = f"http://{host}:{chosen_port}"
    if open_browser:
        webbrowser.open(url, new=2)

    console.print(f"[bold]PRreviewBot[/bold] running at {url}")
    uvicorn.run(
        create_app(data_dir=data_dir),
        host=host,
        port=chosen_port,
        log_level="info",
    )


@app.command()
def review(
    pr_link: str = typer.Argument(..., help="Pull request URL (GitHub/GitLab/Bitbucket/Azure DevOps)"),
    language: Optional[str] = typer.Option(None, help="Language override (e.g. python, typescript)"),
    llm_provider: Optional[str] = typer.Option(None, help="LLM provider override (heuristic|openai|azure_openai)"),
    llm_model: Optional[str] = typer.Option(None, help="Model/deployment override (e.g. gpt-4o-mini or deployment)"),
    data_dir: Optional[Path] = typer.Option(None, help="Config dir (defaults to ~/.prreviewbot)"),
):
    """Run a review headlessly and print a markdown report."""
    from prreviewbot.core.review_service import ReviewService
    from prreviewbot.storage.config import ConfigStore

    cfg = ConfigStore(data_dir=data_dir).load()
    service = ReviewService.from_config(cfg)
    result = service.review(pr_link=pr_link, language=language, llm_provider=llm_provider, llm_model=llm_model)
    console.print(result.as_markdown())



#!/usr/bin/env python3
"""AgentReady — AI Agent-Readiness Auditor CLI."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

app = typer.Typer(
    name="agentready",
    help="AI Agent-Readiness Auditor — score any URL for AI agent compatibility.",
    add_completion=False,
)
console = Console()


def _validate_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        console.print(f"[red]Invalid URL: {url}[/red]")
        raise typer.Exit(1)
    return url


def _output_path(url: str, fmt: str, output_dir: str) -> str:
    domain = urlparse(url).netloc.replace(".", "_").replace(":", "_")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(output_dir) / f"agentready_{domain}.{fmt}")


async def _run_audit(url: str, skip_ai: bool) -> "AuditResult":
    from agentready.crawler import render_page
    from agentready.checks import (
        check_semantic_html,
        check_accessibility,
        check_layout_stability,
        check_interactive_elements,
        check_action_clarity,
    )
    from agentready.scorer import compute_score
    from agentready.ai_layer import get_recommendations

    page_data = await render_page(url)

    categories = [
        check_semantic_html(page_data.html),
        check_accessibility(page_data.html, page_data.a11y_snapshot),
        check_layout_stability(page_data.html, page_data.cls_score),
        check_interactive_elements(page_data.interactive_elements),
        check_action_clarity(page_data.html, page_data.interactive_elements),
    ]

    result = compute_score(url, categories, screenshot_b64=page_data.screenshot_b64)

    if not skip_ai:
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[yellow]⚠ ANTHROPIC_API_KEY not set — skipping AI recommendations.[/yellow]")
        else:
            result.recommendations = get_recommendations(result)

    return result, page_data.page_title


@app.command()
def audit(
    url: str = typer.Argument(..., help="URL to audit"),
    output: str = typer.Option("reports", "--output", "-o", help="Output directory for reports"),
    fmt: str = typer.Option("html", "--format", "-f", help="Output format: html, json, or both"),
    skip_ai: bool = typer.Option(False, "--no-ai", help="Skip Claude AI recommendations"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress CLI report, only save files"),
):
    """Audit a single URL for AI agent-readiness."""
    url = _validate_url(url)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("Rendering page with Playwright...", total=None)
        result, page_title = asyncio.run(_run_audit(url, skip_ai))
        progress.update(task, description="Generating report...")

    if not quiet:
        from agentready.reporter import print_cli_report
        print_cli_report(result)

    from agentready.reporter import save_html, save_json

    saved = []
    if fmt in ("html", "both"):
        path = _output_path(url, "html", output)
        save_html(result, path, page_title=page_title)
        saved.append(path)
    if fmt in ("json", "both"):
        path = _output_path(url, "json", output)
        save_json(result, path)
        saved.append(path)

    for path in saved:
        console.print(f"[dim]Saved → {path}[/dim]")


@app.command()
def bulk(
    urls_file: str = typer.Argument(..., help="Path to file with one URL per line, or comma-separated URLs"),
    output: str = typer.Option("reports", "--output", "-o", help="Output directory"),
    fmt: str = typer.Option("html", "--format", "-f", help="Output format: html, json, or both"),
    skip_ai: bool = typer.Option(False, "--no-ai", help="Skip Claude AI recommendations"),
    delay: float = typer.Option(2.0, "--delay", "-d", help="Seconds between requests"),
):
    """Audit multiple URLs from a file (one per line) or a comma-separated list."""
    import time

    # Accept either a file path or a comma-separated string
    p = Path(urls_file)
    if p.exists():
        raw_urls = p.read_text().strip().splitlines()
    else:
        raw_urls = [u.strip() for u in urls_file.split(",")]

    urls = [_validate_url(u.strip()) for u in raw_urls if u.strip() and not u.startswith("#")]

    if not urls:
        console.print("[red]No URLs found.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]AgentReady Bulk Audit[/bold] — {len(urls)} URL(s)")

    from agentready.reporter import save_html, save_json, print_cli_report

    results_summary = []

    for i, url in enumerate(urls, 1):
        console.print(f"\n[dim][{i}/{len(urls)}][/dim] {url}")
        try:
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
                t = prog.add_task("Auditing...", total=None)
                result, page_title = asyncio.run(_run_audit(url, skip_ai))

            print_cli_report(result)

            if fmt in ("html", "both"):
                path = _output_path(url, "html", output)
                save_html(result, path, page_title=page_title)
                console.print(f"[dim]Saved → {path}[/dim]")
            if fmt in ("json", "both"):
                path = _output_path(url, "json", output)
                save_json(result, path)
                console.print(f"[dim]Saved → {path}[/dim]")

            results_summary.append({"url": url, "score": result.overall_score, "grade": result.grade})

        except Exception as e:
            console.print(f"[red]Error auditing {url}: {e}[/red]")
            results_summary.append({"url": url, "score": None, "grade": "ERR", "error": str(e)})

        if i < len(urls):
            time.sleep(delay)

    # Summary table
    from rich.table import Table
    from rich import box as rbox
    console.print()
    console.print("[bold]Bulk Audit Summary[/bold]")
    tbl = Table(box=rbox.ROUNDED)
    tbl.add_column("URL", style="dim")
    tbl.add_column("Score", justify="right")
    tbl.add_column("Grade", justify="center")
    for r in results_summary:
        score_str = f"{r['score']}/100" if r['score'] is not None else "ERROR"
        color = "green" if r.get("grade", "F") in ("A", "B") else ("yellow" if r.get("grade") == "C" else "red")
        tbl.add_row(r["url"], f"[{color}]{score_str}[/{color}]", f"[{color}]{r['grade']}[/{color}]")
    console.print(tbl)


if __name__ == "__main__":
    app()

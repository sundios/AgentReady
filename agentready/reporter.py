import json
import os
from pathlib import Path
from textwrap import wrap

from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from .models import AuditResult

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
console = Console()

SEVERITY_COLORS = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "green",
}

GRADE_COLORS = {
    "A": "bold green",
    "B": "green",
    "C": "yellow",
    "D": "red",
    "F": "bold red",
}


def _score_color(pct: float) -> str:
    if pct >= 80:
        return "green"
    elif pct >= 50:
        return "yellow"
    return "red"


def print_cli_report(result: AuditResult) -> None:
    console.print()
    grade_color = GRADE_COLORS.get(result.grade, "white")

    console.print(f"[bold]AgentReady Audit[/bold]  [dim]{result.url}[/dim]")
    console.print(
        f"Overall Score: [{grade_color}]{result.overall_score}/100  Grade: {result.grade}[/{grade_color}]"
    )
    console.print()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Category", style="bold", width=24)
    table.add_column("Score", justify="right", width=10)
    table.add_column("Checks", justify="right", width=10)
    table.add_column("Status", width=30)

    for cat in result.categories:
        pct = cat.percentage
        color = _score_color(pct)
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        table.add_row(
            cat.category,
            f"[{color}]{cat.score:.0f}/{cat.max_score:.0f}[/{color}]",
            f"{cat.passed_checks}/{cat.total_checks}",
            f"[{color}]{bar}[/{color}]",
        )
    console.print(table)

    all_issues = [
        (cat.category, issue)
        for cat in result.categories
        for issue in cat.issues
    ]

    if all_issues:
        console.print()
        console.print("[bold]Issues Found:[/bold]")
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_issues = sorted(all_issues, key=lambda x: severity_order.get(x[1].severity, 99))
        for cat_name, issue in sorted_issues:
            color = SEVERITY_COLORS.get(issue.severity, "white")
            console.print(f"  [{color}][{issue.severity.upper()}][/{color}]  {issue.title}")
            for line in wrap(issue.description, width=console.width - 10):
                console.print(f"  [dim]        {line}[/dim]")

    if result.recommendations:
        console.print()
        console.print("[bold]Top AI Recommendations:[/bold]")
        for i, rec in enumerate(result.recommendations[:5], 1):
            color = SEVERITY_COLORS.get(rec.severity, "white")
            console.print(
                f"  {i}. [{color}]{rec.issue}[/{color}]  "
                f"[dim]({rec.category} · CRO: {rec.cro_impact} · Effort: {rec.effort})[/dim]"
            )
            for line in wrap(rec.fix, width=console.width - 6):
                console.print(f"     [dim]{line}[/dim]")
    console.print()


def to_json(result: AuditResult) -> str:
    def _ser(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _ser(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [_ser(i) for i in obj]
        return obj

    data = _ser(result)
    # Don't embed full screenshot in JSON to keep it readable
    data.pop("screenshot_b64", None)
    return json.dumps(data, indent=2)


def to_html(result: AuditResult, page_title: str = "") -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("report.html")
    return template.render(result=result, page_title=page_title)


def save_html(result: AuditResult, output_path: str, page_title: str = "") -> str:
    html = to_html(result, page_title=page_title)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def save_json(result: AuditResult, output_path: str) -> str:
    Path(output_path).write_text(to_json(result), encoding="utf-8")
    return output_path

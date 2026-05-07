import json
import os
from typing import Optional

import anthropic

from .models import AuditResult, CategoryResult, Issue, Recommendation

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an AI agent-readiness expert specializing in making websites navigable by autonomous AI agents (like browser-use, Claude computer-use, and similar systems).

You analyze structured audit findings from AgentReady — a tool that checks websites across five categories:
1. Semantic HTML (role attributes, button/anchor usage, landmark elements)
2. Accessibility Tree (ARIA labels, input associations, named interactive elements)
3. Layout Stability (CLS score, image dimensions, animation impact)
4. Interactive Elements (element sizes, cursor styles, ghost overlays)
5. Agent Action Clarity (CTA visibility, form submit buttons, nav structure)

When given audit results, return a JSON array of recommendations. Each recommendation object must have exactly these fields:
- "category": the audit category this addresses (string)
- "severity": one of "critical", "high", "medium", "low" (string)
- "issue": short title of the problem (string, max 80 chars)
- "fix": specific, actionable fix description in 2-3 sentences (string)
- "code_example": concrete before/after HTML or CSS snippet (string, use actual code not pseudocode)
- "cro_impact": "high", "medium", or "low" estimated conversion rate impact (string)
- "effort": "low", "medium", or "high" implementation effort (string)

Sort by: critical first, then high, then medium, then low. Within each severity, high cro_impact first.
Return ONLY a valid JSON array. No markdown, no explanation, no code fences."""


def _build_findings_prompt(result: AuditResult) -> str:
    lines = [
        f"URL: {result.url}",
        f"Overall Score: {result.overall_score}/100 (Grade: {result.grade})",
        "",
        "CATEGORY SCORES:",
    ]
    for cat in result.categories:
        lines.append(f"  {cat.category}: {cat.score}/{cat.max_score} ({cat.passed_checks}/{cat.total_checks} checks passed)")

    lines.append("\nISSUES FOUND:")
    has_issues = False
    for cat in result.categories:
        for issue in cat.issues:
            has_issues = True
            lines.append(f"\n[{cat.category}] [{issue.severity.upper()}] {issue.title}")
            lines.append(f"  {issue.description}")
            if issue.element:
                lines.append(f"  Element: {issue.element[:200]}")

    if not has_issues:
        lines.append("  No issues found — all checks passed.")

    return "\n".join(lines)


def get_recommendations(result: AuditResult) -> list[Recommendation]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    client = anthropic.Anthropic(api_key=api_key)
    findings = _build_findings_prompt(result)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze these audit findings and return prioritized recommendations:\n\n{findings}",
                }
            ],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if model wraps anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        return [
            Recommendation(
                category=r.get("category", ""),
                severity=r.get("severity", "medium"),
                issue=r.get("issue", ""),
                fix=r.get("fix", ""),
                code_example=r.get("code_example", ""),
                cro_impact=r.get("cro_impact", "medium"),
                effort=r.get("effort", "medium"),
            )
            for r in data
            if isinstance(r, dict)
        ]

    except Exception as e:
        return []

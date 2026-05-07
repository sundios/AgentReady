from .models import AuditResult, CategoryResult
from datetime import datetime, timezone


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 50:
        return "D"
    return "F"


def compute_score(
    url: str,
    categories: list[CategoryResult],
    screenshot_b64: str | None = None,
) -> AuditResult:
    overall = sum(c.score for c in categories)
    max_total = sum(c.max_score for c in categories)
    normalized = round((overall / max_total) * 100, 1) if max_total > 0 else 0

    return AuditResult(
        url=url,
        timestamp=datetime.now(timezone.utc).isoformat(),
        overall_score=normalized,
        grade=_grade(normalized),
        categories=categories,
        screenshot_b64=screenshot_b64,
    )

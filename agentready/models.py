from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    element: Optional[str] = None


@dataclass
class CategoryResult:
    category: str
    score: float
    max_score: float
    passed_checks: int
    total_checks: int
    issues: list[Issue] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


@dataclass
class Recommendation:
    category: str
    severity: str
    issue: str
    fix: str
    code_example: str
    cro_impact: str
    effort: str


@dataclass
class AuditResult:
    url: str
    timestamp: str
    overall_score: float
    grade: str
    categories: list[CategoryResult] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    screenshot_b64: Optional[str] = None
    error: Optional[str] = None

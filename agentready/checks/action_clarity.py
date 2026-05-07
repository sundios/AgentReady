from bs4 import BeautifulSoup
from ..models import CategoryResult, Issue

MAX_SCORE = 10

CTA_KEYWORDS = {
    "buy", "purchase", "add to cart", "checkout", "order", "subscribe",
    "sign up", "register", "get started", "start free", "try", "download",
    "contact", "book", "schedule", "learn more", "shop now", "apply",
    "request", "join", "create account", "log in", "login", "sign in",
    "submit", "send", "continue", "next", "confirm",
}


def _has_cta(soup: BeautifulSoup) -> tuple[bool, list[str]]:
    found = []
    for el in soup.find_all(["button", "a"]):
        text = (el.get_text() or "").strip().lower()
        if any(kw in text for kw in CTA_KEYWORDS):
            found.append(text[:60])
    return bool(found), found


def check_action_clarity(html: str, interactive_elements: list[dict]) -> CategoryResult:
    soup = BeautifulSoup(html, "lxml")
    issues: list[Issue] = []
    passed = 0

    # 1. Primary CTA visible above fold (3pts)
    # Above fold = y < viewport height (800px assumed), or first interactive with CTA keyword
    above_fold_ctas = [
        el for el in interactive_elements
        if el.get("visible")
        and el.get("y", 9999) < 800
        and el.get("tag") in ("button", "a")
        and any(kw in (el.get("text") or "").lower() for kw in CTA_KEYWORDS)
    ]
    has_cta, all_ctas = _has_cta(soup)
    if above_fold_ctas:
        passed += 1
        score_cta = 3
    elif has_cta:
        issues.append(Issue(
            severity="medium",
            title="Primary CTA not visible above the fold",
            description=f"CTA buttons exist ({', '.join(all_ctas[:3])}) but none appear above the fold (first 800px). Agents may not identify the primary action without scrolling.",
        ))
        score_cta = 1
    else:
        issues.append(Issue(
            severity="high",
            title="No clear call-to-action detected",
            description="No button or link with recognizable CTA text was found. Agents cannot determine the intended user journey on this page.",
        ))
        score_cta = 0

    # 2. Forms have clear labels and submit buttons (4pts)
    forms = soup.find_all("form")
    form_score = 4
    if forms:
        forms_without_submit = []
        for form in forms:
            has_submit = bool(
                form.find("button", type=lambda t: t in (None, "submit"))
                or form.find("input", attrs={"type": "submit"})
            )
            if not has_submit:
                forms_without_submit.append(str(form)[:200])
        if forms_without_submit:
            form_score = 2
            issues.append(Issue(
                severity="high",
                title="Forms without submit buttons",
                description=f"{len(forms_without_submit)} form(s) have no submit button. Agents cannot complete form journeys without a clear submission mechanism.",
                element=forms_without_submit[0],
            ))
    else:
        pass  # No forms — not a penalty

    # 3. Navigation structure is clear (3pts)
    nav_score = 3
    nav_els = soup.find_all(["nav"]) or soup.find_all(attrs={"role": "navigation"})
    if not nav_els:
        nav_score = 0
        issues.append(Issue(
            severity="medium",
            title="No navigation landmark detected",
            description="No <nav> element or role='navigation' found. Agents use nav landmarks to understand site structure and available destinations.",
        ))
    else:
        nav_links = nav_els[0].find_all("a") if nav_els else []
        if len(nav_links) < 2:
            nav_score = 1
            issues.append(Issue(
                severity="low",
                title="Navigation contains fewer than 2 links",
                description="The primary navigation has very few links, limiting an agent's ability to plan multi-step journeys across the site.",
            ))

    if not forms or not issues:
        passed += 1 if form_score >= 3 else 0
    if nav_els and nav_score >= 2:
        passed += 1

    total_score = min(score_cta + form_score + nav_score, MAX_SCORE)
    passed_checks = sum([
        score_cta >= 2,
        form_score >= 3,
        nav_score >= 2,
    ])

    return CategoryResult(
        category="Agent Action Clarity",
        score=total_score,
        max_score=MAX_SCORE,
        passed_checks=passed_checks,
        total_checks=3,
        issues=issues,
    )

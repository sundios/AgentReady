from bs4 import BeautifulSoup
from ..models import CategoryResult, Issue

MAX_SCORE = 25
CHECKS = 5
PTS_EACH = MAX_SCORE // CHECKS


def check_semantic_html(html: str) -> CategoryResult:
    soup = BeautifulSoup(html, "lxml")
    issues: list[Issue] = []
    passed = 0

    # 1. Interactive divs/spans without role
    bad_divspans = []
    for el in soup.find_all(["div", "span"]):
        has_onclick = el.get("onclick") or el.get("ng-click") or el.get("@click")
        has_tabindex = el.get("tabindex") is not None and el.get("tabindex") != "-1"
        has_role = el.get("role")
        if (has_onclick or has_tabindex) and not has_role:
            bad_divspans.append(str(el)[:150])
    if bad_divspans:
        issues.append(Issue(
            severity="high",
            title="Interactive divs/spans without role attribute",
            description=f"{len(bad_divspans)} div/span element(s) appear interactive (onclick/tabindex) but lack a role attribute. Agents cannot determine these are actionable.",
            element=bad_divspans[0],
        ))
    else:
        passed += 1

    # 2. Buttons use <button> or have role="button"
    custom_buttons = []
    for el in soup.find_all(attrs={"role": "button"}):
        if el.name not in ("button", "input", "a"):
            if not el.get("tabindex"):
                custom_buttons.append(str(el)[:150])
    if custom_buttons:
        issues.append(Issue(
            severity="medium",
            title="Custom button elements missing tabindex",
            description=f"{len(custom_buttons)} element(s) have role='button' but are missing tabindex='0', making them inaccessible to keyboard agents.",
            element=custom_buttons[0],
        ))
    else:
        passed += 1

    # 3. Links use <a> with href
    bad_links = []
    for el in soup.find_all("a"):
        if not el.get("href"):
            bad_links.append(str(el)[:150])
    if bad_links:
        issues.append(Issue(
            severity="medium",
            title="Anchor tags without href attribute",
            description=f"{len(bad_links)} <a> element(s) lack an href. Agents treat hrefless anchors as non-navigable, breaking journey mapping.",
            element=bad_links[0],
        ))
    else:
        passed += 1

    # 4. Labels have 'for' attribute linking to inputs
    bad_labels = []
    for label in soup.find_all("label"):
        if not label.get("for") and not label.find(["input", "select", "textarea"]):
            bad_labels.append(str(label)[:150])
    if bad_labels:
        issues.append(Issue(
            severity="high",
            title="Labels not associated with inputs",
            description=f"{len(bad_labels)} <label> element(s) lack a 'for' attribute and don't wrap their input. Agents cannot map field labels to inputs.",
            element=bad_labels[0],
        ))
    else:
        passed += 1

    # 5. Semantic landmark elements exist
    has_main = bool(soup.find("main") or soup.find(attrs={"role": "main"}))
    has_nav = bool(soup.find("nav") or soup.find(attrs={"role": "navigation"}))
    if not has_main or not has_nav:
        missing = []
        if not has_main:
            missing.append("<main>")
        if not has_nav:
            missing.append("<nav>")
        issues.append(Issue(
            severity="medium",
            title="Missing semantic landmark elements",
            description=f"Page is missing: {', '.join(missing)}. Landmarks give agents a high-level map of page structure.",
        ))
    else:
        passed += 1

    score = passed * PTS_EACH
    return CategoryResult(
        category="Semantic HTML",
        score=score,
        max_score=MAX_SCORE,
        passed_checks=passed,
        total_checks=CHECKS,
        issues=issues,
    )

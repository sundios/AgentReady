from bs4 import BeautifulSoup
from ..models import CategoryResult, Issue

MAX_SCORE = 25
CHECKS = 5
PTS_EACH = MAX_SCORE // CHECKS

LANDMARK_ROLES = {"main", "nav", "navigation", "header", "banner", "footer", "contentinfo", "complementary", "search"}


def check_accessibility(html: str, a11y_snapshot: list[dict]) -> CategoryResult:
    soup = BeautifulSoup(html, "lxml")
    issues: list[Issue] = []
    passed = 0

    all_nodes: list[dict] = a11y_snapshot or []

    interactive_roles = {
        "button", "link", "checkbox", "radio", "textbox", "combobox",
        "listbox", "menuitem", "menuitemcheckbox", "menuitemradio",
        "option", "slider", "spinbutton", "switch", "tab", "treeitem",
        "input", "select", "textarea",
    }

    # 1. All interactive elements have accessible names
    unnamed = [
        n for n in all_nodes
        if n.get("role") in interactive_roles and not (n.get("name") or "").strip()
    ]
    if unnamed:
        issues.append(Issue(
            severity="critical",
            title="Interactive elements without accessible names",
            description=f"{len(unnamed)} interactive element(s) have no accessible name. Agents rely on names to understand what an element does.",
            element=str(unnamed[:3]),
        ))
    else:
        passed += 1

    # 2. Form inputs have associated labels (via for/id or aria-label)
    unlabeled_inputs = []
    label_fors = {label.get("for") for label in soup.find_all("label") if label.get("for")}
    for inp in soup.find_all(["input", "select", "textarea"]):
        if inp.get("type") in ("hidden", "submit", "button", "reset", "image"):
            continue
        has_label_for = inp.get("id") in label_fors
        has_aria_label = inp.get("aria-label") or inp.get("aria-labelledby")
        has_wrapped = inp.find_parent("label")
        if not (has_label_for or has_aria_label or has_wrapped):
            unlabeled_inputs.append(str(inp)[:150])
    if unlabeled_inputs:
        issues.append(Issue(
            severity="high",
            title="Form inputs without labels",
            description=f"{len(unlabeled_inputs)} input(s) have no associated label. Agents cannot determine the purpose of unlabeled inputs.",
            element=unlabeled_inputs[0],
        ))
    else:
        passed += 1

    # 3. Landmark roles present in a11y tree
    tree_roles = {n.get("role") for n in all_nodes}
    has_landmarks = bool(tree_roles & LANDMARK_ROLES)
    if not has_landmarks:
        issues.append(Issue(
            severity="high",
            title="No landmark roles in accessibility tree",
            description="The accessibility tree has no landmark roles (main, nav, header, footer). Agents use landmarks to understand page structure and skip to relevant sections.",
        ))
    else:
        passed += 1

    # 4. ARIA attributes are valid (no orphaned aria-labelledby)
    bad_aria = []
    all_ids = {el.get("id") for el in soup.find_all(True) if el.get("id")}
    for el in soup.find_all(attrs={"aria-labelledby": True}):
        refs = el.get("aria-labelledby", "").split()
        broken = [ref for ref in refs if ref not in all_ids]
        if broken:
            bad_aria.append(f"{el.name}[aria-labelledby='{el.get('aria-labelledby')}'] refs missing id(s): {broken}")
    if bad_aria:
        issues.append(Issue(
            severity="medium",
            title="Broken aria-labelledby references",
            description=f"{len(bad_aria)} element(s) reference non-existent IDs in aria-labelledby. This confuses agents reading the accessibility tree.",
            element=bad_aria[0],
        ))
    else:
        passed += 1

    # 5. Images have alt text
    imgs_without_alt = [
        str(img)[:150] for img in soup.find_all("img")
        if img.get("alt") is None  # missing entirely, not empty string (decorative is OK)
    ]
    if imgs_without_alt:
        issues.append(Issue(
            severity="medium",
            title="Images missing alt attribute",
            description=f"{len(imgs_without_alt)} <img> element(s) have no alt attribute. Agents using vision+DOM combined mode need alt text to understand images.",
            element=imgs_without_alt[0],
        ))
    else:
        passed += 1

    score = passed * PTS_EACH
    return CategoryResult(
        category="Accessibility Tree",
        score=score,
        max_score=MAX_SCORE,
        passed_checks=passed,
        total_checks=CHECKS,
        issues=issues,
    )

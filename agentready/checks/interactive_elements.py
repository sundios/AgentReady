from ..models import CategoryResult, Issue

MAX_SCORE = 20
CHECKS = 4
PTS_EACH = MAX_SCORE // CHECKS

MIN_DIMENSION_PX = 8


def check_interactive_elements(interactive_elements: list[dict]) -> CategoryResult:
    issues: list[Issue] = []
    passed = 0

    visible = [el for el in interactive_elements if el.get("visible")]

    # 1. All interactive elements > 8x8 CSS pixels
    too_small = [
        el for el in visible
        if el.get("width", 0) < MIN_DIMENSION_PX or el.get("height", 0) < MIN_DIMENSION_PX
    ]
    if too_small:
        examples = [f"<{el['tag']}> '{el['text'][:40]}' ({el['width']:.0f}x{el['height']:.0f}px)" for el in too_small[:3]]
        issues.append(Issue(
            severity="high",
            title=f"Interactive elements below 8×8 px minimum",
            description=f"{len(too_small)} element(s) are smaller than the 8×8 px threshold and may be filtered out by agent visual analysis: {'; '.join(examples)}",
            element=too_small[0].get("outerHTML", ""),
        ))
    else:
        passed += 1

    # 2. Interactive elements have cursor:pointer
    no_pointer = [
        el for el in visible
        if el.get("cursor") not in ("pointer", "text", "move")
        and el.get("tag") in ("a", "button")
    ]
    if no_pointer:
        examples = [f"<{el['tag']}> '{el['text'][:40]}'" for el in no_pointer[:3]]
        issues.append(Issue(
            severity="medium",
            title="Buttons/links missing cursor:pointer",
            description=f"{len(no_pointer)} button/link element(s) lack cursor:pointer CSS. Agents using visual modality rely on cursor signals to identify clickable areas: {'; '.join(examples)}",
            element=no_pointer[0].get("outerHTML", ""),
        ))
    else:
        passed += 1

    # 3. No ghost/transparent overlays covering interactive elements
    # Check for elements with very low opacity that are still in the DOM as interactive
    ghost_elements = [
        el for el in visible
        if el.get("opacity", 1) < 0.1 and el.get("tag") in ("button", "a", "input", "select")
    ]
    if ghost_elements:
        examples = [f"<{el['tag']}> '{el['text'][:40]}' (opacity: {el.get('opacity', 0):.2f})" for el in ghost_elements[:3]]
        issues.append(Issue(
            severity="high",
            title="Transparent interactive elements detected",
            description=f"{len(ghost_elements)} interactive element(s) have near-zero opacity but remain in the DOM. Agents may identify these as ghost elements and skip them.",
            element=ghost_elements[0].get("outerHTML", ""),
        ))
    else:
        passed += 1

    # 4. Interactive elements are keyboard accessible (tabindex != -1 unless intentional)
    removed_from_tab = [
        el for el in interactive_elements
        if str(el.get("tabindex", "")) == "-1"
        and el.get("tag") in ("button", "a", "input", "select", "textarea")
        and not el.get("aria-hidden")
    ]
    if removed_from_tab:
        examples = [f"<{el['tag']}> '{el['text'][:40]}'" for el in removed_from_tab[:3]]
        issues.append(Issue(
            severity="medium",
            title="Interactive elements removed from tab order",
            description=f"{len(removed_from_tab)} interactive element(s) have tabindex='-1', removing them from keyboard navigation. Keyboard-driven agents cannot reach these: {'; '.join(examples)}",
            element=removed_from_tab[0].get("outerHTML", ""),
        ))
    else:
        passed += 1

    score = passed * PTS_EACH
    return CategoryResult(
        category="Interactive Elements",
        score=score,
        max_score=MAX_SCORE,
        passed_checks=passed,
        total_checks=CHECKS,
        issues=issues,
    )

from bs4 import BeautifulSoup
from ..models import CategoryResult, Issue

MAX_SCORE = 20
CHECKS = 4
PTS_EACH = MAX_SCORE // CHECKS

CLS_GOOD = 0.1
CLS_POOR = 0.25


def check_layout_stability(html: str, cls_score: float) -> CategoryResult:
    soup = BeautifulSoup(html, "lxml")
    issues: list[Issue] = []
    passed = 0

    # 1. CLS score
    if cls_score <= CLS_GOOD:
        passed += 1
    elif cls_score <= CLS_POOR:
        issues.append(Issue(
            severity="medium",
            title=f"Moderate layout shift detected (CLS: {cls_score:.3f})",
            description=f"Cumulative Layout Shift of {cls_score:.3f} (threshold: <0.1). Moving elements disorient agents taking timed screenshots for navigation.",
        ))
    else:
        issues.append(Issue(
            severity="high",
            title=f"High layout shift detected (CLS: {cls_score:.3f})",
            description=f"Cumulative Layout Shift of {cls_score:.3f} is above the poor threshold (0.25). Agents relying on screenshots will navigate incorrect positions.",
        ))

    # 2. Images without explicit width/height (cause reflow)
    imgs_no_dims = [
        str(img)[:150] for img in soup.find_all("img")
        if not (img.get("width") and img.get("height")) and not img.get("style", "").find("width") > -1
    ]
    if imgs_no_dims:
        issues.append(Issue(
            severity="medium",
            title="Images without explicit dimensions",
            description=f"{len(imgs_no_dims)} image(s) lack width/height attributes, causing layout reflow on load that shifts page content under agents.",
            element=imgs_no_dims[0],
        ))
    else:
        passed += 1

    # 3. No dynamically injected above-fold content patterns
    suspect_scripts = []
    for script in soup.find_all("script"):
        src = script.get("src", "")
        content = script.string or ""
        if any(kw in content.lower() for kw in ["insertbefore", "prepend", "innerhtml", "document.write"]):
            suspect_scripts.append(src or content[:100])
    if suspect_scripts:
        issues.append(Issue(
            severity="low",
            title="Inline scripts may inject above-fold content",
            description=f"{len(suspect_scripts)} script(s) contain DOM injection patterns (innerHTML, document.write, prepend). These can shift layout after initial render.",
            element=suspect_scripts[0],
        ))
    else:
        passed += 1

    # 4. No CSS animations on structural elements
    style_tags = soup.find_all("style")
    animation_issues = []
    for style in style_tags:
        css = style.string or ""
        if "animation" in css and any(prop in css for prop in ["width", "height", "top", "left", "margin", "padding"]):
            animation_issues.append(css[:100])
    if animation_issues:
        issues.append(Issue(
            severity="low",
            title="CSS animations affect layout properties",
            description="Detected CSS animations that modify width/height/position. Agents capturing screenshots mid-animation may see incorrect element positions.",
        ))
    else:
        passed += 1

    score = passed * PTS_EACH
    return CategoryResult(
        category="Layout Stability",
        score=score,
        max_score=MAX_SCORE,
        passed_checks=passed,
        total_checks=CHECKS,
        issues=issues,
    )

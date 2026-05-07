# AgentReady — AI Agent-Readiness Auditor

Audit any URL and score how well it works for AI agents (browser-use, Claude computer-use, GPT browsing, etc). Returns a 0–100 score with prioritized fixes.

```
python3 main.py audit https://yoursite.com
```

![AgentReady screenshot 1](/image1.png)
![AgentReady screenshot 2](/image2.png)

---

## The Problem

AI agents don't experience websites the way humans do. They read raw HTML, walk the accessibility tree, and take screenshots to navigate. Sites built for visual beauty — hover states, animated layouts, CSS-driven interactions — are often functionally broken for agents. AgentReady finds those gaps.

---

## Scoring

100 points across 5 categories:

| Grade | Score |
|-------|-------|
| A | 90–100 |
| B | 80–89 |
| C | 70–79 |
| D | 50–69 |
| F | < 50 |

---

## What It Checks

### 1. Semantic HTML — 25 points

Agents parse the DOM to understand what elements do. Semantic markup is their primary signal for intent.

| Check | Points | What's tested |
|-------|--------|---------------|
| No interactive divs/spans without role | 5 | `<div>` or `<span>` elements with `onclick` or `tabindex` but no `role` attribute — agents can't tell these are actionable |
| Custom role="button" elements have tabindex | 5 | Elements with `role="button"` that aren't `<button>`, `<a>`, or `<input>` must have `tabindex="0"` to be keyboard-reachable |
| Anchor tags have href | 5 | `<a>` tags without an `href` are treated as non-navigable by agents mapping available destinations |
| Labels associated with inputs | 5 | `<label>` elements must use the `for` attribute linking to an input's `id`, or wrap the input directly — agents use this to understand field purpose |
| Semantic landmark elements present | 5 | Page must include `<main>` and `<nav>` (or their ARIA equivalents) so agents can orient themselves on the page |

---

### 2. Accessibility Tree — 25 points

The accessibility tree is a browser-native API that strips visual noise and exposes only roles, names, and states. It's the highest-fidelity map an agent has.

| Check | Points | What's tested |
|-------|--------|---------------|
| All interactive elements have accessible names | 5 | Buttons, links, checkboxes, inputs, and other interactive roles must have a non-empty accessible name — without one, agents don't know what the element does |
| Form inputs have associated labels | 5 | Every `<input>`, `<select>`, and `<textarea>` (except hidden/submit/button types) must be linked to a label via `for`/`id`, `aria-label`, or `aria-labelledby` |
| Landmark roles in accessibility tree | 5 | The accessibility tree must contain at least one landmark role (`main`, `nav`, `header`, `footer`, `banner`, etc.) — agents use these to skip to relevant sections |
| Valid aria-labelledby references | 5 | Every `aria-labelledby` attribute must reference an ID that actually exists in the DOM — broken references silently confuse agents reading the tree |
| Images have alt attributes | 5 | `<img>` elements must have an `alt` attribute (empty string is acceptable for decorative images) — agents using combined visual+DOM mode rely on alt text to understand images |

---

### 3. Layout Stability — 20 points

Agents that take screenshots to navigate are confused by pages that shift after load. They click where a button was, not where it ended up.

| Check | Points | What's tested |
|-------|--------|---------------|
| Cumulative Layout Shift (CLS) < 0.1 | 5 | Measured live using the browser's `PerformanceObserver` API. CLS > 0.1 is flagged as medium, > 0.25 as high severity |
| Images have explicit width/height | 5 | Images without `width` and `height` attributes cause reflow when they load, shifting everything below them — a common source of layout shift |
| No above-fold DOM injection in scripts | 5 | Inline scripts using `innerHTML`, `document.write`, `prepend`, or `insertBefore` can inject content that shifts layout after the initial render agents capture |
| No CSS animations on layout properties | 5 | Animations that modify `width`, `height`, `top`, `left`, `margin`, or `padding` move elements between the time an agent captures a screenshot and the time it acts |

---

### 4. Interactive Elements — 20 points

Agents doing visual analysis filter out elements that are too small, invisible, or unreachable. These checks ensure every interactive element survives that filter.

| Check | Points | What's tested |
|-------|--------|---------------|
| All interactive elements ≥ 8×8 CSS pixels | 5 | Buttons, links, inputs, and custom interactive elements must have a rendered bounding box of at least 8×8px — smaller elements are filtered out by agent visual analysis |
| Buttons and links have cursor: pointer | 5 | `cursor: pointer` is a strong visual signal of actionability that agents using screenshot analysis rely on — missing it from `<button>` and `<a>` elements reduces confidence |
| No transparent interactive elements | 5 | Interactive elements (`button`, `a`, `input`, `select`) with `opacity < 0.1` are invisible but still in the DOM — agents may attempt to interact with them and fail |
| Interactive elements not removed from tab order | 5 | `<button>`, `<a>`, `<input>`, `<select>`, and `<textarea>` elements with `tabindex="-1"` are unreachable by keyboard-driven agents — flagged unless intentionally hidden with `aria-hidden` |

---

### 5. Agent Action Clarity — 10 points

Agents need to understand what the page wants them to do. This category checks whether the primary user journey is clear enough to be planned without human interpretation.

| Check | Points | What's tested |
|-------|--------|---------------|
| Primary CTA visible above the fold | 3 | A button or link with recognizable action text (buy, sign up, get started, contact, etc.) must be visible in the first 800px of the page — agents need a clear starting point |
| Forms have submit buttons | 4 | Every `<form>` must contain a `<button type="submit">` or `<input type="submit">` — agents cannot complete form journeys without an explicit submission mechanism |
| Navigation structure is clear | 3 | A `<nav>` element or `role="navigation"` must be present and contain at least 2 links — agents use nav structure to plan multi-step journeys across the site |

---

## AI Recommendations

When an `ANTHROPIC_API_KEY` is set, audit findings are sent to Claude (`claude-sonnet-4-6`) which returns prioritized recommendations including:

- **Severity** — critical / high / medium / low
- **Fix description** — specific, actionable in 2–3 sentences
- **Code example** — before/after HTML or CSS snippet
- **CRO impact** — estimated effect on conversion rate
- **Effort** — low / medium / high implementation cost

Recommendations are sorted by severity × CRO impact so the highest-value fixes come first.

---

## Usage

```bash
# Single URL — HTML report + CLI output
python3 main.py audit https://yoursite.com

# Single URL — JSON output, no AI
python3 main.py audit https://yoursite.com --format json --no-ai

# Both formats
python3 main.py audit https://yoursite.com --format both

# Bulk — comma-separated
python3 main.py bulk "https://site1.com,https://site2.com"

# Bulk — from file (one URL per line)
python3 main.py bulk urls.txt --format both

# Custom output directory
python3 main.py audit https://yoursite.com --output ~/Desktop/reports
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `html` | Output format: `html`, `json`, or `both` |
| `--output` | `reports/` | Directory to save report files |
| `--no-ai` | off | Skip Claude API recommendations |
| `--quiet` | off | Suppress CLI output, only save files |
| `--delay` | `2.0` | Seconds between requests in bulk mode |

---

## Setup

```bash
# Install dependencies
pip3 install playwright beautifulsoup4 lxml anthropic typer rich jinja2 python-dotenv

# Install Chromium
python3 -m playwright install chromium

# Add API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

---

## Output Files

| Format | Contents |
|--------|----------|
| HTML | Self-contained dashboard with score gauge, category bars, issue list, AI recommendations with code examples, and page screenshot |
| JSON | Machine-readable full audit result — all scores, checks, issues, and recommendations |
| CLI | Color-coded terminal table with scores, issue list, and top 5 recommendations |

---

## How Agents See Your Site

Agents use three modalities — often in combination:

- **HTML/DOM** — reads element hierarchy, attributes, and relationships. A "Buy Now" button inside a product container is assumed to belong to that product.
- **Accessibility tree** — browser-native API that strips CSS noise and exposes only roles, names, and states. The highest-fidelity structured view.
- **Screenshots** — vision model identifies elements by position, color, and size. Used to cross-reference structure with visual layout.

AgentReady checks all three channels to surface gaps that only appear when one modality is missing signal the others provide.

---

## Inspiration

This script was inspired by [Designing for AI agents: UX considerations for the agentic web](https://web.dev/articles/ai-agent-site-ux) on web.dev.

import asyncio
import base64
from dataclasses import dataclass
from typing import Any, Optional

from playwright.async_api import async_playwright, Page, Browser


@dataclass
class PageData:
    url: str
    html: str
    a11y_snapshot: list[dict]   # flat list of a11y nodes from JS evaluation
    aria_text: str              # raw aria_snapshot() YAML-like string
    screenshot_b64: str
    interactive_elements: list[dict]
    computed_styles: dict[str, str]
    cls_score: float
    page_title: str
    viewport: dict


async def _capture_interactive_elements(page: Page) -> list[dict]:
    """Get bounding boxes and styles for all interactive elements."""
    return await page.evaluate("""() => {
        const selectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="menuitem"], [tabindex]';
        const elements = Array.from(document.querySelectorAll(selectors));
        return elements.map(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return {
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role'),
                text: (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 100),
                href: el.getAttribute('href'),
                type: el.getAttribute('type'),
                tabindex: el.getAttribute('tabindex'),
                ariaLabel: el.getAttribute('aria-label'),
                ariaDescribedby: el.getAttribute('aria-describedby'),
                id: el.getAttribute('id'),
                name: el.getAttribute('name'),
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                visible: rect.width > 0 && rect.height > 0,
                cursor: style.cursor,
                opacity: parseFloat(style.opacity),
                display: style.display,
                visibility: style.visibility,
                outerHTML: el.outerHTML.slice(0, 300)
            };
        });
    }""")


async def _get_cls_score(page: Page) -> float:
    """Measure Cumulative Layout Shift using PerformanceObserver."""
    try:
        return await page.evaluate("""() => {
            return new Promise(resolve => {
                let clsValue = 0;
                try {
                    const observer = new PerformanceObserver(list => {
                        for (const entry of list.getEntries()) {
                            if (!entry.hadRecentInput) {
                                clsValue += entry.value;
                            }
                        }
                    });
                    observer.observe({ type: 'layout-shift', buffered: true });
                    setTimeout(() => {
                        observer.disconnect();
                        resolve(clsValue);
                    }, 2000);
                } catch(e) {
                    resolve(0);
                }
            });
        }""")
    except Exception:
        return 0.0


async def _get_ghost_overlays(page: Page) -> list[dict]:
    """Find transparent/invisible overlays that may block interactive elements."""
    return await page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        return all.filter(el => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (rect.width < 10 || rect.height < 10) return false;
            const isOverlay = (style.position === 'absolute' || style.position === 'fixed')
                && parseInt(style.zIndex || '0') > 5;
            const isClear = parseFloat(style.opacity) < 0.1
                || style.visibility === 'hidden'
                || style.backgroundColor === 'transparent';
            return isOverlay && isClear;
        }).map(el => ({
            tag: el.tagName.toLowerCase(),
            id: el.getAttribute('id'),
            className: el.className,
            zIndex: window.getComputedStyle(el).zIndex,
            outerHTML: el.outerHTML.slice(0, 200)
        }));
    }""")


async def render_page(url: str, timeout: int = 25000) -> PageData:
    """Render a URL with Playwright and capture all required data."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (compatible; AgentReady/1.0; +https://agentready.io)"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout)
        except Exception:
            # Fall back to domcontentloaded if networkidle times out
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        await page.wait_for_timeout(1500)

        html = await page.content()
        title = await page.title()

        # aria_snapshot() returns a YAML-like string (Playwright 1.44+)
        try:
            aria_text = await page.aria_snapshot() or ""
        except Exception:
            aria_text = ""

        # Flat JS-evaluated a11y node list for structured checks
        a11y_nodes = await page.evaluate("""() => {
            const INTERACTIVE = new Set(['button','link','checkbox','radio','textbox',
                'combobox','listbox','menuitem','menuitemcheckbox','menuitemradio',
                'option','slider','spinbutton','switch','tab','treeitem']);
            const els = Array.from(document.querySelectorAll(
                'a, button, input, select, textarea, [role], [aria-label], [aria-labelledby], main, nav, header, footer'
            ));
            return els.map(el => {
                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                const ariaLabel = el.getAttribute('aria-label') || '';
                const text = (el.textContent || '').trim().slice(0, 80);
                return {
                    role,
                    name: ariaLabel || text,
                    tag: el.tagName.toLowerCase(),
                    ariaLabel,
                    ariaLabelledby: el.getAttribute('aria-labelledby') || '',
                    id: el.getAttribute('id') || '',
                };
            });
        }""")

        screenshot_bytes = await page.screenshot(full_page=False, type="jpeg", quality=75)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        interactive_elements = await _capture_interactive_elements(page)
        cls_score = await _get_cls_score(page)

        viewport = page.viewport_size or {"width": 1280, "height": 800}

        await browser.close()

        return PageData(
            url=url,
            html=html,
            a11y_snapshot=a11y_nodes,
            aria_text=aria_text,
            screenshot_b64=screenshot_b64,
            interactive_elements=interactive_elements,
            computed_styles={},
            cls_score=cls_score,
            page_title=title,
            viewport=viewport,
        )

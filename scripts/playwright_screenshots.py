"""
Take ClaimLens screenshots using Playwright headless browser.
No window focus issues — runs completely headless.
"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8501"
OUT = "docs/screenshots"
os.makedirs(OUT, exist_ok=True)

PRESETS = [
    ("02_lemon_water", "Hot Lemon Water (Medical Hoax)"),
    ("03_nasa_signal",  "NASA Alien Signal (Tech Hoax)"),
    ("04_cash_ban",     "US Cash Ban (Policy Misinfo)"),
    ("05_leqembi",      "Leqembi FDA Approval (Real News)"),
]

TAB_TEXTS = ["Dual Comparison", "Source Explorer", "Agent Trace", "Audit History"]
TAB_FILES = ["tab1_comparison", "tab2_sources", "tab3_trace", "tab4_history"]


async def wait_for_stable(page, timeout=12000):
    """Wait for Streamlit to finish rendering."""
    try:
        await page.wait_for_selector('[data-testid="stSpinner"]', timeout=3000)
        await page.wait_for_selector('[data-testid="stSpinner"]', state="detached", timeout=timeout)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    await asyncio.sleep(1.5)


async def discover_tab_selector(page):
    """Find which selector Streamlit is using for tabs."""
    for sel in ['[data-baseweb="tab"]', 'button[role="tab"]', '[data-testid="stTab"]']:
        try:
            await page.wait_for_selector(sel, timeout=6000, state="visible")
            count = await page.locator(sel).count()
            if count >= 2:
                return sel
        except Exception:
            continue
    return None


async def click_tab(page, tab_text, sel):
    """Click a Streamlit tab by partial text match."""
    if sel:
        loc = page.locator(f'{sel}:has-text("{tab_text}")')
        try:
            await loc.first.click(timeout=8000)
            await asyncio.sleep(1.2)
            return True
        except Exception:
            pass
    # Fallback through all known selectors
    for s in ['[data-baseweb="tab"]', 'button[role="tab"]', '[data-testid="stTab"]']:
        loc = page.locator(f'{s}:has-text("{tab_text}")')
        try:
            if await loc.count() > 0:
                await loc.first.click(timeout=5000)
                await asyncio.sleep(1.2)
                return True
        except Exception:
            continue
    print(f"  WARNING: could not click tab '{tab_text}'")
    return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = await ctx.new_page()

        # ── Initial page load ───────────────────────────────────────────────────
        print("Loading home page...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await asyncio.sleep(4)

        # Zoom out so both dual-comparison columns fit without horizontal scrolling
        await page.evaluate("document.body.style.zoom = '85%'")
        await asyncio.sleep(0.5)

        await page.screenshot(path=f"{OUT}/01_home.png", full_page=False)
        print("  saved 01_home.png")

        # Discover which tab selector Streamlit is using
        tab_sel = await discover_tab_selector(page)
        print(f"  tab selector: {tab_sel or 'not found yet — will retry per preset'}")

        # ── Each preset ─────────────────────────────────────────────────────────
        for prefix, label in PRESETS:
            print(f"\nPreset: {label}")

            # Click the sidebar preset button
            sidebar_btn = page.locator(
                f'[data-testid="stSidebar"] button:has-text("{label[:22]}")'
            )
            try:
                await sidebar_btn.first.click(timeout=8000)
            except Exception:
                # Fallback: any button with that text
                await page.locator(f'button:has-text("{label[:22]}")').first.click(timeout=8000)

            await wait_for_stable(page)

            # Re-apply zoom after Streamlit re-render
            await page.evaluate("document.body.style.zoom = '85%'")
            await asyncio.sleep(0.5)
            print("  preset loaded")

            # Re-discover tab selector (tabs re-render after preset click)
            tab_sel = await discover_tab_selector(page)
            if tab_sel:
                print(f"  tabs found via: {tab_sel}")
            else:
                print("  WARNING: tab selector not found — will attempt fallback clicks")

            # Screenshot each tab
            for tab_text, tab_file in zip(TAB_TEXTS, TAB_FILES):
                # Tab 1 (Dual Comparison) is active by default after preset load
                if tab_text != "Dual Comparison":
                    ok = await click_tab(page, tab_text, tab_sel)
                    if not ok:
                        print(f"  skipped {tab_file}")
                        continue
                    await wait_for_stable(page)
                    await page.evaluate("document.body.style.zoom = '85%'")

                path = f"{OUT}/{prefix}_{tab_file}.png"
                await page.screenshot(path=path, full_page=False)
                print(f"  saved {prefix}_{tab_file}.png")

            # Return to Tab 1 before next preset
            await click_tab(page, "Dual Comparison", tab_sel)
            await asyncio.sleep(0.5)

        await browser.close()
        print("\nAll screenshots saved to docs/screenshots/")


asyncio.run(main())

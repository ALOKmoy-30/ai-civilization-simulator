"""
Script to capture clean, high-resolution screenshots of the AutoSociety Streamlit dashboard.
Saves exact filenames into docs/screenshots/ as required by README.md.
Provides generous load times and element expansions to ensure all data and charts are fully visible.
"""

import time
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# List of old filenames to clean up
OLD_FILES = [
    "analytics.png",
    "citizens.png",
    "dashboard.png",
    "government.png",
    "government_policies.png",
]

def clean_old_screenshots():
    for old_name in OLD_FILES:
        old_path = SCREENSHOTS_DIR / old_name
        if old_path.exists():
            try:
                old_path.unlink()
                print(f"  Removed old screenshot: {old_name}")
            except OSError:
                pass

def hide_streamlit_decorations(page):
    """Hide top menu, footer, and status widgets for clean presentation."""
    page.evaluate("""() => {
        const style = document.createElement('style');
        style.innerHTML = `
            #MainMenu {visibility: hidden !important;}
            footer {visibility: hidden !important;}
            header[data-testid="stHeader"] {display: none !important;}
            [data-testid="stStatusWidget"] {visibility: hidden !important;}
            .stApp > header {display: none !important;}
        `;
        document.head.appendChild(style);
    }""")

def take_screenshots():
    print("Starting Playwright to capture fresh screenshots...")
    
    with sync_playwright() as p:
        # Launch headless Chromium with a crisp 1600x1200 resolution at 1.5x scale
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1200},
            device_scale_factor=1.5,
            color_scheme="dark"
        )
        page = context.new_page()

        # 1. Dashboard Overview (app.py)
        print("Capturing Dashboard Overview...")
        page.goto("http://localhost:8501/")
        # Wait for Streamlit to render and settle down
        page.wait_for_selector('[data-testid="stMetricValue"]', timeout=30000)
        time.sleep(10)  # Generous delay to ensure all metric counters and live charts render fully
        hide_streamlit_decorations(page)
        page.screenshot(path=str(SCREENSHOTS_DIR / "dashboard_overview.png"), full_page=False)
        print("  -> Saved dashboard_overview.png")

        # 2. Macro Analytics (1_Analytics.py)
        print("Capturing Macro Analytics...")
        page.goto("http://localhost:8501/Analytics")
        page.wait_for_selector('.js-plotly-plot', timeout=30000)
        time.sleep(10)  # Wait for Plotly to animate and draw all datasets completely
        hide_streamlit_decorations(page)
        page.screenshot(path=str(SCREENSHOTS_DIR / "macro_analytics.png"), full_page=False)
        print("  -> Saved macro_analytics.png")

        # 3. Government Panel (2_Government.py - top view)
        print("Capturing Government Policy Chamber...")
        page.goto("http://localhost:8501/Government")
        page.wait_for_selector('h1', timeout=30000)
        time.sleep(10)
        hide_streamlit_decorations(page)
        page.screenshot(path=str(SCREENSHOTS_DIR / "government_panel.png"), full_page=False)
        print("  -> Saved government_panel.png")

        # 4. Enacted Policies (2_Government.py - scrolled to policies)
        print("Capturing Enacted Policies (with reasoning expanded)...")
        # Scroll down so Enacted Policies header is at the top
        page.evaluate("""() => {
            const headers = Array.from(document.querySelectorAll('h3, h2'));
            const pHeader = headers.find(h => h.innerText.includes('Enacted Policies'));
            if (pHeader) pHeader.scrollIntoView({behavior: 'instant', block: 'start'});
        }""")
        time.sleep(3)
        # Expand one or more governor reasoning details
        try:
            expanders = page.locator('summary').filter(has_text="Governor Reasoning").all()
            for idx, exp in enumerate(expanders):
                if exp.is_visible():
                    exp.click()
                    print(f"    Expanded policy reasoning box {idx + 1}")
                    time.sleep(1)
        except Exception as e:
            print(f"    Note: Could not expand policy reasoning box: {e}")
        time.sleep(5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "enacted_policies.png"), full_page=False)
        print("  -> Saved enacted_policies.png")

        # 5. Citizen Registry (3_Citizens.py)
        print("Capturing Citizen Registry...")
        page.goto("http://localhost:8501/Citizens")
        page.wait_for_selector('[data-testid="stDataFrame"]', timeout=30000)
        time.sleep(10)
        hide_streamlit_decorations(page)
        page.screenshot(path=str(SCREENSHOTS_DIR / "citizen_registry.png"), full_page=False)
        print("  -> Saved citizen_registry.png")

        # 6. Historical Backup Restoration (4_Deep_Analytics.py - top part)
        print("Capturing Historical Backup Restoration Overlay...")
        page.goto("http://localhost:8501/Deep_Analytics")
        page.wait_for_selector('h1', timeout=30000)
        time.sleep(10)
        hide_streamlit_decorations(page)
        page.screenshot(path=str(SCREENSHOTS_DIR / "backup_restoration.png"), full_page=False)
        print("  -> Saved backup_restoration.png")

        # 7. Deep Analytics Search & Filter (4_Deep_Analytics.py - scrolled down)
        print("Capturing Deep Analytics Event Search...")
        page.evaluate("""() => {
            const headers = Array.from(document.querySelectorAll('h3, h2'));
            const sHeader = headers.find(h => h.innerText.includes('Event Search'));
            if (sHeader) sHeader.scrollIntoView({behavior: 'instant', block: 'start'});
        }""")
        time.sleep(5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "deep_analytics.png"), full_page=False)
        print("  -> Saved deep_analytics.png")

        # 8. Hybrid Model Stats (4_Deep_Analytics.py - scrolled to AI Decision Log / Event Distribution)
        print("Capturing Hybrid Model Stats & AI Decision Log (with event expanded)...")
        page.evaluate("""() => {
            const headers = Array.from(document.querySelectorAll('h3, h2'));
            const dHeader = headers.find(h => h.innerText.includes('AI Decision Log') || h.innerText.includes('Event Distribution'));
            if (dHeader) dHeader.scrollIntoView({behavior: 'instant', block: 'start'});
        }""")
        time.sleep(3)
        # Expand the first critical/warning event details if available
        try:
            event_expanders = page.locator('summary').filter(has_text="[").all()
            for idx, exp in enumerate(event_expanders[:2]):
                if exp.is_visible():
                    exp.click()
                    print(f"    Expanded event card {idx + 1}")
                    time.sleep(1)
        except Exception as e:
            print(f"    Note: Could not expand event card: {e}")
        time.sleep(5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "hybrid_model_stats.png"), full_page=False)
        print("  -> Saved hybrid_model_stats.png")

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    clean_old_screenshots()
    take_screenshots()

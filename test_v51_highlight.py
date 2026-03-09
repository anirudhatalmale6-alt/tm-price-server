"""Check if sections get properly highlighted and colored."""
import json
from playwright.sync_api import sync_playwright

MOCK_REPORT_HTML = r'''<html><head><title>Report</title></head><body><h1>Test Event - Raymond James Stadium</h1><a href="https://www.ticketmaster.com/test-event/event/0D00636ED3B8BF22">Buy</a><script>var defined = { tickets: [{"section":"101","row":"A","seat":"1-2","price":150,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"}], };</script></body></html>'''

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 900})

        page.goto("http://localhost:3000/admin", wait_until="networkidle")
        page.wait_for_timeout(2000)

        page.evaluate('''(html) => {
            document.getElementById("reportHtml0").value = html;
        }''', MOCK_REPORT_HTML)
        page.evaluate('parseFromHtml(0)')
        page.wait_for_timeout(10000)

        # Check how sections are colored
        colors = page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            if (!svg) return {};
            const result = {};
            const paths = svg.querySelectorAll('path[data-has-stock="1"]');
            for (const p of Array.from(paths).slice(0, 10)) {
                result[p.id] = {
                    fill: p.getAttribute("fill"),
                    fillOpacity: p.getAttribute("fill-opacity"),
                    stroke: p.getAttribute("stroke")
                };
            }
            return result;
        }''')
        print("Section colors (sample):", json.dumps(colors, indent=2))

        # Click section 135 (center, should be visible)
        page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            const sec = svg.querySelector('path[id="135"]');
            if (sec) sec.dispatchEvent(new Event("click", {bubbles: true}));
        }''')
        page.wait_for_timeout(500)

        # Check highlight state
        highlight = page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            const sec = svg.querySelector('path[id="135"]');
            return {
                hasActiveClass: sec ? sec.classList.contains("map-sec-active") : false,
                stroke: sec ? sec.getAttribute("stroke") : null,
                strokeWidth: sec ? sec.getAttribute("stroke-width") : null,
                fill: sec ? sec.getAttribute("fill") : null,
            };
        }''')
        print("Section 135 highlight:", json.dumps(highlight, indent=2))

        # Take screenshot with section 135 selected
        map_col = page.locator("#mapCol")
        map_col.screenshot(path="v51_highlight_test.png")
        print("Highlight screenshot saved")

        browser.close()

if __name__ == "__main__":
    run()

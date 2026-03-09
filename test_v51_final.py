"""Take final screenshots of v5.1 for client delivery."""
import json
from playwright.sync_api import sync_playwright

MOCK_REPORT_HTML = r'''<html><head><title>Report</title></head><body><h1>Test Event - Raymond James Stadium</h1><a href="https://www.ticketmaster.com/test-event/event/0D00636ED3B8BF22">Buy</a><script>var defined = { tickets: [{"section":"101","row":"A","seat":"1-2","price":150,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"102","row":"B","seat":"3-4","price":175,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"201","row":"C","seat":"5-6","price":95,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"301","row":"D","seat":"7-8","price":55,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"FLOOR A","row":"GA","seat":"GA","price":250,"count":4,"type":"Premium","eventId":"0D00636ED3B8BF22"}], };</script></body></html>'''

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 900})

        page.goto("http://localhost:3000/admin", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Fill textarea and parse
        page.evaluate('''(html) => {
            document.getElementById("reportHtml0").value = html;
        }''', MOCK_REPORT_HTML)
        page.evaluate('parseFromHtml(0)')
        page.wait_for_timeout(10000)

        # Screenshot A: Full overview
        page.screenshot(path="v51_a.png")
        print("A: Full overview")

        # Screenshot B: Map panel with color legend and sections
        map_col = page.locator("#mapCol")
        map_col.screenshot(path="v51_b.png")
        print("B: Map panel")

        # Click section 135 (center of venue, should be clearly visible)
        page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            const sec = svg.querySelector('path[id="135"]');
            if (sec) sec.dispatchEvent(new Event("click", {bubbles: true}));
        }''')
        page.wait_for_timeout(500)
        # Screenshot C: Section clicked with detail panel
        map_col.screenshot(path="v51_c.png")
        print("C: Section 135 clicked")

        # Deselect section
        page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            const sec = svg.querySelector('path[id="135"]');
            if (sec) sec.dispatchEvent(new Event("click", {bubbles: true}));
        }''')
        page.wait_for_timeout(300)

        # Click 200s zone filter
        page.evaluate('''() => {
            const btns = document.querySelectorAll(".map-type-btn");
            for (const b of btns) {
                if (b.textContent.includes("200s")) { b.click(); break; }
            }
        }''')
        page.wait_for_timeout(500)
        # Screenshot D: 200s zone filtered
        map_col.screenshot(path="v51_d.png")
        print("D: 200s zone filter")

        print("All screenshots done!")
        browser.close()

if __name__ == "__main__":
    run()

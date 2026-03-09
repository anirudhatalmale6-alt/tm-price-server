"""Test generated chart fallback (when SVG unavailable)."""
import json
from playwright.sync_api import sync_playwright

# Use an event ID that won't be in Wayback Machine cache
MOCK_REPORT_HTML = r'''<html><head><title>Report</title></head><body><h1>Fake Event - No SVG Available</h1><a href="https://www.ticketmaster.com/event/ZZZZZZZZZZZZZZZZ">Buy</a><script>var defined = { tickets: [{"section":"101","row":"A","seat":"1-2","price":150,"count":2,"type":"Standard","eventId":"ZZZZZZZZZZZZZZZZ"},{"section":"102","row":"B","seat":"3-4","price":175,"count":2,"type":"Standard","eventId":"ZZZZZZZZZZZZZZZZ"},{"section":"201","row":"C","seat":"5-6","price":95,"count":2,"type":"Standard","eventId":"ZZZZZZZZZZZZZZZZ"}], };</script></body></html>'''

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
        page.wait_for_timeout(12000)

        status = page.evaluate('''() => {
            const svgContainer = document.getElementById("svgMapContainer");
            const genChart = svgContainer ? svgContainer.querySelector(".gen-chart") : null;
            return {
                mapMode: typeof svgMapMode !== 'undefined' ? svgMapMode : 'N/A',
                hasGenChart: !!genChart,
                genSections: genChart ? genChart.querySelectorAll(".gen-sec").length : 0,
                hasZoneCards: document.getElementById("stockContent") ? document.getElementById("stockContent").querySelectorAll(".stock-zone").length : 0,
            };
        }''')
        print("Status:", json.dumps(status, indent=2))

        map_col = page.locator("#mapCol")
        if map_col.is_visible():
            map_col.screenshot(path="v51b_gen.png")
            print("Generated chart screenshot saved")

        browser.close()

if __name__ == "__main__":
    run()

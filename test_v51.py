"""Test v5.1 interactive SVG map - inject mock report via JS and verify map renders."""
import json
from playwright.sync_api import sync_playwright

MOCK_REPORT_HTML = r'''<html><head><title>Report</title></head><body><h1>Test Event - Raymond James Stadium</h1><a href="https://www.ticketmaster.com/test-event/event/0D00636ED3B8BF22">Buy</a><script>var defined = { tickets: [{"section":"101","row":"A","seat":"1-2","price":150,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"102","row":"B","seat":"3-4","price":175,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"201","row":"C","seat":"5-6","price":95,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"301","row":"D","seat":"7-8","price":55,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"},{"section":"FLOOR A","row":"GA","seat":"GA","price":250,"count":4,"type":"Premium","eventId":"0D00636ED3B8BF22"}], };</script></body></html>'''

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        page.goto("http://localhost:3000/admin", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Use JS to fill the textarea and trigger parse
        page.evaluate('''(html) => {
            const ta = document.getElementById("reportHtml0");
            ta.value = html;
        }''', MOCK_REPORT_HTML)
        page.wait_for_timeout(300)

        # Call parseFromHtml directly
        page.evaluate('parseFromHtml(0)')

        # Wait for async fetches (map + stock)
        page.wait_for_timeout(10000)

        # Check status
        status = page.evaluate('''() => {
            const mapCol = document.getElementById("mapCol");
            const svgContainer = document.getElementById("svgMapContainer");
            const svg = svgContainer ? svgContainer.querySelector("svg") : null;
            const paths = svg ? svg.querySelectorAll("path[id]") : [];
            const numericPaths = Array.from(paths).filter(p => /^\\d+$/.test(p.id));
            const stockContent = document.getElementById("stockContent");
            const secTypes = document.getElementById("mapSectionTypes");
            return {
                mapVisible: mapCol ? mapCol.style.display : "N/A",
                hasSvg: !!svg,
                totalPaths: paths.length,
                numericPaths: numericPaths.length,
                coloredPaths: numericPaths.filter(p => p.getAttribute("data-has-stock") === "1").length,
                hasZoneCards: stockContent ? stockContent.querySelectorAll(".stock-zone").length : 0,
                hasSectionTypes: secTypes ? secTypes.innerHTML.length > 0 : false,
                eventId: document.getElementById("eventIdInput0") ? document.getElementById("eventIdInput0").value : "N/A",
                eventName: document.getElementById("eventName0") ? document.getElementById("eventName0").textContent : "N/A"
            };
        }''')
        print("Status:", json.dumps(status, indent=2))

        # Take full page screenshot (viewport only)
        page.screenshot(path="v51_full.png")
        print("Full screenshot saved")

        if status.get("hasSvg"):
            # Click a section with stock
            clicked = page.evaluate('''() => {
                const svg = document.querySelector("#svgMapContainer svg");
                const paths = svg.querySelectorAll('path[data-has-stock="1"]');
                if (paths.length > 0) {
                    paths[0].dispatchEvent(new Event("click", {bubbles: true}));
                    return paths[0].id;
                }
                return null;
            }''')
            if clicked:
                print(f"Clicked section: {clicked}")
                page.wait_for_timeout(500)
                page.screenshot(path="v51_clicked.png")
                print("Clicked screenshot saved")

                detail_visible = page.evaluate('''() => {
                    const d = document.getElementById("secDetail");
                    return d ? d.classList.contains("visible") : false;
                }''')
                print("Section detail visible:", detail_visible)

        print("Done!")
        browser.close()

if __name__ == "__main__":
    run()

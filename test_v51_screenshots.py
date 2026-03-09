"""Take focused screenshots of v5.1 for client."""
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

        # Screenshot 1: Full overview at reasonable size
        page.screenshot(path="v51_a_overview.png")
        print("1. Overview saved")

        # Screenshot 2: Focus on just the map panel
        map_col = page.locator("#mapCol")
        if map_col.is_visible():
            map_col.screenshot(path="v51_b_map.png")
            print("2. Map panel saved")

        # Screenshot 3: Click a section and show detail
        clicked = page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            // Find section 242 or first available
            let target = svg.querySelector('path[id="242"][data-has-stock="1"]') ||
                          svg.querySelector('path[data-has-stock="1"]');
            if (target) {
                target.dispatchEvent(new Event("click", {bubbles: true}));
                return target.id;
            }
            return null;
        }''')
        if clicked:
            print(f"3. Clicked section {clicked}")
            page.wait_for_timeout(500)
            # Screenshot the map panel with section detail visible
            map_col.screenshot(path="v51_c_detail.png")
            print("3. Detail view saved")

        # Screenshot 4: Scroll down to see stock zone cards
        page.evaluate('document.getElementById("stockContent").scrollIntoView()')
        page.wait_for_timeout(300)
        stock_content = page.locator("#stockContent")
        stock_content.screenshot(path="v51_d_stock.png")
        print("4. Stock cards saved")

        # Screenshot 5: Click a zone filter button
        page.evaluate('''() => {
            const btns = document.querySelectorAll(".map-type-btn");
            if (btns.length > 0) btns[0].click();
        }''')
        page.wait_for_timeout(500)
        map_col.screenshot(path="v51_e_filtered.png")
        print("5. Zone filter saved")

        print("All screenshots done!")
        browser.close()

if __name__ == "__main__":
    run()

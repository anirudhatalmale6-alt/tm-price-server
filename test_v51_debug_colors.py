"""Debug SVG section colors to see if they're being applied."""
import json
from playwright.sync_api import sync_playwright

MOCK_REPORT_HTML = r'''<html><head><title>Report</title></head><body><h1>Test Event</h1><a href="https://www.ticketmaster.com/test-event/event/0D00636ED3B8BF22">Buy</a><script>var defined = { tickets: [{"section":"101","row":"A","seat":"1-2","price":150,"count":2,"type":"Standard","eventId":"0D00636ED3B8BF22"}], };</script></body></html>'''

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

        # Check colors of several different sections
        colors = page.evaluate('''() => {
            const svg = document.querySelector("#svgMapContainer svg");
            if (!svg) return {error: "no svg"};
            const result = {};
            // Sample from different price tiers
            const ids = ["102","135","201","301","343","FLOOR"];
            for (const id of ids) {
                const p = svg.querySelector('path[id="' + id + '"]');
                if (p) {
                    const computed = window.getComputedStyle(p);
                    result[id] = {
                        attrFill: p.getAttribute("fill"),
                        attrFillOpacity: p.getAttribute("fill-opacity"),
                        attrStroke: p.getAttribute("stroke"),
                        attrStrokeWidth: p.getAttribute("stroke-width"),
                        computedFill: computed.fill,
                        computedOpacity: computed.opacity,
                        hasStock: p.getAttribute("data-has-stock")
                    };
                }
            }
            // Also check the background rect
            const rects = svg.querySelectorAll("rect");
            result._rects = Array.from(rects).slice(0,3).map(r => ({
                fill: r.getAttribute("fill"),
                fillOpacity: r.getAttribute("fill-opacity"),
                width: r.getAttribute("width"),
                height: r.getAttribute("height")
            }));
            // Check if there are nested SVGs
            result._nestedSvgs = svg.querySelectorAll("svg").length;
            // Check background container
            const bgContainer = svg.querySelector("#background-container");
            result._bgContainer = bgContainer ? bgContainer.innerHTML.substring(0, 200) : "none";
            return result;
        }''')
        print(json.dumps(colors, indent=2))
        browser.close()

if __name__ == "__main__":
    run()

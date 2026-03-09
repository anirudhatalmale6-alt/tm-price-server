"""Test v5.1b with client's actual Broker Buds report URL."""
import json
from playwright.sync_api import sync_playwright

REPORT_URL = "https://brokerbuds-tools.s3.us-east-1.amazonaws.com/stock-checker/reports/a3f3c0e5-17ae-4764-9220-7eb451049e8a.html"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 900})

        page.goto("http://localhost:3000/admin", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Use the URL import method - paste URL and click Import
        page.evaluate(f'''() => {{
            document.getElementById("reportUrl0").value = "{REPORT_URL}";
        }}''')
        page.evaluate('importFromUrl(0)')

        # Wait for report import + map + stock to load
        page.wait_for_timeout(15000)

        # Check status
        status = page.evaluate('''() => {
            const mapCol = document.getElementById("mapCol");
            const svgContainer = document.getElementById("svgMapContainer");
            const svg = svgContainer ? svgContainer.querySelector("svg") : null;
            const genChart = svgContainer ? svgContainer.querySelector(".gen-chart") : null;
            const paths = svg ? svg.querySelectorAll("path[id]") : [];
            const numericPaths = Array.from(paths).filter(p => /^\\d+$/.test(p.id));
            const stockContent = document.getElementById("stockContent");
            return {
                mapVisible: mapCol ? mapCol.style.display : "N/A",
                hasSvg: !!svg,
                hasGenChart: !!genChart,
                mapMode: typeof svgMapMode !== 'undefined' ? svgMapMode : 'N/A',
                totalPaths: paths.length,
                numericPaths: numericPaths.length,
                coloredPaths: numericPaths.filter(p => p.getAttribute("data-has-stock") === "1").length,
                genSections: genChart ? genChart.querySelectorAll(".gen-sec").length : 0,
                hasZoneCards: stockContent ? stockContent.querySelectorAll(".stock-zone").length : 0,
                eventId: document.getElementById("eventIdInput0") ? document.getElementById("eventIdInput0").value : "N/A",
                eventName: document.getElementById("eventName0") ? document.getElementById("eventName0").textContent : "N/A"
            };
        }''')
        print("Status:", json.dumps(status, indent=2))

        # Screenshot A: Full overview
        page.screenshot(path="v51b_a.png")
        print("A: Overview saved")

        # Screenshot B: Map panel
        map_col = page.locator("#mapCol")
        if map_col.is_visible():
            map_col.screenshot(path="v51b_b.png")
            print("B: Map panel saved")

        # Click a section
        if status.get("hasSvg") and status.get("numericPaths", 0) > 0:
            clicked = page.evaluate('''() => {
                const svg = document.querySelector("#svgMapContainer svg");
                const target = svg.querySelector('path[data-has-stock="1"]');
                if (target) { target.dispatchEvent(new Event("click", {bubbles: true})); return target.id; }
                return null;
            }''')
            if clicked:
                print(f"Clicked section: {clicked}")
                page.wait_for_timeout(500)
                map_col.screenshot(path="v51b_c.png")
                print("C: Section detail saved")
        elif status.get("hasGenChart"):
            clicked = page.evaluate('''() => {
                const sec = document.querySelector(".gen-sec");
                if (sec) { sec.click(); return sec.dataset.section; }
                return null;
            }''')
            if clicked:
                print(f"Clicked gen section: {clicked}")
                page.wait_for_timeout(500)
                map_col.screenshot(path="v51b_c.png")
                print("C: Section detail saved")

        print("Done!")
        browser.close()

if __name__ == "__main__":
    run()

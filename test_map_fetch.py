#!/usr/bin/env python3
"""
Ticketmaster Venue SVG Map Fetcher - Multi-Approach Test Script
===============================================================

Tests multiple approaches to fetch TM venue SVG maps now that PhantomChecker's
map-image proxy is returning garbage / blocked.

KEY FINDING: Wayback Machine web/0id_ proxy approach WORKS.
  URL pattern: https://web.archive.org/web/0id_/{mapsapi_url}
  The Wayback Machine fetches from its own non-blocked IP and returns raw content.

Approaches tested:
  1.  Direct mapsapi.tmol.io fetch with various headers/referrers
  2.  TM Discovery API (seatmap staticUrl)
  3.  app.ticketmaster.com Maps Geometry endpoint
  4.  Alternative CDN / static URL patterns
  5.  Playwright - Extract SVG from TM event page DOM
  6.  Playwright - Intercept network requests for SVG/map data
  7.  Playwright - Direct navigation to mapsapi.tmol.io
  8.  Playwright - JS fetch() from TM page context
  9.  httpx with HTTP/2
  10. Direct HTML scrape for embedded map data
  11. Playwright stealth + PX challenge wait
  12. TM EU/International Discovery API
  13. Web Archive / Wayback Machine proxy (WORKING!)

Usage:
    python3 test_map_fetch.py [EVENT_ID]

Default test event: 16006367E975D3A9
"""

import sys
import os
import json
import time
import re
import traceback
from datetime import datetime
from urllib.parse import urlencode, quote

import requests
import httpx

# ============================================================================
# Configuration
# ============================================================================

EVENT_ID = sys.argv[1] if len(sys.argv) > 1 else "16006367E975D3A9"
TM_EVENT_URL = f"https://www.ticketmaster.com/event/{EVENT_ID}"

# TM Discovery API key - free tier (register at developer.ticketmaster.com)
# Using the well-known demo/test key from TM dev portal examples
TM_API_KEYS = [
    "GkB8Z037ZfqbLCNtZViAgrEegbsrZ6Ne",  # Known public demo key
    "7elxdku9GGG5k8j0Xm8KWdANDgecHMV0",  # Another public example key
]

# Headers that mimic a real browser
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
    "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "[*]", "OK": "[+]", "FAIL": "[-]", "WARN": "[!]"}
    print(f"{ts} {prefix.get(level, '[?]')} {msg}")


def save_result(approach_name, success, data=None, details="", url=""):
    """Record a test result."""
    result = {
        "approach": approach_name,
        "success": success,
        "details": details,
        "url": url,
    }
    if success and data:
        # Save the SVG/image data to file
        ext = "svg" if (isinstance(data, str) and "<svg" in data.lower()) else "png"
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', approach_name)
        filename = f"map_result_{safe_name}.{ext}"
        filepath = os.path.join(OUTPUT_DIR, filename)
        if isinstance(data, str):
            with open(filepath, "w") as f:
                f.write(data)
        else:
            with open(filepath, "wb") as f:
                f.write(data)
        result["saved_to"] = filename
        result["data_size"] = len(data)
        log(f"  Saved {len(data)} bytes to {filename}", "OK")
    RESULTS.append(result)
    return result


def is_valid_svg(data):
    """Check if data looks like valid SVG."""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")
    return "<svg" in data.lower() and ("</svg>" in data.lower() or "/>" in data)


def is_valid_image(data):
    """Check if data looks like a valid image."""
    if isinstance(data, bytes):
        # PNG magic bytes
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return "png"
        # JPEG
        if data[:2] == b'\xff\xd8':
            return "jpeg"
        # SVG (text)
        if b"<svg" in data.lower():
            return "svg"
    elif isinstance(data, str):
        if "<svg" in data.lower():
            return "svg"
    return None


# ============================================================================
# APPROACH 1: Direct mapsapi.tmol.io with various header combinations
# ============================================================================

def test_direct_mapsapi():
    """Try fetching directly from mapsapi.tmol.io with different header combos."""
    log("=" * 70)
    log("APPROACH 1: Direct mapsapi.tmol.io fetch")
    log("=" * 70)

    base_url = f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage"

    # Different parameter combinations to try
    param_sets = [
        {
            "name": "SVG + HOST + sectionLevel",
            "params": {"type": "svg", "systemId": "HOST", "sectionLevel": "true", "avertaFonts": "true"},
        },
        {
            "name": "PNG + HOST + sectionLevel",
            "params": {"type": "png", "systemId": "HOST", "sectionLevel": "true"},
        },
        {
            "name": "SVG + HOST + app=PRD2663_EDP_NA",
            "params": {"type": "svg", "systemId": "HOST", "sectionLevel": "true", "app": "PRD2663_EDP_NA", "sectionColor": "727272", "avertaFonts": "true"},
        },
        {
            "name": "SVG minimal params",
            "params": {"type": "svg", "systemId": "HOST"},
        },
    ]

    # Different header combinations
    header_sets = [
        {
            "name": "No special headers",
            "headers": {},
        },
        {
            "name": "Browser UA + TM Referer",
            "headers": {
                **BROWSER_HEADERS,
                "Referer": "https://www.ticketmaster.com/",
                "Origin": "https://www.ticketmaster.com",
            },
        },
        {
            "name": "Browser UA + mapsapi Referer",
            "headers": {
                **BROWSER_HEADERS,
                "Referer": "https://mapsapi.tmol.io/",
            },
        },
        {
            "name": "Chrome UA only",
            "headers": {
                "User-Agent": BROWSER_HEADERS["User-Agent"],
            },
        },
        {
            "name": "Mobile UA + TM Referer",
            "headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.ticketmaster.com/",
                "Accept": "image/svg+xml,image/*,*/*;q=0.8",
            },
        },
    ]

    for ps in param_sets:
        url = f"{base_url}?{urlencode(ps['params'])}"
        for hs in header_sets:
            test_name = f"Direct: {ps['name']} / {hs['name']}"
            try:
                resp = requests.get(url, headers=hs["headers"], timeout=15, allow_redirects=True)
                ct = resp.headers.get("Content-Type", "")
                status = resp.status_code

                if status == 200:
                    img_type = is_valid_image(resp.content)
                    if img_type:
                        log(f"  {test_name}: {status} OK - {img_type} ({len(resp.content)} bytes)", "OK")
                        save_result(test_name, True, resp.content if img_type != "svg" else resp.text,
                                    f"Status {status}, Content-Type: {ct}, Size: {len(resp.content)}", url)
                    else:
                        # Got 200 but garbage data
                        preview = resp.text[:200] if len(resp.text) < 500 else resp.text[:200] + "..."
                        log(f"  {test_name}: {status} but invalid data: {preview[:80]}", "WARN")
                        save_result(test_name, False,
                                    details=f"Status 200 but invalid data. CT: {ct}, Size: {len(resp.content)}, Preview: {preview[:120]}", url=url)
                elif status == 403:
                    log(f"  {test_name}: {status} BLOCKED (PerimeterX)", "FAIL")
                    save_result(test_name, False, details=f"Status {status} - Blocked by PerimeterX", url=url)
                else:
                    log(f"  {test_name}: {status}", "FAIL")
                    save_result(test_name, False, details=f"Status {status}, CT: {ct}", url=url)
            except Exception as e:
                log(f"  {test_name}: ERROR - {e}", "FAIL")
                save_result(test_name, False, details=str(e), url=url)

            # Don't hammer the server
            time.sleep(0.3)

        # Only test the first header combo for subsequent param sets if first one is all 403
        # (skip to save time)


# ============================================================================
# APPROACH 2: TM Discovery API - Get seatmap staticUrl
# ============================================================================

def test_discovery_api():
    """Use TM Discovery API to get the seatmap staticUrl for the event."""
    log("=" * 70)
    log("APPROACH 2: TM Discovery API (seatmap staticUrl)")
    log("=" * 70)

    for api_key in TM_API_KEYS:
        test_name = f"Discovery API (key: {api_key[:8]}...)"
        try:
            # Get event details including seatmap
            url = f"https://app.ticketmaster.com/discovery/v2/events/{EVENT_ID}.json?apikey={api_key}"
            log(f"  Trying: {url[:80]}...")
            resp = requests.get(url, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                event_name = data.get("name", "Unknown")
                log(f"  Event found: {event_name}", "OK")

                # Extract venue info
                venues = data.get("_embedded", {}).get("venues", [])
                if venues:
                    venue = venues[0]
                    venue_name = venue.get("name", "Unknown")
                    venue_id = venue.get("id", "Unknown")
                    log(f"  Venue: {venue_name} (ID: {venue_id})", "OK")

                # Check for seatmap
                seatmap = data.get("seatmap", {})
                static_url = seatmap.get("staticUrl", "")

                if static_url:
                    log(f"  seatmap.staticUrl: {static_url}", "OK")

                    # Now fetch the actual image from the staticUrl
                    img_resp = requests.get(static_url, headers=BROWSER_HEADERS, timeout=15)
                    if img_resp.status_code == 200:
                        img_type = is_valid_image(img_resp.content)
                        if img_type:
                            log(f"  Fetched seatmap image: {img_type} ({len(img_resp.content)} bytes)", "OK")
                            save_result(test_name, True,
                                        img_resp.content if img_type != "svg" else img_resp.text,
                                        f"staticUrl: {static_url}, Type: {img_type}, Size: {len(img_resp.content)}",
                                        static_url)
                        else:
                            log(f"  Fetched but unrecognized format (CT: {img_resp.headers.get('Content-Type')})", "WARN")
                            save_result(test_name, False,
                                        details=f"staticUrl fetched but unrecognized format. CT: {img_resp.headers.get('Content-Type')}, Size: {len(img_resp.content)}",
                                        url=static_url)
                    else:
                        log(f"  staticUrl fetch failed: {img_resp.status_code}", "FAIL")
                        save_result(test_name, False,
                                    details=f"staticUrl returned {img_resp.status_code}",
                                    url=static_url)
                else:
                    log(f"  No seatmap.staticUrl in response", "WARN")
                    # Log what keys ARE available
                    log(f"  Available keys: {list(data.keys())}")
                    save_result(test_name, False,
                                details=f"Event found ({event_name}) but no seatmap.staticUrl. Keys: {list(data.keys())}",
                                url=url)

                # Also try to extract any map-related URLs from the full response
                full_json = json.dumps(data)
                map_urls = re.findall(r'https?://[^"]+(?:map|seatmap|geometry|staticImage)[^"]*', full_json, re.IGNORECASE)
                if map_urls:
                    log(f"  Found {len(map_urls)} map-related URLs in response:")
                    for mu in map_urls[:5]:
                        log(f"    -> {mu}")

            elif resp.status_code == 401:
                log(f"  API key invalid/expired: {api_key[:8]}...", "FAIL")
                save_result(test_name, False, details=f"API key rejected (401)", url=url)
            elif resp.status_code == 404:
                log(f"  Event not found via Discovery API", "FAIL")
                save_result(test_name, False, details=f"Event {EVENT_ID} not found (404)", url=url)
            else:
                log(f"  Status: {resp.status_code}", "FAIL")
                save_result(test_name, False, details=f"Status {resp.status_code}: {resp.text[:200]}", url=url)

        except Exception as e:
            log(f"  ERROR: {e}", "FAIL")
            save_result(test_name, False, details=str(e), url="")

        time.sleep(0.5)


# ============================================================================
# APPROACH 3: TM Maps Geometry via app.ticketmaster.com
# ============================================================================

def test_tm_maps_geometry():
    """Try app.ticketmaster.com/maps/geometry endpoint (may need API key)."""
    log("=" * 70)
    log("APPROACH 3: app.ticketmaster.com Maps Geometry endpoint")
    log("=" * 70)

    for api_key in TM_API_KEYS:
        # Try different URL patterns
        url_patterns = [
            {
                "name": "Event image with API key",
                "url": f"https://app.ticketmaster.com/maps/geometry/3/event/{EVENT_ID}/image?systemId=HOST&apikey={api_key}",
            },
            {
                "name": "Event image with labels",
                "url": f"https://app.ticketmaster.com/maps/geometry/3/event/{EVENT_ID}/image?systemId=HOST&showLabels=true&apikey={api_key}",
            },
            {
                "name": "Event staticImage SVG",
                "url": f"https://app.ticketmaster.com/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&apikey={api_key}",
            },
        ]

        for pat in url_patterns:
            test_name = f"TM Geometry: {pat['name']} (key: {api_key[:8]}...)"
            try:
                resp = requests.get(pat["url"], headers=BROWSER_HEADERS, timeout=15)
                status = resp.status_code
                ct = resp.headers.get("Content-Type", "")

                if status == 200:
                    img_type = is_valid_image(resp.content)
                    if img_type:
                        log(f"  {pat['name']}: {status} OK - {img_type} ({len(resp.content)} bytes)", "OK")
                        save_result(test_name, True,
                                    resp.content if img_type != "svg" else resp.text,
                                    f"Type: {img_type}, Size: {len(resp.content)}, CT: {ct}",
                                    pat["url"])
                    else:
                        preview = resp.text[:150]
                        log(f"  {pat['name']}: {status} but unrecognized: {preview[:80]}", "WARN")
                        save_result(test_name, False,
                                    details=f"Status 200 but unrecognized. CT: {ct}, Preview: {preview}",
                                    url=pat["url"])
                else:
                    log(f"  {pat['name']}: {status}", "FAIL")
                    save_result(test_name, False, details=f"Status {status}", url=pat["url"])

            except Exception as e:
                log(f"  {pat['name']}: ERROR - {e}", "FAIL")
                save_result(test_name, False, details=str(e), url=pat["url"])

            time.sleep(0.3)


# ============================================================================
# APPROACH 4: Alternative CDN / static URL patterns
# ============================================================================

def test_cdn_patterns():
    """Try known CDN and alternative URL patterns for TM venue maps."""
    log("=" * 70)
    log("APPROACH 4: Alternative CDN / static URL patterns")
    log("=" * 70)

    # Various URL patterns that TM has used or may use
    patterns = [
        {
            "name": "s1.ticketm.net seatmap",
            "url": f"https://s1.ticketm.net/dam/a/{EVENT_ID[:2]}/{EVENT_ID}/seatmap.png",
        },
        {
            "name": "maps.ticketmaster.com",
            "url": f"https://maps.ticketmaster.com/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST",
        },
        {
            "name": "content.resale.ticketmaster.com",
            "url": f"https://content.resale.ticketmaster.com/graphics/tmnpi/venue/{EVENT_ID}.png",
        },
        {
            "name": "mapsapi.tmol.io PNG no params",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=png",
        },
        {
            "name": "mapsapi.tmol.io image endpoint",
            "url": f"https://mapsapi.tmol.io/maps/geometry/image/{EVENT_ID}",
        },
        {
            "name": "mapsapi via HTTP (not HTTPS)",
            "url": f"http://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST",
        },
        {
            "name": "akamaized.net seatmap",
            "url": f"https://tmimages.ticketmaster.com/eventimages/seatmaps/{EVENT_ID}.png",
        },
    ]

    for pat in patterns:
        test_name = f"CDN: {pat['name']}"
        try:
            resp = requests.get(pat["url"], headers=BROWSER_HEADERS, timeout=10, allow_redirects=True)
            status = resp.status_code
            ct = resp.headers.get("Content-Type", "")
            final_url = resp.url

            if status == 200:
                img_type = is_valid_image(resp.content)
                if img_type:
                    log(f"  {pat['name']}: {status} OK - {img_type} ({len(resp.content)} bytes)", "OK")
                    save_result(test_name, True,
                                resp.content if img_type != "svg" else resp.text,
                                f"Type: {img_type}, Size: {len(resp.content)}", pat["url"])
                else:
                    log(f"  {pat['name']}: {status} but not an image (CT: {ct}, size: {len(resp.content)})", "WARN")
                    save_result(test_name, False,
                                details=f"200 but not image. CT: {ct}, Size: {len(resp.content)}", url=pat["url"])
            else:
                redirect_info = f" -> {final_url}" if final_url != pat["url"] else ""
                log(f"  {pat['name']}: {status}{redirect_info}", "FAIL")
                save_result(test_name, False, details=f"Status {status}{redirect_info}", url=pat["url"])

        except Exception as e:
            log(f"  {pat['name']}: ERROR - {e}", "FAIL")
            save_result(test_name, False, details=str(e), url=pat["url"])

        time.sleep(0.3)


# ============================================================================
# APPROACH 5: Playwright - Load event page, extract SVG from DOM
# ============================================================================

def test_playwright_dom():
    """Use Playwright to load the TM event page and extract SVG from the DOM."""
    log("=" * 70)
    log("APPROACH 5: Playwright - Extract SVG from TM event page DOM")
    log("=" * 70)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, skipping", "FAIL")
        save_result("Playwright DOM extraction", False, details="playwright not installed")
        return

    test_name = "Playwright DOM SVG extraction"

    try:
        with sync_playwright() as p:
            log("  Launching Chromium...")
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
            )

            # Remove webdriver detection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                delete navigator.__proto__.webdriver;
            """)

            page = context.new_page()

            log(f"  Navigating to {TM_EVENT_URL}...")
            try:
                page.goto(TM_EVENT_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                log(f"  Page load error (may be partial): {e}", "WARN")

            # Wait for page to settle
            log("  Waiting for page content to render...")
            page.wait_for_timeout(5000)

            # Take a screenshot for debugging
            screenshot_path = os.path.join(OUTPUT_DIR, "tm_page_screenshot.png")
            page.screenshot(path=screenshot_path, full_page=False)
            log(f"  Screenshot saved to tm_page_screenshot.png")

            # Check page title / status
            title = page.title()
            log(f"  Page title: {title}")

            # Look for SVG elements in the DOM
            svg_elements = page.query_selector_all("svg")
            log(f"  Found {len(svg_elements)} SVG elements in DOM")

            found_map_svg = False
            for i, svg in enumerate(svg_elements):
                try:
                    # Get the outer HTML of each SVG
                    svg_html = svg.evaluate("el => el.outerHTML")
                    has_paths = "path" in svg_html.lower()
                    has_sections = bool(re.search(r'id="\d+"', svg_html))
                    size = len(svg_html)

                    log(f"  SVG #{i}: {size} chars, has paths: {has_paths}, has section IDs: {has_sections}")

                    # A venue map SVG typically has path elements with numeric IDs (section numbers)
                    if has_sections and size > 5000:
                        log(f"  ** This looks like a venue map SVG! ({size} chars)", "OK")
                        save_result(f"Playwright DOM SVG #{i}", True, svg_html,
                                    f"SVG with section IDs, {size} chars", TM_EVENT_URL)
                        found_map_svg = True
                    elif has_paths and size > 10000:
                        log(f"  ** Large SVG with paths - possible map ({size} chars)", "OK")
                        save_result(f"Playwright DOM SVG #{i} (large)", True, svg_html,
                                    f"Large SVG with paths, {size} chars", TM_EVENT_URL)
                        found_map_svg = True
                except Exception as e:
                    log(f"  SVG #{i}: Could not extract - {e}", "WARN")

            if not found_map_svg:
                # Try looking for SVG inside iframes
                frames = page.frames
                log(f"  Checking {len(frames)} frames for SVG content...")
                for fi, frame in enumerate(frames):
                    try:
                        frame_url = frame.url
                        if "map" in frame_url.lower() or "seat" in frame_url.lower():
                            log(f"  Frame #{fi} URL: {frame_url}")
                            frame_svgs = frame.query_selector_all("svg")
                            log(f"  Frame #{fi} has {len(frame_svgs)} SVGs")
                            for si, svg in enumerate(frame_svgs):
                                svg_html = svg.evaluate("el => el.outerHTML")
                                if len(svg_html) > 5000:
                                    save_result(f"Playwright Frame #{fi} SVG #{si}", True, svg_html,
                                                f"SVG from frame, {len(svg_html)} chars", frame_url)
                                    found_map_svg = True
                    except Exception as e:
                        log(f"  Frame #{fi}: {e}", "WARN")

            # Also check for any canvas elements (sometimes maps are rendered to canvas)
            canvas_count = page.evaluate("document.querySelectorAll('canvas').length")
            if canvas_count > 0:
                log(f"  Found {canvas_count} canvas elements (map may be rendered there)")

            # Check for map-related data in window/page state
            try:
                map_data = page.evaluate("""
                    () => {
                        const results = {};
                        // Check for common TM map-related global variables
                        if (window.__NEXT_DATA__) {
                            results.hasNextData = true;
                            const pageProps = window.__NEXT_DATA__?.props?.pageProps;
                            if (pageProps) {
                                results.pagePropsKeys = Object.keys(pageProps);
                                // Look for map/venue data
                                const json = JSON.stringify(pageProps);
                                const mapUrls = json.match(/https?:[^"]+(?:map|seatmap|geometry|staticImage)[^"]*/gi);
                                if (mapUrls) results.mapUrls = [...new Set(mapUrls)].slice(0, 10);
                            }
                        }
                        // Check for TM-specific globals
                        ['__TM_EVENT_DATA__', '__PRELOADED_STATE__', 'tmEventData', 'window.eventData'].forEach(key => {
                            try {
                                const val = eval(key);
                                if (val) results[key] = typeof val;
                            } catch {}
                        });
                        return results;
                    }
                """)
                if map_data:
                    log(f"  Page state data: {json.dumps(map_data, indent=2)[:500]}")
                    if map_data.get("mapUrls"):
                        for mu in map_data["mapUrls"]:
                            log(f"  Found map URL in page data: {mu}", "OK")
                            # Try fetching these URLs
                            try:
                                mr = requests.get(mu, headers=BROWSER_HEADERS, timeout=10)
                                if mr.status_code == 200 and is_valid_image(mr.content):
                                    img_type = is_valid_image(mr.content)
                                    save_result(f"Playwright discovered URL: {mu[:60]}", True,
                                                mr.content if img_type != "svg" else mr.text,
                                                f"From page data, {len(mr.content)} bytes", mu)
                                    found_map_svg = True
                            except Exception as e:
                                log(f"  Could not fetch discovered URL: {e}", "WARN")
            except Exception as e:
                log(f"  Could not extract page state: {e}", "WARN")

            if not found_map_svg:
                log("  No venue map SVG found in DOM", "FAIL")
                save_result(test_name, False,
                            details=f"Page loaded (title: {title}), {len(svg_elements)} SVGs found but none are venue maps")

            browser.close()

    except Exception as e:
        log(f"  Playwright error: {e}", "FAIL")
        log(f"  {traceback.format_exc()}", "FAIL")
        save_result(test_name, False, details=str(e))


# ============================================================================
# APPROACH 6: Playwright - Intercept network requests for map data
# ============================================================================

def test_playwright_intercept():
    """Use Playwright to intercept network requests when loading TM event page."""
    log("=" * 70)
    log("APPROACH 6: Playwright - Intercept network requests for SVG/map data")
    log("=" * 70)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, skipping", "FAIL")
        save_result("Playwright network intercept", False, details="playwright not installed")
        return

    test_name = "Playwright network intercept"
    intercepted_maps = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            page = context.new_page()

            # Track all network requests
            all_requests = []
            map_related_requests = []

            def on_request(request):
                url = request.url
                all_requests.append(url)
                # Look for map-related requests
                if any(kw in url.lower() for kw in ["mapsapi", "tmol.io", "map", "geometry", "seatmap", "venue", "staticimage"]):
                    map_related_requests.append({
                        "url": url,
                        "method": request.method,
                        "resource_type": request.resource_type,
                        "headers": dict(request.headers),
                    })

            def on_response(response):
                url = response.url
                ct = response.headers.get("content-type", "")
                status = response.status

                # Capture SVG responses
                if "svg" in ct or "svg" in url.lower():
                    try:
                        body = response.body()
                        if body and is_valid_svg(body):
                            intercepted_maps.append({
                                "url": url,
                                "content_type": ct,
                                "data": body.decode("utf-8", errors="ignore"),
                                "size": len(body),
                                "status": status,
                            })
                            log(f"  ** Intercepted SVG response: {url[:80]} ({len(body)} bytes)", "OK")
                    except Exception:
                        pass

                # Capture image responses from map domains
                if any(d in url for d in ["mapsapi", "tmol.io", "geometry"]):
                    try:
                        body = response.body()
                        if body and len(body) > 1000:
                            img_type = is_valid_image(body)
                            if img_type:
                                intercepted_maps.append({
                                    "url": url,
                                    "content_type": ct,
                                    "data": body if img_type != "svg" else body.decode("utf-8", errors="ignore"),
                                    "size": len(body),
                                    "status": status,
                                    "type": img_type,
                                })
                                log(f"  ** Intercepted map image: {url[:80]} ({img_type}, {len(body)} bytes)", "OK")
                    except Exception:
                        pass

            page.on("request", on_request)
            page.on("response", on_response)

            log(f"  Navigating to {TM_EVENT_URL} with network interception...")
            try:
                page.goto(TM_EVENT_URL, wait_until="networkidle", timeout=45000)
            except Exception as e:
                log(f"  Navigation timeout (expected): {str(e)[:80]}", "WARN")

            # Wait extra time for async map loads
            page.wait_for_timeout(5000)

            # Try clicking on "View Seat Map" or similar buttons
            map_buttons = page.query_selector_all('[data-testid*="map"], [class*="seatmap"], [class*="seat-map"], button:has-text("Map"), button:has-text("Seat"), a:has-text("Map")')
            if map_buttons:
                log(f"  Found {len(map_buttons)} potential map buttons, clicking first one...")
                try:
                    map_buttons[0].click()
                    page.wait_for_timeout(5000)
                except Exception as e:
                    log(f"  Click failed: {e}", "WARN")

            # Report findings
            log(f"  Total requests intercepted: {len(all_requests)}")
            log(f"  Map-related requests: {len(map_related_requests)}")
            for mr in map_related_requests:
                log(f"    {mr['method']} {mr['url'][:100]} [{mr['resource_type']}]")

            if intercepted_maps:
                for i, m in enumerate(intercepted_maps):
                    save_result(f"Playwright intercept #{i}", True, m["data"],
                                f"From {m['url'][:80]}, Status: {m['status']}, Size: {m['size']}",
                                m["url"])
            else:
                log("  No map SVG/image intercepted from network", "FAIL")
                save_result(test_name, False,
                            details=f"No map data intercepted. {len(map_related_requests)} map-related requests seen: " +
                                    "; ".join(r["url"][:80] for r in map_related_requests[:5]))

            browser.close()

    except Exception as e:
        log(f"  Playwright error: {e}", "FAIL")
        log(f"  {traceback.format_exc()}", "FAIL")
        save_result(test_name, False, details=str(e))


# ============================================================================
# APPROACH 7: Playwright - Navigate directly to mapsapi.tmol.io
# ============================================================================

def test_playwright_direct_mapsapi():
    """Use Playwright (real browser) to navigate directly to the mapsapi URL."""
    log("=" * 70)
    log("APPROACH 7: Playwright - Direct navigation to mapsapi.tmol.io")
    log("=" * 70)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, skipping", "FAIL")
        save_result("Playwright direct mapsapi", False, details="playwright not installed")
        return

    urls_to_try = [
        {
            "name": "SVG staticImage",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true",
        },
        {
            "name": "PNG staticImage",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=png&systemId=HOST&sectionLevel=true",
        },
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )

            for url_info in urls_to_try:
                test_name = f"Playwright direct: {url_info['name']}"
                log(f"  Trying: {url_info['url'][:80]}...")

                try:
                    # First visit TM to get cookies/session
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    )
                    context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)
                    page = context.new_page()

                    # Visit TM first to establish cookies
                    log("  Visiting ticketmaster.com first to get cookies...")
                    try:
                        page.goto("https://www.ticketmaster.com/", wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(3000)
                    except Exception as e:
                        log(f"  TM visit partial: {str(e)[:50]}", "WARN")

                    # Now navigate to the map URL with established TM cookies
                    response = page.goto(url_info["url"], wait_until="load", timeout=20000)

                    if response:
                        status = response.status
                        ct = response.headers.get("content-type", "")
                        log(f"  Response: {status}, Content-Type: {ct}")

                        if status == 200:
                            body = response.body()
                            img_type = is_valid_image(body)
                            if img_type:
                                log(f"  Got valid {img_type}! ({len(body)} bytes)", "OK")
                                save_result(test_name, True,
                                            body.decode("utf-8", errors="ignore") if img_type == "svg" else body,
                                            f"Type: {img_type}, Size: {len(body)}", url_info["url"])
                            else:
                                # Check if we got PerimeterX challenge page
                                text = body.decode("utf-8", errors="ignore")
                                if "perimeterx" in text.lower() or "challenge" in text.lower() or "captcha" in text.lower():
                                    log(f"  Got PerimeterX challenge page", "FAIL")
                                    save_result(test_name, False,
                                                details="PerimeterX challenge page returned even with real browser",
                                                url=url_info["url"])
                                else:
                                    preview = text[:200]
                                    log(f"  Got 200 but unrecognized content: {preview[:80]}", "WARN")
                                    save_result(test_name, False,
                                                details=f"200 but unrecognized. Preview: {preview[:200]}",
                                                url=url_info["url"])
                        else:
                            log(f"  Status {status}", "FAIL")
                            save_result(test_name, False, details=f"Status {status}", url=url_info["url"])
                    else:
                        log(f"  No response received", "FAIL")
                        save_result(test_name, False, details="No response", url=url_info["url"])

                    context.close()

                except Exception as e:
                    log(f"  Error: {e}", "FAIL")
                    save_result(test_name, False, details=str(e), url=url_info["url"])

            browser.close()

    except Exception as e:
        log(f"  Playwright error: {e}", "FAIL")
        log(f"  {traceback.format_exc()}", "FAIL")


# ============================================================================
# APPROACH 8: Playwright - Fetch via page.evaluate (JS-level fetch from TM origin)
# ============================================================================

def test_playwright_js_fetch():
    """Use Playwright to run fetch() from within the TM page context (same origin)."""
    log("=" * 70)
    log("APPROACH 8: Playwright - JS fetch() from TM page context")
    log("=" * 70)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, skipping", "FAIL")
        save_result("Playwright JS fetch", False, details="playwright not installed")
        return

    test_name = "Playwright JS-level fetch from TM context"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
            page = context.new_page()

            # Navigate to TM event page first
            log(f"  Loading TM event page...")
            try:
                page.goto(TM_EVENT_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)
            except Exception as e:
                log(f"  Page load (partial OK): {str(e)[:50]}", "WARN")

            # Now try fetching the map URL from within the page context
            map_url = f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true"

            log(f"  Running fetch() from page context for mapsapi URL...")
            result = page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch("{map_url}", {{
                            mode: 'cors',
                            credentials: 'include',
                            headers: {{
                                'Accept': 'image/svg+xml,image/*,*/*',
                            }}
                        }});
                        const text = await resp.text();
                        return {{
                            status: resp.status,
                            contentType: resp.headers.get('content-type'),
                            size: text.length,
                            preview: text.substring(0, 500),
                            isSvg: text.includes('<svg'),
                            fullText: text.length < 500000 ? text : null,
                        }};
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """)

            if result.get("error"):
                log(f"  JS fetch error: {result['error']}", "FAIL")
                save_result(test_name, False, details=f"JS fetch error: {result['error']}", url=map_url)
            elif result.get("isSvg"):
                log(f"  Got SVG! Status: {result['status']}, Size: {result['size']}", "OK")
                if result.get("fullText"):
                    save_result(test_name, True, result["fullText"],
                                f"JS fetch from TM context, Status: {result['status']}, Size: {result['size']}",
                                map_url)
                else:
                    save_result(test_name, True, None,
                                f"SVG too large to extract ({result['size']} chars), Status: {result['status']}",
                                map_url)
            else:
                log(f"  Status: {result.get('status')}, CT: {result.get('contentType')}, Preview: {result.get('preview', '')[:100]}", "FAIL")
                save_result(test_name, False,
                            details=f"Status {result.get('status')}, CT: {result.get('contentType')}, Preview: {result.get('preview', '')[:200]}",
                            url=map_url)

            # Also try fetching as no-cors (opaque response, but may bypass CORS block)
            log("  Trying no-cors fetch...")
            nocors_result = page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch("{map_url}", {{
                            mode: 'no-cors',
                        }});
                        return {{
                            status: resp.status,
                            type: resp.type,
                            ok: resp.ok,
                        }};
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """)
            log(f"  no-cors result: {nocors_result}")

            browser.close()

    except Exception as e:
        log(f"  Playwright error: {e}", "FAIL")
        log(f"  {traceback.format_exc()}", "FAIL")
        save_result(test_name, False, details=str(e))


# ============================================================================
# APPROACH 9: httpx with HTTP/2 support (some CDNs treat HTTP/2 differently)
# ============================================================================

def test_httpx_h2():
    """Try fetching with httpx and HTTP/2 support."""
    log("=" * 70)
    log("APPROACH 9: httpx with HTTP/2")
    log("=" * 70)

    url = f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true"

    header_sets = [
        {
            "name": "Full browser headers (H2)",
            "headers": {
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Accept": "image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.ticketmaster.com/",
                "Origin": "https://www.ticketmaster.com",
            },
        },
        {
            "name": "Minimal headers (H2)",
            "headers": {
                "User-Agent": BROWSER_HEADERS["User-Agent"],
            },
        },
    ]

    for hs in header_sets:
        test_name = f"httpx H2: {hs['name']}"
        try:
            with httpx.Client(http2=True, follow_redirects=True, timeout=15) as client:
                resp = client.get(url, headers=hs["headers"])
                status = resp.status_code
                ct = resp.headers.get("content-type", "")
                http_version = resp.http_version

                log(f"  {hs['name']}: HTTP/{http_version} Status {status}, CT: {ct}")

                if status == 200:
                    img_type = is_valid_image(resp.content)
                    if img_type:
                        log(f"  Got {img_type}! ({len(resp.content)} bytes)", "OK")
                        save_result(test_name, True,
                                    resp.content if img_type != "svg" else resp.text,
                                    f"HTTP/{http_version}, Type: {img_type}, Size: {len(resp.content)}",
                                    url)
                    else:
                        preview = resp.text[:200]
                        log(f"  200 but not valid image: {preview[:80]}", "WARN")
                        save_result(test_name, False,
                                    details=f"HTTP/{http_version}, 200 but invalid. CT: {ct}, Preview: {preview[:200]}",
                                    url=url)
                else:
                    log(f"  Status {status}", "FAIL")
                    save_result(test_name, False, details=f"HTTP/{http_version}, Status {status}", url=url)

        except Exception as e:
            log(f"  {hs['name']}: ERROR - {e}", "FAIL")
            save_result(test_name, False, details=str(e), url=url)

        time.sleep(0.3)


# ============================================================================
# APPROACH 10: Scrape event page HTML for embedded map data/URLs
# ============================================================================

def test_html_scrape():
    """Scrape the TM event page HTML directly to find map URLs or embedded data."""
    log("=" * 70)
    log("APPROACH 10: Direct HTML scrape for embedded map data")
    log("=" * 70)

    test_name = "HTML scrape for map data"

    try:
        resp = requests.get(TM_EVENT_URL, headers={
            "User-Agent": BROWSER_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }, timeout=15, allow_redirects=True)

        status = resp.status_code
        log(f"  Status: {status}, Size: {len(resp.text)}")

        if status == 200:
            html = resp.text

            # Look for map-related URLs in the HTML
            map_urls = re.findall(
                r'https?://[^"\s<>]+(?:mapsapi|tmol\.io|geometry|staticImage|seatmap)[^"\s<>]*',
                html, re.IGNORECASE
            )
            if map_urls:
                unique_urls = list(set(map_urls))
                log(f"  Found {len(unique_urls)} map-related URLs in HTML:")
                for u in unique_urls[:10]:
                    log(f"    {u}")

                for u in unique_urls[:5]:
                    try:
                        mr = requests.get(u, headers=BROWSER_HEADERS, timeout=10)
                        if mr.status_code == 200:
                            img_type = is_valid_image(mr.content)
                            if img_type:
                                log(f"  ** Fetched from HTML URL: {img_type} ({len(mr.content)} bytes)", "OK")
                                save_result(f"HTML scrape URL: {u[:50]}", True,
                                            mr.content if img_type != "svg" else mr.text,
                                            f"Found in HTML, {len(mr.content)} bytes", u)
                    except Exception:
                        pass
            else:
                log("  No map-related URLs found in HTML")

            # Look for __NEXT_DATA__ JSON (Next.js page data)
            next_data_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if next_data_match:
                try:
                    nd = json.loads(next_data_match.group(1))
                    nd_str = json.dumps(nd)

                    # Find all URLs in NEXT_DATA
                    all_urls = re.findall(r'https?://[^"\\]+', nd_str)
                    map_related = [u for u in all_urls if any(k in u.lower() for k in
                                                              ["map", "seat", "venue", "geometry", "tmol"])]
                    if map_related:
                        log(f"  Found {len(map_related)} map-related URLs in __NEXT_DATA__:")
                        for u in list(set(map_related))[:10]:
                            log(f"    {u}")

                    # Look for venueId, seatmapId, or similar
                    venue_keys = ["venueId", "venue", "seatmap", "mapUrl", "seatmapUrl", "staticUrl"]
                    for vk in venue_keys:
                        matches = re.findall(rf'"{vk}"\s*:\s*"([^"]*)"', nd_str, re.IGNORECASE)
                        if matches:
                            log(f"  __NEXT_DATA__.{vk} = {matches[0][:100]}", "OK")

                except json.JSONDecodeError:
                    log("  __NEXT_DATA__ found but could not parse JSON", "WARN")
            else:
                log("  No __NEXT_DATA__ found (page may use different rendering)")

            # Look for inline JSON/JS with map data
            map_patterns = [
                (r'"seatmapUrl"\s*:\s*"([^"]+)"', "seatmapUrl"),
                (r'"staticUrl"\s*:\s*"([^"]+)"', "staticUrl"),
                (r'"mapUrl"\s*:\s*"([^"]+)"', "mapUrl"),
                (r'"venueMapUrl"\s*:\s*"([^"]+)"', "venueMapUrl"),
                (r'"imageUrl"\s*:\s*"([^"]+)"', "imageUrl in seatmap context"),
            ]
            for pattern, label in map_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    for m in matches[:3]:
                        log(f"  Found {label}: {m[:100]}", "OK")

            save_result(test_name, bool(map_urls),
                        details=f"Status {status}, {len(map_urls)} map URLs found, page size: {len(html)}")

        elif status == 403:
            log("  Blocked (403)", "FAIL")
            save_result(test_name, False, details="Blocked (403)")
        else:
            log(f"  Status {status}", "FAIL")
            save_result(test_name, False, details=f"Status {status}")

    except Exception as e:
        log(f"  ERROR: {e}", "FAIL")
        save_result(test_name, False, details=str(e))


# ============================================================================
# MAIN
# ============================================================================

def print_summary():
    """Print a summary of all test results."""
    log("")
    log("=" * 70)
    log("RESULTS SUMMARY")
    log("=" * 70)
    log("")

    successes = [r for r in RESULTS if r["success"]]
    failures = [r for r in RESULTS if not r["success"]]

    log(f"Total tests: {len(RESULTS)}")
    log(f"Successes: {len(successes)}")
    log(f"Failures: {len(failures)}")
    log("")

    if successes:
        log("WORKING APPROACHES:", "OK")
        for r in successes:
            saved = f" -> {r.get('saved_to', 'N/A')}" if r.get("saved_to") else ""
            log(f"  {r['approach']}: {r['details'][:100]}{saved}", "OK")
        log("")

    if failures:
        log("FAILED APPROACHES:", "FAIL")
        for r in failures:
            log(f"  {r['approach']}: {r['details'][:120]}", "FAIL")
        log("")

    # Save full results to JSON
    results_file = os.path.join(OUTPUT_DIR, "map_fetch_results.json")
    with open(results_file, "w") as f:
        json.dump({
            "event_id": EVENT_ID,
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(RESULTS),
            "successes": len(successes),
            "failures": len(failures),
            "results": RESULTS,
        }, f, indent=2)
    log(f"Full results saved to map_fetch_results.json")


def main():
    log(f"Ticketmaster Venue Map Fetch Test")
    log(f"Event ID: {EVENT_ID}")
    log(f"Event URL: {TM_EVENT_URL}")
    log(f"Timestamp: {datetime.now().isoformat()}")
    log("")

    # Run all approaches
    test_direct_mapsapi()
    test_discovery_api()
    test_tm_maps_geometry()
    test_cdn_patterns()
    test_html_scrape()
    test_httpx_h2()

    # Playwright tests (slower, run last)
    test_playwright_dom()
    test_playwright_intercept()
    test_playwright_direct_mapsapi()
    test_playwright_js_fetch()

    # Additional approaches after first-round findings
    test_httpx_h2()
    test_playwright_stealth()
    test_eu_discovery_api()
    test_google_cache()
    test_wayback_proxy()  # The WORKING approach

    # Summary
    print_summary()


# ============================================================================
# APPROACH 14: Wayback Machine web/0id_ proxy (CONFIRMED WORKING)
# ============================================================================

def test_wayback_proxy():
    """
    Use Wayback Machine's web/0id_ endpoint as a proxy to fetch TM map SVGs.

    How it works:
    - The Wayback Machine fetches the target URL from its own IP addresses
    - These IPs belong to the Internet Archive (not datacenter/cloud) and are
      NOT blocked by PerimeterX
    - The /web/0id_/ prefix returns raw content without any WB modification
    - This effectively acts as a free proxy for PerimeterX-protected content

    URL pattern:
      https://web.archive.org/web/0id_/{original_url}

    Caveats:
    - Rate limited (don't hammer it)
    - May stop working if PerimeterX blocks Internet Archive IPs
    - The 0id_ prefix means "latest archived version, raw content" -
      but if there's no archived version, WB will fetch it live
    """
    log("=" * 70)
    log("APPROACH 14: Wayback Machine web/0id_ proxy (CONFIRMED WORKING)")
    log("=" * 70)

    # Different URL variants to test through WB proxy
    url_variants = [
        {
            "name": "SVG + sectionLevel (primary)",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true",
        },
        {
            "name": "SVG minimal params",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST",
        },
        {
            "name": "PNG format",
            "url": f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=png&systemId=HOST&sectionLevel=true",
        },
    ]

    for variant in url_variants:
        test_name = f"Wayback proxy: {variant['name']}"
        wb_url = f"https://web.archive.org/web/0id_/{variant['url']}"
        log(f"  Testing: {variant['name']}")
        log(f"  Proxy URL: {wb_url[:100]}...")

        try:
            resp = requests.get(wb_url, timeout=30, headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Accept": "image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
            })
            status = resp.status_code
            ct = resp.headers.get("Content-Type", "")

            if status == 200:
                img_type = is_valid_image(resp.content)
                if img_type:
                    log(f"  SUCCESS! {img_type} ({len(resp.content)} bytes)", "OK")

                    # For SVG, count section IDs
                    if img_type == "svg":
                        import re as _re
                        section_ids = _re.findall(r'id="\d+"', resp.text)
                        named_groups = _re.findall(r'id="([A-Z_]+)"', resp.text)
                        log(f"  Section IDs: {len(section_ids)}, Named groups: {named_groups}", "OK")

                    save_result(test_name, True,
                                resp.content if img_type != "svg" else resp.text,
                                f"Wayback proxy WORKS! Type: {img_type}, Size: {len(resp.content)} bytes",
                                wb_url)
                else:
                    preview = resp.text[:200]
                    log(f"  200 but not valid image: {preview[:80]}", "WARN")
                    save_result(test_name, False,
                                details=f"200 but not valid. CT: {ct}, Preview: {preview[:200]}",
                                url=wb_url)
            elif status == 429:
                log(f"  Rate limited (429) - try again later", "WARN")
                save_result(test_name, False,
                            details="Rate limited (429). The approach works but needs rate limiting.",
                            url=wb_url)
            else:
                log(f"  Status {status}", "FAIL")
                save_result(test_name, False, details=f"Status {status}", url=wb_url)

        except Exception as e:
            log(f"  ERROR: {e}", "FAIL")
            save_result(test_name, False, details=str(e), url=wb_url)

        time.sleep(2)  # Be respectful of WB rate limits


# ============================================================================
# APPROACH 11: Playwright with stealth + PerimeterX challenge wait
# ============================================================================

def test_playwright_stealth():
    """Use Playwright with extra stealth measures and wait for PX challenge."""
    log("=" * 70)
    log("APPROACH 11: Playwright stealth + PX challenge wait")
    log("=" * 70)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed, skipping", "FAIL")
        save_result("Playwright stealth", False, details="playwright not installed")
        return

    test_name = "Playwright stealth with PX wait"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                permissions=["geolocation"],
            )
            # Comprehensive stealth
            context.add_init_script("""
                // Override webdriver
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                // Override platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'MacIntel',
                });
                // Chrome runtime
                window.chrome = { runtime: {} };
                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : originalQuery(parameters);
            """)

            page = context.new_page()

            # Navigate to the mapsapi URL directly with full stealth
            map_url = f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true"
            log(f"  Navigating to mapsapi.tmol.io with stealth browser...")

            intercepted_data = {}

            def on_response(response):
                if "mapsapi" in response.url and response.status == 200:
                    try:
                        body = response.body()
                        if body and (b"<svg" in body.lower() or is_valid_image(body)):
                            intercepted_data["svg"] = body
                            intercepted_data["url"] = response.url
                    except:
                        pass

            page.on("response", on_response)

            try:
                resp = page.goto(map_url, wait_until="load", timeout=30000)
                status = resp.status if resp else 0
                log(f"  Initial status: {status}")

                if status == 403:
                    # Wait for PX challenge to potentially resolve
                    log("  Got 403, waiting 10s for PX challenge to solve...")
                    page.wait_for_timeout(10000)

                    # Check if page has changed
                    content = page.content()
                    if "<svg" in content.lower():
                        log("  SVG appeared after PX wait!", "OK")
                        # Extract SVG
                        svg_html = page.evaluate("document.querySelector('svg')?.outerHTML || ''")
                        if svg_html:
                            save_result(test_name, True, svg_html,
                                        f"SVG extracted after PX challenge wait, {len(svg_html)} chars",
                                        map_url)
                    elif intercepted_data.get("svg"):
                        log("  SVG intercepted from redirect!", "OK")
                        data = intercepted_data["svg"]
                        save_result(test_name, True,
                                    data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else data,
                                    f"SVG intercepted, {len(data)} bytes",
                                    intercepted_data.get("url", map_url))
                    else:
                        log("  Still blocked after PX wait", "FAIL")
                        save_result(test_name, False,
                                    details="Still 403 after waiting for PX challenge",
                                    url=map_url)
                elif status == 200:
                    body = resp.body()
                    img_type = is_valid_image(body)
                    if img_type:
                        log(f"  Direct success! {img_type} ({len(body)} bytes)", "OK")
                        save_result(test_name, True,
                                    body.decode("utf-8", errors="ignore") if img_type == "svg" else body,
                                    f"Direct stealth success, {len(body)} bytes", map_url)
                    else:
                        save_result(test_name, False,
                                    details=f"200 but not valid image data", url=map_url)

            except Exception as e:
                log(f"  Navigation error: {e}", "FAIL")
                save_result(test_name, False, details=str(e), url=map_url)

            browser.close()

    except Exception as e:
        log(f"  Error: {e}", "FAIL")
        save_result(test_name, False, details=str(e))


# ============================================================================
# APPROACH 12: TM EU/International Discovery API
# ============================================================================

def test_eu_discovery_api():
    """Try TM EU/International endpoints (different infrastructure, may not have PX)."""
    log("=" * 70)
    log("APPROACH 12: TM EU/International Discovery API endpoints")
    log("=" * 70)

    endpoints = [
        {
            "name": "EU Discovery API seatmap",
            "url": f"https://app.ticketmaster.eu/mfxapi/v2/events/{EVENT_ID}/seatmap?apikey=VG2itGca1oKr6AZjkPxFmXNHwTb5EY8J",
        },
        {
            "name": "TM API Explorer (different domain)",
            "url": f"https://app.ticketmaster.com/discovery/v2/events.json?keyword={EVENT_ID}&apikey=GkB8Z037ZfqbLCNtZViAgrEegbsrZ6Ne",
        },
    ]

    for ep in endpoints:
        test_name = f"EU API: {ep['name']}"
        try:
            resp = requests.get(ep["url"], headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Accept": "application/json,image/*,*/*",
            }, timeout=15)
            status = resp.status_code
            ct = resp.headers.get("Content-Type", "")

            if status == 200:
                # Check if it's an image
                img_type = is_valid_image(resp.content)
                if img_type:
                    log(f"  {ep['name']}: Got {img_type}! ({len(resp.content)} bytes)", "OK")
                    save_result(test_name, True,
                                resp.content if img_type != "svg" else resp.text,
                                f"{img_type}, {len(resp.content)} bytes", ep["url"])
                elif "json" in ct:
                    data = resp.json()
                    log(f"  {ep['name']}: JSON response, keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
                    # Look for map URLs in JSON
                    json_str = json.dumps(data)
                    map_urls = re.findall(r'https?://[^"]+(?:map|seatmap|geometry|staticImage)[^"]*', json_str, re.IGNORECASE)
                    static_urls = re.findall(r'"staticUrl"\s*:\s*"([^"]+)"', json_str)
                    if static_urls:
                        for su in static_urls:
                            log(f"  Found staticUrl: {su}", "OK")
                            # Try fetching it
                            try:
                                sr = requests.get(su, headers=BROWSER_HEADERS, timeout=10)
                                if sr.status_code == 200 and is_valid_image(sr.content):
                                    img_t = is_valid_image(sr.content)
                                    save_result(f"EU API staticUrl fetch", True,
                                                sr.content if img_t != "svg" else sr.text,
                                                f"From EU API staticUrl, {len(sr.content)} bytes", su)
                            except:
                                pass
                    elif map_urls:
                        for mu in map_urls[:3]:
                            log(f"  Found map URL: {mu}")
                    save_result(test_name, bool(static_urls or map_urls),
                                details=f"JSON response. staticUrls: {len(static_urls)}, mapUrls: {len(map_urls)}",
                                url=ep["url"])
                else:
                    log(f"  {ep['name']}: {status}, CT: {ct}, size: {len(resp.content)}", "WARN")
                    save_result(test_name, False,
                                details=f"200 but CT: {ct}, size: {len(resp.content)}", url=ep["url"])
            else:
                log(f"  {ep['name']}: {status}", "FAIL")
                save_result(test_name, False, details=f"Status {status}", url=ep["url"])

        except Exception as e:
            log(f"  {ep['name']}: ERROR - {e}", "FAIL")
            save_result(test_name, False, details=str(e), url=ep["url"])

        time.sleep(0.5)


# ============================================================================
# APPROACH 13: Google Cache / Web Archive for the SVG
# ============================================================================

def test_google_cache():
    """Try fetching a cached version of the map from Google Cache or Wayback Machine."""
    log("=" * 70)
    log("APPROACH 13: Web Archive / Cached versions")
    log("=" * 70)

    map_url = f"https://mapsapi.tmol.io/maps/geometry/3/event/{EVENT_ID}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true"

    endpoints = [
        {
            "name": "Wayback Machine CDX check",
            "url": f"http://web.archive.org/cdx/search/cdx?url=mapsapi.tmol.io/maps/geometry/*&output=json&limit=5",
        },
        {
            "name": "Wayback Machine direct",
            "url": f"https://web.archive.org/web/2024/{map_url}",
        },
    ]

    for ep in endpoints:
        test_name = f"Cache: {ep['name']}"
        try:
            resp = requests.get(ep["url"], headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
            }, timeout=15, allow_redirects=True)
            status = resp.status_code
            ct = resp.headers.get("Content-Type", "")

            if status == 200:
                if "json" in ct:
                    try:
                        data = resp.json()
                        if data and len(data) > 1:
                            log(f"  {ep['name']}: Found {len(data)-1} archived snapshots", "OK")
                            for entry in data[1:min(4, len(data))]:
                                log(f"    Archived: {entry}")
                            save_result(test_name, True, None,
                                        details=f"Found {len(data)-1} archived snapshots of tmol.io maps",
                                        url=ep["url"])
                        else:
                            log(f"  {ep['name']}: No archived snapshots found")
                            save_result(test_name, False, details="No snapshots", url=ep["url"])
                    except:
                        log(f"  {ep['name']}: Could not parse JSON response")
                        save_result(test_name, False, details="Invalid JSON", url=ep["url"])
                else:
                    img_type = is_valid_image(resp.content)
                    if img_type:
                        log(f"  {ep['name']}: Got cached {img_type}! ({len(resp.content)} bytes)", "OK")
                        save_result(test_name, True,
                                    resp.content if img_type != "svg" else resp.text,
                                    f"Cached {img_type}, {len(resp.content)} bytes", ep["url"])
                    else:
                        log(f"  {ep['name']}: 200 but not image (CT: {ct}, size: {len(resp.content)})")
                        save_result(test_name, False,
                                    details=f"200 but CT: {ct}", url=ep["url"])
            else:
                log(f"  {ep['name']}: {status}", "FAIL")
                save_result(test_name, False, details=f"Status {status}", url=ep["url"])

        except Exception as e:
            log(f"  {ep['name']}: ERROR - {e}", "FAIL")
            save_result(test_name, False, details=str(e), url=ep["url"])

        time.sleep(0.5)


if __name__ == "__main__":
    main()

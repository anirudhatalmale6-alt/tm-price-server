async function test() {
  const eventId = '16006367E975D3A9';
  const mapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${eventId}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;

  // Test: exact same Wayback URL as in the server code
  console.log('Testing Wayback with exact server code approach...');
  const wbResp = await fetch(`https://web.archive.org/web/0id_/${mapUrl}`, {
    headers: { 'Accept-Encoding': 'gzip, deflate, br' },
    redirect: 'follow',
    // Note: timeout option is not standard fetch, needs AbortController
  });

  console.log('Status:', wbResp.status);
  console.log('Content-Type:', wbResp.headers.get('content-type'));

  const svg = await wbResp.text();
  console.log('Length:', svg.length);
  console.log('Has <svg>:', svg.includes('<svg'));
  console.log('First 200 chars:', svg.substring(0, 200));

  // The SVG map has sections with IDs - check if they're clickable
  const sectionIds = svg.match(/id="(\d+)"/g);
  console.log('Section IDs found:', sectionIds?.length || 0);
  if (sectionIds) console.log('Sample IDs:', sectionIds.slice(0, 10).map(s => s.match(/\d+/)[0]));

  // Try fetching map for the other events via Wayback with different timestamp formats
  console.log('\n--- Other events with different WB timestamp formats ---');
  const events = ['0E006457911B7175', '1E006372CA2D9BE3'];
  const wbFormats = [
    (url) => `https://web.archive.org/web/0id_/${url}`,
    (url) => `https://web.archive.org/web/2id_/${url}`,
    (url) => `https://web.archive.org/web/${url}`,
  ];

  for (const eid of events) {
    const mUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${eid}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;
    for (const fmt of wbFormats) {
      const testUrl = fmt(mUrl);
      try {
        const resp = await fetch(testUrl, { redirect: 'follow' });
        if (resp.ok) {
          const body = await resp.text();
          console.log(`${eid} [${testUrl.split('/web/')[1].substring(0, 5)}]: ${resp.status} len=${body.length} svg=${body.includes('<svg')}`);
          if (body.includes('<svg')) break;
        } else {
          console.log(`${eid} [${testUrl.split('/web/')[1].substring(0, 5)}]: ${resp.status}`);
        }
      } catch (e) {
        console.log(`${eid} error: ${e.message}`);
      }
    }
  }

  // Can we generate an SVG from the section data?
  // PhantomChecker stock data has sectionId's that match the SVG path IDs
  // If we can't get SVG, we could build a more useful generated view
  console.log('\n--- Alternative: Build venue map from TM seatmap API ---');
  // Try the seatmap static image from TM's CDN (different from SVG)
  const seatmapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${eventId}/staticImage?type=png&systemId=HOST&sectionLevel=true`;
  try {
    // Through Wayback
    const resp = await fetch(`https://web.archive.org/web/0id_/${seatmapUrl}`, { redirect: 'follow' });
    console.log('PNG via Wayback:', resp.status, resp.headers.get('content-type'));
  } catch (e) {
    console.log('PNG error:', e.message);
  }
}

test().catch(e => console.error(e));

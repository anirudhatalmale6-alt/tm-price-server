async function test() {
  const testEventId = '010063680247AA20';

  // Try Wayback Machine
  const mapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${testEventId}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;

  console.log('--- Wayback Machine ---');
  try {
    const wbResp = await fetch(`https://web.archive.org/web/0id_/${mapUrl}`, {
      headers: { 'Accept-Encoding': 'gzip, deflate, br' },
      redirect: 'follow'
    });
    console.log('WB status:', wbResp.status);
    if (wbResp.ok) {
      const body = await wbResp.text();
      console.log('WB body length:', body.length, 'Is SVG:', body.includes('<svg'));
      if (body.includes('<svg')) console.log('SVG preview:', body.substring(0, 200));
    }
  } catch (e) {
    console.log('WB error:', e.message);
  }

  // Try TM Discovery API for venue info
  console.log('\n--- TM Discovery API ---');
  try {
    const discoveryUrl = `https://app.ticketmaster.com/discovery/v2/events/${testEventId}?apikey=ceBFZOQaA2G5GPuHUucz5eFiAmsaOlRa`;
    const resp = await fetch(discoveryUrl);
    console.log('Discovery status:', resp.status);
    if (resp.ok) {
      const data = await resp.json();
      const venue = data._embedded?.venues?.[0];
      console.log('Venue:', venue?.name, venue?.id);
      // Check for seatmap
      if (data.seatmap) console.log('Seatmap:', data.seatmap);
      if (venue?.seatmap) console.log('Venue seatmap:', venue.seatmap);
    }
  } catch (e) {
    console.log('Discovery error:', e.message);
  }

  // Try different TM map URL patterns
  console.log('\n--- Alt map URL patterns ---');
  const altUrls = [
    `https://maps.ticketmaster.com/maps/geometry/3/event/${testEventId}/staticImage?type=svg`,
    `https://content.ticketmaster.com/maps/${testEventId}.svg`,
    `https://mapsapi.tmol.io/maps/geometry/3/event/${testEventId}/staticImage?type=png&systemId=HOST`,
  ];

  for (const url of altUrls) {
    try {
      const resp = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'https://www.ticketmaster.com/'
        }
      });
      const ct = resp.headers.get('content-type');
      console.log(`${url.substring(0, 80)}... => ${resp.status} (${ct})`);
    } catch (e) {
      console.log(`${url.substring(0, 60)}... => ERROR: ${e.message}`);
    }
  }

  // Try fetching venue seatmap directly
  console.log('\n--- Seatmap static URLs ---');
  try {
    // TM Seatmap API
    const seatmapUrl = `https://app.ticketmaster.com/discovery/v2/events/${testEventId}?apikey=ceBFZOQaA2G5GPuHUucz5eFiAmsaOlRa&locale=en-us`;
    const resp = await fetch(seatmapUrl);
    if (resp.ok) {
      const data = await resp.json();
      if (data.seatmap?.staticUrl) {
        console.log('Seatmap staticUrl:', data.seatmap.staticUrl);
        // Fetch the static seatmap image
        const imgResp = await fetch(data.seatmap.staticUrl);
        console.log('Seatmap image:', imgResp.status, imgResp.headers.get('content-type'));
      }
    }
  } catch (e) {
    console.log('Seatmap error:', e.message);
  }
}

test().catch(e => console.error(e));

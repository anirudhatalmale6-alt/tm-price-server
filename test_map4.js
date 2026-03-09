async function test() {
  // Use the actual active events from the server
  const eventIds = ['16006367E975D3A9', '0E006457911B7175', '1E006372CA2D9BE3'];

  for (const eventId of eventIds) {
    console.log(`\n=== Event: ${eventId} ===`);

    // Try Wayback Machine
    const mapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${eventId}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;
    try {
      const wbResp = await fetch(`https://web.archive.org/web/0id_/${mapUrl}`, {
        redirect: 'follow'
      });
      console.log('Wayback:', wbResp.status);
      if (wbResp.ok) {
        const body = await wbResp.text();
        console.log('  Length:', body.length, 'Is SVG:', body.includes('<svg'));
      }
    } catch (e) {
      console.log('Wayback error:', e.message);
    }

    // Try TM Discovery API with multiple keys
    const apiKeys = ['b462oi7fic6pehcdkzony5bxhe', 'Qat71kEJtEOIFQOc1imeIblT4wSf1gkr'];
    for (const key of apiKeys) {
      try {
        const resp = await fetch(`https://app.ticketmaster.com/discovery/v2/events/${eventId}?apikey=${key}&locale=en-us`);
        console.log(`Discovery (${key.substring(0,8)}):`, resp.status);
        if (resp.ok) {
          const data = await resp.json();
          console.log('  Name:', data.name);
          if (data.seatmap?.staticUrl) {
            console.log('  Seatmap URL:', data.seatmap.staticUrl);
            // Fetch seatmap image
            const imgResp = await fetch(data.seatmap.staticUrl);
            console.log('  Seatmap fetch:', imgResp.status, imgResp.headers.get('content-type'));
          }
          const venue = data._embedded?.venues?.[0];
          if (venue) console.log('  Venue:', venue.name, '| ID:', venue.id);
        }
      } catch (e) {
        console.log(`Discovery error: ${e.message}`);
      }
    }

    // Try PhantomChecker stock to get section data
    const FIREBASE_API_KEY = 'AIzaSyDrD5U6PJ5WhCBmrtTaQzAe1dteO103ux0';
    const PC_API = 'https://api.phantomcheckerapi.com/api/v1';
    const loginResp = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'remote@nickets.com', password: 'rWvXirgpVy4uEhZ', returnSecureToken: true })
    });
    const { idToken: token } = await loginResp.json();

    const stockResp = await fetch(`${PC_API}/sites/ticketmaster/stock-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({ eventId })
    });
    if (stockResp.ok) {
      const stockData = await stockResp.json();
      const sections = stockData.sectionStock || [];
      console.log('  PC Stock sections:', sections.length);
      if (sections.length > 0) {
        console.log('  First section:', JSON.stringify(sections[0]).substring(0, 300));
      }
    } else {
      console.log('  PC Stock:', stockResp.status, await stockResp.text().then(t => t.substring(0, 200)));
    }
  }
}

test().catch(e => console.error(e));

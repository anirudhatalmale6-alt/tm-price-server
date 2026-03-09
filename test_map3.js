async function test() {
  // Try TM Discovery with different API keys (public keys commonly used)
  const apiKeys = [
    'ceBFZOQaA2G5GPuHUucz5eFiAmsaOlRa',
    'Qat71kEJtEOIFQOc1imeIblT4wSf1gkr',
    'cDu7Z7HUJ5yBs2aBkBh8DkMX7KKNHBZ2',
  ];

  // Use a known valid event - let's try a more recent one
  // The client's admin showed an event - let me try fetching from the live server
  console.log('--- Checking live server for events ---');
  try {
    const resp = await fetch('https://tm-price-server.onrender.com/api/events');
    const events = await resp.json();
    console.log('Active events:', events);
  } catch (e) {
    console.log('Server error:', e.message);
  }

  // Try TM's internal API that the seat selection page uses
  // When you go to buy tickets, TM loads the map from a different endpoint
  console.log('\n--- TM Inventory API (seat selection) ---');
  const testEventId = '010063680247AA20';

  // The TM seat selection page fetches from this API
  const inventoryUrl = `https://offeradapter.ticketmaster.com/api/ismds/event/${testEventId}/facets?by=inventorytypes+available+shape+section+zone+places+offertype&show=places&q=available%20--%3E%20true&compress&apikey=b462oi7fic6pehcdkzony5bxhe&apts=1740000000&sid=host`;

  try {
    const resp = await fetch(inventoryUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.ticketmaster.com/',
        'Origin': 'https://www.ticketmaster.com'
      }
    });
    console.log('Inventory API:', resp.status, resp.headers.get('content-type'));
    if (resp.ok) {
      const data = await resp.json();
      console.log('Keys:', Object.keys(data));
      // Check if it has map data
      if (data.seatMapUrl) console.log('seatMapUrl:', data.seatMapUrl);
      if (data.mapUrl) console.log('mapUrl:', data.mapUrl);
    }
  } catch (e) {
    console.log('Inventory error:', e.message);
  }

  // Try TM's static seatmap CDN
  console.log('\n--- TM Static CDN ---');
  const cdnUrls = [
    `https://s1.ticketm.net/tm/en-us/img/seatmaps/${testEventId}.svg`,
    `https://s1.ticketm.net/tm/en-us/img/seatmap/${testEventId}.svg`,
    `https://media.ticketmaster.com/tm/en-us/dbimages/seatmap/${testEventId}.png`,
  ];

  for (const url of cdnUrls) {
    try {
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0' }
      });
      console.log(`${url.substring(url.lastIndexOf('/') + 1)} => ${resp.status} (${resp.headers.get('content-type')})`);
    } catch (e) {
      console.log(`CDN error: ${e.message}`);
    }
  }

  // PhantomChecker might have a different endpoint for maps
  console.log('\n--- PhantomChecker endpoints exploration ---');
  const FIREBASE_API_KEY = 'AIzaSyDrD5U6PJ5WhCBmrtTaQzAe1dteO103ux0';
  const PC_API = 'https://api.phantomcheckerapi.com/api/v1';

  const loginResp = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'remote@nickets.com', password: 'rWvXirgpVy4uEhZ', returnSecureToken: true })
  });
  const loginData = await loginResp.json();
  const token = loginData.idToken;

  // Try stock-info to see if it includes map data
  const stockResp = await fetch(`${PC_API}/sites/ticketmaster/stock-info`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
    body: JSON.stringify({ eventId: testEventId })
  });
  if (stockResp.ok) {
    const stockData = await stockResp.json();
    console.log('Stock top-level keys:', Object.keys(stockData));
    if (stockData.mapUrl) console.log('mapUrl in stock:', stockData.mapUrl);
    if (stockData.seatmapUrl) console.log('seatmapUrl in stock:', stockData.seatmapUrl);
    // Check first section for shape/geometry data
    const firstSec = stockData.sectionStock?.[0];
    if (firstSec) {
      console.log('First section keys:', Object.keys(firstSec));
    }
  } else {
    console.log('Stock failed:', stockResp.status);
  }

  // Try PhantomChecker event-details endpoint
  const endpoints = [
    { url: `${PC_API}/sites/ticketmaster/event-details`, method: 'POST', body: { eventId: testEventId } },
    { url: `${PC_API}/sites/ticketmaster/venue-map`, method: 'POST', body: { eventId: testEventId } },
    { url: `${PC_API}/sites/ticketmaster/map/${testEventId}`, method: 'GET' },
  ];

  for (const ep of endpoints) {
    try {
      const opts = { method: ep.method, headers: { 'Authorization': 'Bearer ' + token } };
      if (ep.body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(ep.body);
      }
      const resp = await fetch(ep.url, opts);
      console.log(`${ep.url.replace(PC_API, 'PC')} => ${resp.status}`);
      if (resp.ok) {
        const text = await resp.text();
        console.log('  Length:', text.length, 'Preview:', text.substring(0, 200));
      }
    } catch (e) {
      console.log(`${ep.url.replace(PC_API, 'PC')} => ERROR: ${e.message}`);
    }
  }
}

test().catch(e => console.error(e));

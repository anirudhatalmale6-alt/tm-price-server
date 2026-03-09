const PC_API = 'https://api.phantomcheckerapi.com/api/v1';
const FIREBASE_API_KEY = 'AIzaSyDrD5U6PJ5WhCBmrtTaQzAe1dteO103ux0';

async function test() {
  // Login to PhantomChecker
  const loginResp = await fetch('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + FIREBASE_API_KEY, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'remote@nickets.com', password: 'rWvXirgpVy4uEhZ', returnSecureToken: true })
  });
  const loginData = await loginResp.json();
  if (!loginData.idToken) { console.log('Login failed:', loginData); return; }
  console.log('Login OK');

  const token = loginData.idToken;
  const testEventId = '010063680247AA20';

  // Try map-image endpoint
  const mapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${testEventId}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;
  console.log('Trying map-image endpoint...');
  const mapResp = await fetch(`${PC_API}/sites/ticketmaster/map-image?query=${encodeURIComponent(mapUrl)}`, {
    method: 'GET',
    headers: { 'Authorization': 'Bearer ' + token }
  });
  console.log('Map status:', mapResp.status);
  if (mapResp.ok) {
    const b64 = await mapResp.text();
    console.log('Map response length:', b64.length);
    console.log('Map response preview:', b64.substring(0, 200));
    // Try decode
    const decoded = Buffer.from(b64.replace(/^"|"$/g, ''), 'base64').toString('utf8');
    console.log('Decoded length:', decoded.length);
    console.log('Is SVG:', decoded.includes('<svg'));
    console.log('Decoded preview:', decoded.substring(0, 300));
  } else {
    console.log('Map error:', await mapResp.text());
  }

  // Also try direct TM map fetch with various approaches
  console.log('\n--- Direct TM fetch attempts ---');

  // Attempt 1: Direct fetch
  try {
    const directResp = await fetch(mapUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'image/svg+xml,image/*,*/*',
        'Referer': 'https://www.ticketmaster.com/',
      }
    });
    console.log('Direct TM:', directResp.status, directResp.headers.get('content-type'));
    if (directResp.ok) {
      const body = await directResp.text();
      console.log('Body length:', body.length, 'Is SVG:', body.includes('<svg'));
    }
  } catch (e) {
    console.log('Direct TM error:', e.message);
  }

  // Attempt 2: Try the interactive map URL format
  try {
    const interactiveUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${testEventId}/staticImage?type=svg&systemId=HOST`;
    const resp2 = await fetch(interactiveUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
      }
    });
    console.log('Interactive TM:', resp2.status);
  } catch (e) {
    console.log('Interactive error:', e.message);
  }
}

test().catch(e => console.error(e));

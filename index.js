const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const app = express();

app.use(cors());
app.use(express.json({ limit: '5mb' }));

// Serve static admin panel
app.use('/admin', express.static(path.join(__dirname, 'public')));

// Persistent file-based store
const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
const STORE_FILE = path.join(DATA_DIR, 'rules.json');

// In-memory store backed by file
const store = new Map();

// Load from disk on startup
function loadStore() {
  try {
    if (fs.existsSync(STORE_FILE)) {
      const data = JSON.parse(fs.readFileSync(STORE_FILE, 'utf8'));
      for (const [key, val] of Object.entries(data)) {
        store.set(key, val);
      }
      console.log(`[LOAD] Restored ${store.size} events from disk`);
    }
  } catch (e) {
    console.log('[LOAD] Could not load store:', e.message);
  }
}

// Save to disk
function saveStore() {
  try {
    const obj = {};
    store.forEach((val, key) => { obj[key] = val; });
    fs.writeFileSync(STORE_FILE, JSON.stringify(obj, null, 2));
  } catch (e) {
    console.log('[SAVE] Could not persist store:', e.message);
  }
}

loadStore();

// Redirect root to admin panel
app.get('/', (req, res) => {
  res.redirect('/admin');
});

// Proxy endpoint for fetching Broker Buds reports (avoids CORS)
app.get('/api/proxy', async (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).json({ error: 'url parameter required' });

  try {
    const resp = await fetch(url);
    if (!resp.ok) return res.status(resp.status).json({ error: 'Upstream returned ' + resp.status });
    const html = await resp.text();
    res.type('text/html').send(html);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Save rules for an event (Admin panel / extension)
app.post('/api/rules/:eventId', (req, res) => {
  const { eventId } = req.params;
  const { rules } = req.body;

  if (!Array.isArray(rules)) {
    return res.status(400).json({ error: 'rules must be an array' });
  }

  store.set(eventId, {
    rules,
    updatedAt: Date.now()
  });

  saveStore();
  console.log(`[SAVE] Event ${eventId}: ${rules.length} rules`);
  res.json({ success: true, eventId, ruleCount: rules.length });
});

// Get rules for an event (VA extension)
app.get('/api/rules/:eventId', (req, res) => {
  const { eventId } = req.params;
  const data = store.get(eventId);

  if (!data) {
    return res.json({ rules: [], updatedAt: null });
  }

  res.json(data);
});

// Delete rules for an event
app.delete('/api/rules/:eventId', (req, res) => {
  const { eventId } = req.params;
  store.delete(eventId);
  saveStore();
  res.json({ success: true });
});

// List all events with rules
app.get('/api/events', (req, res) => {
  const events = [];
  store.forEach((data, eventId) => {
    events.push({ eventId, ruleCount: data.rules.length, updatedAt: data.updatedAt });
  });
  res.json(events);
});

// Image proxy for venue maps (avoids CORS, sends browser-like headers)
app.get('/api/map-proxy', async (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).json({ error: 'url parameter required' });

  try {
    const resp = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.ticketmaster.com/',
        'Origin': 'https://www.ticketmaster.com'
      }
    });
    if (!resp.ok) return res.status(resp.status).end();
    const contentType = resp.headers.get('content-type') || 'image/png';
    res.type(contentType);
    const buffer = await resp.arrayBuffer();
    res.send(Buffer.from(buffer));
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ============ PHANTOMCHECKER INTEGRATION ============
const PC_API = 'https://api.phantomcheckerapi.com/api/v1';
const FIREBASE_API_KEY = 'AIzaSyDrD5U6PJ5WhCBmrtTaQzAe1dteO103ux0';
const PC_EMAIL = 'remote@nickets.com';
const PC_PASSWORD = 'rWvXirgpVy4uEhZ';

let pcToken = null;
let pcTokenExpiry = 0;
let pcRefreshToken = null;

async function getPCToken() {
  // Return cached token if still valid (with 5min buffer)
  if (pcToken && Date.now() < pcTokenExpiry - 300000) return pcToken;

  // Try refresh first
  if (pcRefreshToken) {
    try {
      const resp = await fetch(`https://securetoken.googleapis.com/v1/token?key=${FIREBASE_API_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ grant_type: 'refresh_token', refresh_token: pcRefreshToken })
      });
      if (resp.ok) {
        const data = await resp.json();
        pcToken = data.id_token;
        pcRefreshToken = data.refresh_token;
        pcTokenExpiry = Date.now() + parseInt(data.expires_in) * 1000;
        console.log('[PC] Token refreshed');
        return pcToken;
      }
    } catch (e) { /* fall through to full login */ }
  }

  // Full login
  try {
    const resp = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: PC_EMAIL, password: PC_PASSWORD, returnSecureToken: true })
    });
    if (!resp.ok) throw new Error('Firebase login failed: ' + resp.status);
    const data = await resp.json();
    pcToken = data.idToken;
    pcRefreshToken = data.refreshToken;
    pcTokenExpiry = Date.now() + parseInt(data.expiresIn) * 1000;
    console.log('[PC] Logged in successfully');
    return pcToken;
  } catch (e) {
    console.log('[PC] Login error:', e.message);
    throw e;
  }
}

// Helper: call PC API with auto-retry on 401
async function pcApiCall(url, options = {}) {
  let token = await getPCToken();
  let resp = await fetch(url, {
    ...options,
    headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
  });
  // If 401, force re-login and retry once
  if (resp.status === 401) {
    pcToken = null; pcTokenExpiry = 0; pcRefreshToken = null;
    token = await getPCToken();
    resp = await fetch(url, {
      ...options,
      headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
    });
  }
  return resp;
}

// Get live stock data for a TM event
app.get('/api/stock/:eventId', async (req, res) => {
  const { eventId } = req.params;
  try {
    const resp = await pcApiCall(`${PC_API}/sites/ticketmaster/stock-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eventId })
    });
    if (!resp.ok) throw new Error('PC API returned ' + resp.status);
    const data = await resp.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Get live stock data directly from TM API (real prices)
const TM_API_KEY = 'b462oi7fic6pehcdkzony5bxhe';
const TM_API_SECRET = 'pquzpfrfz7zd2ylvtz3w5dtyse';

app.get('/api/tm-stock/:eventId', async (req, res) => {
  const { eventId } = req.params;
  const siteType = req.query.site || 'ticketmaster';
  try {
    const facetsUrl = `https://services.${siteType}.com/api/ismds/event/${eventId}/facets?show=count+row+listpricerange+places+maxQuantity+sections+shape&q=available&apikey=${TM_API_KEY}&apisecret=${TM_API_SECRET}&resaleChannelId=internal.ecommerce.consumer.desktop.web.browser.${siteType}.us`;
    const typesUrl = `https://services.${siteType}.com/api/ismds/host/${eventId}/tickettypes?apikey=${TM_API_KEY}&apisecret=${TM_API_SECRET}`;

    const [facetsResp, typesResp] = await Promise.all([
      fetch(facetsUrl, { headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' } }),
      fetch(typesUrl, { headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' } })
    ]);

    if (!facetsResp.ok) throw new Error('TM facets API returned ' + facetsResp.status);
    const facetsData = await facetsResp.json();
    const typesData = typesResp.ok ? await typesResp.json() : null;

    // Transform to same format as PhantomChecker for admin compatibility
    const sectionStock = {};
    const inventory = [];

    if (facetsData.facets) {
      for (const ticket of facetsData.facets) {
        if (!ticket.available) continue;

        let ticketType = 'Standard';
        if (typesData && typesData._embedded) {
          try {
            const td = typesData._embedded.item.find(i => i.ticketTypeId === ticket.ticketTypes[0]);
            if (td) {
              const name = td.name;
              if (name.toLowerCase().includes('resale') || (ticket.inventoryTypes && ticket.inventoryTypes[0] !== 'primary')) {
                ticketType = 'Resale';
              } else if (name.toLowerCase().includes('platinum')) {
                ticketType = 'Official Platinum';
              } else {
                ticketType = name;
              }
            }
          } catch(e) {}
        }

        const section = ticket.section || 'Unknown';
        const price = ticket.listPriceRange && ticket.listPriceRange.length ? ticket.listPriceRange[0].min : 0;
        const count = ticket.count || 0;
        const rows = ticket.row || [];

        // Add to inventory (for the table)
        inventory.push({
          section,
          price,
          count,
          rows,
          type: ticketType,
          offer: ticketType
        });

        // Aggregate section stock (for map/filtered sections)
        if (!sectionStock[section]) {
          sectionStock[section] = { sectionName: section, minPrice: price, maxPrice: price, totalAvail: 0, offers: [] };
        }
        const ss = sectionStock[section];
        ss.minPrice = Math.min(ss.minPrice, price);
        ss.maxPrice = Math.max(ss.maxPrice, price);
        ss.totalAvail += count;
        if (!ss.offers.find(o => o.offerType === ticketType)) {
          ss.offers.push({ offerType: ticketType, minPrice: price, maxPrice: price, available: count });
        } else {
          const existing = ss.offers.find(o => o.offerType === ticketType);
          existing.minPrice = Math.min(existing.minPrice, price);
          existing.maxPrice = Math.max(existing.maxPrice, price);
          existing.available += count;
        }
      }
    }

    res.json({
      source: 'tm-direct',
      sectionStock: Object.values(sectionStock),
      inventory,
      totalSections: Object.keys(sectionStock).length,
      totalTickets: inventory.reduce((s, i) => s + i.count, 0)
    });
  } catch (e) {
    console.log('[TM-STOCK] Error:', e.message);
    res.status(500).json({ error: e.message });
  }
});

// SVG map cache (in-memory, keyed by eventId)
const mapCache = new Map();

// Helper: extract raw SVG from potentially HTML-wrapped Wayback response
function extractSvg(text) {
  if (!text || !text.includes('<svg')) return null;
  // If it starts with <?xml or <svg, it's already raw SVG
  if (text.trimStart().startsWith('<?xml') || text.trimStart().startsWith('<svg')) {
    return text;
  }
  // Otherwise extract SVG from HTML wrapper
  const svgStart = text.indexOf('<svg');
  const svgEnd = text.lastIndexOf('</svg>');
  if (svgStart >= 0 && svgEnd > svgStart) {
    return text.substring(svgStart, svgEnd + 6);
  }
  return null;
}

// Get venue SVG map for a TM event
// Strategy: 1) Wayback Machine (multiple URL formats)  2) PhantomChecker  3) 404 (frontend generates chart)
app.get('/api/map/:eventId', async (req, res) => {
  const { eventId } = req.params;

  // Check cache first
  if (mapCache.has(eventId)) {
    console.log(`[MAP] Cache hit for ${eventId}`);
    return res.type('image/svg+xml').send(mapCache.get(eventId));
  }

  const mapUrl = `https://mapsapi.tmol.io/maps/geometry/3/event/${eventId}/staticImage?type=svg&systemId=HOST&sectionLevel=true&avertaFonts=true`;

  // Strategy 1: Wayback Machine proxy (bypasses PerimeterX)
  // Try multiple URL formats — 0id_ returns raw file, plain URL returns latest cached version
  const wbUrls = [
    `https://web.archive.org/web/0id_/${mapUrl}`,
    `https://web.archive.org/web/${mapUrl}`,
    `https://web.archive.org/web/2id_/${mapUrl}`,
  ];

  for (const wbUrl of wbUrls) {
    try {
      const label = wbUrl.includes('0id_') ? '0id_' : wbUrl.includes('2id_') ? '2id_' : 'plain';
      console.log(`[MAP] Trying Wayback (${label}) for ${eventId}...`);
      const wbResp = await fetch(wbUrl, {
        headers: { 'Accept-Encoding': 'gzip, deflate, br' },
        redirect: 'follow'
      });
      if (wbResp.ok) {
        const text = await wbResp.text();
        const svg = extractSvg(text);
        if (svg && svg.length > 1000) {
          mapCache.set(eventId, svg);
          console.log(`[MAP] Wayback (${label}) hit for ${eventId} (${svg.length} chars)`);
          return res.type('image/svg+xml').send(svg);
        }
      }
      console.log(`[MAP] Wayback (${label}) miss for ${eventId} (${wbResp.status})`);
    } catch (e) {
      console.log(`[MAP] Wayback error: ${e.message}`);
    }
  }

  // Strategy 2: PhantomChecker proxy (often broken, but try)
  try {
    console.log(`[MAP] Trying PhantomChecker for ${eventId}...`);
    const resp = await pcApiCall(`${PC_API}/sites/ticketmaster/map-image?query=${encodeURIComponent(mapUrl)}`, {
      method: 'GET'
    });
    if (resp.ok) {
      const b64 = await resp.text();
      if (b64 && b64.length > 10) {
        const decoded = Buffer.from(b64.replace(/^"|"$/g, ''), 'base64').toString('utf8');
        const svg = extractSvg(decoded);
        if (svg && svg.length > 1000) {
          mapCache.set(eventId, svg);
          console.log(`[MAP] PC hit for ${eventId} (${svg.length} chars)`);
          return res.type('image/svg+xml').send(svg);
        }
      }
      console.log(`[MAP] PC returned invalid data for ${eventId}`);
    }
  } catch (e) {
    console.log(`[MAP] PC error: ${e.message}`);
  }

  // No SVG available - return 404 so frontend uses generated chart
  console.log(`[MAP] No SVG available for ${eventId}`);
  res.status(404).json({ error: 'Map not available', fallback: 'generated' });
});

// Pre-warm PC token on startup
getPCToken().catch(() => {});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`TM Price Server running on port ${PORT}`);
  console.log(`Admin panel: http://localhost:${PORT}/admin`);
});

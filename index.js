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

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`TM Price Server running on port ${PORT}`);
  console.log(`Admin panel: http://localhost:${PORT}/admin`);
});

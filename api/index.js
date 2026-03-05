// Vercel serverless: catch-all handler
const store = new Map();

// Simple in-memory store (resets on cold start, but fine for testing)
module.exports = (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const path = req.url.replace(/^\/api/, '');

  // Health check
  if (path === '/' || path === '') {
    return res.json({ status: 'ok', events: store.size });
  }

  // /rules/:eventId
  const rulesMatch = path.match(/^\/rules\/([^\/]+)/);
  if (rulesMatch) {
    const eventId = rulesMatch[1];

    if (req.method === 'GET') {
      const data = store.get(eventId);
      return res.json(data || { rules: [], updatedAt: null });
    }

    if (req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const { rules } = JSON.parse(body);
          if (!Array.isArray(rules)) return res.status(400).json({ error: 'rules must be an array' });
          store.set(eventId, { rules, updatedAt: Date.now() });
          console.log(`[SAVE] Event ${eventId}: ${rules.length} rules`);
          return res.json({ success: true, eventId, ruleCount: rules.length });
        } catch (e) {
          return res.status(400).json({ error: 'Invalid JSON' });
        }
      });
      return;
    }

    if (req.method === 'DELETE') {
      store.delete(eventId);
      return res.json({ success: true });
    }
  }

  // /events
  if (path === '/events') {
    const events = [];
    store.forEach((data, eventId) => {
      events.push({ eventId, ruleCount: data.rules.length, updatedAt: data.updatedAt });
    });
    return res.json(events);
  }

  res.status(404).json({ error: 'Not found' });
};

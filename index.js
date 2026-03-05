const express = require('express');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

// In-memory store: eventId -> { rules: [...], updatedAt: timestamp }
const store = new Map();

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', events: store.size });
});

// Save rules for an event (Admin extension)
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

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`TM Price Server running on port ${PORT}`);
});

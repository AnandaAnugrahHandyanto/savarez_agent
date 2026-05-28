import express from 'express';

const app = express();
app.use(express.json({ limit: '1mb' }));

const BOT_METHOD_RE = /^[A-Za-z0-9_]+$/;

app.post('/api/telegram/:method', async (req, res) => {
  try {
    const { method } = req.params;
    const { token, params = {} } = req.body ?? {};
    if (!BOT_METHOD_RE.test(method)) return res.status(400).json({ ok: false, description: 'Invalid method name' });
    if (!token || typeof token !== 'string') return res.status(400).json({ ok: false, description: 'Missing bot token' });

    const response = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const text = await response.text();
    res.status(response.status).type(response.headers.get('content-type') || 'application/json').send(text);
  } catch (error) {
    res.status(500).json({ ok: false, description: error instanceof Error ? error.message : String(error) });
  }
});

const port = Number(process.env.PORT || 8787);
app.listen(port, () => {
  console.log(`Telegram proxy listening on http://localhost:${port}`);
});

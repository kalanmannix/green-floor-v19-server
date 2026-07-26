# Green Floor V32 — Render Pro server

Build command: `pip install -r requirements.txt`

Start command: `python server.py`

Health check: `/health`

The included Blueprint uses `plan: pro`. Keep this service at one instance because live world and audio state are held in the process.

V32 adds a 32 kHz IMA ADPCM WebSocket voice relay with dedicated bounded audio queues per player. Slow listeners no longer block every other listener, stale queued audio is dropped, and ping/pong heartbeat handling supports automatic client reconnection.

The server also owns boombox held/placed state. Boombox frames are delivered only to players in the boombox's current world or personal room. After deployment, `/health` must report `"build": 32`.

# Green Floor V30 — Render server

Build command: `pip install -r requirements.txt`

Start command: `python server.py`

Health check: `/health`

V30 makes combat server-authoritative and manual per hit. Each attack message can start or queue only one combo step. Misses, parries, interruptions, disconnects, and expired continuation windows release hitstun safely. After deployment, `/health` must report `"build": 30`.

Text chat is relayed by the Render WebSocket server. Messages are plain-text sanitized, limited to 140 characters, rate-limited, and delivered only to players in the sender's current world or personal room.

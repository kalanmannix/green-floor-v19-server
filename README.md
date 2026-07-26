# Green Floor V31 — Render server

Build command: `pip install -r requirements.txt`

Start command: `python server.py`

Health check: `/health`

V31 makes combat server-authoritative and manual per hit. Each attack message can start or queue only one combo step. Misses, parries, interruptions, disconnects, and expired continuation windows release hitstun safely. After deployment, `/health` must report `"build": 31`.

Text chat is relayed by the Render WebSocket server. Messages are plain-text sanitized, limited to 140 characters, rate-limited, and delivered only to players in the sender's current world or personal room.

This build supports synchronized `/e` emotes: dance, dance2, wave, cheer, laugh, point, and sit.


V31 broadcasts emote-start events immediately and requires the matching V31 client, preventing silent connection to an older chat-only server.

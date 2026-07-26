# Green Floor V25 — Render server

Render settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`
- Health check: `/health`

After deployment, `/health` must report `"build": 25`. V25 adds shared rival NPC simulation, capsules, objectives, rival reputation, fast travel, and server-enforced block leases.

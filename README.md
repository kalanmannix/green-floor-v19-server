# Green Floor V26 — Render server

Upload these files to the root of the GitHub repository linked to Render.

Render settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`
- Health check path: `/health`
- Instance type: Free

After deployment, `/health` must report `"build": 26`.

V26 provides authoritative multiplayer physics combat, automatic fighting-style combos, directional parries, steerable dash attacks, collision for the expanded map, progression, rooms, voice relay, boombox relay, and administration.

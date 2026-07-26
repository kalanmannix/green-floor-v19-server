# Green Floor V24 — Render server

Upload these files to the root of the GitHub repository linked to Render.

Render settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`
- Health check path: `/health`
- Instance type: Free

The health endpoint should report `"build": 24` after deployment.

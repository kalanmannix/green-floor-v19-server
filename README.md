# Green Floor V39 — Render Pro join reliability server

Deploy this folder to the same Render Pro web service, then confirm `/health` reports `"build": 39`.

V39 keeps gameplay and voice on separate WebSockets while improving multi-device joining. A duplicated character identity no longer kicks the player already online; the newcomer is told to generate a fresh identity. Both `/ws` and `/ws/` are accepted, as are `/voice` and `/voice/`.

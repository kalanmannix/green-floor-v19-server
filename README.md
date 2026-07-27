# Green Floor V38 — Render Pro stability server

Deploy this folder as a Render Python web service using the included `render.yaml`. Confirm the health endpoint reports `"build": 38` before deploying the matching Netlify client.

V38 separates 32 kHz voice relay traffic onto the `/voice` WebSocket while `/ws` handles gameplay. Voice sessions authenticate with the active game-session token and have independent heartbeat, reconnect, buffering, and send queues. Gameplay snapshots are sent concurrently so one slow connection does not hold up other players.

Physics props now spawn across the courtyard rather than in one cluster. Shopping-cart heading is server-stabilized and follows planar movement without tumbling. Loose-object spin is capped, and existing combat, chat, emotes, rooms, ragdolls, grenades, airstrikes, low gravity, carrying, progression, and boombox systems remain included.

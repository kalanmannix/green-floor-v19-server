# Green Floor V41 — Render Pro clear voice server

Deploy this folder to the Render Pro web service, then confirm `/health` reports `"build": 40`.

V41 keeps gameplay and voice on separate WebSockets and gives live speech its own high-priority bounded queue. Voice uses 24 kHz mono PCM16; boombox music stays on compact ADPCM and can no longer crowd speech out of the relay. V39 multi-device join recovery remains included.


V41 audio service:
- /voice carries only live PCM speech.
- /music carries only boombox ADPCM.
- Server applies room and distance filtering before relay.

'use strict';

const http = require('http');
const crypto = require('crypto');

const PORT = Number(process.env.PORT || 8080);
const BUILD = 1;
const WORLD_SIZE = 12000;
const PLAYER_SPEED = 250;
const PLAYER_RADIUS = 24;
const MONSTER_RADIUS = 68;
const MAX_PLAYERS = 16;
const STATE_RATE = 15;
const TICK_RATE = 30;
const MAX_AVATAR_LENGTH = 240000;

const players = new Map();
const sockets = new Map();

const monster = {
  x: WORLD_SIZE * 0.18,
  y: WORLD_SIZE * 0.71,
  vx: 0,
  vy: 0,
  angle: Math.random() * Math.PI * 2,
  state: 'wandering',
  targetId: null,
  lastTurnAt: 0,
  pulse: 0,
};

function wrap(value) {
  value %= WORLD_SIZE;
  return value < 0 ? value + WORLD_SIZE : value;
}

function wrappedDelta(from, to) {
  let delta = to - from;
  if (delta > WORLD_SIZE / 2) delta -= WORLD_SIZE;
  if (delta < -WORLD_SIZE / 2) delta += WORLD_SIZE;
  return delta;
}

function wrappedDistance(ax, ay, bx, by) {
  return Math.hypot(wrappedDelta(ax, bx), wrappedDelta(ay, by));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function safeText(value, fallback, maxLength) {
  const text = String(value ?? '').replace(/[<>\u0000-\u001f]/g, '').trim();
  return (text || fallback).slice(0, maxLength);
}

function safeColor(value) {
  const color = String(value || '');
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#d7dde5';
}

function safeAvatar(value) {
  if (typeof value !== 'string' || value.length > MAX_AVATAR_LENGTH) return '';
  return /^data:image\/(png|jpeg|webp);base64,[a-zA-Z0-9+/=]+$/.test(value) ? value : '';
}

function encodeFrame(payload, opcode = 0x1) {
  const data = Buffer.isBuffer(payload) ? payload : Buffer.from(String(payload));
  let header;
  if (data.length < 126) {
    header = Buffer.allocUnsafe(2);
    header[0] = 0x80 | opcode;
    header[1] = data.length;
  } else if (data.length <= 0xffff) {
    header = Buffer.allocUnsafe(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(data.length, 2);
  } else {
    header = Buffer.allocUnsafe(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(data.length), 2);
  }
  return Buffer.concat([header, data]);
}

function send(client, payload) {
  if (!client || !client.open) return;
  try {
    client.socket.write(encodeFrame(JSON.stringify(payload)));
  } catch (_) {
    client.close();
  }
}

function broadcast(payload, exceptId = null) {
  const frame = encodeFrame(JSON.stringify(payload));
  for (const [id, client] of sockets) {
    if (id === exceptId || !client.open) continue;
    try {
      client.socket.write(frame);
    } catch (_) {
      client.close();
    }
  }
}

function publicProfile(player) {
  return {
    id: player.id,
    name: player.name,
    color: player.color,
    avatar: player.avatar,
  };
}

function publicState(player, now) {
  return {
    id: player.id,
    x: Math.round(player.x * 10) / 10,
    y: Math.round(player.y * 10) / 10,
    vx: Math.round(player.vx * 10) / 10,
    vy: Math.round(player.vy * 10) / 10,
    down: player.downUntil > now,
    protected: player.protectedUntil > now,
    voice: Math.round(player.voiceLevel * 100) / 100,
  };
}

function spawnPoint() {
  const active = [...players.values()].filter((player) => player.joined);
  if (!active.length) {
    return {
      x: wrap(WORLD_SIZE / 2 + (Math.random() - 0.5) * 600),
      y: wrap(WORLD_SIZE / 2 + (Math.random() - 0.5) * 600),
    };
  }
  const anchor = active[Math.floor(Math.random() * active.length)];
  const angle = Math.random() * Math.PI * 2;
  const distance = 320 + Math.random() * 680;
  return {
    x: wrap(anchor.x + Math.cos(angle) * distance),
    y: wrap(anchor.y + Math.sin(angle) * distance),
  };
}

function chooseMonsterTarget(now) {
  let best = null;
  let bestScore = -Infinity;

  for (const player of players.values()) {
    if (!player.joined || player.downUntil > now || player.protectedUntil > now) continue;
    const distance = wrappedDistance(monster.x, monster.y, player.x, player.y);
    const voiceAttraction = Math.pow(clamp(player.voiceLevel, 0, 1), 0.72) * 6500;
    const proximityAttraction = Math.max(0, 1150 - distance) * 1.35;
    const score = voiceAttraction + proximityAttraction - distance * 0.34;
    if (score > bestScore && (player.voiceLevel > 0.035 || distance < 1050)) {
      bestScore = score;
      best = player;
    }
  }

  return best;
}

function isMonsterObserved(now) {
  for (const player of players.values()) {
    if (!player.joined || player.downUntil > now) continue;
    if (wrappedDistance(player.x, player.y, monster.x, monster.y) < 690) return true;
  }
  return false;
}

function moveMonster(dt, now) {
  const target = chooseMonsterTarget(now);
  const observed = isMonsterObserved(now);

  if (target) {
    monster.state = observed ? 'stalking' : 'hunting';
    monster.targetId = target.id;
    const dx = wrappedDelta(monster.x, target.x);
    const dy = wrappedDelta(monster.y, target.y);
    const length = Math.hypot(dx, dy) || 1;
    const speed = observed ? 72 : 178 + clamp(target.voiceLevel, 0, 1) * 42;
    monster.vx += ((dx / length) * speed - monster.vx) * Math.min(1, dt * 3.5);
    monster.vy += ((dy / length) * speed - monster.vy) * Math.min(1, dt * 3.5);
  } else {
    monster.state = 'wandering';
    monster.targetId = null;
    if (now - monster.lastTurnAt > 1700 + Math.random() * 2600) {
      monster.lastTurnAt = now;
      monster.angle += (Math.random() - 0.5) * 2.1;
    }
    const speed = 88;
    monster.vx += (Math.cos(monster.angle) * speed - monster.vx) * Math.min(1, dt * 1.2);
    monster.vy += (Math.sin(monster.angle) * speed - monster.vy) * Math.min(1, dt * 1.2);
  }

  monster.x = wrap(monster.x + monster.vx * dt);
  monster.y = wrap(monster.y + monster.vy * dt);
  monster.pulse = (monster.pulse + dt * (monster.state === 'hunting' ? 4.5 : 1.6)) % (Math.PI * 2);

  for (const player of players.values()) {
    if (!player.joined || player.downUntil > now || player.protectedUntil > now) continue;
    const distance = wrappedDistance(monster.x, monster.y, player.x, player.y);
    if (distance > MONSTER_RADIUS + PLAYER_RADIUS + 8) continue;

    player.downUntil = now + 3400;
    player.protectedUntil = now + 8500;
    player.inputX = 0;
    player.inputY = 0;
    player.vx = 0;
    player.vy = 0;

    const escapeAngle = Math.random() * Math.PI * 2;
    const escapeDistance = 900 + Math.random() * 750;
    player.respawnX = wrap(player.x + Math.cos(escapeAngle) * escapeDistance);
    player.respawnY = wrap(player.y + Math.sin(escapeAngle) * escapeDistance);

    monster.x = wrap(monster.x - Math.cos(escapeAngle) * 1100);
    monster.y = wrap(monster.y - Math.sin(escapeAngle) * 1100);
    monster.vx *= -0.35;
    monster.vy *= -0.35;

    broadcast({ type: 'caught', playerId: player.id, at: now });
    break;
  }
}

let previousTick = Date.now();
setInterval(() => {
  const now = Date.now();
  const dt = Math.min(0.1, (now - previousTick) / 1000);
  previousTick = now;

  for (const player of players.values()) {
    if (!player.joined) continue;

    if (player.downUntil && player.downUntil <= now && player.respawnX != null) {
      player.x = player.respawnX;
      player.y = player.respawnY;
      player.respawnX = null;
      player.respawnY = null;
    }

    if (player.downUntil > now) continue;

    const length = Math.hypot(player.inputX, player.inputY);
    const nx = length > 1 ? player.inputX / length : player.inputX;
    const ny = length > 1 ? player.inputY / length : player.inputY;
    const targetVx = nx * PLAYER_SPEED;
    const targetVy = ny * PLAYER_SPEED;
    const response = Math.min(1, dt * 12);
    player.vx += (targetVx - player.vx) * response;
    player.vy += (targetVy - player.vy) * response;
    player.x = wrap(player.x + player.vx * dt);
    player.y = wrap(player.y + player.vy * dt);
    player.voiceLevel *= Math.pow(0.12, dt);
  }

  moveMonster(dt, now);
}, 1000 / TICK_RATE);

setInterval(() => {
  const now = Date.now();
  broadcast({
    type: 'state',
    at: now,
    players: [...players.values()].filter((player) => player.joined).map((player) => publicState(player, now)),
    monster: {
      x: Math.round(monster.x * 10) / 10,
      y: Math.round(monster.y * 10) / 10,
      vx: Math.round(monster.vx * 10) / 10,
      vy: Math.round(monster.vy * 10) / 10,
      state: monster.state,
      targetId: monster.targetId,
      pulse: monster.pulse,
    },
  });
}, 1000 / STATE_RATE);

const server = http.createServer((request, response) => {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Headers', 'content-type');

  if (request.url === '/health') {
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ ok: true, build: BUILD, players: players.size, worldSize: WORLD_SIZE }));
    return;
  }

  response.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end('The Room multiplayer server is running.');
});

function createRawWebSocket(socket, head, onMessage, onClose) {
  const client = {
    socket,
    open: true,
    buffer: head && head.length ? Buffer.from(head) : Buffer.alloc(0),
    fragmentedOpcode: 0,
    fragments: [],
    fragmentLength: 0,
    close() {
      if (!client.open) return;
      client.open = false;
      try { socket.end(encodeFrame(Buffer.alloc(0), 0x8)); } catch (_) {}
      try { socket.destroy(); } catch (_) {}
      onClose();
    },
  };

  socket.setNoDelay(true);

  function consumeFrames() {
    while (client.buffer.length >= 2) {
      const first = client.buffer[0];
      const second = client.buffer[1];
      const fin = Boolean(first & 0x80);
      const opcode = first & 0x0f;
      const masked = Boolean(second & 0x80);
      let payloadLength = second & 0x7f;
      let offset = 2;

      if (payloadLength === 126) {
        if (client.buffer.length < 4) return;
        payloadLength = client.buffer.readUInt16BE(2);
        offset = 4;
      } else if (payloadLength === 127) {
        if (client.buffer.length < 10) return;
        const bigLength = client.buffer.readBigUInt64BE(2);
        if (bigLength > BigInt(320000)) return client.close();
        payloadLength = Number(bigLength);
        offset = 10;
      }

      if (payloadLength > 320000) return client.close();
      const maskLength = masked ? 4 : 0;
      const totalLength = offset + maskLength + payloadLength;
      if (client.buffer.length < totalLength) return;

      let mask;
      if (masked) mask = client.buffer.subarray(offset, offset + 4);
      const payloadStart = offset + maskLength;
      const payload = Buffer.from(client.buffer.subarray(payloadStart, payloadStart + payloadLength));
      client.buffer = client.buffer.subarray(totalLength);

      if (masked) {
        for (let index = 0; index < payload.length; index += 1) payload[index] ^= mask[index % 4];
      }

      if (opcode === 0x8) return client.close();
      if (opcode === 0x9) {
        try { socket.write(encodeFrame(payload, 0xA)); } catch (_) { client.close(); }
        continue;
      }
      if (opcode === 0xA) continue;

      if (opcode === 0x1 && fin) {
        onMessage(payload.toString('utf8'));
        continue;
      }

      if ((opcode === 0x1 || opcode === 0x2) && !fin) {
        client.fragmentedOpcode = opcode;
        client.fragments = [payload];
        client.fragmentLength = payload.length;
        continue;
      }

      if (opcode === 0x0 && client.fragmentedOpcode) {
        client.fragments.push(payload);
        client.fragmentLength += payload.length;
        if (client.fragmentLength > 320000) return client.close();
        if (fin) {
          const combined = Buffer.concat(client.fragments, client.fragmentLength);
          const originalOpcode = client.fragmentedOpcode;
          client.fragmentedOpcode = 0;
          client.fragments = [];
          client.fragmentLength = 0;
          if (originalOpcode === 0x1) onMessage(combined.toString('utf8'));
        }
        continue;
      }

      return client.close();
    }
  }

  socket.on('data', (chunk) => {
    if (!client.open) return;
    client.buffer = client.buffer.length ? Buffer.concat([client.buffer, chunk]) : Buffer.from(chunk);
    if (client.buffer.length > 640000) return client.close();
    consumeFrames();
  });
  socket.on('end', client.close);
  socket.on('close', client.close);
  socket.on('error', client.close);

  if (client.buffer.length) consumeFrames();
  return client;
}

function handleClientMessage(id, player, client, raw) {
  let message;
  try {
    message = JSON.parse(String(raw));
  } catch (_) {
    return;
  }

  player.lastMessageAt = Date.now();

  if (message.type === 'join') {
    player.name = safeText(message.name, player.name, 18);
    player.color = safeColor(message.color);
    player.avatar = safeAvatar(message.avatar);
    player.joined = true;

    send(client, {
      type: 'welcome',
      id,
      worldSize: WORLD_SIZE,
      profiles: [...players.values()].filter((item) => item.joined).map(publicProfile),
      players: [...players.values()].filter((item) => item.joined).map((item) => publicState(item, Date.now())),
      monster: { ...monster },
    });
    broadcast({ type: 'peer-joined', profile: publicProfile(player) }, id);
    return;
  }

  if (!player.joined) return;

  if (message.type === 'input') {
    player.inputX = clamp(Number(message.x) || 0, -1, 1);
    player.inputY = clamp(Number(message.y) || 0, -1, 1);
    return;
  }

  if (message.type === 'voice') {
    player.voiceLevel = clamp(Number(message.level) || 0, 0, 1);
    return;
  }

  if (message.type === 'profile') {
    player.name = safeText(message.name, player.name, 18);
    player.color = safeColor(message.color || player.color);
    const avatar = safeAvatar(message.avatar);
    if (avatar) player.avatar = avatar;
    broadcast({ type: 'profile', profile: publicProfile(player) });
    return;
  }

  if (message.type === 'signal') {
    const targetId = String(message.to || '');
    const targetClient = sockets.get(targetId);
    if (!targetClient || targetId === id) return;
    const signalText = JSON.stringify(message.data ?? null);
    if (signalText.length > 90000) return;
    send(targetClient, { type: 'signal', from: id, data: message.data });
    return;
  }

  if (message.type === 'ping') send(client, { type: 'pong', at: message.at || Date.now() });
}

server.on('upgrade', (request, socket, head) => {
  const key = request.headers['sec-websocket-key'];
  const upgrade = String(request.headers.upgrade || '').toLowerCase();
  if (!key || upgrade !== 'websocket') {
    socket.destroy();
    return;
  }

  if (players.size >= MAX_PLAYERS) {
    socket.write('HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n');
    socket.destroy();
    return;
  }

  const accept = crypto.createHash('sha1')
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
    .digest('base64');
  socket.write([
    'HTTP/1.1 101 Switching Protocols',
    'Upgrade: websocket',
    'Connection: Upgrade',
    `Sec-WebSocket-Accept: ${accept}`,
    '\r\n',
  ].join('\r\n'));

  const id = crypto.randomUUID().slice(0, 8);
  const spawn = spawnPoint();
  const player = {
    id,
    joined: false,
    name: `Player ${id.slice(0, 3)}`,
    color: '#d7dde5',
    avatar: '',
    x: spawn.x,
    y: spawn.y,
    vx: 0,
    vy: 0,
    inputX: 0,
    inputY: 0,
    voiceLevel: 0,
    downUntil: 0,
    protectedUntil: Date.now() + 4500,
    respawnX: null,
    respawnY: null,
    lastMessageAt: Date.now(),
  };

  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    players.delete(id);
    sockets.delete(id);
    broadcast({ type: 'peer-left', id });
  };

  let client;
  const queuedMessages = [];
  client = createRawWebSocket(
    socket,
    head,
    (raw) => {
      if (client) handleClientMessage(id, player, client, raw);
      else queuedMessages.push(raw);
    },
    cleanup,
  );
  for (const raw of queuedMessages) handleClientMessage(id, player, client, raw);

  players.set(id, player);
  sockets.set(id, client);
  send(client, {
    type: 'hello',
    id,
    build: BUILD,
    worldSize: WORLD_SIZE,
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
  });
});

setInterval(() => {
  const cutoff = Date.now() - 120000;
  for (const [id, client] of sockets) {
    const player = players.get(id);
    if (!player || player.lastMessageAt < cutoff || !client.open) client.close();
  }
}, 30000);

server.listen(PORT, '0.0.0.0', () => {
  console.log(`The Room server build ${BUILD} listening on port ${PORT}`);
});

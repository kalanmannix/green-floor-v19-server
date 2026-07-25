import asyncio
import hashlib
import json
import math
import os
import random
import secrets
import sqlite3
import string
import time
from aiohttp import web, WSMsgType

BUILD = 19
PROTOCOL = 19
MAX_PLAYERS = 16
WORLD_W = 3200
WORLD_H = 2200
RADIUS = 30
SPEED = 285
SPRINT = 1.58
BLOCK_MOVE = 0.44
STAMINA_MAX = 100
SPRINT_DRAIN = 29
STAMINA_REGEN = 24
PUNCH_COST = 7
BLOCK_COST = 18
PUNCH_RANGE = 152
PUNCH_LOCK = 560
PUNCH_DAMAGE = 13
PUNCH_COOLDOWN = 0.405
PUNCH_KB = 520
GRAB_RANGE = 132
GRAB_COST = 11
THROW_DAMAGE = 14
THROW_KB = 760
KO_TIME = 3.0
RECONNECT_GRACE = 25.0
INTERACT_RANGE = 145
VOICE_MAX_FRAME = 380
VOICE_MIN_INTERVAL = 0.010
MAIN_WORLD_CODE = "MAIN"
ROOM_W = 920
ROOM_H = 650
ROOM_DOOR = (1600, 2035)
ROOM_EXIT = (460, 600)
SCAVENGER_POINTS = [(760,560),(1120,460),(1460,720),(1890,620),(2260,510),(2670,980),(2360,1530),(1770,1720),(1080,1580),(650,1260)]
COLLECTION_TYPES = ["Manga", "Keychain", "School Badge", "Trading Card", "Music Tape", "Arcade Prize", "Photo"]
DB_PATH = os.getenv("DATABASE_PATH", "green_floor_v17.db")

TRAINING_DUMMY = (500, 650)
DELIVERY_START = (2760, 430)
DELIVERY_END = (440, 1760)
VENDING = (2550, 1680)
SHOP = (610, 360)
MISSION_BOARD = (1600, 250)
ARCADE = (2780, 1750)
BASKETBALL = (2520, 620)
CONTROL_CENTER = (1600, 1100)
CONTROL_RADIUS = 310

SHOP_CATALOG = {
    "red-headband": {"id": "red-headband", "name": "Red Headband", "slot": "head", "price": 25, "kind": "cosmetic"},
    "school-bag": {"id": "school-bag", "name": "School Bag", "slot": "back", "price": 40, "kind": "cosmetic"},
    "lucky-charm": {"id": "lucky-charm", "name": "Lucky Charm", "slot": "hand", "price": 55, "kind": "cosmetic"},
    "energy-drink": {"id": "energy-drink", "name": "Energy Drink", "slot": "consumable", "price": 10, "kind": "consumable"},
    "room-poster": {"id": "room-poster", "name": "School Poster", "slot": "room", "price": 35, "kind": "cosmetic"},
    "room-lamp": {"id": "room-lamp", "name": "Desk Lamp", "slot": "room", "price": 50, "kind": "cosmetic"},
}

MISSION_DEFS = {
    "training": {"title": "Training Day", "stat": "training", "goal": 10, "xp": 50, "coins": 25},
    "pickups": {"title": "Clean the Grounds", "stat": "pickups", "goal": 8, "xp": 45, "coins": 20},
    "deliveries": {"title": "Courier", "stat": "deliveries", "goal": 2, "xp": 80, "coins": 45},
    "kos": {"title": "Courtyard Reputation", "stat": "kos", "goal": 3, "xp": 100, "coins": 50},
}

PICKUP_POINTS = [
    (360, 360), (850, 300), (1280, 420), (1920, 430), (2360, 340), (2860, 760),
    (2900, 1350), (2650, 1990), (2150, 1880), (1680, 1980), (1160, 1850), (680, 1980),
    (330, 1420), (410, 980), (880, 1060), (1260, 850), (2020, 860), (2350, 1200),
]

rooms = {}

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS characters (character_id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, data TEXT NOT NULL, updated REAL NOT NULL)")
    conn.commit()
    return conn

def secret_hash(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()

def clean_character_id(value):
    value = ''.join(c for c in str(value or '') if c.isalnum() or c in '_-')[:16]
    return value if len(value) == 16 else ''

def load_character(character_id, secret):
    if not character_id or not secret:
        return None, False
    with db_connect() as conn:
        row = conn.execute("SELECT secret_hash, data FROM characters WHERE character_id=?", (character_id,)).fetchone()
    if not row:
        return None, True
    if not secrets.compare_digest(row['secret_hash'], secret_hash(secret)):
        return None, False
    try:
        return json.loads(row['data']), True
    except Exception:
        return None, True

def store_character_payload(character_id, secret, payload):
    if not character_id or not secret:
        return
    encoded = json.dumps(payload, separators=(',', ':'))
    with db_connect() as conn:
        conn.execute("INSERT INTO characters(character_id, secret_hash, data, updated) VALUES(?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET data=excluded.data, updated=excluded.updated", (character_id, secret_hash(secret), encoded, time.time()))
        conn.commit()


def clamp(v, a, b):
    return max(a, min(b, v))


def clean_name(v):
    s = ''.join(c for c in str(v or 'Player') if ord(c) >= 32 and c not in '<>').strip()[:24]
    return s or 'Player'


def room_code(v):
    return ''.join(c for c in str(v or '').upper() if c.isalnum())[:8]


def token(v):
    s = ''.join(c for c in str(v or '') if c.isalnum() or c in '_-')[:96]
    return s if len(s) >= 12 else ''


def unique_code():
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choice(alphabet) for _ in range(6))
        if code not in rooms:
            return code


def sanitize_input(m):
    x = clamp(float(m.get('x') or 0), -1, 1)
    y = clamp(float(m.get('y') or 0), -1, 1)
    length = math.hypot(x, y)
    if length > 1:
        x /= length
        y /= length
    return {'x': x, 'y': y, 'block': m.get('block') is True, 'sprint': m.get('sprint') is True}


def sanitize_profile(v):
    v = v if isinstance(v, dict) else {}
    return {
        'heritage': clean_name(v.get('heritage') or 'Japanese')[:20],
        'heightLabel': clean_name(v.get('heightLabel') or 'Average')[:20],
        'buildLabel': clean_name(v.get('buildLabel') or 'Average')[:20],
        'style': clean_name(v.get('style') or 'Street Fighting')[:24],
        'styleDescription': clean_name(v.get('styleDescription') or 'Balanced')[:60],
        'speedMult': clamp(float(v.get('speedMult') or 1), .88, 1.12),
        'sprintMult': clamp(float(v.get('sprintMult') or 1), .9, 1.12),
        'maxHealth': round(clamp(float(v.get('maxHealth') or 100), 90, 115)),
        'reachMult': clamp(float(v.get('reachMult') or 1), .88, 1.16),
        'punchDamageMult': clamp(float(v.get('punchDamageMult') or 1), .88, 1.18),
        'grabPowerMult': clamp(float(v.get('grabPowerMult') or 1), .9, 1.22),
        'grabRangeMult': clamp(float(v.get('grabRangeMult') or 1), .9, 1.25),
        'attackSpeedMult': clamp(float(v.get('attackSpeedMult') or 1), .9, 1.12),
        'sizeScale': clamp(float(v.get('sizeScale') or 1), .88, 1.12),
    }


def sanitize_avatar(v):
    if not isinstance(v, dict) or not isinstance(v.get('parts'), dict):
        return None
    total = 0
    parts = {}
    for name in ['head', 'torso', 'leftArm', 'rightArm', 'leftLeg', 'rightLeg']:
        part = v['parts'].get(name)
        if not part:
            parts[name] = None
            continue
        data = str(part.get('data') or '')
        if not data.startswith('data:image/png;base64,') or len(data) > 450000:
            return None
        total += len(data)
        parts[name] = {
            'data': data,
            'pivotX': clamp(float(part.get('pivotX') or 0), -3, 3),
            'pivotY': clamp(float(part.get('pivotY') or 0), -3, 3),
            'width': clamp(float(part.get('width') or 1), 1, 512),
            'height': clamp(float(part.get('height') or 1), 1, 512),
        }
    if total > 1800000:
        return None
    return {'version': 4, 'view': 'side', 'parts': parts, 'layout': v.get('layout')}


def sanitize_progress(v):
    v = v if isinstance(v, dict) else {}
    stats = v.get('missionStats') if isinstance(v.get('missionStats'), dict) else {}
    claimed = v.get('missionClaimed') if isinstance(v.get('missionClaimed'), dict) else {}
    return {
        'xp': int(clamp(float(v.get('xp') or 0), 0, 250000)),
        'coins': int(clamp(float(v.get('coins') or 35), 0, 250000)),
        'reputation': int(clamp(float(v.get('reputation') or 0), 0, 100000)),
        'missionStats': {key: int(clamp(float(stats.get(key) or 0), 0, 100000)) for key in ('training', 'pickups', 'deliveries', 'kos')},
        'missionClaimed': {key: claimed.get(key) is True for key in MISSION_DEFS},
    }


def level_for_xp(xp):
    level = 1
    remaining = max(0, int(xp))
    while level < 50:
        need = 70 + level * 45
        if remaining < need:
            break
        remaining -= need
        level += 1
    return level, remaining, 70 + level * 45


def sanitize_item(item):
    if not isinstance(item, dict):
        return None
    item_id = ''.join(c for c in str(item.get('id') or '') if c.isalnum() or c in '-_')[:48]
    name = clean_name(item.get('name') or 'Custom Item')[:24]
    slot = str(item.get('slot') or '')
    if slot not in ('head', 'back', 'hand', 'room', 'consumable') or not item_id:
        return None
    image = str(item.get('image') or '')
    builtin = item.get('builtin') is True
    if image and (not image.startswith('data:image/png;base64,') or len(image) > 320000):
        return None
    if not builtin and not image:
        return None
    return {
        'id': item_id,
        'name': name,
        'slot': slot,
        'image': image,
        'builtin': builtin,
        'scale': clamp(float(item.get('scale') or 1), .35, 2.5),
        'offsetX': clamp(float(item.get('offsetX') or 0), -120, 120),
        'offsetY': clamp(float(item.get('offsetY') or 0), -160, 160),
    }


def sanitize_inventory(value):
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for raw in value[:24]:
        item = sanitize_item(raw)
        if item and item['id'] not in seen:
            seen.add(item['id'])
            result.append(item)
    return result


def sanitize_loadout(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    total = 0
    for slot in ('head', 'back', 'hand'):
        item = sanitize_item(value.get(slot))
        if item and item['slot'] == slot:
            total += len(item.get('image') or '')
            if total <= 720000:
                result[slot] = item
    return result


def sanitize_collections(value):
    value = value if isinstance(value, dict) else {}
    return {name: int(clamp(float(value.get(name) or 0), 0, 999)) for name in COLLECTION_TYPES}

def sanitize_records(value):
    value = value if isinstance(value, dict) else {}
    return {
        'deliveries': int(clamp(float(value.get('deliveries') or 0), 0, 100000)),
        'arcadeHigh': int(clamp(float(value.get('arcadeHigh') or 0), 0, 999999)),
        'basketballMade': int(clamp(float(value.get('basketballMade') or 0), 0, 100000)),
        'scavengerWins': int(clamp(float(value.get('scavengerWins') or 0), 0, 100000)),
        'itemsFound': int(clamp(float(value.get('itemsFound') or 0), 0, 100000)),
    }

def sanitize_room_decor(value, inventory=None):
    if not isinstance(value, list):
        return []
    owned = {item.get('id') for item in (inventory or [])}
    result = []
    for raw in value[:12]:
        if not isinstance(raw, dict):
            continue
        item = sanitize_item(raw.get('item') or raw)
        if not item or item['slot'] != 'room' or (owned and item['id'] not in owned):
            continue
        result.append({
            'item': item,
            'x': clamp(float(raw.get('x') or 160 + len(result) * 90), 70, ROOM_W - 70),
            'y': clamp(float(raw.get('y') or 170 + (len(result) % 2) * 150), 90, ROOM_H - 80),
            'scale': clamp(float(raw.get('scale') or item.get('scale') or 1), .35, 2.5),
        })
    return result

def character_payload(player, room=None):
    room = room or player.get('roomRef')
    avatar = room.get('avatars', {}).get(player['id']) if room else None
    return {
        'characterId': player.get('characterId'), 'name': player.get('name'),
        'profile': player.get('profileSummary') or {}, 'avatar': avatar,
        'progress': {k: player.get(k) for k in ('xp','coins','reputation','missionStats','missionClaimed')},
        'inventory': player.get('inventory') or [], 'loadout': player.get('loadout') or {},
        'collections': player.get('collections') or {}, 'records': player.get('records') or {},
        'roomDecor': player.get('roomDecor') or [], 'title': player.get('title') or 'New Student',
    }

def save_character(player):
    if player.get('characterId') and player.get('characterSecret'):
        store_character_payload(player['characterId'], player['characterSecret'], character_payload(player))

def apply_profile(player, profile, reset=False):
    profile = sanitize_profile(profile)
    player.update(profile)
    player['profileSummary'] = profile
    if reset or 'health' not in player:
        player['health'] = profile['maxHealth']
    else:
        player['health'] = clamp(player['health'], 0, profile['maxHealth'])


def apply_progress(player, raw):
    progress = sanitize_progress(raw)
    player.update(progress)
    level, current, needed = level_for_xp(player['xp'])
    player['level'] = level
    player['levelXp'] = current
    player['levelXpNeeded'] = needed


def make_pickups():
    return [
        {'id': f'p{i+1}', 'x': x, 'y': y, 'active': True, 'respawnAt': 0.0}
        for i, (x, y) in enumerate(PICKUP_POINTS)
    ]


def make_room(code):
    return {
        'code': code,
        'players': {},
        'sessions': {},
        'avatars': {},
        'loadouts': {},
        'pickups': make_pickups(),
        'controlOwner': None,
        'controlSince': 0.0,
        'controlRewardAt': 0.0,
        'event': None, 'nextEventAt': time.monotonic() + 45,
        'createdAt': time.time(),
    }


def make_player(name, profile, progress, inventory, loadout, session, character_id, character_secret, collections=None, records=None, room_decor=None):
    angle = random.random() * math.tau
    distance = 70 + random.random() * 170
    player = {
        'id': character_id or secrets.token_hex(8),
        'characterId': character_id or secrets.token_hex(12),
        'characterSecret': character_secret,
        'name': clean_name(name),
        'x': clamp(WORLD_W / 2 + math.cos(angle) * distance, RADIUS, WORLD_W - RADIUS),
        'y': clamp(WORLD_H / 2 + math.sin(angle) * distance, RADIUS, WORLD_H - RADIUS),
        'vx': 0, 'vy': 0, 'moveVx': 0, 'moveVy': 0,
        'direction': random.random() * math.tau, 'facing': 1,
        'moving': False, 'sprinting': False, 'blocking': False,
        'stamina': STAMINA_MAX, 'lastStaminaUseAt': 0,
        'score': 0, 'knockedOut': False, 'respawnAt': 0,
        'lastPunchAt': -10, 'lastTrainingAt': -10,
        'attackHand': 'right', 'attackAngle': 0,
        'impulseX': 0, 'impulseY': 0,
        'grabbedTargetId': None, 'grabbedBy': None,
        'job': None, 'space': 'world', 'roomOwner': None,
        'title': 'New Student',
        'inventory': sanitize_inventory(inventory),
        'connected': False, 'ws': None, 'input': sanitize_input({}),
        'sessionToken': session, 'remove_task': None,
        'lastVoiceAt': 0.0,
        'collections': sanitize_collections(collections),
        'records': sanitize_records(records),
        'roomDecor': [], 'roomRef': None,
    }
    apply_profile(player, profile, True)
    apply_progress(player, progress)
    player['loadout'] = sanitize_loadout(loadout)
    player['roomDecor'] = sanitize_room_decor(room_decor, player['inventory'])
    return player


def public_player(player):
    excluded = {'ws', 'input', 'sessionToken', 'remove_task', 'connected', 'inventory', 'loadout', 'roomDecor', 'lastVoiceAt', 'characterSecret', 'roomRef'}
    result = {k: v for k, v in player.items() if k not in excluded}
    result['inventoryCount'] = len(player.get('inventory') or [])
    return result


def connected(room, space=None):
    players = [p for p in room['players'].values() if p['connected']]
    return players if space is None else [p for p in players if p.get('space','world') == space]


async def send(ws, obj):
    if not ws.closed:
        try:
            await ws.send_str(json.dumps(obj, separators=(',', ':')))
        except Exception:
            pass


async def broadcast(room, obj, exclude=None, space=None):
    data = json.dumps(obj, separators=(',', ':'))
    for player in connected(room, space):
        if player['ws'] is exclude or player['ws'].closed:
            continue
        try:
            await player['ws'].send_str(data)
        except Exception:
            pass


async def broadcast_bytes(room, data, exclude=None):
    for player in connected(room):
        if player['ws'] is exclude or player['ws'].closed:
            continue
        try:
            await player['ws'].send_bytes(data)
        except Exception:
            pass


async def snapshot(room):
    all_online = [
        {'id': p['id'], 'characterId': p.get('characterId'), 'name': p['name'], 'space': p.get('space','world'), 'title': p.get('title','New Student'), 'level': p.get('level',1)}
        for p in connected(room)
    ]
    for receiver in connected(room):
        same_space = connected(room, receiver.get('space','world'))
        await send(receiver['ws'], {
            'type': 'snapshot',
            'players': {p['id']: public_player(p) for p in same_space},
            'serverTime': int(time.time() * 1000),
            'controlOwner': room.get('controlOwner'),
            'online': all_online,
            'space': receiver.get('space','world'),
        })


async def send_world(room, ws=None):
    async def packet_for(player):
        packet = {
            'type': 'world-state', 'pickups': room['pickups'], 'event': room.get('event'),
            'zones': {'training': TRAINING_DUMMY, 'deliveryStart': DELIVERY_START, 'deliveryEnd': DELIVERY_END, 'vending': VENDING, 'shop': SHOP, 'missions': MISSION_BOARD, 'arcade': ARCADE, 'basketball': BASKETBALL, 'control': CONTROL_CENTER, 'roomDoor': ROOM_DOOR, 'roomExit': ROOM_EXIT},
            'catalog': list(SHOP_CATALOG.values()), 'space': player.get('space','world'),
        }
        if player.get('space','world').startswith('room:'):
            owner_id = player.get('roomOwner') or player.get('space','world').split(':',1)[1]
            owner = room['players'].get(owner_id)
            packet['room'] = {'ownerId': owner_id, 'ownerName': owner['name'] if owner else 'Friend', 'decor': owner.get('roomDecor',[]) if owner else []}
        return packet
    if ws:
        player = next((p for p in connected(room) if p['ws'] is ws), None)
        if player: await send(ws, await packet_for(player))
    else:
        for player in connected(room): await send(player['ws'], await packet_for(player))


def nearest(room, attacker, max_distance):
    best = None
    best_distance = max_distance
    for player in connected(room, attacker.get('space','world')):
        if player['id'] == attacker['id'] or player['knockedOut']:
            continue
        distance = math.hypot(player['x'] - attacker['x'], player['y'] - attacker['y'])
        if distance < best_distance:
            best = player
            best_distance = distance
    return best, best_distance


def release(room, player):
    if player.get('grabbedTargetId'):
        target = room['players'].get(player['grabbedTargetId'])
        player['grabbedTargetId'] = None
        if target:
            target['grabbedBy'] = None
    if player.get('grabbedBy'):
        holder = room['players'].get(player['grabbedBy'])
        player['grabbedBy'] = None
        if holder:
            holder['grabbedTargetId'] = None


async def send_progress(player, reason=''):
    await send(player['ws'], {
        'type': 'progress',
        'progress': {
            'xp': player['xp'],
            'coins': player['coins'],
            'reputation': player['reputation'],
            'level': player['level'],
            'levelXp': player['levelXp'],
            'levelXpNeeded': player['levelXpNeeded'],
            'missionStats': player['missionStats'],
            'missionClaimed': player['missionClaimed'],
            'job': player.get('job'), 'collections': player.get('collections') or {}, 'records': player.get('records') or {}, 'title': player.get('title','New Student'),
        },
        'inventory': player.get('inventory') or [],
        'reason': reason,
    })
    save_character(player)


async def check_missions(player):
    completed = []
    for key, mission in MISSION_DEFS.items():
        if player['missionClaimed'].get(key):
            continue
        if player['missionStats'].get(mission['stat'], 0) >= mission['goal']:
            player['missionClaimed'][key] = True
            player['xp'] += mission['xp']
            player['coins'] += mission['coins']
            completed.append({'id': key, **mission})
    if completed:
        level, current, needed = level_for_xp(player['xp'])
        player['level'] = level
        player['levelXp'] = current
        player['levelXpNeeded'] = needed
        await send(player['ws'], {'type': 'mission-complete', 'missions': completed})


async def grant(player, xp=0, coins=0, reputation=0, reason=''):
    old_level = player['level']
    player['xp'] += max(0, int(xp))
    player['coins'] += int(coins)
    player['reputation'] += max(0, int(reputation))
    player['coins'] = max(0, player['coins'])
    level, current, needed = level_for_xp(player['xp'])
    player['level'] = level
    player['levelXp'] = current
    player['levelXpNeeded'] = needed
    player['title'] = 'School Legend' if player['reputation'] >= 500 else 'Crew Captain' if player['reputation'] >= 200 else 'Known Face' if player['reputation'] >= 60 else 'New Student'
    await check_missions(player)
    await send(player['ws'], {
        'type': 'reward',
        'xp': int(xp), 'coins': int(coins), 'reputation': int(reputation),
        'reason': reason,
        'level': player['level'], 'levelUp': player['level'] > old_level,
    })
    await send_progress(player, reason)


def knockout(room, target, attacker):
    target['knockedOut'] = True
    target['respawnAt'] = time.monotonic() + KO_TIME
    target['blocking'] = target['sprinting'] = False
    release(room, target)
    attacker['score'] += 1


async def reward_knockout(attacker):
    attacker['missionStats']['kos'] += 1
    await grant(attacker, xp=18, coins=8, reputation=2, reason='Knockout')


def respawn(player):
    if player.get('space','world').startswith('room:'):
        player['x'], player['y'] = 460, 350
    else:
        angle = random.random() * math.tau
        distance = 90 + random.random() * 190
        player['x'] = clamp(WORLD_W / 2 + math.cos(angle) * distance, RADIUS, WORLD_W - RADIUS)
        player['y'] = clamp(WORLD_H / 2 + math.sin(angle) * distance, RADIUS, WORLD_H - RADIUS)
    for key in ['vx', 'vy', 'moveVx', 'moveVy', 'impulseX', 'impulseY']:
        player[key] = 0
    player['health'] = player['maxHealth']
    player['stamina'] = STAMINA_MAX
    player['knockedOut'] = False
    player['respawnAt'] = 0
    player['blocking'] = player['sprinting'] = False
    player['grabbedTargetId'] = player['grabbedBy'] = None


async def training_hit(room, attacker):
    if attacker.get('space','world') != 'world':
        return False
    now = time.monotonic()
    if now - attacker['lastTrainingAt'] < 0.7:
        return False
    if math.hypot(attacker['x'] - TRAINING_DUMMY[0], attacker['y'] - TRAINING_DUMMY[1]) > 185:
        return False
    attacker['lastTrainingAt'] = now
    attacker['missionStats']['training'] += 1
    await broadcast(room, {
        'type': 'activity-effect',
        'kind': 'training-hit',
        'playerId': attacker['id'],
        'x': TRAINING_DUMMY[0], 'y': TRAINING_DUMMY[1] - 55,
    })
    await grant(attacker, xp=2, coins=1, reason='Training hit')
    return True


async def punch(room, attacker):
    now = time.monotonic()
    cooldown = PUNCH_COOLDOWN / (attacker.get('attackSpeedMult') or 1)
    if attacker['knockedOut'] or attacker['blocking'] or attacker['grabbedBy'] or attacker['grabbedTargetId'] or attacker['stamina'] < PUNCH_COST or now - attacker['lastPunchAt'] < cooldown:
        return
    attacker['lastPunchAt'] = now
    attacker['sprinting'] = False
    attacker['stamina'] = max(0, attacker['stamina'] - PUNCH_COST)
    attacker['lastStaminaUseAt'] = now
    attacker['attackHand'] = 'left' if attacker['attackHand'] == 'right' else 'right'
    target, distance = nearest(room, attacker, PUNCH_LOCK * (attacker.get('reachMult') or 1))
    angle = 0 if attacker['facing'] >= 0 else math.pi
    if target:
        angle = math.atan2(target['y'] - attacker['y'], target['x'] - attacker['x'])
        attacker['direction'] = angle
        attacker['facing'] = 1 if math.cos(angle) >= 0 else -1
    attacker['attackAngle'] = angle
    hit = bool(target and distance <= PUNCH_RANGE * (attacker.get('reachMult') or 1))
    blocked = False
    knocked_out = False
    damage = round(PUNCH_DAMAGE * (attacker.get('punchDamageMult') or 1))
    knockback = PUNCH_KB * (.84 + (attacker.get('grabPowerMult') or 1) * .16)
    impact_x = attacker['x'] + math.cos(angle) * 88
    impact_y = attacker['y'] + math.sin(angle) * 88 - 44
    if hit:
        if target['blocking'] and target['stamina'] > 0:
            blocked = True
            target['stamina'] = max(0, target['stamina'] - BLOCK_COST)
            damage = max(1, round(damage * .2))
            knockback *= .25
            if target['stamina'] <= 0:
                target['blocking'] = False
        target['health'] = max(0, target['health'] - damage)
        target['impulseX'] += math.cos(angle) * knockback
        target['impulseY'] += math.sin(angle) * knockback
        impact_x = (attacker['x'] + target['x']) / 2
        impact_y = (attacker['y'] + target['y']) / 2 - 48
        if target['health'] <= 0:
            knocked_out = True
            knockout(room, target, attacker)
            asyncio.create_task(reward_knockout(attacker))
    else:
        await training_hit(room, attacker)
    await broadcast(room, {
        'type': 'combat',
        'event': {
            'kind': 'punch', 'attackerId': attacker['id'],
            'targetId': target['id'] if target else None,
            'angle': angle, 'hand': attacker['attackHand'],
            'hit': hit, 'blocked': blocked,
            'damage': damage if hit else 0,
            'knockedOut': knocked_out,
            'x': impact_x, 'y': impact_y,
        },
    }, space=attacker.get('space','world'))


async def grab(room, attacker):
    if attacker['knockedOut'] or attacker['blocking'] or attacker['grabbedBy'] or attacker['grabbedTargetId'] or attacker['stamina'] < GRAB_COST:
        return
    target, _ = nearest(room, attacker, GRAB_RANGE * (attacker.get('grabRangeMult') or 1))
    if not target or target['grabbedBy']:
        return
    angle = math.atan2(target['y'] - attacker['y'], target['x'] - attacker['x'])
    attacker['attackAngle'] = attacker['direction'] = angle
    attacker['facing'] = 1 if math.cos(angle) >= 0 else -1
    attacker['stamina'] -= GRAB_COST
    attacker['grabbedTargetId'] = target['id']
    target['grabbedBy'] = attacker['id']
    target['blocking'] = target['sprinting'] = False
    await broadcast(room, {'type': 'combat', 'event': {'kind': 'grab', 'attackerId': attacker['id'], 'targetId': target['id'], 'angle': angle, 'hit': True, 'x': (attacker['x'] + target['x']) / 2, 'y': (attacker['y'] + target['y']) / 2 - 42}}, space=attacker.get('space','world'))


async def throw(room, attacker):
    target_id = attacker.get('grabbedTargetId')
    attacker['grabbedTargetId'] = None
    if not target_id:
        return
    target = room['players'].get(target_id)
    if not target:
        return
    target['grabbedBy'] = None
    angle = attacker.get('attackAngle') or attacker.get('direction') or 0
    power = attacker.get('grabPowerMult') or 1
    damage = round(THROW_DAMAGE * power)
    target['impulseX'] += math.cos(angle) * THROW_KB * power
    target['impulseY'] += math.sin(angle) * THROW_KB * power
    target['health'] = max(0, target['health'] - damage)
    knocked_out = False
    if target['health'] <= 0:
        knocked_out = True
        knockout(room, target, attacker)
        asyncio.create_task(reward_knockout(attacker))
    await broadcast(room, {'type': 'combat', 'event': {'kind': 'throw', 'attackerId': attacker['id'], 'targetId': target['id'], 'angle': angle, 'hit': True, 'damage': damage, 'knockedOut': knocked_out, 'x': (attacker['x'] + target['x']) / 2, 'y': (attacker['y'] + target['y']) / 2 - 42}}, space=attacker.get('space','world'))


async def add_collection(player, kind=None, reason='Collection found'):
    kind = kind if kind in COLLECTION_TYPES else random.choice(COLLECTION_TYPES)
    player['collections'][kind] = player['collections'].get(kind, 0) + 1
    player['records']['itemsFound'] = player['records'].get('itemsFound', 0) + 1
    await send(player['ws'], {'type': 'collection-found', 'kind': kind, 'count': player['collections'][kind], 'message': f'Found {kind}'})
    save_character(player)

async def enter_personal_room(room, player, owner_id):
    owner = room['players'].get(owner_id)
    if not owner:
        await send(player['ws'], {'type':'activity-message','message':'That character is not online.'})
        return
    release(room, player)
    player['space'] = f'room:{owner_id}'
    player['roomOwner'] = owner_id
    player['x'], player['y'] = 460, 350
    player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
    await send(player['ws'], {'type':'space-change','space':player['space'],'ownerId':owner_id,'ownerName':owner['name']})
    await send_world(room, player['ws'])
    await snapshot(room)

async def leave_personal_room(room, player):
    release(room, player)
    player['space'] = 'world'; player['roomOwner'] = None
    player['x'], player['y'] = ROOM_DOOR[0], ROOM_DOOR[1]-100
    player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
    await send(player['ws'], {'type':'space-change','space':'world'})
    await send_world(room, player['ws']); await snapshot(room)

async def interact(room, player):
    if player['knockedOut'] or player.get('grabbedBy'):
        return
    now = time.monotonic()
    if player.get('space','world').startswith('room:'):
        if math.hypot(player['x']-ROOM_EXIT[0], player['y']-ROOM_EXIT[1]) <= INTERACT_RANGE+30:
            await leave_personal_room(room, player)
        else:
            await send(player['ws'], {'type':'activity-message','message':'Use the door at the bottom to leave the room.'})
        return
    event = room.get('event')
    if event and event.get('kind') == 'scavenger':
        for item in event.get('items',[]):
            if item.get('active') and math.hypot(player['x']-item['x'], player['y']-item['y']) <= INTERACT_RANGE:
                item['active'] = False; item['foundBy'] = player['id']
                player['records']['scavengerWins'] += 1
                await add_collection(player, item.get('collection'), 'Scavenger find')
                await grant(player, xp=18, coins=12, reputation=2, reason='Scavenger find')
                await send_world(room)
                return
    nearest_pickup = None
    nearest_distance = INTERACT_RANGE
    for pickup in room['pickups']:
        if not pickup['active']:
            continue
        distance = math.hypot(player['x'] - pickup['x'], player['y'] - pickup['y'])
        if distance < nearest_distance:
            nearest_pickup = pickup
            nearest_distance = distance
    if nearest_pickup:
        nearest_pickup['active'] = False
        nearest_pickup['respawnAt'] = now + 22
        player['missionStats']['pickups'] += 1
        if random.random() < .35: await add_collection(player)
        await grant(player, xp=5, coins=3, reason='Found salvage')
        await send_world(room)
        return

    def close(point, distance=INTERACT_RANGE):
        return math.hypot(player['x'] - point[0], player['y'] - point[1]) <= distance

    if close(ROOM_DOOR):
        await enter_personal_room(room, player, player['id'])
        return
    if close(DELIVERY_START):
        if player.get('job'):
            await send(player['ws'], {'type': 'activity-message', 'message': 'You are already carrying a delivery.'})
        else:
            player['job'] = {'type': 'delivery', 'target': 'School office'}
            await send(player['ws'], {'type': 'activity-message', 'message': 'Delivery started. Take the package to the school office.'})
            await send_progress(player, 'Delivery started')
        return
    if close(DELIVERY_END):
        if player.get('job', {}).get('type') == 'delivery':
            player['job'] = None
            player['missionStats']['deliveries'] += 1
            player['records']['deliveries'] += 1
            await grant(player, xp=30, coins=25, reputation=3, reason='Delivery completed')
        else:
            await send(player['ws'], {'type': 'activity-message', 'message': 'Pick up a package at the convenience store first.'})
        return
    if close(VENDING):
        if player['coins'] < 8:
            await send(player['ws'], {'type': 'activity-message', 'message': 'You need 8 coins for a drink.'})
        else:
            player['coins'] -= 8
            player['health'] = min(player['maxHealth'], player['health'] + 24)
            player['stamina'] = STAMINA_MAX
            await send_progress(player, 'Bought a drink')
            await send(player['ws'], {'type': 'activity-message', 'message': 'Drink used: health and stamina restored.'})
        return
    if close(SHOP):
        await send(player['ws'], {'type': 'shop-open', 'catalog': list(SHOP_CATALOG.values())})
        return
    if close(MISSION_BOARD):
        await send(player['ws'], {'type': 'missions-open', 'missions': MISSION_DEFS, 'stats': player['missionStats'], 'claimed': player['missionClaimed']})
        return
    if close(ARCADE):
        if player['coins'] < 5:
            await send(player['ws'], {'type': 'activity-message', 'message': 'The arcade machine costs 5 coins.'})
        else:
            player['coins'] -= 5
            score = random.randint(80, 1000)
            player['records']['arcadeHigh'] = max(player['records']['arcadeHigh'], score)
            won = score >= 600
            if won:
                await grant(player, xp=12, coins=12, reason='Arcade win')
            else:
                await send_progress(player, 'Arcade played')
                await send(player['ws'], {'type': 'activity-message', 'message': f'Arcade score: {score}.'})
            save_character(player)
        return
    if close(BASKETBALL):
        scored = random.random() < .55
        if scored:
            player['records']['basketballMade'] += 1
            await grant(player, xp=6, coins=3, reason='Basketball score')
            await send(player['ws'], {'type': 'activity-message', 'message': 'Basket made.'})
        else:
            await send(player['ws'], {'type': 'activity-message', 'message': 'The shot missed.'})
        await broadcast(room, {'type': 'activity-effect', 'kind': 'basketball', 'playerId': player['id'], 'success': scored, 'x': BASKETBALL[0], 'y': BASKETBALL[1]})
        return
    await send(player['ws'], {'type': 'activity-message', 'message': 'Nothing nearby to interact with.'})


async def buy_item(room, player, item_id):
    item = SHOP_CATALOG.get(str(item_id or ''))
    if not item:
        return
    if item['kind'] == 'consumable':
        if player['coins'] < item['price']:
            await send(player['ws'], {'type': 'purchase-result', 'ok': False, 'message': 'Not enough coins.'})
            return
        player['coins'] -= item['price']
        player['health'] = min(player['maxHealth'], player['health'] + 24)
        player['stamina'] = STAMINA_MAX
        await send_progress(player, 'Energy drink')
        await send(player['ws'], {'type': 'purchase-result', 'ok': True, 'message': 'Energy restored.'})
        return
    if any(existing['id'] == item['id'] for existing in player['inventory']):
        await send(player['ws'], {'type': 'purchase-result', 'ok': False, 'message': 'You already own that item.'})
        return
    if player['coins'] < item['price']:
        await send(player['ws'], {'type': 'purchase-result', 'ok': False, 'message': 'Not enough coins.'})
        return
    player['coins'] -= item['price']
    owned = {**item, 'builtin': True, 'image': '', 'scale': 1, 'offsetX': 0, 'offsetY': 0}
    player['inventory'].append(owned)
    await send_progress(player, f'Bought {item["name"]}')
    await send(player['ws'], {'type': 'purchase-result', 'ok': True, 'message': f'Bought {item["name"]}.', 'item': owned})
    save_character(player)


async def craft_item(room, player, raw_item):
    item = sanitize_item(raw_item)
    if not item or item['builtin'] or item['slot'] == 'consumable':
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'That custom item is invalid.'})
        return
    if len(player['inventory']) >= 24:
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'Inventory is full.'})
        return
    if any(existing['id'] == item['id'] for existing in player['inventory']):
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'That item already exists.'})
        return
    cost = 30
    if player['coins'] < cost:
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': f'You need {cost} coins to craft it.'})
        return
    player['coins'] -= cost
    player['inventory'].append(item)
    await send_progress(player, f'Crafted {item["name"]}')
    await send(player['ws'], {'type': 'craft-result', 'ok': True, 'message': f'Crafted {item["name"]}.', 'item': item})
    save_character(player)


async def equip_loadout(room, player, raw_loadout):
    loadout = sanitize_loadout(raw_loadout)
    owned_ids = {item['id'] for item in player['inventory']}
    loadout = {slot: item for slot, item in loadout.items() if item['id'] in owned_ids}
    player['loadout'] = loadout
    room['loadouts'][player['id']] = loadout
    await broadcast(room, {'type': 'loadout', 'id': player['id'], 'loadout': loadout})
    await send(player['ws'], {'type': 'loadout-saved', 'loadout': loadout})
    save_character(player)


async def save_room_decor(room, player, raw):
    player['roomDecor'] = sanitize_room_decor(raw, player.get('inventory') or [])
    save_character(player)
    await send(player['ws'], {'type':'room-decor-saved','decor':player['roomDecor']})
    for visitor in connected(room, f"room:{player['id']}"):
        await send_world(room, visitor['ws'])

def start_scavenger(room, now):
    points = random.sample(SCAVENGER_POINTS, 5)
    room['event'] = {'kind':'scavenger','title':'Scavenger Hunt','endsAt':time.time()+180,'items':[{'id':f'h{i}','x':x,'y':y,'active':True,'collection':random.choice(COLLECTION_TYPES)} for i,(x,y) in enumerate(points)]}
    room['nextEventAt'] = now + 360

def simulate(room, dt, now):
    if room.get('event') and time.time() >= room['event'].get('endsAt',0): room['event'] = None
    if not room.get('event') and now >= room.get('nextEventAt', now+60): start_scavenger(room, now)
    for pickup in room['pickups']:
        if not pickup['active'] and now >= pickup['respawnAt']:
            pickup['active'] = True
            pickup['respawnAt'] = 0

    center_players = [p for p in connected(room, 'world') if not p['knockedOut'] and math.hypot(p['x'] - CONTROL_CENTER[0], p['y'] - CONTROL_CENTER[1]) <= CONTROL_RADIUS]
    if len(center_players) == 1:
        owner = center_players[0]
        if room.get('controlOwner') != owner['id']:
            room['controlOwner'] = owner['id']
            room['controlSince'] = now
            room['controlRewardAt'] = now + 10
        elif now >= room.get('controlRewardAt', now + 10):
            room['controlRewardAt'] = now + 10
            asyncio.create_task(grant(owner, xp=8, coins=3, reputation=1, reason='Held the courtyard'))
    elif room.get('controlOwner') is not None:
        room['controlOwner'] = None
        room['controlSince'] = 0
        room['controlRewardAt'] = 0

    for player in connected(room):
        if player['knockedOut'] and now >= player['respawnAt']:
            respawn(player)
        if player['grabbedBy']:
            holder = room['players'].get(player['grabbedBy'])
            if not holder or not holder['connected'] or holder['grabbedTargetId'] != player['id']:
                player['grabbedBy'] = None
            else:
                angle = holder.get('attackAngle') or holder.get('direction') or 0
                player['x'] = clamp(holder['x'] + math.cos(angle) * 42, RADIUS, WORLD_W - RADIUS)
                player['y'] = clamp(holder['y'] + math.sin(angle) * 42, RADIUS, WORLD_H - RADIUS)
                player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
                player['moving'] = player['blocking'] = player['sprinting'] = False
                continue
        control = player['input']
        length = math.hypot(control['x'], control['y'])
        x = control['x'] / length if length > 1 else control['x']
        y = control['y'] / length if length > 1 else control['y']
        can_act = not player['knockedOut']
        player['blocking'] = can_act and control['block'] and player['stamina'] > 1 and not player['grabbedTargetId']
        player['sprinting'] = can_act and not player['blocking'] and control['sprint'] and length > .08 and player['stamina'] > 1 and not player['grabbedTargetId']
        if player['sprinting']:
            player['stamina'] = max(0, player['stamina'] - SPRINT_DRAIN * dt)
            player['lastStaminaUseAt'] = now
        elif now - player['lastStaminaUseAt'] > .36:
            player['stamina'] = min(STAMINA_MAX, player['stamina'] + STAMINA_REGEN * (.45 if player['blocking'] else 1) * dt)
        speed = SPEED * player.get('speedMult', 1)
        if player['sprinting']:
            speed *= SPRINT * player.get('sprintMult', 1)
        if player['blocking']:
            speed *= BLOCK_MOVE
        if player['grabbedTargetId']:
            speed *= .34
        if not can_act:
            speed = 0
        target_vx = x * speed
        target_vy = y * speed
        blend = 1 - math.exp(-(18 if length > .04 else 24) * dt)
        player['moveVx'] += (target_vx - player['moveVx']) * blend
        player['moveVy'] += (target_vy - player['moveVy']) * blend
        player['moving'] = math.hypot(player['moveVx'], player['moveVy']) > 5
        if player['moving'] and not player['blocking']:
            player['direction'] = math.atan2(player['moveVy'], player['moveVx'])
            player['facing'] = 1 if math.cos(player['direction']) >= 0 else -1
        decay = math.exp(-8.5 * dt)
        player['impulseX'] *= decay
        player['impulseY'] *= decay
        player['vx'] = player['moveVx'] + player['impulseX']
        player['vy'] = player['moveVy'] + player['impulseY']
        bound_w, bound_h = (ROOM_W, ROOM_H) if player.get('space','world').startswith('room:') else (WORLD_W, WORLD_H)
        player['x'] = clamp(player['x'] + player['vx'] * dt, RADIUS, bound_w - RADIUS)
        player['y'] = clamp(player['y'] + player['vy'] * dt, RADIUS, bound_h - RADIUS)


async def remove_later(room, player):
    await asyncio.sleep(RECONNECT_GRACE)
    if player['connected']:
        return
    release(room, player)
    save_character(player)
    room['players'].pop(player['id'], None)
    room['sessions'].pop(player['sessionToken'], None)
    for visitor in connected(room, f"room:{player['id']}"):
        visitor['space'] = 'world'; visitor['roomOwner'] = None
        visitor['x'], visitor['y'] = ROOM_DOOR[0], ROOM_DOOR[1]-100
        await send(visitor['ws'], {'type':'space-change','space':'world'})
        await send_world(room, visitor['ws'])
    room['avatars'].pop(player['id'], None)
    room['loadouts'].pop(player['id'], None)
    await broadcast(room, {'type': 'avatar-remove', 'id': player['id']})
    await broadcast(room, {'type': 'loadout-remove', 'id': player['id']})
    await snapshot(room)



async def ws_handler(request):
    ws = web.WebSocketResponse(max_msg_size=12_000_000, heartbeat=25, compress=False)
    await ws.prepare(request)
    state = None
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                if not state:
                    continue
                room, player = state
                data = bytes(msg.data)
                now = time.monotonic()
                # V18 voice frame: A, codec version, flags, sequence, timestamp, 320 mu-law bytes.
                if (len(data) != 329 or data[:2] != b'A\x01' or
                        now - player['lastVoiceAt'] < VOICE_MIN_INTERVAL):
                    continue
                player['lastVoiceAt'] = now
                # Server packet: A, codec version, 16-byte speaker id, then flags/sequence/timestamp/payload.
                packet = b'A\x01' + player['id'].encode('ascii') + data[2:]
                targets = connected(room, player.get('space', 'world'))
                for other in targets:
                    if other['ws'] is ws or other['ws'].closed:
                        continue
                    try:
                        await asyncio.wait_for(other['ws'].send_bytes(packet), timeout=0.20)
                    except Exception:
                        pass
                continue
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                message = json.loads(msg.data)
            except Exception:
                continue
            if not state:
                if message.get('type') not in ('enter-world', 'create-room', 'join-room'):
                    await send(ws, {'type': 'error', 'message': 'Enter the shared world first.'}); continue
                if int(message.get('protocol') or 0) != PROTOCOL or int(message.get('build') or 0) != BUILD:
                    await send(ws, {'type':'version-mismatch','build':BUILD,'protocol':PROTOCOL}); break
                room = rooms.setdefault(MAIN_WORLD_CODE, make_room(MAIN_WORLD_CODE))
                character_id = clean_character_id(message.get('characterId')) or secrets.token_urlsafe(18).replace('-','').replace('_','')[:16]
                character_secret = token(message.get('characterSecret')) or secrets.token_urlsafe(24)
                stored, auth_ok = load_character(character_id, character_secret)
                if not auth_ok:
                    await send(ws, {'type':'character-auth-failed'}); break
                existing = room['players'].get(character_id)
                if existing and existing.get('connected'):
                    old_ws = existing.get('ws')
                    existing['connected'] = False; existing['ws'] = None
                    if old_ws:
                        await send(old_ws, {'type':'duplicate-login'})
                        try: await old_ws.close()
                        except Exception: pass
                source = stored or {}
                player = existing if existing and not existing.get('connected') else make_player(
                    source.get('name') or message.get('name'), source.get('profile') or message.get('profile'), source.get('progress') or message.get('progress'),
                    source.get('inventory') or message.get('inventory'), source.get('loadout') or message.get('loadout'), token(message.get('sessionToken')) or secrets.token_urlsafe(24),
                    character_id, character_secret, source.get('collections') or message.get('collections'), source.get('records') or message.get('records'), source.get('roomDecor') or message.get('roomDecor'))
                player['id'] = character_id; player['characterId'] = character_id; player['characterSecret'] = character_secret; player['roomRef'] = room
                if existing and player is existing:
                    if player.get('remove_task'): player['remove_task'].cancel(); player['remove_task']=None
                room['players'][character_id] = player; room['sessions'][player['sessionToken']] = character_id
                player['connected']=True; player['ws']=ws; player['input']=sanitize_input(message.get('input') or {})
                avatar = sanitize_avatar(source.get('avatar') or message.get('avatar'))
                if avatar: room['avatars'][character_id]=avatar
                room['loadouts'][character_id]=player.get('loadout') or {}
                state=(room,player)
                save_character(player)
                await send(ws, {'type':'welcome','id':character_id,'roomCode':MAIN_WORLD_CODE,'sessionToken':player['sessionToken'],'build':BUILD,'protocol':PROTOCOL,'characterId':character_id,'characterSecret':character_secret,'character':character_payload(player,room),'singleWorld':True})
                await send(ws, {'type':'avatar-batch','avatars':room['avatars']}); await send(ws, {'type':'loadout-batch','loadouts':room['loadouts']})
                await send_world(room,ws); await send_progress(player,'Connected'); await snapshot(room)
                continue

            room, player = state
            message_type = message.get('type')
            if message_type == 'input':
                player['input'] = sanitize_input(message)
            elif message_type == 'punch':
                await punch(room, player)
            elif message_type == 'grab-start':
                await grab(room, player)
            elif message_type == 'throw':
                await throw(room, player)
            elif message_type == 'interact':
                await interact(room, player)
            elif message_type == 'buy-item':
                await buy_item(room, player, message.get('itemId'))
            elif message_type == 'craft-item':
                await craft_item(room, player, message.get('item'))
            elif message_type == 'equip-loadout':
                await equip_loadout(room, player, message.get('loadout'))
            elif message_type == 'visit-room':
                await enter_personal_room(room, player, clean_character_id(message.get('characterId')))
            elif message_type == 'leave-room':
                await leave_personal_room(room, player)
            elif message_type == 'save-room-decor':
                await save_room_decor(room, player, message.get('decor'))
            elif message_type == 'profile':
                apply_profile(player, message.get('profile'), False)
                save_character(player)
                await snapshot(room)
            elif message_type == 'progress-sync':
                await send_progress(player, 'Progress synchronized')
            elif message_type == 'avatar':
                avatar = sanitize_avatar(message.get('avatar'))
                if avatar:
                    room['avatars'][player['id']] = avatar
                    await broadcast(room, {'type': 'avatar', 'id': player['id'], 'avatar': avatar})
                    save_character(player)
            elif message_type == 'ping':
                await send(ws, {'type': 'pong', 'now': int(time.time() * 1000)})
    finally:
        if state:
            room, player = state
            if player.get('ws') is ws:
                player['connected'] = False
                player['ws'] = None
                player['input'] = sanitize_input({})
                player['moving'] = player['blocking'] = player['sprinting'] = False
                release(room, player)
                save_character(player)
                await snapshot(room)
                player['remove_task'] = asyncio.create_task(remove_later(room, player))
    return ws


async def game_loop(app):
    last = time.monotonic()
    snapshot_accumulator = 0
    world_accumulator = 0
    save_accumulator = 0
    while True:
        await asyncio.sleep(1 / 60)
        now = time.monotonic()
        dt = min(now - last, .05)
        last = now
        snapshot_accumulator += dt
        world_accumulator += dt
        save_accumulator += dt
        for room in list(rooms.values()):
            simulate(room, dt, now)
        if snapshot_accumulator >= 1 / 30:
            snapshot_accumulator = 0
            for room in list(rooms.values()):
                await snapshot(room)
        if world_accumulator >= 2:
            world_accumulator = 0
            for room in list(rooms.values()): await send_world(room)
        if save_accumulator >= 15:
            save_accumulator = 0
            for room in list(rooms.values()):
                for player in room['players'].values(): save_character(player)


async def health(request):
    response = web.json_response({
        'ok': True,
        'service': 'green-floor-v19',
        'rooms': len(rooms),
        'players': sum(len(connected(room)) for room in rooms.values()),
        'build': BUILD,
        'voice': 'mulaw-websocket-relay', 'singleWorld': True, 'automaticConnection': True, 'roomCodes': False, 'persistence': 'sqlite',
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-store'
    return response


async def startup(app):
    db_connect().close()
    rooms[MAIN_WORLD_CODE] = make_room(MAIN_WORLD_CODE)
    app['loop_task'] = asyncio.create_task(game_loop(app))


async def cleanup(app):
    app['loop_task'].cancel()


app = web.Application(client_max_size=12_000_000)
app.router.add_get('/', health)
app.router.add_get('/health', health)
app.router.add_get('/ws', ws_handler)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.getenv('PORT', '10000')))

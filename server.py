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

BUILD = 24
PROTOCOL = 24
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
CONTROL_CENTER = (1600, 1100)
CONTROL_RADIUS = 310
PASSIVE_COIN_INTERVAL = 60.0
PASSIVE_COIN_REWARD = 2
KO_COIN_REWARD = 12
MAX_WEAPON_LEVEL = 30
MAX_WEAPON_MASTERY = 15
MAX_ATTRIBUTE_LEVEL = 25
ADMIN_CODE = os.getenv("ADMIN_CODE", "1279")
ROOM_ART_MAX = 900000
DB_PATH = os.getenv("DATABASE_PATH", "green_floor_v17.db")

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


def load_public_character(character_id):
    if not character_id:
        return None
    with db_connect() as conn:
        row = conn.execute("SELECT data FROM characters WHERE character_id=?", (character_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row['data'])
    except Exception:
        return None


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


def sanitize_attributes(value):
    value = value if isinstance(value, dict) else {}
    return {
        key: int(clamp(float(value.get(key) or 0), 0, MAX_ATTRIBUTE_LEVEL))
        for key in ('health', 'speed', 'reach', 'melee', 'weapon')
    }


def sanitize_progress(v):
    v = v if isinstance(v, dict) else {}
    stats = v.get('missionStats') if isinstance(v.get('missionStats'), dict) else {}
    skill_points = None if 'skillPoints' not in v else int(clamp(float(v.get('skillPoints') or 0), 0, 1000))
    return {
        'xp': int(clamp(float(v.get('xp') or 0), 0, 250000)),
        'coins': int(clamp(float(v.get('coins') or 35), 0, 250000)),
        'reputation': int(clamp(float(v.get('reputation') or 0), 0, 100000)),
        'skillPoints': skill_points,
        'attributes': sanitize_attributes(v.get('attributes')),
        'missionStats': {
            'kos': int(clamp(float(stats.get('kos') or 0), 0, 100000)),
            'minutes': int(clamp(float(stats.get('minutes') or 0), 0, 1000000)),
        },
        'missionClaimed': {},
        'careerClaimed': {str(k): True for k, val in (v.get('careerClaimed') if isinstance(v.get('careerClaimed'), dict) else {}).items() if val},
        'dailyClaimDay': str(v.get('dailyClaimDay') or '')[:16],
        'loginStreak': int(clamp(float(v.get('loginStreak') or 0), 0, 9999)),
        'bestLoginStreak': int(clamp(float(v.get('bestLoginStreak') or 0), 0, 9999)),
        'selectedTitle': (''.join(c for c in str(v.get('selectedTitle') or '') if ord(c) >= 32 and c not in '<>').strip()[:24]),
        'nameplateTheme': str(v.get('nameplateTheme') or 'classic')[:16] if str(v.get('nameplateTheme') or 'classic') in ('classic','pink','blue','red','gold','shadow') else 'classic',
        'accentColor': str(v.get('accentColor') or '#b9f6c8')[:7] if str(v.get('accentColor') or '').startswith('#') else '#b9f6c8',
    }

def level_for_xp(xp):
    level = 1
    remaining = max(0, int(xp))
    while level < 100:
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
    name = clean_name(item.get('name') or 'Custom Weapon')[:24]
    if not item_id:
        return None
    image = str(item.get('image') or '')
    if not image.startswith('data:image/png;base64,') or len(image) > 320000:
        return None
    return {
        'id': item_id,
        'name': name,
        'slot': 'weapon',
        'kind': 'weapon',
        'image': image,
        'builtin': False,
        'level': int(clamp(float(item.get('level') or 1), 1, MAX_WEAPON_LEVEL)),
        'masteryRank': int(clamp(float(item.get('masteryRank') or 1), 1, MAX_WEAPON_MASTERY)),
        'masteryXp': int(clamp(float(item.get('masteryXp') or 0), 0, 99999)),
        'hits': int(clamp(float(item.get('hits') or 0), 0, 999999)),
        'kos': int(clamp(float(item.get('kos') or 0), 0, 999999)),
        'path': str(item.get('path') or 'balanced') if str(item.get('path') or 'balanced') in ('balanced','power','swift','reach') else 'balanced',
        'trail': str(item.get('trail') or 'slash') if str(item.get('trail') or 'slash') in ('none','slash','spark','glow') else 'slash',
        'tint': str(item.get('tint') or '#ffffff')[:7] if str(item.get('tint') or '').startswith('#') else '#ffffff',
        'rotation': clamp(float(item.get('rotation') or 0), -180, 180),
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
    item = sanitize_item(value.get('weapon'))
    return {'weapon': item} if item else {}

def sanitize_collections(value):
    return {}

def sanitize_records(value):
    value = value if isinstance(value, dict) else {}
    return {
        'kos': int(clamp(float(value.get('kos') or 0), 0, 100000)),
        'minutesOnline': int(clamp(float(value.get('minutesOnline') or 0), 0, 1000000)),
        'coinsEarned': int(clamp(float(value.get('coinsEarned') or 0), 0, 10000000)),
        'weaponHits': int(clamp(float(value.get('weaponHits') or 0), 0, 10000000)),
        'weaponKos': int(clamp(float(value.get('weaponKos') or 0), 0, 1000000)),
        'skillPointsSpent': int(clamp(float(value.get('skillPointsSpent') or 0), 0, 10000)),
        'currentKoStreak': int(clamp(float(value.get('currentKoStreak') or 0), 0, 100000)),
        'bestKoStreak': int(clamp(float(value.get('bestKoStreak') or 0), 0, 100000)),
        'blocks': int(clamp(float(value.get('blocks') or 0), 0, 1000000)),
    }

def sanitize_room_decor(value, inventory=None):
    return []

def sanitize_room_art(value):
    value = str(value or '')
    if not value:
        return ''
    if not value.startswith('data:image/png;base64,') or len(value) > ROOM_ART_MAX:
        return ''
    return value

def character_payload(player, room=None):
    room = room or player.get('roomRef')
    avatar = room.get('avatars', {}).get(player['id']) if room else None
    return {
        'characterId': player.get('characterId'), 'name': player.get('name'),
        'profile': player.get('profileSummary') or {}, 'avatar': avatar,
        'progress': {k: player.get(k) for k in ('xp','coins','reputation','skillPoints','attributes','missionStats','missionClaimed','careerClaimed','dailyClaimDay','loginStreak','bestLoginStreak','selectedTitle','nameplateTheme','accentColor')},
        'inventory': player.get('inventory') or [], 'loadout': player.get('loadout') or {},
        'collections': {}, 'records': player.get('records') or {},
        'roomDecor': [], 'roomArt': player.get('roomArt') or '',
        'title': player.get('title') or 'New Student',
    }

def save_character(player):
    if player.get('characterId') and player.get('characterSecret'):
        store_character_payload(player['characterId'], player['characterSecret'], character_payload(player))

def apply_attributes(player, preserve_health=True):
    profile = player.get('profileSummary') or sanitize_profile({})
    attributes = sanitize_attributes(player.get('attributes'))
    old_max = float(player.get('maxHealth') or profile['maxHealth'])
    old_health = float(player.get('health') or old_max)
    player['attributes'] = attributes
    health_milestones = attributes['health'] // 5
    speed_milestones = attributes['speed'] // 5
    reach_milestones = attributes['reach'] // 5
    melee_milestones = attributes['melee'] // 5
    weapon_milestones = attributes['weapon'] // 5
    player['maxHealth'] = round(profile['maxHealth'] + attributes['health'] * 5 + health_milestones * 3)
    player['speedMult'] = clamp(profile['speedMult'] * (1 + attributes['speed'] * .0125 + speed_milestones * .008), .75, 1.70)
    player['sprintMult'] = clamp(profile['sprintMult'] * (1 + attributes['speed'] * .0075 + speed_milestones * .006), .80, 1.60)
    player['reachMult'] = clamp(profile['reachMult'] * (1 + attributes['reach'] * .0125 + reach_milestones * .008), .75, 1.70)
    player['grabRangeMult'] = clamp(profile['grabRangeMult'] * (1 + attributes['reach'] * .009 + reach_milestones * .006), .75, 1.65)
    player['punchDamageMult'] = clamp(profile['punchDamageMult'] * (1 + attributes['melee'] * .035 + melee_milestones * .018), .70, 2.6)
    player['weaponDamageMult'] = 1 + attributes['weapon'] * .045 + weapon_milestones * .022
    player['weaponReachMult'] = 1 + attributes['weapon'] * .018 + weapon_milestones * .01
    if preserve_health:
        ratio = clamp(old_health / max(1, old_max), 0, 1)
        player['health'] = clamp(player['maxHealth'] * ratio, 0, player['maxHealth'])
    else:
        player['health'] = player['maxHealth']


def apply_profile(player, profile, reset=False):
    profile = sanitize_profile(profile)
    player['profileSummary'] = profile
    for key in ('heritage','heightLabel','buildLabel','style','styleDescription','grabPowerMult','attackSpeedMult','sizeScale'):
        player[key] = profile[key]
    apply_attributes(player, preserve_health=not reset)


def apply_progress(player, raw):
    progress = sanitize_progress(raw)
    player.update(progress)
    level, current, needed = level_for_xp(player['xp'])
    player['level'] = level
    player['levelXp'] = current
    player['levelXpNeeded'] = needed
    spent = sum(sanitize_attributes(player.get('attributes')).values())
    if player.get('skillPoints') is None:
        player['skillPoints'] = max(0, level - 1 - spent)
    else:
        player['skillPoints'] = max(0, int(player.get('skillPoints') or 0))
    earned_points = max(0, level - 1)
    accounted_points = spent + player['skillPoints']
    if accounted_points < earned_points:
        player['skillPoints'] += earned_points - accounted_points
    apply_attributes(player, preserve_health=True)


def make_room(code):
    return {
        'code': code,
        'players': {},
        'sessions': {},
        'avatars': {},
        'loadouts': {},
        'createdAt': time.time(),
    }

def make_player(name, profile, progress, inventory, loadout, session, character_id, character_secret, collections=None, records=None, room_decor=None, room_art=None):
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
        'lastPunchAt': -10,
        'attackHand': 'right', 'attackAngle': 0,
        'impulseX': 0, 'impulseY': 0,
        'grabbedTargetId': None, 'grabbedBy': None,
        'space': 'world', 'roomOwner': None,
        'title': 'New Student',
        'inventory': sanitize_inventory(inventory),
        'connected': False, 'ws': None, 'input': sanitize_input({}),
        'sessionToken': session, 'remove_task': None,
        'lastVoiceAt': 0.0, 'lastBoomAt': 0.0,
        'lastInputAt': time.monotonic(), 'isAdmin': False, 'frozen': False,
        'records': sanitize_records(records),
        'roomArt': sanitize_room_art(room_art), 'roomRef': None,
        'nextPassiveCoinAt': time.monotonic() + PASSIVE_COIN_INTERVAL,
    }
    apply_profile(player, profile, True)
    apply_progress(player, progress)
    player['loadout'] = sanitize_loadout(loadout)
    update_title(player)
    return player

def public_player(player):
    excluded = {'ws', 'input', 'sessionToken', 'remove_task', 'connected', 'inventory', 'loadout', 'roomArt', 'lastVoiceAt', 'lastBoomAt', 'lastInputAt', 'isAdmin', 'characterSecret', 'roomRef', 'nextPassiveCoinAt'}
    result = {k: v for k, v in player.items() if k not in excluded}
    result['inventoryCount'] = len(player.get('inventory') or [])
    weapon = (player.get('loadout') or {}).get('weapon')
    result['weaponLevel'] = int(weapon.get('level') or 0) if weapon else 0
    result['weaponMasteryRank'] = int(weapon.get('masteryRank') or 0) if weapon else 0
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
            'online': all_online,
            'space': receiver.get('space','world'),
        })

async def send_world(room, ws=None):
    async def room_data(owner_id):
        owner = room['players'].get(owner_id)
        if owner:
            return {'ownerId': owner_id, 'ownerName': owner['name'], 'art': owner.get('roomArt') or ''}
        stored = load_public_character(owner_id) or {}
        return {'ownerId': owner_id, 'ownerName': clean_name(stored.get('name') or 'Friend'), 'art': sanitize_room_art(stored.get('roomArt'))}

    async def packet_for(player):
        packet = {
            'type': 'world-state',
            'pickups': [], 'event': None, 'zones': {}, 'catalog': [],
            'space': player.get('space','world'),
        }
        if player.get('space','world').startswith('room:'):
            owner_id = player.get('roomOwner') or player.get('space','world').split(':',1)[1]
            packet['room'] = await room_data(owner_id)
        return packet
    if ws:
        player = next((p for p in connected(room) if p['ws'] is ws), None)
        if player:
            await send(ws, await packet_for(player))
    else:
        for player in connected(room):
            await send(player['ws'], await packet_for(player))


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
            'skillPoints': player.get('skillPoints', 0),
            'attributes': player.get('attributes') or sanitize_attributes({}),
            'missionStats': player['missionStats'],
            'missionClaimed': {},
            'careerClaimed': player.get('careerClaimed') or {},
            'dailyClaimDay': player.get('dailyClaimDay') or '',
            'loginStreak': player.get('loginStreak') or 0,
            'bestLoginStreak': player.get('bestLoginStreak') or 0,
            'selectedTitle': player.get('selectedTitle') or '',
            'unlockedTitles': unlocked_titles(player),
            'nameplateTheme': player.get('nameplateTheme') or 'classic',
            'accentColor': player.get('accentColor') or '#b9f6c8',
            'job': None, 'collections': {}, 'records': player.get('records') or {}, 'title': player.get('title','New Student'),
        },
        'inventory': player.get('inventory') or [],
        'loadout': player.get('loadout') or {},
        'reason': reason,
    })
    save_character(player)

async def check_missions(player):
    return

def weapon_mastery_needed(rank):
    rank = int(clamp(rank, 1, MAX_WEAPON_MASTERY))
    return 24 + rank * 16


def unlocked_titles(player):
    level = int(player.get('level') or 1)
    rep = int(player.get('reputation') or 0)
    kos = int((player.get('records') or {}).get('kos') or 0)
    best_streak = int((player.get('records') or {}).get('bestKoStreak') or 0)
    weapons = player.get('inventory') or []
    mastery = max([int(w.get('masteryRank') or 1) for w in weapons] or [0])
    titles = ['New Student']
    if level >= 5 or rep >= 25: titles.append('Known Face')
    if kos >= 10 or rep >= 100: titles.append('Fighter')
    if best_streak >= 5: titles.append('Unshaken')
    if level >= 30 or rep >= 350: titles.append('Veteran')
    if mastery >= 10: titles.append('Weapon Master')
    if level >= 60 or rep >= 750: titles.append('School Legend')
    if level >= 90 and mastery >= 15: titles.append('Living Legend')
    return titles


def update_title(player):
    titles = unlocked_titles(player)
    selected = clean_name(player.get('selectedTitle') or '')[:24]
    if selected in titles:
        player['title'] = selected
    else:
        player['title'] = titles[-1]
        player['selectedTitle'] = player['title']


async def check_career_milestones(player):
    claimed = player.setdefault('careerClaimed', {})
    records = player.get('records') or {}
    attributes = sanitize_attributes(player.get('attributes'))
    weapons = player.get('inventory') or []
    best_level = max([int(w.get('level') or 1) for w in weapons] or [0])
    best_mastery = max([int(w.get('masteryRank') or 1) for w in weapons] or [0])
    conditions = [
        ('level5', player.get('level', 1) >= 5, 45, 8, 'Reached level 5'),
        ('level10', player.get('level', 1) >= 10, 80, 15, 'Reached level 10'),
        ('level20', player.get('level', 1) >= 20, 150, 30, 'Reached level 20'),
        ('level40', player.get('level', 1) >= 40, 300, 60, 'Reached level 40'),
        ('level60', player.get('level', 1) >= 60, 500, 90, 'Reached level 60'),
        ('level80', player.get('level', 1) >= 80, 800, 140, 'Reached level 80'),
        ('ko10', int(records.get('kos') or 0) >= 10, 70, 15, '10 knockouts'),
        ('ko25', int(records.get('kos') or 0) >= 25, 140, 30, '25 knockouts'),
        ('ko50', int(records.get('kos') or 0) >= 50, 280, 55, '50 knockouts'),
        ('streak5', int(records.get('bestKoStreak') or 0) >= 5, 120, 25, '5 knockout streak'),
        ('minutes30', int(records.get('minutesOnline') or 0) >= 30, 60, 8, '30 minutes online'),
        ('minutes120', int(records.get('minutesOnline') or 0) >= 120, 180, 25, '120 minutes online'),
        ('minutes300', int(records.get('minutesOnline') or 0) >= 300, 400, 60, '300 minutes online'),
        ('streak7', int(player.get('bestLoginStreak') or 0) >= 7, 180, 25, '7 day login streak'),
        ('weapon5', best_level >= 5, 55, 8, 'Weapon level 5'),
        ('weapon10', best_level >= 10, 110, 18, 'Weapon level 10'),
        ('weapon20', best_level >= 20, 240, 40, 'Weapon level 20'),
        ('weapon30', best_level >= 30, 500, 80, 'Weapon level 30'),
        ('mastery5', best_mastery >= 5, 110, 20, 'Weapon mastery 5'),
        ('mastery10', best_mastery >= 10, 260, 55, 'Weapon mastery 10'),
        ('mastery15', best_mastery >= 15, 520, 100, 'Weapon mastery 15'),
        ('skills10', sum(attributes.values()) >= 10, 80, 12, 'Spent 10 skill points'),
        ('skills30', sum(attributes.values()) >= 30, 180, 28, 'Spent 30 skill points'),
        ('skills60', sum(attributes.values()) >= 60, 420, 70, 'Spent 60 skill points'),
    ]
    unlocked = []
    total_coins = 0
    total_rep = 0
    for key, ready, coins, rep, label in conditions:
        if ready and not claimed.get(key):
            claimed[key] = True
            total_coins += coins
            total_rep += rep
            unlocked.append(label)
    if unlocked:
        player['coins'] = min(250000, int(player.get('coins') or 0) + total_coins)
        player['reputation'] = min(100000, int(player.get('reputation') or 0) + total_rep)
        records['coinsEarned'] = int(records.get('coinsEarned') or 0) + total_coins
        player['records'] = records
        update_title(player)
        await send(player['ws'], {'type':'career-reward','unlocked':unlocked,'coins':total_coins,'reputation':total_rep})
    return bool(unlocked)


async def grant_daily_login(player):
    day = time.strftime('%Y-%m-%d', time.gmtime())
    previous = str(player.get('dailyClaimDay') or '')
    if previous == day:
        return False
    yesterday = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400))
    streak = int(player.get('loginStreak') or 0) + 1 if previous == yesterday else 1
    player['dailyClaimDay'] = day
    player['loginStreak'] = streak
    player['bestLoginStreak'] = max(int(player.get('bestLoginStreak') or 0), streak)
    coins = min(70, 20 + streak * 5)
    rep = 3 + (5 if streak % 7 == 0 else 0)
    bonus_sp = 1 if streak % 7 == 0 else 0
    player['coins'] = min(250000, int(player.get('coins') or 0) + coins)
    player['reputation'] = min(100000, int(player.get('reputation') or 0) + rep)
    player['skillPoints'] = int(player.get('skillPoints') or 0) + bonus_sp
    player['records']['coinsEarned'] = int(player['records'].get('coinsEarned') or 0) + coins
    update_title(player)
    await send(player['ws'], {'type':'daily-reward','streak':streak,'coins':coins,'reputation':rep,'skillPoints':bonus_sp})
    await check_career_milestones(player)
    save_character(player)
    return True


async def award_weapon_mastery(room, player, xp, knockout=False):
    weapon = (player.get('loadout') or {}).get('weapon')
    if not weapon:
        return
    owned = next((item for item in player.get('inventory', []) if item.get('id') == weapon.get('id')), None)
    if not owned:
        return
    old_rank = int(owned.get('masteryRank') or 1)
    rank = old_rank
    current = int(owned.get('masteryXp') or 0) + max(0, int(xp))
    while rank < MAX_WEAPON_MASTERY:
        needed = weapon_mastery_needed(rank)
        if current < needed:
            break
        current -= needed
        rank += 1
    if rank >= MAX_WEAPON_MASTERY:
        current = 0
    owned['masteryRank'] = rank
    owned['masteryXp'] = current
    owned['hits'] = int(owned.get('hits') or 0) + 1
    if knockout:
        owned['kos'] = int(owned.get('kos') or 0) + 1
    records = player.get('records') or {}
    records['weaponHits'] = int(records.get('weaponHits') or 0) + 1
    if knockout:
        records['weaponKos'] = int(records.get('weaponKos') or 0) + 1
    player['records'] = records
    player['loadout']['weapon'] = owned
    room['loadouts'][player['id']] = player['loadout']
    await broadcast(room, {'type':'loadout','id':player['id'],'loadout':player['loadout']})
    if rank > old_rank:
        await send(player['ws'], {'type':'weapon-mastery','item':owned,'rankUp':True,'message':f'{owned["name"]} mastery reached rank {rank}.'})
    else:
        await send(player['ws'], {'type':'weapon-mastery','item':owned,'rankUp':False})
    await check_career_milestones(player)
    save_character(player)


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
    levels_gained = max(0, player['level'] - old_level)
    bonus_coins = 0
    bonus_rep = 0
    if levels_gained:
        player['skillPoints'] = int(player.get('skillPoints') or 0) + levels_gained
        for gained_level in range(old_level + 1, player['level'] + 1):
            if gained_level % 5 == 0: bonus_coins += 25
            if gained_level % 10 == 0: bonus_rep += 8
        player['coins'] += bonus_coins
        player['reputation'] += bonus_rep
        player['records']['coinsEarned'] = int(player['records'].get('coinsEarned') or 0) + bonus_coins
    update_title(player)
    await check_missions(player)
    await check_career_milestones(player)
    await send(player['ws'], {
        'type': 'reward',
        'xp': int(xp), 'coins': int(coins), 'reputation': int(reputation),
        'reason': reason,
        'level': player['level'], 'levelUp': player['level'] > old_level,
        'skillPointsGained': levels_gained, 'levelBonusCoins': bonus_coins, 'levelBonusReputation': bonus_rep,
    })
    await send_progress(player, reason)


def knockout(room, target, attacker):
    target['knockedOut'] = True
    target['respawnAt'] = time.monotonic() + KO_TIME
    target['blocking'] = target['sprinting'] = False
    target_records = target.get('records') or {}
    target_records['currentKoStreak'] = 0
    target['records'] = target_records
    release(room, target)
    attacker['score'] += 1


async def reward_knockout(attacker):
    attacker['missionStats']['kos'] = attacker['missionStats'].get('kos', 0) + 1
    records = attacker.get('records') or {}
    records['kos'] = int(records.get('kos') or 0) + 1
    records['currentKoStreak'] = int(records.get('currentKoStreak') or 0) + 1
    records['bestKoStreak'] = max(int(records.get('bestKoStreak') or 0), records['currentKoStreak'])
    streak = records['currentKoStreak']
    streak_bonus = 0 if streak < 3 else min(24, streak * 2)
    streak_rep = 2 if streak >= 5 else 0
    records['coinsEarned'] = int(records.get('coinsEarned') or 0) + KO_COIN_REWARD + streak_bonus
    attacker['records'] = records
    reason = f'Knockout streak x{streak}' if streak >= 3 else 'Knockout'
    await grant(attacker, xp=22 + min(18, streak * 2), coins=KO_COIN_REWARD + streak_bonus, reputation=3 + streak_rep, reason=reason)

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
    return False

async def punch(room, attacker):
    now = time.monotonic()
    weapon = (attacker.get('loadout') or {}).get('weapon')
    weapon_level = int(weapon.get('level') or 0) if weapon else 0
    weapon_mastery = int(weapon.get('masteryRank') or 1) if weapon else 0
    weapon_path = str(weapon.get('path') or 'balanced') if weapon else 'balanced'
    path_damage = {'balanced':1.0,'power':1.16,'swift':0.90,'reach':0.95}.get(weapon_path,1.0)
    path_speed = {'balanced':1.0,'power':0.94,'swift':1.20,'reach':0.98}.get(weapon_path,1.0)
    path_reach = {'balanced':1.0,'power':0.98,'swift':0.96,'reach':1.15}.get(weapon_path,1.0)
    mastery_speed = (1 + max(0, weapon_mastery - 1) * .012) * path_speed if weapon else 1
    cooldown = PUNCH_COOLDOWN / ((attacker.get('attackSpeedMult') or 1) * mastery_speed)
    if attacker['knockedOut'] or attacker['blocking'] or attacker['grabbedBy'] or attacker['grabbedTargetId'] or attacker['stamina'] < PUNCH_COST or now - attacker['lastPunchAt'] < cooldown:
        return
    attacker['lastPunchAt'] = now
    attacker['sprinting'] = False
    attacker['stamina'] = max(0, attacker['stamina'] - PUNCH_COST)
    attacker['lastStaminaUseAt'] = now
    attacker['attackHand'] = 'right' if weapon else ('left' if attacker['attackHand'] == 'right' else 'right')
    lock_multiplier = (attacker.get('reachMult') or 1) * ((attacker.get('weaponReachMult') or 1) if weapon else 1)
    target, distance = nearest(room, attacker, PUNCH_LOCK * lock_multiplier)
    angle = 0 if attacker['facing'] >= 0 else math.pi
    if target:
        angle = math.atan2(target['y'] - attacker['y'], target['x'] - attacker['x'])
        attacker['direction'] = angle
        attacker['facing'] = 1 if math.cos(angle) >= 0 else -1
    attacker['attackAngle'] = angle
    mastery_reach = 1 + max(0, weapon_mastery - 1) * .008
    hit_range = (PUNCH_RANGE + weapon_level * 5) * lock_multiplier * mastery_reach * path_reach
    hit = bool(target and distance <= hit_range)
    blocked = False
    knocked_out = False
    if weapon:
        mastery_damage = 1 + max(0, weapon_mastery - 1) * .02
        damage = round((PUNCH_DAMAGE + weapon_level * 2) * (attacker.get('weaponDamageMult') or 1) * mastery_damage * path_damage)
    else:
        damage = round(PUNCH_DAMAGE * (attacker.get('punchDamageMult') or 1))
    knockback = PUNCH_KB * (.84 + (attacker.get('grabPowerMult') or 1) * .16)
    impact_x = attacker['x'] + math.cos(angle) * 88
    impact_y = attacker['y'] + math.sin(angle) * 88 - 44
    if hit:
        if target['blocking'] and target['stamina'] > 0:
            blocked = True
            target['stamina'] = max(0, target['stamina'] - BLOCK_COST)
            target['records']['blocks'] = int(target['records'].get('blocks') or 0) + 1
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
        if weapon:
            asyncio.create_task(award_weapon_mastery(room, attacker, 12 if knocked_out else (4 if blocked else 6), knockout=knocked_out))
    await broadcast(room, {
        'type': 'combat',
        'event': {
            'kind': 'weapon-swing' if weapon else 'punch', 'attackerId': attacker['id'],
            'targetId': target['id'] if target else None,
            'angle': angle, 'hand': attacker['attackHand'],
            'hit': hit, 'blocked': blocked,
            'damage': damage if hit else 0,
            'knockedOut': knocked_out,
            'x': impact_x, 'y': impact_y, 'weaponLevel': weapon_level,
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


async def add_collection(player, kind=None, reason=''):
    return

async def enter_personal_room(room, player, owner_id):
    owner_id = clean_character_id(owner_id)
    owner = room['players'].get(owner_id)
    stored = load_public_character(owner_id) if not owner else None
    if not owner and not stored:
        await send(player['ws'], {'type':'activity-message','message':'That room could not be loaded.'})
        return
    owner_name = owner['name'] if owner else clean_name(stored.get('name') or 'Friend')
    release(room, player)
    player['space'] = f'room:{owner_id}'
    player['roomOwner'] = owner_id
    player['x'], player['y'] = 460, 350
    player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
    await send(player['ws'], {'type':'space-change','space':player['space'],'ownerId':owner_id,'ownerName':owner_name})
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
    return

async def buy_item(room, player, item_id):
    await send(player['ws'], {'type':'purchase-result','ok':False,'message':'The shop was removed.'})

async def craft_item(room, player, raw_item):
    item = sanitize_item(raw_item)
    if not item:
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'That PNG weapon is invalid.'})
        return
    if len(player['inventory']) >= 24:
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'Weapon inventory is full.'})
        return
    if any(existing['id'] == item['id'] for existing in player['inventory']):
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': 'That weapon already exists.'})
        return
    cost = 30
    if player['coins'] < cost:
        await send(player['ws'], {'type': 'craft-result', 'ok': False, 'message': f'You need {cost} coins to create it.'})
        return
    item['level'] = 1
    player['coins'] -= cost
    player['inventory'].append(item)
    await send_progress(player, f'Created {item["name"]}')
    await send(player['ws'], {'type': 'craft-result', 'ok': True, 'message': f'Created {item["name"]}.', 'item': item})
    save_character(player)

async def equip_loadout(room, player, raw_loadout):
    loadout = sanitize_loadout(raw_loadout)
    owned = {item['id']: item for item in player['inventory']}
    weapon = loadout.get('weapon')
    if weapon and weapon['id'] in owned:
        loadout = {'weapon': owned[weapon['id']]}
    else:
        loadout = {}
    player['loadout'] = loadout
    room['loadouts'][player['id']] = loadout
    await broadcast(room, {'type': 'loadout', 'id': player['id'], 'loadout': loadout})
    await send(player['ws'], {'type': 'loadout-saved', 'loadout': loadout})
    save_character(player)

async def save_room_decor(room, player, raw):
    return

async def save_room_art(room, player, raw):
    art = sanitize_room_art(raw)
    if raw and not art:
        await send(player['ws'], {'type':'room-art-saved','ok':False,'message':'Room drawing is too large.'})
        return
    player['roomArt'] = art
    save_character(player)
    await send(player['ws'], {'type':'room-art-saved','ok':True,'art':art})
    for visitor in connected(room, f"room:{player['id']}"):
        await send_world(room, visitor['ws'])

async def upgrade_weapon(room, player, item_id):
    item_id = str(item_id or '')
    weapon = next((item for item in player.get('inventory', []) if item.get('id') == item_id), None)
    if not weapon:
        await send(player['ws'], {'type':'weapon-upgrade','ok':False,'message':'Weapon not found.'})
        return
    level = int(weapon.get('level') or 1)
    if level >= MAX_WEAPON_LEVEL:
        await send(player['ws'], {'type':'weapon-upgrade','ok':False,'message':'Weapon is already max level.'})
        return
    cost = 20 + level * 12 + max(0, level - 10) * 8 + max(0, level - 20) * 12
    if player['coins'] < cost:
        await send(player['ws'], {'type':'weapon-upgrade','ok':False,'message':f'You need {cost} coins.'})
        return
    player['coins'] -= cost
    weapon['level'] = level + 1
    if (player.get('loadout') or {}).get('weapon', {}).get('id') == item_id:
        player['loadout']['weapon'] = weapon
        room['loadouts'][player['id']] = player['loadout']
        await broadcast(room, {'type':'loadout','id':player['id'],'loadout':player['loadout']})
    await send_progress(player, f'Upgraded {weapon["name"]} to level {weapon["level"]}')
    await send(player['ws'], {'type':'weapon-upgrade','ok':True,'message':f'{weapon["name"]} reached level {weapon["level"]}.','item':weapon})
    await check_career_milestones(player)
    save_character(player)

async def set_weapon_path(room, player, item_id, path):
    path = str(path or '')
    if path not in ('balanced','power','swift','reach'):
        await send(player['ws'], {'type':'weapon-customized','ok':False,'message':'Unknown weapon path.'}); return
    weapon = next((item for item in player.get('inventory', []) if item.get('id') == item_id), None)
    if not weapon:
        await send(player['ws'], {'type':'weapon-customized','ok':False,'message':'Weapon not found.'}); return
    if int(weapon.get('level') or 1) < 5:
        await send(player['ws'], {'type':'weapon-customized','ok':False,'message':'Reach weapon level 5 first.'}); return
    changing = str(weapon.get('path') or 'balanced') != 'balanced' and str(weapon.get('path') or 'balanced') != path
    cost = 45 if changing else 0
    if player['coins'] < cost:
        await send(player['ws'], {'type':'weapon-customized','ok':False,'message':f'You need {cost} coins.'}); return
    player['coins'] -= cost
    weapon['path'] = path
    if (player.get('loadout') or {}).get('weapon', {}).get('id') == item_id:
        player['loadout']['weapon'] = weapon
    room['loadouts'][player['id']] = player.get('loadout') or {}
    await broadcast(room, {'type':'loadout','id':player['id'],'loadout':player['loadout']})
    await send_progress(player, 'Weapon path changed')
    await send(player['ws'], {'type':'weapon-customized','ok':True,'message':f'{weapon["name"]} now uses the {path.title()} path.','item':weapon})
    save_character(player)


async def customize_weapon(room, player, item_id, trail, tint, rotation, name=None):
    weapon = next((item for item in player.get('inventory', []) if item.get('id') == item_id), None)
    if not weapon:
        await send(player['ws'], {'type':'weapon-customized','ok':False,'message':'Weapon not found.'}); return
    trail = str(trail or weapon.get('trail') or 'slash')
    if trail not in ('none','slash','spark','glow'): trail = 'slash'
    tint = str(tint or weapon.get('tint') or '#ffffff')[:7]
    if not tint.startswith('#') or len(tint) != 7: tint = '#ffffff'
    weapon['trail'] = trail
    weapon['tint'] = tint
    weapon['rotation'] = clamp(float(rotation or 0), -180, 180)
    if name is not None:
        renamed = clean_name(name)[:24]
        if renamed and renamed != weapon['name']:
            if player['coins'] < 10:
                await send(player['ws'], {'type':'weapon-customized','ok':False,'message':'You need 10 coins to rename a weapon.'}); return
            player['coins'] -= 10
            weapon['name'] = renamed
    if (player.get('loadout') or {}).get('weapon', {}).get('id') == item_id:
        player['loadout']['weapon'] = weapon
    room['loadouts'][player['id']] = player.get('loadout') or {}
    await broadcast(room, {'type':'loadout','id':player['id'],'loadout':player['loadout']})
    await send_progress(player, 'Weapon customized')
    await send(player['ws'], {'type':'weapon-customized','ok':True,'message':'Weapon customization saved.','item':weapon})
    save_character(player)


async def set_style(player, title, theme, accent):
    titles = unlocked_titles(player)
    title = clean_name(title or player.get('title') or '')[:24]
    if title not in titles:
        await send(player['ws'], {'type':'style-result','ok':False,'message':'That title is not unlocked.'}); return
    allowed_themes = ['classic']
    level = int(player.get('level') or 1)
    if level >= 5: allowed_themes.append('pink')
    if level >= 10: allowed_themes.append('red')
    if level >= 15: allowed_themes.append('blue')
    if level >= 20: allowed_themes.append('gold')
    if level >= 30: allowed_themes.append('shadow')
    theme = str(theme or 'classic')
    if theme not in allowed_themes: theme = 'classic'
    accent = str(accent or '#b9f6c8')[:7]
    if not accent.startswith('#') or len(accent) != 7: accent = '#b9f6c8'
    player['selectedTitle'] = title
    player['nameplateTheme'] = theme
    player['accentColor'] = accent
    update_title(player)
    await send_progress(player, 'Style saved')
    await send(player['ws'], {'type':'style-result','ok':True,'message':'Character style saved.'})
    save_character(player)


async def spend_skill(room, player, attribute):
    attribute = str(attribute or '').lower()
    if attribute not in ('health', 'speed', 'reach', 'melee', 'weapon'):
        await send(player['ws'], {'type':'skill-result','ok':False,'message':'Unknown attribute.'})
        return
    attributes = sanitize_attributes(player.get('attributes'))
    if int(player.get('skillPoints') or 0) <= 0:
        await send(player['ws'], {'type':'skill-result','ok':False,'message':'You do not have a skill point.'})
        return
    if attributes[attribute] >= MAX_ATTRIBUTE_LEVEL:
        await send(player['ws'], {'type':'skill-result','ok':False,'message':f'{attribute.title()} is already maxed.'})
        return
    player['skillPoints'] = int(player.get('skillPoints') or 0) - 1
    attributes[attribute] += 1
    player['attributes'] = attributes
    player['records']['skillPointsSpent'] = int(player['records'].get('skillPointsSpent') or 0) + 1
    apply_attributes(player, preserve_health=True)
    save_character(player)
    await send_progress(player, f'Raised {attribute.title()}')
    await send(player['ws'], {'type':'skill-result','ok':True,'message':f'{attribute.title()} increased to {attributes[attribute]}.'})
    await check_career_milestones(player)
    await snapshot(room)


async def respec_skills(room, player):
    attributes = sanitize_attributes(player.get('attributes'))
    spent = sum(attributes.values())
    if spent <= 0:
        await send(player['ws'], {'type':'skill-result','ok':False,'message':'No spent skill points to reset.'})
        return
    cost = 40 + spent * 4
    if int(player.get('coins') or 0) < cost:
        await send(player['ws'], {'type':'skill-result','ok':False,'message':f'You need {cost} coins to reset skills.'})
        return
    player['coins'] -= cost
    player['skillPoints'] = int(player.get('skillPoints') or 0) + spent
    player['attributes'] = sanitize_attributes({})
    apply_attributes(player, preserve_health=True)
    save_character(player)
    await send_progress(player, 'Skills reset')
    await send(player['ws'], {'type':'skill-result','ok':True,'message':f'Reset {spent} skill points for {cost} coins.'})
    await snapshot(room)


async def authenticate_admin(player, code):
    ok = secrets.compare_digest(str(code or ''), ADMIN_CODE)
    player['isAdmin'] = ok
    await send(player['ws'], {'type':'admin-auth','ok':ok,'message':'Admin unlocked.' if ok else 'Wrong admin code.'})


def admin_target(room, target_id):
    target_id = clean_character_id(target_id)
    return room['players'].get(target_id)


async def admin_action(room, admin, message):
    if not admin.get('isAdmin'):
        await send(admin['ws'], {'type':'admin-result','ok':False,'message':'Admin access is locked.'})
        return
    action = str(message.get('action') or '')
    amount = int(clamp(float(message.get('amount') or 0), -99999, 99999))
    if action == 'announce':
        text = ''.join(c for c in str(message.get('message') or '') if ord(c) >= 32 and c not in '<>').strip()[:120]
        if text:
            await broadcast(room, {'type':'announcement','message':text})
            await send(admin['ws'], {'type':'admin-result','ok':True,'message':'Announcement sent.'})
        return
    target = admin_target(room, message.get('targetId'))
    if not target:
        await send(admin['ws'], {'type':'admin-result','ok':False,'message':'Target player is not online.'})
        return
    result = 'Action completed.'
    if action == 'grant-coins':
        target['coins'] = max(0, min(250000, target['coins'] + amount))
        result = f'{target["name"]} now has {target["coins"]} coins.'
        await send_progress(target, 'Admin coins')
    elif action == 'grant-xp':
        await grant(target, xp=max(0, amount), reason='Admin XP')
        result = f'Gave {max(0, amount)} XP to {target["name"]}.'
    elif action == 'grant-skill':
        target['skillPoints'] = max(0, min(1000, int(target.get('skillPoints') or 0) + amount))
        await send_progress(target, 'Admin skill points')
        result = f'{target["name"]} now has {target["skillPoints"]} skill points.'
    elif action == 'heal':
        target['health'] = target['maxHealth']; target['stamina'] = STAMINA_MAX
        result = f'Healed {target["name"]}.'
    elif action == 'revive':
        respawn(target); result = f'Revived {target["name"]}.'
    elif action == 'ko':
        target['health'] = 0; target['knockedOut'] = True; target['respawnAt'] = time.monotonic() + KO_TIME
        target['blocking'] = target['sprinting'] = False; release(room, target)
        result = f'Knocked out {target["name"]}.'
    elif action == 'summon':
        target['space'] = admin.get('space','world'); target['roomOwner'] = admin.get('roomOwner')
        target['x'], target['y'] = admin['x'] + 70, admin['y']
        result = f'Summoned {target["name"]}.'
    elif action == 'teleport':
        admin['space'] = target.get('space','world'); admin['roomOwner'] = target.get('roomOwner')
        admin['x'], admin['y'] = target['x'] + 70, target['y']
        result = f'Teleported to {target["name"]}.'
    elif action == 'freeze':
        target['frozen'] = not bool(target.get('frozen'))
        target['input'] = sanitize_input({}); target['blocking'] = target['sprinting'] = False
        result = f'{target["name"]} is {"frozen" if target["frozen"] else "unfrozen"}.'
    elif action == 'max-weapon':
        weapon = (target.get('loadout') or {}).get('weapon')
        if not weapon:
            result = f'{target["name"]} has no equipped weapon.'
        else:
            owned = next((item for item in target.get('inventory',[]) if item.get('id') == weapon.get('id')), None)
            if owned:
                owned['level'] = MAX_WEAPON_LEVEL
                target['loadout']['weapon'] = owned
                room['loadouts'][target['id']] = target['loadout']
                await broadcast(room, {'type':'loadout','id':target['id'],'loadout':target['loadout']})
                await send_progress(target, 'Admin max weapon')
                result = f"Maxed {target['name']}'s weapon."
    elif action == 'clear-room-art':
        target['roomArt'] = ''
        await send(target['ws'], {'type':'room-art-saved','ok':True,'art':''})
        result = f"Cleared {target['name']}'s room drawing."
    elif action == 'kick':
        result = f'Kicked {target["name"]}.'
        await send(target['ws'], {'type':'kicked','message':'You were removed by an admin.'})
        try: await target['ws'].close()
        except Exception: pass
    else:
        await send(admin['ws'], {'type':'admin-result','ok':False,'message':'Unknown admin action.'})
        return
    save_character(target)
    await send(admin['ws'], {'type':'admin-result','ok':True,'message':result})
    await snapshot(room)


def simulate(room, dt, now):
    for player in connected(room):
        if now >= player.get('nextPassiveCoinAt', now + PASSIVE_COIN_INTERVAL):
            player['nextPassiveCoinAt'] = now + PASSIVE_COIN_INTERVAL
            player['missionStats']['minutes'] = player['missionStats'].get('minutes', 0) + 1
            player['records']['minutesOnline'] = player['records'].get('minutesOnline', 0) + 1
            player['records']['coinsEarned'] = player['records'].get('coinsEarned', 0) + PASSIVE_COIN_REWARD
            asyncio.create_task(grant(player, xp=3, coins=PASSIVE_COIN_REWARD, reason='Time played'))
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
        if player.get('frozen') or now - float(player.get('lastInputAt') or now) > .75:
            player['input'] = sanitize_input({})
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
                # Audio frames: A = microphone voice, B = secret boombox music.
                if len(data) != 329 or data[1:2] != b'\x01' or data[:1] not in (b'A', b'B'):
                    continue
                clock_key = 'lastVoiceAt' if data[:1] == b'A' else 'lastBoomAt'
                if now - float(player.get(clock_key) or 0) < VOICE_MIN_INTERVAL:
                    continue
                player[clock_key] = now
                # Server packet keeps the frame type and inserts the 16-byte speaker id.
                packet = data[:2] + player['id'].encode('ascii') + data[2:]
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
                    character_id, character_secret, source.get('collections') or message.get('collections'), source.get('records') or message.get('records'), None, source.get('roomArt') or message.get('roomArt'))
                player['id'] = character_id; player['characterId'] = character_id; player['characterSecret'] = character_secret; player['roomRef'] = room
                player.setdefault('roomArt', sanitize_room_art(source.get('roomArt') or message.get('roomArt')))
                player.setdefault('records', sanitize_records(source.get('records') or message.get('records')))
                player.setdefault('careerClaimed', sanitize_progress(source.get('progress') or message.get('progress')).get('careerClaimed', {}))
                player.setdefault('nextPassiveCoinAt', time.monotonic() + PASSIVE_COIN_INTERVAL)
                player['inventory'] = sanitize_inventory(player.get('inventory') or source.get('inventory') or message.get('inventory'))
                player['loadout'] = sanitize_loadout(player.get('loadout') or source.get('loadout') or message.get('loadout'))
                if existing and player is existing:
                    if player.get('remove_task'): player['remove_task'].cancel(); player['remove_task']=None
                room['players'][character_id] = player; room['sessions'][player['sessionToken']] = character_id
                player['connected']=True; player['ws']=ws; player['input']=sanitize_input(message.get('input') or {}); player['lastInputAt']=time.monotonic(); player['isAdmin']=False
                avatar = sanitize_avatar(source.get('avatar') or message.get('avatar'))
                if avatar: room['avatars'][character_id]=avatar
                room['loadouts'][character_id]=player.get('loadout') or {}
                state=(room,player)
                save_character(player)
                await send(ws, {'type':'welcome','id':character_id,'roomCode':MAIN_WORLD_CODE,'sessionToken':player['sessionToken'],'build':BUILD,'protocol':PROTOCOL,'characterId':character_id,'characterSecret':character_secret,'character':character_payload(player,room),'singleWorld':True})
                await send(ws, {'type':'avatar-batch','avatars':room['avatars']}); await send(ws, {'type':'loadout-batch','loadouts':room['loadouts']})
                await send_world(room,ws); await grant_daily_login(player); await check_career_milestones(player); await send_progress(player,'Connected'); await snapshot(room)
                continue

            room, player = state
            message_type = message.get('type')
            if message_type == 'input':
                player['input'] = sanitize_input(message)
                player['lastInputAt'] = time.monotonic()
            elif message_type == 'punch':
                await punch(room, player)
            elif message_type == 'grab-start':
                await grab(room, player)
            elif message_type == 'throw':
                await throw(room, player)
            elif message_type == 'interact':
                pass
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
            elif message_type == 'save-room-art':
                await save_room_art(room, player, message.get('art'))
            elif message_type == 'upgrade-weapon':
                await upgrade_weapon(room, player, message.get('itemId'))
            elif message_type == 'set-weapon-path':
                await set_weapon_path(room, player, message.get('itemId'), message.get('path'))
            elif message_type == 'customize-weapon':
                await customize_weapon(room, player, message.get('itemId'), message.get('trail'), message.get('tint'), message.get('rotation'), message.get('name'))
            elif message_type == 'set-style':
                await set_style(player, message.get('title'), message.get('theme'), message.get('accent'))
            elif message_type == 'spend-skill':
                await spend_skill(room, player, message.get('attribute'))
            elif message_type == 'respec-skills':
                await respec_skills(room, player)
            elif message_type == 'admin-auth':
                await authenticate_admin(player, message.get('code'))
            elif message_type == 'admin-action':
                await admin_action(room, player, message)
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
        'service': 'green-floor-v24',
        'rooms': len(rooms),
        'players': sum(len(connected(room)) for room in rooms.values()),
        'build': BUILD,
        'voice': 'mulaw-websocket-relay+boombox', 'singleWorld': True, 'automaticConnection': True, 'roomCodes': False, 'persistence': 'sqlite', 'gameplay': 'v24-premium-ui-progression-weapons-rooms-voice-input-hardening',
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

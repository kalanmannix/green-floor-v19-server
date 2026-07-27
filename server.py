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
from collections import deque
from aiohttp import web, WSMsgType

BUILD = 41
PROTOCOL = 36
MAX_PLAYERS = 16
WORLD_W = 7200
WORLD_H = 4800
DUMMY_X, DUMMY_Y, DUMMY_RADIUS = 2050, 1120, 36
SPAWN_X = 1700
SPAWN_Y = 930
RADIUS = 30
SPEED = 285
SPRINT = 1.58
STAMINA_MAX = 100
SPRINT_DRAIN = 29
STAMINA_REGEN = 27
STAMINA_REGEN_DELAY = 0.68
PUNCH_RANGE = 176
PUNCH_LOCK = 680
PARRY_ACTIVE = 0.36
PARRY_RECOVERY = 0.30
PARRY_COOLDOWN = 1.15
PARRY_STUN = 0.66
PARRY_FACING_ANGLE = 1.80
DASH_DURATION = 0.52
DASH_COOLDOWN = 1.45
DASH_SPEED = 690
DASH_TURN_RATE = 4.25
COMBO_RELEASE_PROTECTION = 0.34
COMBO_INPUT_GRACE = 0.62
ATTACK_QUEUE_LIMIT = 1
EARLY_MASH_LIMIT = 1
MASH_RECOVERY_PENALTY = 0.24
COUNTER_DAMAGE_MULT = 1.25
COUNTER_STUN_BONUS = 0.10
DASH_INVULNERABILITY = 0.18
KO_TIME = 3.0
RAGDOLL_MIN_DURATION = 0.70
RAGDOLL_MAX_STRENGTH = 1.55
RAGDOLL_EVENT_VERSION = 1
RECONNECT_GRACE = 25.0
INTERACT_RANGE = 145
PHYSICS_GRAB_RANGE = 132
PHYSICS_HELP_RANGE = 118
PHYSICS_KICK_RANGE = 148
PHYSICS_THROW_CHARGE_MAX = 1.25
PHYSICS_THROW_MIN = 470
PHYSICS_THROW_MAX = 1160
PHYSICS_OBJECT_RESET_TIME = 18.0
GRENADE_COST = 10
GRENADE_MAX = 4
GRENADE_FUSE = 2.35
GRENADE_RADIUS = 430
GRENADE_COOLDOWN = 0.55
GRAVITY_GRENADE_COST = 16
GRAVITY_GRENADE_MAX = 3
GRAVITY_GRENADE_FUSE = 1.15
GRAVITY_FIELD_DURATION = 2.85
GRAVITY_FIELD_RADIUS = 560
GRAVITY_PULL = 980
GRAVITY_RELEASE_FORCE = 760
AIRSTRIKE_COST = 30
AIRSTRIKE_MAX = 1
AIRSTRIKE_WARNING = 3.6
AIRSTRIKE_RADIUS = 520
AIRSTRIKE_IMPACTS = 6
AIRSTRIKE_COOLDOWN = 75.0
LOW_GRAVITY_DURATION = 34.0
LOW_GRAVITY_FIRST_DELAY = 70.0
LOW_GRAVITY_INTERVAL_MIN = 220.0
LOW_GRAVITY_INTERVAL_MAX = 340.0
CARRY_RANGE = 118
CART_MOUNT_RANGE = 122
CART_CRASH_SPEED = 360
TABLE_X, TABLE_Y, TABLE_W, TABLE_H = 1700, 1800, 190, 92
TABLE_RESPAWN = 12.0
HOOP_X, HOOP_Y = 2120, 1000
OBJECT_TYPES = {
    'cone': {'radius': 21, 'mass': 0.45, 'bounce': 0.54, 'friction': 2.25, 'throw': 1.14, 'kick': 1.18, 'downSpeed': 690, 'stunSpeed': 360, 'label': 'traffic cone'},
    'chair': {'radius': 32, 'mass': 1.15, 'bounce': 0.34, 'friction': 2.80, 'throw': 0.86, 'kick': 0.86, 'downSpeed': 430, 'stunSpeed': 260, 'label': 'folding chair'},
    'trashcan': {'radius': 38, 'mass': 1.75, 'bounce': 0.27, 'friction': 3.20, 'throw': 0.64, 'kick': 0.66, 'downSpeed': 320, 'stunSpeed': 220, 'label': 'trash can'},
    'basketball': {'radius': 19, 'mass': 0.34, 'bounce': 0.78, 'friction': 1.35, 'throw': 1.24, 'kick': 1.32, 'downSpeed': 850, 'stunSpeed': 470, 'label': 'basketball'},
    'grenade': {'radius': 14, 'mass': 0.38, 'bounce': 0.62, 'friction': 1.65, 'throw': 1.08, 'kick': 1.16, 'downSpeed': 9999, 'stunSpeed': 9999, 'label': 'knockback grenade'},
    'gravity-grenade': {'radius': 15, 'mass': 0.42, 'bounce': 0.58, 'friction': 1.55, 'throw': 1.05, 'kick': 1.10, 'downSpeed': 9999, 'stunSpeed': 9999, 'label': 'gravity grenade'},
    'cart': {'radius': 48, 'mass': 2.5, 'bounce': 0.20, 'friction': 2.20, 'throw': 0.0, 'kick': 0.42, 'downSpeed': 390, 'stunSpeed': 250, 'label': 'shopping cart'},
}
PHYSICS_SPAWNS = [
    # Spread across verified open courtyard lanes; none intersect building collision boxes.
    ('cone-1','cone',790,900), ('cone-2','cone',2500,900),
    ('chair-1','chair',1200,900), ('chair-2','chair',2250,1800),
    ('trashcan-1','trashcan',1450,900),
    ('basketball-1','basketball',2030,930), ('basketball-2','basketball',1940,1085),
    ('cart-1','cart',1000,1800),
]
VOICE_CODEC_VERSION = 3
VOICE_CLIENT_FRAME = 973
VOICE_SERVER_FRAME = 989
BOOM_CODEC_VERSION = 2
BOOM_CLIENT_FRAME = 333
BOOM_SERVER_FRAME = 349
VOICE_MAX_FRAME = 1200
VOICE_MIN_INTERVAL = 0.014
BOOM_MIN_INTERVAL = 0.016
AUDIO_VOICE_QUEUE_MAX = 56
AUDIO_MUSIC_QUEUE_MAX = 14
VOICE_RELAY_DISTANCE = 1100.0
BOOM_RELAY_DISTANCE = 1750.0
WS_HEARTBEAT = 15
CHAT_MAX_LENGTH = 140
CHAT_COOLDOWN = 0.75
EMOTE_COOLDOWN = 0.35
EMOTE_DURATIONS = {
    'dance': 8.0,
    'dance2': 8.0,
    'wave': 4.0,
    'cheer': 4.0,
    'laugh': 4.5,
    'point': 4.0,
    'sit': 10.0,
}
EMOTE_ALIASES = {
    'dance': 'dance', 'dance1': 'dance',
    'dance2': 'dance2',
    'wave': 'wave', 'hello': 'wave',
    'cheer': 'cheer', 'celebrate': 'cheer',
    'laugh': 'laugh', 'lol': 'laugh',
    'point': 'point',
    'sit': 'sit',
}
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

STYLE_DATA = {
    "Street Brawler": {
        "kinds":["brawler-jab","brawler-cross","brawler-body-hook","brawler-uppercut","brawler-overhand"],
        "hands":["left","right","left","right","right"],
        "durations":[0.28,0.32,0.36,0.40,0.52],
        "windups":[0.09,0.11,0.13,0.15,0.21],
        "damage":[4,5,5,6,9], "knockback":[72,92,118,148,340],
        "stamina":[8,9,10,11,15], "hitstun":[0.18,0.19,0.20,0.22,0.32],
        "advance":[18,23,18,25,34], "targetAdvance":[10,14,14,18,44],
        "recovery":0.52,"whiffRecovery":0.48,"reach":1.00
    },
    "Boxer": {
        "kinds":["boxer-jab","boxer-cross","boxer-lead-hook","boxer-uppercut","boxer-long-straight"],
        "hands":["left","right","left","right","right"],
        "durations":[0.22,0.25,0.29,0.33,0.38],
        "windups":[0.065,0.075,0.095,0.115,0.13],
        "damage":[3,4,4,5,7], "knockback":[52,66,78,96,235],
        "stamina":[6,7,7,8,11], "hitstun":[0.15,0.16,0.17,0.19,0.26],
        "advance":[15,20,15,20,28], "targetAdvance":[7,9,11,13,34],
        "recovery":0.36,"whiffRecovery":0.34,"reach":0.94
    },
    "Kickboxer": {
        "kinds":["kickbox-jab","kickbox-cross","kickbox-low-kick","kickbox-knee","kickbox-roundhouse"],
        "hands":["left","right","right","left","right"],
        "durations":[0.25,0.29,0.36,0.39,0.49],
        "windups":[0.075,0.09,0.13,0.14,0.19],
        "damage":[4,4,6,6,9], "knockback":[66,78,112,128,315],
        "stamina":[7,8,11,12,16], "hitstun":[0.17,0.18,0.22,0.24,0.32],
        "advance":[15,20,12,24,30], "targetAdvance":[9,11,15,17,40],
        "recovery":0.50,"whiffRecovery":0.48,"reach":1.10
    },
    "Karate": {
        "kinds":["karate-palm","karate-reverse-punch","karate-front-kick","karate-sidekick"],
        "hands":["left","right","left","right"],
        "durations":[0.28,0.32,0.39,0.50],
        "windups":[0.09,0.105,0.145,0.20],
        "damage":[5,6,7,10], "knockback":[82,110,150,350],
        "stamina":[8,9,12,16], "hitstun":[0.19,0.20,0.25,0.34],
        "advance":[16,23,20,32], "targetAdvance":[10,13,18,45],
        "recovery":0.56,"whiffRecovery":0.54,"reach":1.07
    },
    "Heavy Weapon": {
        "kinds":["weapon-overhead","weapon-backhand","weapon-thrust-heavy","weapon-finisher"],
        "hands":["right","right","right","right"],
        "durations":[0.46,0.43,0.42,0.60],
        "windups":[0.20,0.18,0.17,0.27],
        "damage":[7,8,8,13], "knockback":[130,155,178,440],
        "stamina":[13,14,15,20], "hitstun":[0.23,0.25,0.27,0.38],
        "advance":[23,21,30,38], "targetAdvance":[14,16,20,50],
        "recovery":0.72,"whiffRecovery":0.68,"reach":1.16
    },
    "Light Weapon": {
        "kinds":["weapon-diagonal","weapon-backslash","weapon-thrust","weapon-rising-cut","weapon-spin-finisher"],
        "hands":["right","right","right","right","right"],
        "durations":[0.25,0.27,0.29,0.31,0.43],
        "windups":[0.075,0.085,0.09,0.10,0.16],
        "damage":[3,4,4,5,8], "knockback":[58,70,82,98,275],
        "stamina":[6,7,8,9,12], "hitstun":[0.15,0.16,0.17,0.18,0.28],
        "advance":[16,18,24,18,30], "targetAdvance":[8,10,12,13,38],
        "recovery":0.38,"whiffRecovery":0.36,"reach":1.02
    },
}
STYLE_ALIASES = {"Street Fighting":"Street Brawler","Boxing":"Boxer","Muay Thai":"Kickboxer","Wrestling":"Street Brawler","Judo":"Street Brawler"}
BUILDINGS = [
    (320,280,1480,480),(420,1130,720,520),(1450,1160,760,480),
    (3880,260,620,420),(4680,260,620,420),(5480,260,620,420),(6280,260,620,420),
    (3900,1040,900,520),(5060,1060,720,500),(6010,1040,900,520),
    (300,3020,520,500),(1020,3020,520,500),(1740,3020,520,500),
    (420,3860,620,500),(1320,3860,620,500),(2180,3820,430,540),
    (4620,3000,1050,620),(5860,3000,1040,620),(4720,3970,850,560),(5840,3970,1120,560)
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


def clean_chat_text(v):
    # Keep chat plain text, remove control characters, and collapse whitespace.
    text = ''.join(c for c in str(v or '') if ord(c) >= 32 and c not in '<>')
    return ' '.join(text.split())[:CHAT_MAX_LENGTH]


def clean_emote(v):
    key = ''.join(c for c in str(v or '').lower().strip() if c.isalnum())[:16]
    return EMOTE_ALIASES.get(key, '')


def cancel_emote(player):
    if player.get('emote'):
        player['emote'] = ''
        player['emoteUntil'] = 0.0
        player['emoteSerial'] = int(player.get('emoteSerial') or 0) + 1


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
    return {'x': x, 'y': y, 'sprint': m.get('sprint') is True}


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



def make_physics_object(object_id, kind, x, y):
    spec = OBJECT_TYPES[kind]
    return {
        'id': object_id, 'type': kind, 'x': float(x), 'y': float(y),
        'vx': 0.0, 'vy': 0.0, 'angle': random.random() * math.tau,
        'angularVelocity': 0.0, 'radius': spec['radius'], 'heldBy': None,
        'space': 'world', 'spawnX': float(x), 'spawnY': float(y),
        'lastThrower': None, 'ownerImmuneUntil': 0.0, 'lastHitAt': {},
        'fuseEnd': 0.0, 'fieldEnd': 0.0, 'createdAt': time.monotonic(), 'lastActiveAt': time.monotonic(),
        'scoredAt': 0.0, 'riderId': None, 'lastCollisionAt': 0.0,
        'heading': 0.0,
    }


def create_world_objects():
    return {object_id: make_physics_object(object_id, kind, x, y) for object_id, kind, x, y in PHYSICS_SPAWNS}


def public_physics_object(obj, now=None):
    now = time.monotonic() if now is None else now
    result = {
        'id': obj['id'], 'type': obj['type'], 'x': round(float(obj.get('x') or 0), 2),
        'y': round(float(obj.get('y') or 0), 2), 'vx': round(float(obj.get('vx') or 0), 2),
        'vy': round(float(obj.get('vy') or 0), 2), 'angle': round(float(obj.get('angle') or 0), 4),
        'angularVelocity': round(float(obj.get('angularVelocity') or 0), 3),
        'heldBy': obj.get('heldBy'), 'space': obj.get('space','world'),
    }
    if obj.get('type') in ('grenade','gravity-grenade'):
        result['fuseMs'] = max(0, int((float(obj.get('fuseEnd') or now) - now) * 1000))
    if obj.get('type') == 'gravity-grenade':
        result['fieldMs'] = max(0, int((float(obj.get('fieldEnd') or now) - now) * 1000))
        result['fieldActive'] = now >= float(obj.get('fuseEnd') or now) and now < float(obj.get('fieldEnd') or 0)
    if obj.get('type') == 'cart':
        result['riderId'] = obj.get('riderId')
    return result


def public_table(room, now=None):
    now = time.monotonic() if now is None else now
    table = room.get('physicsTable') or {}
    broken_until = float(table.get('brokenUntil') or 0)
    return {
        'x': TABLE_X, 'y': TABLE_Y, 'w': TABLE_W, 'h': TABLE_H,
        'broken': now < broken_until,
        'respawnMs': max(0, int((broken_until - now) * 1000)),
        'serial': int(table.get('serial') or 0),
    }


def public_chaos_state(room, now=None):
    now = time.monotonic() if now is None else now
    low_until = float(room.get('lowGravityUntil') or 0)
    warning_at = float(room.get('lowGravityWarningAt') or 0)
    air = room.get('airstrike') or None
    public_air = None
    if air and float(air.get('endAt') or 0) > now:
        public_air = {
            'serial': int(air.get('serial') or 0), 'x': round(float(air.get('x') or 0), 1),
            'y': round(float(air.get('y') or 0), 1), 'ownerId': air.get('ownerId'),
            'impactMs': max(0, int((float(air.get('impactAt') or now)-now)*1000)),
            'endMs': max(0, int((float(air.get('endAt') or now)-now)*1000)),
            'radius': AIRSTRIKE_RADIUS,
        }
    return {
        'lowGravity': now < low_until,
        'lowGravityMs': max(0, int((low_until-now)*1000)),
        'lowGravityWarningMs': max(0, int((warning_at-now)*1000)) if warning_at > now else 0,
        'airstrike': public_air,
    }


def low_gravity_active(room, now=None):
    now = time.monotonic() if now is None else now
    return now < float(room.get('lowGravityUntil') or 0)


def object_spec(obj):
    return OBJECT_TYPES.get(str(obj.get('type') or ''), OBJECT_TYPES['cone'])


def trigger_ragdoll(room, target, duration, source_x=None, source_y=None, force=0.0, knockout=False):
    """Create one authoritative ragdoll impulse shared by every client."""
    now = time.monotonic()
    tx = float(target.get('x') or 0)
    ty = float(target.get('y') or 0)
    if source_x is None or source_y is None or math.hypot(tx-float(source_x), ty-float(source_y)) < 1.0:
        away = float(target.get('direction') or 0) + math.pi
    else:
        away = math.atan2(ty-float(source_y), tx-float(source_x))
    serial = int(target.get('ragdollSerial') or 0) + 1
    strength = clamp(.32 + float(force or 0) / 620.0, .32, RAGDOLL_MAX_STRENGTH)
    # Values are generated once on the server so all clients see the same fall.
    spin = random.uniform(-1.0, 1.0)
    if abs(spin) < .24:
        spin = .24 if spin >= 0 else -.24
    target['ragdollSerial'] = serial
    target['ragdollStartedAt'] = now
    target['ragdollDuration'] = max(RAGDOLL_MIN_DURATION, float(duration or RAGDOLL_MIN_DURATION))
    target['ragdollAngle'] = away
    target['ragdollStrength'] = strength
    target['ragdollSpin'] = spin
    target['ragdollSeed'] = random.random()
    target['ragdollKnockout'] = bool(knockout)
    payload = {
        'type':'ragdoll', 'version':RAGDOLL_EVENT_VERSION,
        'playerId':target.get('id'), 'serial':serial,
        'angle':round(away,4), 'strength':round(strength,3),
        'spin':round(spin,3), 'seed':round(float(target['ragdollSeed']),4),
        'durationMs':int(target['ragdollDuration']*1000), 'knockout':bool(knockout),
    }
    try:
        asyncio.get_running_loop().create_task(broadcast(room, payload, space=target.get('space','world')))
    except RuntimeError:
        pass
    return payload


def release_held_object(room, player, place=True):
    object_id = player.get('heldObjectId')
    player['heldObjectId'] = None
    player['throwChargeStartedAt'] = 0.0
    if not object_id:
        return None
    obj = room.get('physicsObjects', {}).get(object_id)
    if not obj or obj.get('heldBy') != player.get('id'):
        return None
    obj['heldBy'] = None
    obj['space'] = player.get('space','world')
    facing = 1 if int(player.get('facing') or 1) >= 0 else -1
    angle = float(player.get('direction') or (0 if facing >= 0 else math.pi))
    if place:
        placement = 82 if obj.get('type') == 'cart' else 58
        obj['x'] = float(player.get('x') or 0) + math.cos(angle) * placement
        obj['y'] = float(player.get('y') or 0) + math.sin(angle) * placement
        obj['vx'] = float(player.get('vx') or 0) * 0.15
        obj['vy'] = float(player.get('vy') or 0) * 0.15
        obj['angularVelocity'] *= 0.25
    obj['lastActiveAt'] = time.monotonic()
    return obj


def knock_player_down(room, target, duration, source_x, source_y, force=0.0):
    now = time.monotonic()
    if target.get('knockedOut') or now < float(target.get('downedImmunityUntil') or 0):
        return False
    carrier_id = target.get('carriedBy')
    if carrier_id:
        carrier = room.get('players', {}).get(carrier_id)
        if carrier and carrier.get('carriedTargetId') == target.get('id'):
            drop_carried_player(room, carrier)
        else:
            target['carriedBy'] = None
    target['downedUntil'] = max(float(target.get('downedUntil') or 0), now + duration)
    target['downedImmunityUntil'] = now + duration + 0.65
    target['input'] = sanitize_input({})
    target['moving'] = target['sprinting'] = target['parrying'] = False
    target['parryUntil'] = 0
    target['dashActive'] = False
    target['dashAttackPending'] = False
    target['moveVx'] = target['moveVy'] = 0
    cancel_emote(target)
    cancel_combo(room, target)
    release_held_object(room, target, place=True)
    drop_carried_player(room, target)
    dismount_cart(room, target, knocked=True)
    if force > 0:
        angle = math.atan2(target['y'] - source_y, target['x'] - source_x)
        target['impulseX'] += math.cos(angle) * force
        target['impulseY'] += math.sin(angle) * force
    trigger_ragdoll(room, target, duration, source_x, source_y, force=force, knockout=False)
    return True


def drop_carried_player(room, carrier):
    target_id = carrier.get('carriedTargetId')
    carrier['carriedTargetId'] = None
    if not target_id:
        return None
    target = room.get('players', {}).get(target_id)
    if not target or target.get('carriedBy') != carrier.get('id'):
        return None
    target['carriedBy'] = None
    angle = float(carrier.get('direction') or 0)
    target['x'] = clamp(carrier['x'] - math.cos(angle)*54, RADIUS, WORLD_W-RADIUS)
    target['y'] = clamp(carrier['y'] - math.sin(angle)*54, RADIUS, WORLD_H-RADIUS)
    target['downedImmunityUntil'] = max(float(target.get('downedImmunityUntil') or 0), time.monotonic()+0.7)
    return target


def dismount_cart(room, player, knocked=False):
    cart_id = player.get('ridingCartId')
    player['ridingCartId'] = None
    if not cart_id:
        return None
    cart = room.get('physicsObjects', {}).get(cart_id)
    if not cart or cart.get('riderId') != player.get('id'):
        return None
    cart['riderId'] = None
    angle = float(cart.get('angle') or 0)
    side = 1 if random.random() > .5 else -1
    player['x'] = clamp(float(cart.get('x') or player['x']) + math.cos(angle+math.pi/2)*72*side, RADIUS, WORLD_W-RADIUS)
    player['y'] = clamp(float(cart.get('y') or player['y']) + math.sin(angle+math.pi/2)*72*side, RADIUS, WORLD_H-RADIUS)
    if knocked:
        player['impulseX'] += math.cos(angle)*220
        player['impulseY'] += math.sin(angle)*220
    return cart


def nearest_free_object(room, player, max_distance=PHYSICS_GRAB_RANGE):
    best = None
    best_distance = max_distance
    for obj in room.get('physicsObjects', {}).values():
        if obj.get('space','world') != player.get('space','world'):
            continue
        if obj.get('heldBy') and obj.get('type') != 'cart':
            continue
        distance = math.hypot(float(obj.get('x') or 0) - player['x'], float(obj.get('y') or 0) - player['y'])
        if distance < best_distance:
            best, best_distance = obj, distance
    return best, best_distance


async def physics_feedback(room, player, message, kind='info'):
    await send(player['ws'], {'type':'physics-feedback','message':str(message)[:64],'kind':kind})


async def physics_interact(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or now < float(player.get('stunnedUntil') or 0) or player.get('carriedBy'):
        return
    if player.get('ridingCartId'):
        cart = dismount_cart(room, player)
        if cart:
            await broadcast(room, {'type':'physics-event','event':{'kind':'cart-dismount','playerId':player['id'],'objectId':cart['id'],'x':cart['x'],'y':cart['y']}}, space=player.get('space','world'))
        return
    if player.get('carriedTargetId'):
        target = drop_carried_player(room, player)
        if target:
            await broadcast(room, {'type':'physics-event','event':{'kind':'carry-drop','playerId':player['id'],'targetId':target['id'],'x':target['x'],'y':target['y']}}, space=player.get('space','world'))
        return
    if player.get('heldObjectId'):
        obj = release_held_object(room, player, place=True)
        if obj:
            await broadcast(room, {'type':'physics-event','event':{'kind':'placed','objectId':obj['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))
        return
    nearest_downed = None
    nearest_distance = PHYSICS_HELP_RANGE
    for other in connected(room, player.get('space','world')):
        if other['id'] == player['id'] or other.get('knockedOut') or now >= float(other.get('downedUntil') or 0):
            continue
        distance = math.hypot(other['x'] - player['x'], other['y'] - player['y'])
        if distance < nearest_distance:
            nearest_downed, nearest_distance = other, distance
    if nearest_downed:
        nearest_downed['downedUntil'] = 0.0
        nearest_downed['downedImmunityUntil'] = now + 0.8
        nearest_downed['stunnedUntil'] = min(float(nearest_downed.get('stunnedUntil') or 0), now)
        nearest_downed['ragdollDuration'] = max(float(nearest_downed.get('ragdollDuration') or 0), .55)
        await broadcast(room, {'type':'physics-event','event':{'kind':'help-up','helperId':player['id'],'targetId':nearest_downed['id'],'x':nearest_downed['x'],'y':nearest_downed['y']-45}}, space=player.get('space','world'))
        return
    obj, distance = nearest_free_object(room, player)
    if not obj:
        await physics_feedback(room, player, 'Nothing close enough to grab.', 'range')
        return
    speed = math.hypot(float(obj.get('vx') or 0), float(obj.get('vy') or 0))
    if speed > 420:
        await physics_feedback(room, player, 'That object is moving too fast.', 'moving')
        return
    if obj.get('type') in ('grenade','gravity-grenade') and float(obj.get('fuseEnd') or 0) - now < 0.22:
        await physics_feedback(room, player, 'Too late to grab it!', 'danger')
        return
    if obj.get('type') == 'cart':
        angle = float(obj.get('angle') or 0)
        rel = math.atan2(player['y']-obj['y'], player['x']-obj['x'])
        behind = math.cos(rel-angle) < -0.15
        if not obj.get('riderId') and not behind:
            obj['riderId'] = player['id']
            player['ridingCartId'] = obj['id']
            player['input'] = sanitize_input({})
            player['moveVx'] = player['moveVy'] = 0
            cancel_combo(room, player)
            cancel_emote(player)
            await broadcast(room, {'type':'physics-event','event':{'kind':'cart-mount','playerId':player['id'],'objectId':obj['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))
            return
        if obj.get('heldBy') and obj.get('heldBy') != player['id']:
            await physics_feedback(room, player, 'The cart is already being pushed. Approach the seat to ride.', 'cart')
            return
        if obj.get('riderId') and not behind:
            await physics_feedback(room, player, 'The cart seat is occupied. Use the handle to push.', 'cart')
            return
    obj['heldBy'] = player['id']
    obj['vx'] = obj['vy'] = obj['angularVelocity'] = 0.0
    obj['space'] = player.get('space','world')
    player['heldObjectId'] = obj['id']
    player['throwChargeStartedAt'] = 0.0
    cancel_combo(room, player)
    cancel_emote(player)
    await broadcast(room, {'type':'physics-event','event':{'kind':'grabbed','objectId':obj['id'],'playerId':player['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))


async def physics_carry(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or player.get('carriedBy') or player.get('ridingCartId') or player.get('heldObjectId') or now < float(player.get('downedUntil') or 0):
        return
    if player.get('carriedTargetId'):
        target = drop_carried_player(room, player)
        if target:
            await broadcast(room, {'type':'physics-event','event':{'kind':'carry-drop','playerId':player['id'],'targetId':target['id'],'x':target['x'],'y':target['y']}}, space=player.get('space','world'))
        return
    nearest = None
    best = CARRY_RANGE
    for other in connected(room, player.get('space','world')):
        if other['id'] == player['id'] or other.get('knockedOut') or other.get('carriedBy') or other.get('ridingCartId') or now >= float(other.get('downedUntil') or 0):
            continue
        distance = math.hypot(other['x']-player['x'], other['y']-player['y'])
        if distance < best:
            nearest, best = other, distance
    if not nearest:
        await physics_feedback(room, player, 'Move closer to a knocked-down player to carry them.', 'range')
        return
    nearest['carriedBy'] = player['id']
    player['carriedTargetId'] = nearest['id']
    nearest['input'] = sanitize_input({})
    nearest['moveVx'] = nearest['moveVy'] = 0
    cancel_combo(room, player)
    cancel_emote(player)
    await broadcast(room, {'type':'physics-event','event':{'kind':'carry-start','playerId':player['id'],'targetId':nearest['id'],'x':nearest['x'],'y':nearest['y']}}, space=player.get('space','world'))


async def start_throw_charge(room, player):
    now = time.monotonic()
    if not player.get('heldObjectId') or player.get('knockedOut') or now < float(player.get('downedUntil') or 0):
        return
    obj = room.get('physicsObjects', {}).get(player.get('heldObjectId'))
    if not obj or obj.get('type') == 'cart':
        return
    player['throwChargeStartedAt'] = now


async def throw_held_object(room, player):
    now = time.monotonic()
    object_id = player.get('heldObjectId')
    obj = room.get('physicsObjects', {}).get(object_id)
    if not obj or obj.get('heldBy') != player['id']:
        player['heldObjectId'] = None
        player['throwChargeStartedAt'] = 0.0
        return
    if obj.get('type') == 'cart':
        await physics_feedback(room, player, 'Use E to stop pushing the cart.', 'cart')
        return
    charge_started = float(player.get('throwChargeStartedAt') or now)
    charge = clamp((now - charge_started) / PHYSICS_THROW_CHARGE_MAX, 0, 1)
    power = PHYSICS_THROW_MIN + (PHYSICS_THROW_MAX - PHYSICS_THROW_MIN) * (charge ** 0.72)
    if low_gravity_active(room, now):
        power *= 1.38
    spec = object_spec(obj)
    angle = float(player.get('direction') or (0 if player.get('facing',1) >= 0 else math.pi))
    obj['heldBy'] = None
    obj['x'] = player['x'] + math.cos(angle) * 60
    obj['y'] = player['y'] + math.sin(angle) * 60
    obj['vx'] = math.cos(angle) * power * spec['throw'] + float(player.get('vx') or 0) * 0.30
    obj['vy'] = math.sin(angle) * power * spec['throw'] + float(player.get('vy') or 0) * 0.30
    obj['angularVelocity'] = (5.5 + charge * 10.0) * (1 if random.random() > .5 else -1)
    obj['lastThrower'] = player['id']
    obj['ownerImmuneUntil'] = now + 0.30
    obj['lastActiveAt'] = now
    player['heldObjectId'] = None
    player['throwChargeStartedAt'] = 0.0
    await broadcast(room, {'type':'physics-event','event':{'kind':'thrown','objectId':obj['id'],'playerId':player['id'],'charge':round(charge,3),'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))


async def kick_object(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or now < float(player.get('kickReadyAt') or 0) or player.get('heldObjectId'):
        return
    obj, distance = nearest_free_object(room, player, PHYSICS_KICK_RANGE)
    if not obj:
        await physics_feedback(room, player, 'Move closer to an object to kick it.', 'range')
        return
    angle = math.atan2(obj['y'] - player['y'], obj['x'] - player['x']) if distance > 1 else float(player.get('direction') or 0)
    spec = object_spec(obj)
    force = 690 * spec['kick']
    obj['vx'] += math.cos(angle) * force
    obj['vy'] += math.sin(angle) * force
    obj['angularVelocity'] += (8.0 / max(.35, spec['mass'])) * (1 if random.random() > .5 else -1)
    obj['lastThrower'] = player['id']
    obj['ownerImmuneUntil'] = now + 0.20
    obj['lastActiveAt'] = now
    player['kickReadyAt'] = now + 0.48
    await broadcast(room, {'type':'physics-event','event':{'kind':'kicked','objectId':obj['id'],'playerId':player['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))


async def use_knockback_grenade(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or now < float(player.get('grenadeReadyAt') or 0):
        return
    count = int(player.get('grenadeCount') or 0)
    if count <= 0:
        await physics_feedback(room, player, 'Buy a knockback grenade in the Chaos Shop.', 'empty')
        return
    room['physicsSerial'] = int(room.get('physicsSerial') or 0) + 1
    object_id = f"grenade-{room['physicsSerial']}"
    angle = float(player.get('direction') or (0 if player.get('facing',1) >= 0 else math.pi))
    obj = make_physics_object(object_id, 'grenade', player['x'] + math.cos(angle)*58, player['y'] + math.sin(angle)*58)
    obj['vx'] = math.cos(angle) * 660 + float(player.get('vx') or 0) * .3
    obj['vy'] = math.sin(angle) * 660 + float(player.get('vy') or 0) * .3
    obj['angularVelocity'] = 11.0
    obj['fuseEnd'] = now + GRENADE_FUSE
    obj['lastThrower'] = player['id']
    obj['ownerImmuneUntil'] = now + .28
    room['physicsObjects'][object_id] = obj
    player['grenadeCount'] = count - 1
    player['grenadeReadyAt'] = now + GRENADE_COOLDOWN
    await send(player['ws'], {'type':'grenade-count','count':player['grenadeCount']})
    await broadcast(room, {'type':'physics-event','event':{'kind':'grenade-thrown','objectId':object_id,'playerId':player['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))


async def use_gravity_grenade(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or now < float(player.get('grenadeReadyAt') or 0):
        return
    count = int(player.get('gravityGrenadeCount') or 0)
    if count <= 0:
        await physics_feedback(room, player, 'Buy a gravity grenade in the Chaos Shop.', 'empty')
        return
    room['physicsSerial'] = int(room.get('physicsSerial') or 0) + 1
    object_id = f"gravity-{room['physicsSerial']}"
    angle = float(player.get('direction') or (0 if player.get('facing',1) >= 0 else math.pi))
    obj = make_physics_object(object_id, 'gravity-grenade', player['x'] + math.cos(angle)*58, player['y'] + math.sin(angle)*58)
    speed = 610 * (1.28 if low_gravity_active(room, now) else 1.0)
    obj['vx'] = math.cos(angle) * speed + float(player.get('vx') or 0) * .3
    obj['vy'] = math.sin(angle) * speed + float(player.get('vy') or 0) * .3
    obj['angularVelocity'] = -12.0
    obj['fuseEnd'] = now + GRAVITY_GRENADE_FUSE
    obj['fieldEnd'] = obj['fuseEnd'] + GRAVITY_FIELD_DURATION
    obj['lastThrower'] = player['id']
    obj['ownerImmuneUntil'] = now + .25
    room['physicsObjects'][object_id] = obj
    player['gravityGrenadeCount'] = count - 1
    player['grenadeReadyAt'] = now + GRENADE_COOLDOWN
    await send(player['ws'], {'type':'chaos-counts','grenadeCount':int(player.get('grenadeCount') or 0),'gravityGrenadeCount':player['gravityGrenadeCount'],'airstrikeCount':int(player.get('airstrikeCount') or 0)})
    await broadcast(room, {'type':'physics-event','event':{'kind':'gravity-thrown','objectId':object_id,'playerId':player['id'],'x':obj['x'],'y':obj['y']}}, space=player.get('space','world'))


def apply_blast(room, x, y, radius, player_force, object_force, space='world', knock_radius=260, source_kind='blast'):
    now = time.monotonic()
    gravity_mult = 1.30 if low_gravity_active(room, now) else 1.0
    for player in connected(room, space):
        dx, dy = player['x']-x, player['y']-y
        distance = math.hypot(dx, dy)
        if distance > radius:
            continue
        if distance < 1: dx,dy,distance=1,0,1
        falloff = 1-distance/radius
        force = player_force * gravity_mult * (.24+falloff*.76)
        player['impulseX'] += dx/distance*force
        player['impulseY'] += dy/distance*force
        if distance < knock_radius:
            knock_player_down(room, player, 1.35+falloff*.75, x, y, force=70)
    for other in room.get('physicsObjects', {}).values():
        if other.get('heldBy') or other.get('space','world') != space:
            continue
        dx,dy=other['x']-x,other['y']-y
        distance=math.hypot(dx,dy)
        if distance > radius or distance < .5:
            continue
        falloff=1-distance/radius
        spec=object_spec(other)
        force=object_force*gravity_mult*(.22+falloff*.78)/max(.45,spec['mass']**.55)
        other['vx'] += dx/distance*force
        other['vy'] += dy/distance*force
        other['angularVelocity'] += random.uniform(-14,14)*(0.5+falloff)
        other['lastActiveAt']=now
    if math.hypot(TABLE_X-x,TABLE_Y-y) < radius*.78:
        break_table(room,TABLE_X,TABLE_Y,source_kind)


async def run_airstrike(room, serial):
    air = room.get('airstrike')
    if not air or int(air.get('serial') or 0) != serial:
        return
    delay=max(0,float(air['impactAt'])-time.monotonic())
    await asyncio.sleep(delay)
    offsets=[(0,0),(-170,-95),(175,80),(-80,185),(105,-190),(225,-40)]
    for index,(ox,oy) in enumerate(offsets[:AIRSTRIKE_IMPACTS]):
        air=room.get('airstrike')
        if not air or int(air.get('serial') or 0)!=serial:
            return
        x=clamp(float(air['x'])+ox,WORLD_W*.02,WORLD_W*.98)
        y=clamp(float(air['y'])+oy,WORLD_H*.02,WORLD_H*.98)
        apply_blast(room,x,y,AIRSTRIKE_RADIUS*.62,1450,1820,'world',300,'airstrike')
        await broadcast(room,{'type':'physics-event','event':{'kind':'airstrike-impact','serial':serial,'index':index,'x':x,'y':y,'radius':AIRSTRIKE_RADIUS*.62}},space='world')
        await asyncio.sleep(.24)
    air=room.get('airstrike')
    if air and int(air.get('serial') or 0)==serial:
        room['airstrike']=None
        await broadcast(room,{'type':'chaos-state','chaos':public_chaos_state(room)},space='world')


async def target_airstrike(room, player, x, y):
    now=time.monotonic()
    if player.get('space','world')!='world' or player.get('knockedOut') or now < float(player.get('downedUntil') or 0):
        return
    count=int(player.get('airstrikeCount') or 0)
    if count<=0:
        await physics_feedback(room,player,'Buy an airstrike phone in the Chaos Shop.','empty')
        return
    if room.get('airstrike'):
        await physics_feedback(room,player,'An airstrike is already active.','busy')
        return
    if now < float(room.get('airstrikeReadyAt') or 0):
        await physics_feedback(room,player,'Airstrike system is reloading.','cooldown')
        return
    try:
        tx=clamp(float(x or 0),120,WORLD_W-120); ty=clamp(float(y or 0),120,WORLD_H-120)
    except (TypeError, ValueError):
        await physics_feedback(room,player,'Invalid airstrike target.','invalid')
        return
    if math.hypot(tx-SPAWN_X,ty-SPAWN_Y)<560:
        await physics_feedback(room,player,'The spawn area is protected. Pick another target.','protected')
        return
    serial=int(room.get('airstrikeSerial') or 0)+1
    room['airstrikeSerial']=serial
    room['airstrikeReadyAt']=now+AIRSTRIKE_COOLDOWN
    room['airstrike']={'serial':serial,'x':tx,'y':ty,'ownerId':player['id'],'startedAt':now,'impactAt':now+AIRSTRIKE_WARNING,'endAt':now+AIRSTRIKE_WARNING+2.2}
    player['airstrikeCount']=count-1
    await send(player['ws'],{'type':'chaos-counts','grenadeCount':int(player.get('grenadeCount') or 0),'gravityGrenadeCount':int(player.get('gravityGrenadeCount') or 0),'airstrikeCount':player['airstrikeCount']})
    await broadcast(room,{'type':'chaos-state','chaos':public_chaos_state(room)},space='world')
    await broadcast(room,{'type':'physics-event','event':{'kind':'airstrike-targeted','serial':serial,'ownerId':player['id'],'x':tx,'y':ty,'radius':AIRSTRIKE_RADIUS,'warningMs':int(AIRSTRIKE_WARNING*1000)}},space='world')
    asyncio.create_task(run_airstrike(room,serial))


def release_gravity_grenade(room, object_id, now):
    obj=room.get('physicsObjects',{}).pop(object_id,None)
    if not obj:
        return
    x,y=float(obj.get('x') or 0),float(obj.get('y') or 0)
    held_by=obj.get('heldBy')
    if held_by:
        holder=room.get('players',{}).get(held_by)
        if holder and holder.get('heldObjectId')==object_id:
            holder['heldObjectId']=None; holder['throwChargeStartedAt']=0.0
            x,y=holder['x'],holder['y']
    apply_blast(room,x,y,GRAVITY_FIELD_RADIUS*.86,GRAVITY_RELEASE_FORCE,GRAVITY_RELEASE_FORCE*1.15,obj.get('space','world'),205,'gravity-release')
    asyncio.create_task(broadcast(room,{'type':'physics-event','event':{'kind':'gravity-release','x':x,'y':y,'radius':GRAVITY_FIELD_RADIUS}},space=obj.get('space','world')))


def break_table(room, x, y, cause='impact'):
    now = time.monotonic()
    table = room.setdefault('physicsTable', {'brokenUntil':0.0,'serial':0})
    if now < float(table.get('brokenUntil') or 0):
        return False
    table['brokenUntil'] = now + TABLE_RESPAWN
    table['serial'] = int(table.get('serial') or 0) + 1
    asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'table-break','x':x,'y':y,'cause':cause,'serial':table['serial']}}, space='world'))
    return True


def explode_grenade(room, object_id, now):
    obj = room.get('physicsObjects', {}).pop(object_id, None)
    if not obj:
        return
    x, y = float(obj.get('x') or 0), float(obj.get('y') or 0)
    held_by = obj.get('heldBy')
    if held_by:
        holder = room.get('players', {}).get(held_by)
        if holder and holder.get('heldObjectId') == object_id:
            holder['heldObjectId'] = None
            holder['throwChargeStartedAt'] = 0.0
            x, y = float(holder.get('x') or x), float(holder.get('y') or y)
    apply_blast(room, x, y, GRENADE_RADIUS, 1180, 1400, obj.get('space','world'), 245, 'grenade')
    asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'grenade-explode','x':x,'y':y,'radius':GRENADE_RADIUS}}, space=obj.get('space','world')))


def circle_hits_table(x, y, radius):
    nearest_x = clamp(x, TABLE_X - TABLE_W/2, TABLE_X + TABLE_W/2)
    nearest_y = clamp(y, TABLE_Y - TABLE_H/2, TABLE_Y + TABLE_H/2)
    return math.hypot(x-nearest_x, y-nearest_y) <= radius


def simulate_physics(room, dt, now):
    objects = room.get('physicsObjects', {})
    table = room.setdefault('physicsTable', {'brokenUntil':0.0,'serial':0})
    if table.get('brokenUntil') and now >= float(table.get('brokenUntil') or 0):
        table['brokenUntil'] = 0.0
        table['serial'] = int(table.get('serial') or 0) + 1
        asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'table-respawn','x':TABLE_X,'y':TABLE_Y,'serial':table['serial']}}, space='world'))
    explode_ids = []
    for obj in list(objects.values()):
        if obj.get('type') == 'grenade' and now >= float(obj.get('fuseEnd') or 0):
            explode_ids.append(obj['id'])
            continue
        if obj.get('type') == 'gravity-grenade' and now >= float(obj.get('fieldEnd') or 0):
            explode_ids.append(obj['id'])
            continue
        held_by = obj.get('heldBy')
        if held_by and obj.get('type') == 'gravity-grenade' and now >= float(obj.get('fuseEnd') or 0):
            holder = room['players'].get(held_by)
            if holder:
                release_held_object(room, holder, place=True)
            else:
                obj['heldBy'] = None
            held_by = None
        if held_by:
            holder = room['players'].get(held_by)
            if not holder or not holder.get('connected') or holder.get('space','world') != obj.get('space','world') or holder.get('knockedOut') or now < float(holder.get('downedUntil') or 0):
                if holder:
                    release_held_object(room, holder, place=True)
                else:
                    obj['heldBy'] = None
                continue
            angle = float(holder.get('direction') or (0 if holder.get('facing',1) >= 0 else math.pi))
            hold_distance = 86 if obj.get('type') == 'cart' else 52
            obj['x'] = holder['x'] + math.cos(angle) * hold_distance
            obj['y'] = holder['y'] + math.sin(angle) * hold_distance
            obj['angle'] = angle if obj.get('type') == 'cart' else angle + math.pi * .5
            if obj.get('type') == 'cart': obj['heading'] = angle
            obj['vx'] = obj['vy'] = obj['angularVelocity'] = 0.0
            continue
        spec = object_spec(obj)
        if obj.get('type') == 'grenade' and now >= float(obj.get('fuseEnd') or 0):
            explode_ids.append(obj['id'])
            continue
        if obj.get('type') == 'gravity-grenade' and now >= float(obj.get('fieldEnd') or 0):
            explode_ids.append(obj['id'])
            continue
        if obj.get('type') == 'gravity-grenade' and now >= float(obj.get('fuseEnd') or 0):
            obj['vx'] *= math.exp(-9*dt); obj['vy'] *= math.exp(-9*dt); obj['angularVelocity'] *= math.exp(-8*dt)
            x,y=float(obj['x']),float(obj['y'])
            if not obj.get('fieldStarted'):
                obj['fieldStarted'] = True
                asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'gravity-field-start','objectId':obj['id'],'x':x,'y':y,'radius':GRAVITY_FIELD_RADIUS,'durationMs':int(GRAVITY_FIELD_DURATION*1000)}}, space=obj.get('space','world')))
            for target in connected(room,obj.get('space','world')):
                if target.get('knockedOut') or target.get('carriedBy'):
                    continue
                dx,dy=x-target['x'],y-target['y']; distance=math.hypot(dx,dy)
                if .5 < distance < GRAVITY_FIELD_RADIUS:
                    falloff=1-distance/GRAVITY_FIELD_RADIUS
                    force=GRAVITY_PULL*(.20+falloff*.80)*dt
                    target['impulseX'] += dx/distance*force
                    target['impulseY'] += dy/distance*force
            for other in objects.values():
                if other is obj or other.get('heldBy') or other.get('space','world')!=obj.get('space','world'):
                    continue
                dx,dy=x-other['x'],y-other['y']; distance=math.hypot(dx,dy)
                if .5 < distance < GRAVITY_FIELD_RADIUS:
                    falloff=1-distance/GRAVITY_FIELD_RADIUS
                    force=GRAVITY_PULL*1.35*(.18+falloff*.82)*dt/max(.45,object_spec(other)['mass']**.45)
                    other['vx'] += dx/distance*force
                    other['vy'] += dy/distance*force
                    other['angularVelocity'] += math.sin(now*8+distance*.02)*dt*4
            continue
        speed = math.hypot(float(obj.get('vx') or 0), float(obj.get('vy') or 0))
        if speed > 2:
            obj['lastActiveAt'] = now
        old_x, old_y = obj['x'], obj['y']
        nx = clamp(old_x + obj['vx'] * dt, spec['radius'], WORLD_W - spec['radius'])
        ny = clamp(old_y + obj['vy'] * dt, spec['radius'], WORLD_H - spec['radius'])
        collided = False
        if is_position_blocked(nx, old_y, spec['radius']):
            collided = True
            obj['vx'] *= -spec['bounce']
        else:
            obj['x'] = nx
        if is_position_blocked(obj['x'], ny, spec['radius']):
            collided = True
            obj['vy'] *= -spec['bounce']
        else:
            obj['y'] = ny
        if obj['x'] <= spec['radius'] + .1 or obj['x'] >= WORLD_W - spec['radius'] - .1:
            obj['vx'] *= -spec['bounce']
        if obj['y'] <= spec['radius'] + .1 or obj['y'] >= WORLD_H - spec['radius'] - .1:
            obj['vy'] *= -spec['bounce']
        table_broken = now < float(table.get('brokenUntil') or 0)
        if not table_broken and circle_hits_table(obj['x'], obj['y'], spec['radius']):
            impact_speed = math.hypot(obj['vx'], obj['vy'])
            if impact_speed > (390 if obj.get('type') in ('chair','trashcan','grenade') else 610):
                break_table(room, obj['x'], obj['y'], obj.get('type','impact'))
            else:
                if abs(old_x - TABLE_X) > abs(old_y - TABLE_Y): obj['vx'] *= -spec['bounce']
                else: obj['vy'] *= -spec['bounce']
                obj['x'], obj['y'] = old_x, old_y
        if obj.get('type') == 'cart' and collided and speed > CART_CRASH_SPEED and obj.get('riderId') and now-float(obj.get('lastCollisionAt') or 0)>.8:
            rider=room.get('players',{}).get(obj.get('riderId'))
            obj['lastCollisionAt']=now
            if rider:
                dismount_cart(room,rider,knocked=True)
                knock_player_down(room,rider,1.55,obj['x']-obj['vx']*.05,obj['y']-obj['vy']*.05,force=110)
                asyncio.create_task(broadcast(room,{'type':'physics-event','event':{'kind':'cart-crash','objectId':obj['id'],'playerId':rider['id'],'x':obj['x'],'y':obj['y']}},space=obj.get('space','world')))
        friction = spec['friction'] * (.46 if low_gravity_active(room, now) else 1.0)
        linear_decay = math.exp(-friction * dt)
        obj['vx'] *= linear_decay
        obj['vy'] *= linear_decay
        if obj.get('type') == 'cart':
            # The cart is a top-down vehicle: keep its nose aligned with travel and never tumble end-over-end.
            if speed > 18:
                desired = math.atan2(float(obj.get('vy') or 0), float(obj.get('vx') or 0))
                current = float(obj.get('heading') or obj.get('angle') or desired)
                delta = math.atan2(math.sin(desired-current), math.cos(desired-current))
                current += delta * min(1.0, dt * 9.0)
                obj['heading'] = current
                obj['angle'] = current % math.tau
            else:
                obj['angle'] = float(obj.get('heading') or obj.get('angle') or 0) % math.tau
            obj['angularVelocity'] = 0.0
        else:
            obj['angularVelocity'] = clamp(float(obj.get('angularVelocity') or 0), -7.0, 7.0) * math.exp(-3.4 * dt)
            obj['angle'] = (float(obj.get('angle') or 0) + float(obj.get('angularVelocity') or 0) * dt) % math.tau
        if abs(obj['vx']) < 2.5: obj['vx'] = 0.0
        if abs(obj['vy']) < 2.5: obj['vy'] = 0.0
        # Reset abandoned props so the playground cannot be emptied permanently.
        if obj.get('type') not in ('grenade','gravity-grenade') and not obj.get('riderId') and now - float(obj.get('lastActiveAt') or now) > PHYSICS_OBJECT_RESET_TIME:
            if math.hypot(obj['x']-obj['spawnX'], obj['y']-obj['spawnY']) > 260:
                obj['x'], obj['y'] = obj['spawnX'], obj['spawnY']
                obj['vx'] = obj['vy'] = obj['angularVelocity'] = 0.0
                obj['lastThrower'] = None
                obj['lastActiveAt'] = now
        speed = math.hypot(obj['vx'], obj['vy'])
        if speed > 130:
            hits = obj.setdefault('lastHitAt', {})
            for target in connected(room, obj.get('space','world')):
                if target.get('knockedOut'):
                    continue
                if target['id'] == obj.get('lastThrower') and now < float(obj.get('ownerImmuneUntil') or 0):
                    continue
                if now - float(hits.get(target['id']) or 0) < .48:
                    continue
                dx, dy = target['x'] - obj['x'], target['y'] - obj['y']
                distance = math.hypot(dx, dy)
                if distance > spec['radius'] + RADIUS * .78:
                    continue
                hits[target['id']] = now
                if distance < 1: dx,dy,distance=1,0,1
                force = min(610, speed * (0.42 / max(.38, spec['mass'] ** .30)))
                target['impulseX'] += dx/distance * force
                target['impulseY'] += dy/distance * force
                if speed >= spec['downSpeed']:
                    knock_player_down(room, target, 1.45 + min(.75, speed/1400), obj['x'], obj['y'], force=55)
                    state = 'down'
                elif speed >= spec['stunSpeed']:
                    target['stunnedUntil'] = max(float(target.get('stunnedUntil') or 0), now + .24)
                    state = 'hit'
                else:
                    state = 'bump'
                obj['vx'] *= -0.32
                obj['vy'] *= -0.32
                asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'object-hit','objectId':obj['id'],'objectType':obj['type'],'targetId':target['id'],'state':state,'speed':round(speed,1),'x':target['x'],'y':target['y']-42}}, space=obj.get('space','world')))
                break
        if obj.get('type') == 'basketball' and now - float(obj.get('scoredAt') or 0) > 1.0:
            if math.hypot(obj['x']-HOOP_X, obj['y']-HOOP_Y) < 34 and speed > 120:
                obj['scoredAt'] = now
                obj['vx'] *= .52
                obj['vy'] *= .52
                asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'basket-score','objectId':obj['id'],'x':HOOP_X,'y':HOOP_Y}}, space='world'))
    # Server-side object-to-object collisions make piles, cart crashes and blasts coherent for everyone.
    free_objects=[o for o in objects.values() if not o.get('heldBy') and o.get('type') not in ('gravity-grenade',)]
    for i,a in enumerate(free_objects):
        for b in free_objects[i+1:]:
            if a.get('space','world')!=b.get('space','world'):
                continue
            sa,sb=object_spec(a),object_spec(b)
            dx,dy=b['x']-a['x'],b['y']-a['y']; distance=math.hypot(dx,dy); minimum=sa['radius']+sb['radius']
            if distance<=.01 or distance>=minimum:
                continue
            nx,ny=dx/distance,dy/distance; overlap=minimum-distance
            total=max(.1,sa['mass']+sb['mass'])
            a['x']-=nx*overlap*(sb['mass']/total); a['y']-=ny*overlap*(sb['mass']/total)
            b['x']+=nx*overlap*(sa['mass']/total); b['y']+=ny*overlap*(sa['mass']/total)
            relative=(b['vx']-a['vx'])*nx+(b['vy']-a['vy'])*ny
            if relative<0:
                restitution=min(.72,(sa['bounce']+sb['bounce'])*.55)
                impulse=-(1+restitution)*relative/(1/max(.1,sa['mass'])+1/max(.1,sb['mass']))
                a['vx']-=impulse*nx/max(.1,sa['mass']); a['vy']-=impulse*ny/max(.1,sa['mass'])
                b['vx']+=impulse*nx/max(.1,sb['mass']); b['vy']+=impulse*ny/max(.1,sb['mass'])
                
                if a.get('type') != 'cart': a['angularVelocity'] += random.uniform(-1.6,1.6)
                if b.get('type') != 'cart': b['angularVelocity'] += random.uniform(-1.6,1.6)
    for obj in objects.values():
        if obj.get('type')=='cart' and obj.get('riderId'):
            rider=room.get('players',{}).get(obj.get('riderId'))
            if not rider or not rider.get('connected') or rider.get('knockedOut'):
                if rider: dismount_cart(room,rider)
                else: obj['riderId']=None
            else:
                rider['x']=obj['x']; rider['y']=obj['y']-8; rider['direction']=float(obj.get('angle') or 0); rider['facing']=1 if math.cos(rider['direction'])>=0 else -1
                rider['vx']=obj['vx']; rider['vy']=obj['vy']; rider['moveVx']=rider['moveVy']=0; rider['moving']=math.hypot(obj['vx'],obj['vy'])>8
    for object_id in explode_ids:
        obj=objects.get(object_id)
        if obj and obj.get('type')=='gravity-grenade':
            release_gravity_grenade(room,object_id,now)
        else:
            explode_grenade(room, object_id, now)


def make_room(code):
    return {
        'code': code,
        'players': {},
        'sessions': {},
        'avatars': {},
        'loadouts': {},
        'boomboxes': {},
        'physicsObjects': create_world_objects(),
        'snapshotSerial': 0,
        'physicsTable': {'brokenUntil': 0.0, 'serial': 0},
        'physicsSerial': 0,
        'airstrike': None, 'airstrikeSerial': 0, 'airstrikeReadyAt': 0.0,
        'lowGravityUntil': 0.0, 'lowGravityWarningAt': 0.0, 'lowGravityWasActive': False, 'nextLowGravityAt': time.monotonic()+LOW_GRAVITY_FIRST_DELAY,
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
        'x': clamp(SPAWN_X + math.cos(angle) * min(distance, 120), RADIUS, WORLD_W - RADIUS),
        'y': clamp(SPAWN_Y + math.sin(angle) * min(distance, 120), RADIUS, WORLD_H - RADIUS),
        'vx': 0, 'vy': 0, 'moveVx': 0, 'moveVy': 0,
        'direction': random.random() * math.tau, 'facing': 1,
        'moving': False, 'sprinting': False, 'blocking': False, 'parrying': False,
        'stamina': STAMINA_MAX, 'lastStaminaUseAt': 0,
        'score': 0, 'knockedOut': False, 'respawnAt': 0,
        'downedUntil': 0.0, 'downedImmunityUntil': 0.0,
        'ragdollSerial': 0, 'ragdollStartedAt': 0.0, 'ragdollDuration': 0.0,
        'ragdollAngle': 0.0, 'ragdollStrength': 0.0, 'ragdollSpin': 0.0,
        'ragdollSeed': random.random(), 'ragdollKnockout': False,
        'heldObjectId': None, 'throwChargeStartedAt': 0.0, 'kickReadyAt': 0.0,
        'grenadeCount': 1, 'gravityGrenadeCount': 0, 'airstrikeCount': 0, 'grenadeReadyAt': 0.0,
        'ridingCartId': None, 'carriedTargetId': None, 'carriedBy': None,
        'lastPunchAt': -10, 'attackRecoveryUntil': 0,
        'attackHand': 'right', 'attackAngle': 0, 'attackKind': 'jab',
        'impulseX': 0, 'impulseY': 0,
        'stunnedUntil': 0, 'invulnerableUntil': 0,
        'parryUntil': 0, 'parryRecoveryUntil': 0, 'parryReadyAt': 0,
        'dashActive': False, 'dashEndAt': 0, 'dashReadyAt': 0, 'dashAngle': 0, 'dashAttackPending': False,
        'comboOwner': None, 'comboTarget': None, 'comboStep': -1, 'comboLength': 0, 'comboToken': 0,
        'comboDeadline': 0, 'comboDashStarter': False,
        'attackAnimatingUntil': 0, 'attackQueueOpenAt': 0, 'attackQueueCloseAt': 0,
        'attackQueued': False, 'attackHitConfirmed': False, 'earlyMashCount': 0, 'chainLocked': False,
        'attackActionSerial': 0, 'vulnerableUntil': 0, 'lastCombatFeedbackAt': 0,
        'space': 'world', 'roomOwner': None,
        'title': 'New Student',
        'inventory': sanitize_inventory(inventory),
        'connected': False, 'ws': None, 'input': sanitize_input({}),
        'sessionToken': session, 'remove_task': None,
        'lastVoiceAt': 0.0, 'lastBoomAt': 0.0, 'lastChatAt': 0.0, 'lastEmoteAt': 0.0,
        'voiceQueue': None, 'voiceWake': None, 'voiceTask': None, 'voiceWs': None, 'musicQueue': None, 'musicWake': None, 'musicTask': None, 'musicWs': None,
        'emote': '', 'emoteUntil': 0.0, 'emoteSerial': 0,
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

def effective_style(player):
    raw = str(player.get('style') or (player.get('profile') or {}).get('style') or 'Street Brawler')
    style = STYLE_ALIASES.get(raw, raw)
    if style not in STYLE_DATA:
        style = 'Street Brawler'
    return style


def is_position_blocked(x, y, radius=RADIUS):
    for bx, by, bw, bh in BUILDINGS:
        if bx - radius < x < bx + bw + radius and by - radius < y < by + bh + radius:
            return True
    return False


def move_with_collisions(player, dx, dy, bound_w=WORLD_W, bound_h=WORLD_H):
    nx = clamp(player['x'] + dx, RADIUS, bound_w - RADIUS)
    ny = clamp(player['y'] + dy, RADIUS, bound_h - RADIUS)
    if player.get('space','world').startswith('room:'):
        player['x'], player['y'] = nx, ny
        return
    if not is_position_blocked(nx, player['y']):
        player['x'] = nx
    else:
        player['moveVx'] = 0
    if not is_position_blocked(player['x'], ny):
        player['y'] = ny
    else:
        player['moveVy'] = 0


def cancel_combo(room, attacker, release_target=True):
    attacker['comboToken'] = int(attacker.get('comboToken') or 0) + 1
    attacker['attackActionSerial'] = int(attacker.get('attackActionSerial') or 0) + 1
    target_id = attacker.get('comboTarget')
    attacker['comboTarget'] = None
    attacker['comboStep'] = -1
    attacker['comboLength'] = 0
    attacker['comboDeadline'] = 0
    attacker['comboDashStarter'] = False
    attacker['attackQueued'] = False
    attacker['attackAnimatingUntil'] = 0
    attacker['attackQueueOpenAt'] = 0
    attacker['attackQueueCloseAt'] = 0
    attacker['attackHitConfirmed'] = False
    attacker['earlyMashCount'] = 0
    attacker['chainLocked'] = False
    if release_target and target_id and target_id != 'training-dummy':
        target = room['players'].get(target_id)
        if target and target.get('comboOwner') == attacker['id']:
            target['comboOwner'] = None
            target['stunnedUntil'] = min(float(target.get('stunnedUntil') or 0), time.monotonic() + 0.06)
            target['invulnerableUntil'] = max(float(target.get('invulnerableUntil') or 0), time.monotonic() + COMBO_RELEASE_PROTECTION)


def public_player(player, detailed=False):
    """Return a compact 30 Hz gameplay state.

    Only the receiving player's packet carries progression/menu data. Remote
    players receive the fields needed for movement, animation, combat, voice
    positioning, and world interactions. This keeps snapshots small enough to
    remain smooth when the server is busy.
    """
    now = time.monotonic()
    result = {
        'id': player.get('id'),
        'characterId': player.get('characterId'),
        'name': player.get('name','Player'),
        'x': round(float(player.get('x') or 0), 2),
        'y': round(float(player.get('y') or 0), 2),
        'vx': round(float(player.get('vx') or 0), 2),
        'vy': round(float(player.get('vy') or 0), 2),
        'direction': round(float(player.get('direction') or 0), 4),
        'facing': 1 if int(player.get('facing') or 1) >= 0 else -1,
        'moving': bool(player.get('moving')),
        'sprinting': bool(player.get('sprinting')),
        'stamina': round(float(player.get('stamina') or 0), 1),
        'score': int(player.get('score') or 0),
        'knockedOut': bool(player.get('knockedOut')),
        'health': round(float(player.get('health') or 0), 1),
        'maxHealth': round(float(player.get('maxHealth') or 100), 1),
        'style': player.get('style','Street Brawler'),
        'heritage': player.get('heritage','Japanese'),
        'reachMult': round(float(player.get('reachMult') or 1), 3),
        'grabRangeMult': round(float(player.get('grabRangeMult') or 1), 3),
        'attackSpeedMult': round(float(player.get('attackSpeedMult') or 1), 3),
        'sizeScale': round(float(player.get('sizeScale') or 1), 3),
        'weaponDamageMult': round(float(player.get('weaponDamageMult') or 1), 3),
        'weaponReachMult': round(float(player.get('weaponReachMult') or 1), 3),
        'space': player.get('space','world'),
        'title': player.get('title','New Student'),
        'selectedTitle': player.get('selectedTitle') or player.get('title','New Student'),
        'nameplateTheme': player.get('nameplateTheme','classic'),
        'accentColor': player.get('accentColor','#b9f6c8'),
        'attackHand': 'left' if player.get('attackHand') == 'left' else 'right',
        'attackAngle': round(float(player.get('attackAngle') or 0), 4),
        'attackKind': player.get('attackKind','jab'),
        'comboStep': int(player.get('comboStep') or 0),
        'comboLength': max(1, int(player.get('comboLength') or 1)),
        'attackActionSerial': int(player.get('attackActionSerial') or 0),
    }
    result['inventoryCount'] = len(player.get('inventory') or [])
    weapon = (player.get('loadout') or {}).get('weapon')
    result['weaponLevel'] = int(weapon.get('level') or 0) if weapon else 0
    result['weaponMasteryRank'] = int(weapon.get('masteryRank') or 0) if weapon else 0
    result['parrying'] = now < float(player.get('parryUntil') or 0)
    result['stunned'] = now < float(player.get('stunnedUntil') or 0)
    result['comboLocked'] = bool(player.get('comboOwner')) and now < float(player.get('stunnedUntil') or 0)
    result['downed'] = now < float(player.get('downedUntil') or 0)
    result['downedRemainingMs'] = max(0, int((float(player.get('downedUntil') or 0) - now) * 1000))
    ragdoll_started = float(player.get('ragdollStartedAt') or 0)
    ragdoll_duration = max(0.0, float(player.get('ragdollDuration') or 0))
    result['ragdollElapsedMs'] = max(0, int((now-ragdoll_started)*1000)) if ragdoll_started else 0
    result['ragdollDurationMs'] = int(ragdoll_duration*1000)
    result['ragdollAngle'] = round(float(player.get('ragdollAngle') or 0), 4)
    result['ragdollStrength'] = round(float(player.get('ragdollStrength') or 0), 3)
    result['ragdollSpin'] = round(float(player.get('ragdollSpin') or 0), 3)
    result['ragdollSeed'] = round(float(player.get('ragdollSeed') or 0), 4)
    result['ragdollSerial'] = int(player.get('ragdollSerial') or 0)
    result['ragdollKnockout'] = bool(player.get('ragdollKnockout'))
    result['heldObjectId'] = player.get('heldObjectId')
    result['grenadeCount'] = int(player.get('grenadeCount') or 0)
    result['gravityGrenadeCount'] = int(player.get('gravityGrenadeCount') or 0)
    result['airstrikeCount'] = int(player.get('airstrikeCount') or 0)
    result['ridingCartId'] = player.get('ridingCartId')
    result['carriedTargetId'] = player.get('carriedTargetId')
    result['carriedBy'] = player.get('carriedBy')
    result['parryLocked'] = bool(player.get('comboOwner'))
    result['chainReady'] = bool(player.get('attackHitConfirmed')) and not bool(player.get('chainLocked')) and not bool(player.get('attackQueued')) and now >= float(player.get('attackQueueOpenAt') or 0) and now <= float(player.get('attackQueueCloseAt') or 0)
    result['attackQueued'] = bool(player.get('attackQueued'))
    result['chainLocked'] = bool(player.get('chainLocked'))
    result['vulnerable'] = now < float(player.get('vulnerableUntil') or 0)
    result['parryCooldown'] = round(max(0.0, float(player.get('parryReadyAt') or 0) - now), 3)
    result['dashCooldown'] = round(max(0.0, float(player.get('dashReadyAt') or 0) - now), 3)
    result['dashActive'] = bool(player.get('dashActive'))
    result['combatStyle'] = effective_style(player)
    emote_until = float(player.get('emoteUntil') or 0)
    if player.get('emote') and now < emote_until:
        result['emote'] = player['emote']
        result['emoteRemainingMs'] = max(0, int((emote_until - now) * 1000))
        result['emoteDurationMs'] = int(EMOTE_DURATIONS.get(player['emote'], 4.0) * 1000)
    else:
        result['emote'] = ''
        result['emoteRemainingMs'] = 0
        result['emoteDurationMs'] = 0
    result['emoteSerial'] = int(player.get('emoteSerial') or 0)
    if detailed:
        for key in ('xp','coins','reputation','level','levelXp','levelXpNeeded','skillPoints',
                    'attributes','missionStats','missionClaimed','job','loginStreak',
                    'bestLoginStreak','records','unlockedTitles'):
            result[key] = player.get(key)
    return result

def clean_track_name(value):
    return ''.join(ch for ch in str(value or '') if ch.isprintable()).strip()[:48] or 'Boombox track'


def public_boombox(room, owner_id):
    state = room.get('boomboxes', {}).get(owner_id)
    if not state or not state.get('active'):
        return None
    owner = room.get('players', {}).get(owner_id)
    result = dict(state)
    if result.get('mode') == 'held' and owner:
        result['x'] = float(owner.get('x') or 0)
        result['y'] = float(owner.get('y') or 0)
        result['space'] = owner.get('space', 'world')
        result['facing'] = int(owner.get('facing') or 1)
    result['ownerName'] = owner.get('name', 'Player') if owner else result.get('ownerName', 'Player')
    return result


async def broadcast_boombox_state(room, owner_id, previous_space=None):
    state = public_boombox(room, owner_id)
    if not state:
        await broadcast(room, {'type': 'boombox-remove', 'ownerId': owner_id})
        return
    if previous_space and previous_space != state.get('space'):
        await broadcast(room, {'type': 'boombox-remove', 'ownerId': owner_id}, space=previous_space)
    await broadcast(room, {'type': 'boombox-state', 'boombox': state}, space=state.get('space'))


async def control_boombox(room, player, action, track_name=None):
    action = str(action or '').lower()
    states = room.setdefault('boomboxes', {})
    current = states.get(player['id'])
    previous_space = current.get('space') if current else None
    if action in ('start', 'load'):
        serial = int((current or {}).get('serial') or 0) + 1
        states[player['id']] = {
            'id': f"boom-{player['id']}", 'ownerId': player['id'], 'ownerName': player['name'],
            'mode': 'held', 'active': True, 'trackName': clean_track_name(track_name),
            'x': float(player['x']), 'y': float(player['y']), 'space': player.get('space', 'world'),
            'facing': int(player.get('facing') or 1), 'serial': serial,
        }
    elif action == 'place':
        if not current or not current.get('active'):
            await send(player['ws'], {'type': 'boombox-error', 'message': 'Choose a song for the boombox first.'})
            return
        facing = 1 if int(player.get('facing') or 1) >= 0 else -1
        x = clamp(float(player['x']) + facing * 78, 34, (ROOM_W if player.get('space','world').startswith('room:') else WORLD_W) - 34)
        y = clamp(float(player['y']) + 24, 34, (ROOM_H if player.get('space','world').startswith('room:') else WORLD_H) - 34)
        if not player.get('space','world').startswith('room:') and is_position_blocked(x, y, 34):
            x, y = float(player['x']), clamp(float(player['y']) + 84, 34, WORLD_H - 34)
        current.update({'mode': 'placed', 'x': x, 'y': y, 'space': player.get('space','world'), 'facing': facing})
    elif action in ('hold', 'pickup'):
        if not current or not current.get('active'):
            await send(player['ws'], {'type': 'boombox-error', 'message': 'Choose a song for the boombox first.'})
            return
        current.update({'mode': 'held', 'x': float(player['x']), 'y': float(player['y']), 'space': player.get('space','world'), 'facing': int(player.get('facing') or 1)})
    elif action == 'stop':
        if current:
            states.pop(player['id'], None)
            await broadcast(room, {'type': 'boombox-remove', 'ownerId': player['id']})
        return
    else:
        return
    await broadcast_boombox_state(room, player['id'], previous_space)


def connected(room, space=None):
    players = [p for p in room['players'].values() if p['connected']]
    return players if space is None else [p for p in players if p.get('space','world') == space]


_ws_send_locks = {}


def ws_send_lock(ws):
    return _ws_send_locks.setdefault(id(ws), asyncio.Lock())


async def locked_send_text(ws, data):
    if ws.closed:
        return
    async with ws_send_lock(ws):
        if not ws.closed:
            await ws.send_str(data)


async def locked_send_bytes(ws, data):
    if ws.closed:
        return
    async with ws_send_lock(ws):
        if not ws.closed:
            await ws.send_bytes(data)


async def stream_sender(player, queue_key, wake_key, ws_key):
    try:
        while player.get('connected'):
            queue = player.get(queue_key)
            wake = player.get(wake_key)
            if queue is None or wake is None:
                return
            if not queue:
                wake.clear()
                if queue:
                    wake.set()
                    continue
                await wake.wait()
                continue
            packet = queue.popleft()
            ws = player.get(ws_key)
            if not ws or ws.closed:
                continue
            try:
                await asyncio.wait_for(locked_send_bytes(ws, packet), timeout=0.10)
            except (asyncio.TimeoutError, ConnectionError):
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                return
    except asyncio.CancelledError:
        return


def start_stream_sender(player, kind):
    if kind == 'voice':
        task_key, queue_key, wake_key, ws_key, maxlen = 'voiceTask', 'voiceQueue', 'voiceWake', 'voiceWs', AUDIO_VOICE_QUEUE_MAX
    else:
        task_key, queue_key, wake_key, ws_key, maxlen = 'musicTask', 'musicQueue', 'musicWake', 'musicWs', AUDIO_MUSIC_QUEUE_MAX
    task = player.get(task_key)
    if task and not task.done():
        task.cancel()
    player[queue_key] = deque(maxlen=maxlen)
    player[wake_key] = asyncio.Event()
    player[task_key] = asyncio.create_task(stream_sender(player, queue_key, wake_key, ws_key))


def stop_stream_sender(player, kind):
    if kind == 'voice':
        task_key, queue_key, wake_key = 'voiceTask', 'voiceQueue', 'voiceWake'
    else:
        task_key, queue_key, wake_key = 'musicTask', 'musicQueue', 'musicWake'
    task = player.get(task_key)
    if task and not task.done():
        task.cancel()
    player[task_key] = None
    player[queue_key] = None
    player[wake_key] = None


def stop_all_audio_senders(player):
    stop_stream_sender(player, 'voice')
    stop_stream_sender(player, 'music')


def enqueue_audio(player, packet, is_boombox=False):
    queue_key = 'musicQueue' if is_boombox else 'voiceQueue'
    wake_key = 'musicWake' if is_boombox else 'voiceWake'
    queue = player.get(queue_key)
    wake = player.get(wake_key)
    if queue is None or wake is None:
        return
    # Old packets are dropped by deque(maxlen) so latency stays bounded.
    queue.append(packet)
    wake.set()


async def send(ws, obj):
    if not ws.closed:
        try:
            await locked_send_text(ws, json.dumps(obj, separators=(',', ':')))
        except Exception:
            pass


async def broadcast(room, obj, exclude=None, space=None):
    data = json.dumps(obj, separators=(',', ':'))
    for player in connected(room, space):
        if player['ws'] is exclude or player['ws'].closed:
            continue
        try:
            await locked_send_text(player['ws'], data)
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
    server_time = int(time.time() * 1000)
    room['snapshotSerial'] = int(room.get('snapshotSerial') or 0) + 1
    serial = room['snapshotSerial']
    tasks = []
    for receiver in connected(room):
        same_space = connected(room, receiver.get('space','world'))
        packet = {
            'type': 'snapshot',
            'players': {p['id']: public_player(p, detailed=(p['id'] == receiver['id'])) for p in same_space},
            'serverTime': server_time,
            'snapshotSerial': serial,
            'online': all_online,
            'space': receiver.get('space','world'),
            'boomboxes': {
                owner_id: state for owner_id in room.get('boomboxes', {})
                if (state := public_boombox(room, owner_id)) and state.get('space') == receiver.get('space','world')
            },
            'objects': {object_id: public_physics_object(obj) for object_id, obj in room.get('physicsObjects', {}).items() if obj.get('space','world') == receiver.get('space','world')},
            'table': public_table(room),
            'hoop': {'x': HOOP_X, 'y': HOOP_Y},
            'chaos': public_chaos_state(room),
        }
        tasks.append(send(receiver['ws'], packet))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

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
            'boomboxes': {
                owner_id: state for owner_id in room.get('boomboxes', {})
                if (state := public_boombox(room, owner_id)) and state.get('space') == player.get('space','world')
            },
            'objects': {object_id: public_physics_object(obj) for object_id, obj in room.get('physicsObjects', {}).items() if obj.get('space','world') == player.get('space','world')},
            'table': public_table(room),
            'chaos': public_chaos_state(room),
            'hoop': {'x': HOOP_X, 'y': HOOP_Y},
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
    release_held_object(room, player, place=True)
    drop_carried_player(room, player)
    dismount_cart(room, player)
    if player.get('carriedBy'):
        carrier=room.get('players',{}).get(player.get('carriedBy'))
        if carrier and carrier.get('carriedTargetId')==player['id']: carrier['carriedTargetId']=None
        player['carriedBy']=None
    if player.get('comboTarget'):
        cancel_combo(room, player, release_target=True)
    if player.get('comboOwner'):
        owner = room['players'].get(player.get('comboOwner'))
        player['comboOwner'] = None
        player['stunnedUntil'] = min(float(player.get('stunnedUntil') or 0), time.monotonic() + 0.06)
        if owner and owner.get('comboTarget') == player['id']:
            cancel_combo(room, owner, release_target=False)
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
    release_held_object(room, target, place=True)
    target['downedUntil'] = 0.0
    target['knockedOut'] = True
    source_x = float(attacker.get('x') or target.get('x') or 0)
    source_y = float(attacker.get('y') or target.get('y') or 0)
    impact_force = max(260.0, math.hypot(float(target.get('impulseX') or 0), float(target.get('impulseY') or 0)))
    trigger_ragdoll(room, target, KO_TIME, source_x, source_y, force=impact_force, knockout=True)
    target['respawnAt'] = time.monotonic() + KO_TIME
    target['blocking'] = target['sprinting'] = target['parrying'] = False
    target['dashActive'] = False
    target['parryUntil'] = 0
    cancel_combo(room, target)
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
        player['x'] = clamp(SPAWN_X + math.cos(angle) * min(distance, 120), RADIUS, WORLD_W - RADIUS)
        player['y'] = clamp(SPAWN_Y + math.sin(angle) * min(distance, 120), RADIUS, WORLD_H - RADIUS)
    for key in ['vx', 'vy', 'moveVx', 'moveVy', 'impulseX', 'impulseY']:
        player[key] = 0
    player['health'] = player['maxHealth']
    player['stamina'] = STAMINA_MAX
    player['knockedOut'] = False
    player['downedUntil'] = 0.0
    player['downedImmunityUntil'] = time.monotonic() + 0.75
    player['ragdollStartedAt'] = 0.0
    player['ragdollDuration'] = 0.0
    player['ragdollStrength'] = 0.0
    player['ragdollKnockout'] = False
    player['heldObjectId'] = None
    player['throwChargeStartedAt'] = 0.0
    player['respawnAt'] = 0
    player['blocking'] = player['sprinting'] = player['parrying'] = False
    player['dashActive'] = False
    player['dashAttackPending'] = False
    player['stunnedUntil'] = 0
    player['invulnerableUntil'] = time.monotonic() + 0.7
    player['parryUntil'] = player['parryRecoveryUntil'] = 0
    player['comboOwner'] = player['comboTarget'] = None
    player['comboStep'] = -1
    player['comboLength'] = 0
    player['comboDeadline'] = 0
    player['comboDashStarter'] = False
    player['attackQueued'] = False
    player['attackAnimatingUntil'] = 0
    player['attackQueueOpenAt'] = 0
    player['comboToken'] = int(player.get('comboToken') or 0) + 1
    player['attackActionSerial'] = int(player.get('attackActionSerial') or 0) + 1


def angle_difference(a, b):
    return (a - b + math.pi) % math.tau - math.pi


def nearest_combat_target(room, attacker, max_distance):
    best = None
    best_distance = max_distance
    now = time.monotonic()
    for target in connected(room, attacker.get('space','world')):
        if target['id'] == attacker['id'] or target.get('knockedOut'):
            continue
        if target.get('comboOwner') and target.get('comboOwner') != attacker['id']:
            continue
        if now < float(target.get('invulnerableUntil') or 0):
            continue
        distance = math.hypot(target['x'] - attacker['x'], target['y'] - attacker['y'])
        if distance < best_distance:
            best = target
            best_distance = distance
    return best, best_distance


def parry_faces_attacker(defender, attacker):
    toward_attacker = math.atan2(attacker['y'] - defender['y'], attacker['x'] - defender['x'])
    facing_angle = float(defender.get('direction') or (0 if defender.get('facing', 1) >= 0 else math.pi))
    return abs(angle_difference(toward_attacker, facing_angle)) <= PARRY_FACING_ANGLE


async def combat_feedback(player, message, state='info'):
    now = time.monotonic()
    # Prevent repeated click spam from flooding the socket or HUD.
    if now - float(player.get('lastCombatFeedbackAt') or 0) < 0.16 and state != 'chain':
        return
    player['lastCombatFeedbackAt'] = now
    if player.get('ws'):
        await send(player['ws'], {'type':'combat-feedback','message':str(message)[:48],'state':state})


async def parry(room, player):
    now = time.monotonic()
    if player.get('comboOwner'):
        await combat_feedback(player, 'Parry before the first hit', 'parry-locked')
        return
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or player.get('heldObjectId') or player.get('ridingCartId') or player.get('carriedTargetId') or player.get('carriedBy') or now < float(player.get('stunnedUntil') or 0) or player.get('comboTarget') or player.get('dashActive'):
        return
    if now < float(player.get('parryReadyAt') or 0):
        return
    player['sprinting'] = False
    player['parrying'] = True
    player['parryUntil'] = now + PARRY_ACTIVE
    player['parryRecoveryUntil'] = now + PARRY_ACTIVE + PARRY_RECOVERY
    player['parryReadyAt'] = now + PARRY_COOLDOWN
    player['moveVx'] *= 0.25
    player['moveVy'] *= 0.25
    await broadcast(room, {'type':'combat','event':{
        'kind':'parry-start','attackerId':player['id'],'targetId':None,'angle':player.get('direction',0),'visualMs':400,
        'hit':False,'parried':False,'durationMs':round(PARRY_ACTIVE*1000),'x':player['x'],'y':player['y']-50
    }}, space=player.get('space','world'))


async def dash(room, player, raw_x=0, raw_y=0):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('downedUntil') or 0) or player.get('heldObjectId') or player.get('ridingCartId') or player.get('carriedTargetId') or player.get('carriedBy') or now < float(player.get('stunnedUntil') or 0) or now < float(player.get('parryRecoveryUntil') or 0) or player.get('comboTarget'):
        return
    if player.get('dashActive') or now < float(player.get('dashReadyAt') or 0):
        return
    x = clamp(float(raw_x or 0), -1, 1)
    y = clamp(float(raw_y or 0), -1, 1)
    length = math.hypot(x, y)
    if length > .08:
        angle = math.atan2(y, x)
    else:
        angle = float(player.get('direction') or (0 if player.get('facing',1) >= 0 else math.pi))
    if player.get('comboOwner'):
        owner = room['players'].get(player.get('comboOwner'))
        if owner and owner.get('comboTarget') == player['id']:
            cancel_combo(room, owner, release_target=True)
        player['comboOwner'] = None
    player['invulnerableUntil'] = max(float(player.get('invulnerableUntil') or 0), now + DASH_INVULNERABILITY)
    player['dashActive'] = True
    player['dashEndAt'] = now + DASH_DURATION
    player['dashReadyAt'] = now + DASH_DURATION + DASH_COOLDOWN
    player['dashAngle'] = angle
    player['dashAttackPending'] = True
    player['sprinting'] = False
    player['parrying'] = False
    player['parryUntil'] = 0
    player['direction'] = angle
    player['facing'] = 1 if math.cos(angle) >= 0 else -1
    player['moveVx'] = player['moveVy'] = 0
    await broadcast(room, {'type':'combat','event':{
        'kind':'dash-start','attackerId':player['id'],'targetId':None,'angle':angle,'hit':False,
        'durationMs':round(DASH_DURATION*1000),'x':player['x'],'y':player['y']-42
    }}, space=player.get('space','world'))


async def resolve_parry(room, attacker, defender, angle):
    now = time.monotonic()
    defender['parrying'] = False
    defender['parryUntil'] = 0
    defender['parryRecoveryUntil'] = now + 0.09
    defender['parryReadyAt'] = min(float(defender.get('parryReadyAt') or now), now + 0.34)
    attacker['stunnedUntil'] = max(float(attacker.get('stunnedUntil') or 0), now + PARRY_STUN)
    attacker['vulnerableUntil'] = max(float(attacker.get('vulnerableUntil') or 0), now + PARRY_STUN + 0.12)
    attacker['dashActive'] = False
    attacker['dashAttackPending'] = False
    attacker['moveVx'] = attacker['moveVy'] = 0
    attacker['impulseX'] -= math.cos(angle) * 260
    attacker['impulseY'] -= math.sin(angle) * 260
    cancel_combo(room, attacker)
    await broadcast(room, {'type':'combat','event':{
        'kind':'parry','attackerId':attacker['id'],'targetId':defender['id'],'angle':angle,
        'hit':True,'parried':True,'damage':0,'durationMs':round(PARRY_STUN*1000),
        'x':(attacker['x']+defender['x'])/2,'y':(attacker['y']+defender['y'])/2-48
    }}, space=attacker.get('space','world'))


async def broadcast_attack_start(room, attacker, target_id, style_name, style, step, kind, duration, windup, dash_attack=False):
    await broadcast(room, {'type':'combat','event':{
        'kind':'attack-step','attackerId':attacker['id'],'targetId':target_id,
        'angle':attacker.get('attackAngle', attacker.get('direction', 0)),
        'hand':attacker.get('attackHand','right'),'attackKind':kind,
        'comboStep':step,'comboLength':len(style['kinds']),
        'hit':False,'dashAttack':dash_attack and step == 0,
        'durationMs':round(duration*1000),'contactMs':round(windup*1000),'arcRadians':attack_arc_for_kind(kind),'style':style_name,
        'x':attacker['x']+math.cos(attacker.get('attackAngle',0))*80,
        'y':attacker['y']+math.sin(attacker.get('attackAngle',0))*80-46
    }}, space=attacker.get('space','world'))


def style_speed(attacker):
    speed = float(attacker.get('attackSpeedMult') or 1)
    weapon = (attacker.get('loadout') or {}).get('weapon')
    if weapon:
        path = str(weapon.get('path') or 'balanced')
        speed *= {'balanced':1.0,'power':0.94,'swift':1.16,'reach':0.98}.get(path,1.0)
        speed *= 1 + max(0, int(weapon.get('masteryRank') or 1)-1)*0.008
    return clamp(speed, 0.72, 1.48)


def attack_arc_for_kind(kind):
    kind = str(kind or '')
    if any(token in kind for token in ('spin', 'roundhouse')):
        return 1.18
    if any(token in kind for token in ('hook', 'backslash', 'diagonal', 'rising-cut')):
        return 0.92
    if any(token in kind for token in ('sidekick', 'low-kick', 'front-kick')):
        return 0.76
    if any(token in kind for token in ('overhand', 'overhead', 'finisher', 'backhand', 'uppercut')):
        return 0.70
    return 0.58


def attack_telegraph_floor(kind, step):
    kind = str(kind or '')
    step_bonus = min(0.026, max(0, int(step)) * 0.006)
    if any(token in kind for token in ('finisher', 'spin', 'roundhouse', 'sidekick', 'overhand', 'overhead', 'backhand', 'thrust-heavy')):
        return 0.235 + step_bonus
    if any(token in kind for token in ('hook', 'uppercut', 'kick', 'knee', 'rising-cut', 'long-straight')):
        return 0.175 + step_bonus
    return 0.140 + step_bonus


def move_timing(attacker, style, step):
    speed = style_speed(attacker)
    kind = style['kinds'][step]
    duration = float(style['durations'][step]) / speed
    # Attack upgrades may shorten recovery, but the readable startup tell stays consistent.
    raw_windup = float(style['windups'][step]) / math.sqrt(speed)
    windup = max(attack_telegraph_floor(kind, step), raw_windup)
    minimum_followthrough = 0.105 if windup < 0.17 else 0.145
    duration = max(duration, windup + minimum_followthrough)
    return max(0.235, duration), min(duration * 0.72, windup)


def target_position(room, target_id):
    if target_id == 'training-dummy':
        return DUMMY_X, DUMMY_Y
    target = room['players'].get(target_id)
    if not target:
        return None
    return target['x'], target['y']


def training_target_available(attacker, max_distance):
    if attacker.get('space','world') != 'world':
        return False, float('inf')
    distance = math.hypot(DUMMY_X-attacker['x'], DUMMY_Y-attacker['y'])
    return distance <= max_distance, distance


async def finish_manual_attack(room, attacker_id, token_value, action_serial, style_name, step, hit_confirmed, final):
    attacker = room['players'].get(attacker_id)
    if not attacker:
        return
    now = time.monotonic()
    if int(attacker.get('comboToken') or 0) != token_value or int(attacker.get('attackActionSerial') or 0) != action_serial:
        return
    attacker['attackAnimatingUntil'] = 0
    attacker['attackQueueOpenAt'] = 0
    attacker['attackQueueCloseAt'] = 0
    style = STYLE_DATA.get(style_name, STYLE_DATA['Street Brawler'])
    if final:
        attacker['attackQueued'] = False
        recovery = float(style.get('recovery') or .4)
        attacker['attackRecoveryUntil'] = now + recovery
        attacker['vulnerableUntil'] = max(float(attacker.get('vulnerableUntil') or 0), now + recovery * 0.78)
        cancel_combo(room, attacker, release_target=True)
        return
    if hit_confirmed and attacker.get('chainLocked'):
        attacker['attackQueued'] = False
        attacker['attackRecoveryUntil'] = now + MASH_RECOVERY_PENALTY
        attacker['vulnerableUntil'] = max(float(attacker.get('vulnerableUntil') or 0), now + MASH_RECOVERY_PENALTY)
        await combat_feedback(attacker, 'Mash blocked the chain', 'mash')
        cancel_combo(room, attacker, release_target=True)
        return
    if hit_confirmed and attacker.get('attackQueued') and attacker.get('comboTarget'):
        attacker['attackQueued'] = False
        await start_attack(room, attacker, False, from_queue=True)
        return
    if not hit_confirmed:
        attacker['attackQueued'] = False
        recovery = float(style.get('whiffRecovery') or .42)
        attacker['attackRecoveryUntil'] = now + recovery
        attacker['vulnerableUntil'] = max(float(attacker.get('vulnerableUntil') or 0), now + recovery)
        await combat_feedback(attacker, 'Whiff — punishable', 'whiff')
        cancel_combo(room, attacker, release_target=True)
        return
    # A confirmed hit may still be linked by one deliberate click shortly after the animation.
    attacker['attackRecoveryUntil'] = now + 0.055


async def resolve_manual_attack(room, attacker_id, token_value, action_serial, style_name, step, target_id, dash_attack, duration, windup):
    await asyncio.sleep(windup)
    attacker = room['players'].get(attacker_id)
    if not attacker:
        return
    now = time.monotonic()
    if int(attacker.get('comboToken') or 0) != token_value or int(attacker.get('attackActionSerial') or 0) != action_serial:
        return
    if attacker.get('knockedOut') or now < float(attacker.get('stunnedUntil') or 0):
        cancel_combo(room, attacker)
        return
    style = STYLE_DATA.get(style_name, STYLE_DATA['Street Brawler'])
    kind = style['kinds'][step]
    position = target_position(room, target_id)
    hit_confirmed = False
    final = step == len(style['kinds'])-1
    if position:
        tx, ty = position
        target_angle = math.atan2(ty-attacker['y'], tx-attacker['x'])
        angle = float(attacker.get('attackAngle') or attacker.get('direction') or 0)
        distance = math.hypot(tx-attacker['x'], ty-attacker['y'])
        angle_error = abs(angle_difference(target_angle, angle))
        weapon = (attacker.get('loadout') or {}).get('weapon')
        reach_mult = float(attacker.get('reachMult') or 1) * float(style.get('reach') or 1)
        if weapon:
            reach_mult *= float(attacker.get('weaponReachMult') or 1)
        step_reach = (PUNCH_RANGE + (30 if dash_attack and step == 0 else 0) + min(32, step*6)) * reach_mult
        attack_arc = attack_arc_for_kind(kind)
        if distance <= step_reach and angle_error <= attack_arc:
            if target_id == 'training-dummy':
                hit_confirmed = True
                attacker['attackHitConfirmed'] = True
                attacker['comboTarget'] = 'training-dummy'
                attacker['comboStep'] = step
                attacker['comboLength'] = len(style['kinds'])
                attacker['comboDeadline'] = time.monotonic() + max(COMBO_INPUT_GRACE, duration-windup+0.30)
                await broadcast(room, {'type':'combat','event':{
                    'kind':'attack-impact','attackerId':attacker_id,'targetId':'training-dummy','angle':angle,
                    'hand':attacker['attackHand'],'attackKind':kind,'comboStep':step,'comboLength':len(style['kinds']),
                    'hit':True,'damage':0,'knockedOut':False,'finisher':final,'dashAttack':dash_attack and step == 0,
                    'durationMs':round(duration*1000),'style':style_name,'x':DUMMY_X,'y':DUMMY_Y-58
                }}, space='world')
            else:
                target = room['players'].get(target_id)
                if target and target.get('connected') and target.get('space','world') == attacker.get('space','world') and not target.get('knockedOut'):
                    if time.monotonic() < float(target.get('parryUntil') or 0) and parry_faces_attacker(target, attacker):
                        await resolve_parry(room, attacker, target, angle)
                        return
                    # Interrupt a different combo owner immediately.
                    if target.get('comboTarget'):
                        cancel_combo(room, target)
                    if target.get('comboOwner') and target.get('comboOwner') != attacker_id:
                        hit_confirmed = False
                    else:
                        hit_confirmed = True
                        attacker['attackHitConfirmed'] = True
                        attacker['comboTarget'] = target_id
                        attacker['comboStep'] = step
                        attacker['comboLength'] = len(style['kinds'])
                        target['comboOwner'] = attacker_id
                        attacker['comboDeadline'] = time.monotonic() + max(COMBO_INPUT_GRACE, duration-windup+0.30)
                        base_damage = style['damage'][step]
                        if weapon:
                            level = int(weapon.get('level') or 1)
                            mastery = int(weapon.get('masteryRank') or 1)
                            progression_mult = min(1.72, 1 + max(0, level-1)*0.017 + max(0, mastery-1)*0.022)
                            damage_mult = float(attacker.get('weaponDamageMult') or 1) * progression_mult
                        else:
                            damage_mult = float(attacker.get('punchDamageMult') or 1)
                        if dash_attack and step == 0:
                            damage_mult *= 1.08
                        counter = time.monotonic() < float(target.get('vulnerableUntil') or 0)
                        if counter:
                            damage_mult *= COUNTER_DAMAGE_MULT
                        damage = max(1, round(base_damage * damage_mult))
                        target['health'] = max(0, float(target.get('health') or 0)-damage)
                        knockback = float(style['knockback'][step]) * (1.12 if dash_attack and step == 0 else 1)
                        target['impulseX'] += math.cos(angle)*knockback
                        target['impulseY'] += math.sin(angle)*knockback
                        attacker['impulseX'] += math.cos(angle)*min(128, knockback*.30)
                        attacker['impulseY'] += math.sin(angle)*min(128, knockback*.30)
                        move_with_collisions(attacker, math.cos(angle)*float(style['advance'][step]), math.sin(angle)*float(style['advance'][step]))
                        move_with_collisions(target, math.cos(angle)*float(style['targetAdvance'][step]), math.sin(angle)*float(style['targetAdvance'][step]))
                        hitstun = float(style.get('hitstun', [0.18] * len(style['kinds']))[step]) + (COUNTER_STUN_BONUS if counter else 0)
                        target['stunnedUntil'] = max(float(target.get('stunnedUntil') or 0), time.monotonic() + hitstun)
                        target['moving'] = target['sprinting'] = False
                        target['moveVx'] = target['moveVy'] = 0
                        target['parrying'] = False
                        target['parryUntil'] = 0
                        knocked_out = target['health'] <= 0
                        if knocked_out:
                            knockout(room, target, attacker)
                            asyncio.create_task(reward_knockout(attacker))
                        await broadcast(room, {'type':'combat','event':{
                            'kind':'attack-impact','attackerId':attacker_id,'targetId':target_id,'angle':angle,
                            'hand':attacker['attackHand'],'attackKind':kind,'comboStep':step,'comboLength':len(style['kinds']),
                            'hit':True,'damage':damage,'knockedOut':knocked_out,'finisher':final,'dashAttack':dash_attack and step == 0,'counter':counter,
                            'durationMs':round(duration*1000),'style':style_name,
                            'x':(attacker['x']+target['x'])/2,'y':(attacker['y']+target['y'])/2-48
                        }}, space=attacker.get('space','world'))
                        if weapon:
                            asyncio.create_task(award_weapon_mastery(room, attacker, 12 if knocked_out else 7, knockout=knocked_out))
                        if knocked_out:
                            final = True
    remaining = max(0, duration-windup)
    await asyncio.sleep(remaining)
    await finish_manual_attack(room, attacker_id, token_value, action_serial, style_name, step, hit_confirmed, final)


async def start_attack(room, attacker, dash_attack=False, from_queue=False):
    now = time.monotonic()
    if attacker.get('knockedOut') or now < float(attacker.get('downedUntil') or 0) or attacker.get('heldObjectId') or attacker.get('ridingCartId') or attacker.get('carriedTargetId') or attacker.get('carriedBy') or now < float(attacker.get('stunnedUntil') or 0) or now < float(attacker.get('parryRecoveryUntil') or 0):
        return
    if attacker.get('comboOwner'):
        return
    if attacker.get('dashActive') and not dash_attack:
        return

    if now < float(attacker.get('attackAnimatingUntil') or 0):
        if dash_attack or attacker.get('attackQueued'):
            return
        open_at = float(attacker.get('attackQueueOpenAt') or 0)
        close_at = float(attacker.get('attackQueueCloseAt') or 0)
        if now < open_at:
            attacker['earlyMashCount'] = int(attacker.get('earlyMashCount') or 0) + 1
            if attacker['earlyMashCount'] >= EARLY_MASH_LIMIT:
                attacker['chainLocked'] = True
                await combat_feedback(attacker, 'Too early — chain locked', 'mash')
            return
        if now <= close_at and attacker.get('attackHitConfirmed') and not attacker.get('chainLocked'):
            attacker['attackQueued'] = True
            await combat_feedback(attacker, 'Chain queued', 'chain')
        return

    if not from_queue and not attacker.get('comboTarget') and not dash_attack and now < float(attacker.get('attackRecoveryUntil') or 0):
        return

    style_name = effective_style(attacker)
    style = STYLE_DATA[style_name]
    combo_target = attacker.get('comboTarget')
    if combo_target and now > float(attacker.get('comboDeadline') or 0):
        cancel_combo(room, attacker)
        combo_target = None
    if combo_target:
        if attacker.get('chainLocked'):
            cancel_combo(room, attacker)
            return
        step = int(attacker.get('comboStep') or 0) + 1
        if step >= len(style['kinds']):
            cancel_combo(room, attacker)
            return
        target_id = combo_target
        token_value = int(attacker.get('comboToken') or 0)
    else:
        step = 0
        weapon = (attacker.get('loadout') or {}).get('weapon')
        reach_mult = float(attacker.get('reachMult') or 1) * float(style.get('reach') or 1)
        if weapon:
            reach_mult *= float(attacker.get('weaponReachMult') or 1)
        lock_distance = (300 if dash_attack else PUNCH_LOCK) * reach_mult
        target, player_distance = nearest_combat_target(room, attacker, lock_distance)
        dummy_ok, dummy_distance = training_target_available(attacker, lock_distance)
        target_id = None
        if target and (not dummy_ok or player_distance <= dummy_distance):
            target_id = target['id']
        elif dummy_ok:
            target_id = 'training-dummy'
        angle = float(attacker.get('dashAngle') if dash_attack else attacker.get('direction') or 0)
        if target_id:
            position = target_position(room, target_id)
            if position:
                angle = math.atan2(position[1]-attacker['y'], position[0]-attacker['x'])
        attacker['attackAngle'] = angle
        attacker['direction'] = angle
        attacker['facing'] = 1 if math.cos(angle) >= 0 else -1
        attacker['comboToken'] = int(attacker.get('comboToken') or 0) + 1
        token_value = int(attacker['comboToken'])
        attacker['comboStep'] = -1
        attacker['comboLength'] = len(style['kinds'])
        attacker['comboDashStarter'] = bool(dash_attack)

    weapon = (attacker.get('loadout') or {}).get('weapon')
    stamina_cost = int(style.get('stamina', [8] * len(style['kinds']))[step])
    if weapon:
        path = str(weapon.get('path') or 'balanced')
        stamina_cost += {'power':2, 'swift':-1, 'reach':1}.get(path, 0)
    if dash_attack and step == 0:
        stamina_cost += 4
    stamina_cost = max(4, stamina_cost)
    if float(attacker.get('stamina') or 0) < stamina_cost:
        await combat_feedback(attacker, 'Low stamina', 'stamina')
        attacker['attackRecoveryUntil'] = now + 0.18
        if attacker.get('comboTarget'):
            cancel_combo(room, attacker)
        return

    duration, windup = move_timing(attacker, style, step)
    kind = style['kinds'][step]
    hand = style.get('hands',[])[step] if step < len(style.get('hands',[])) else ('left' if step % 2 == 0 else 'right')
    attacker['stamina'] = max(0, float(attacker.get('stamina') or 0) - stamina_cost)
    attacker['lastStaminaUseAt'] = now
    attacker['attackHand'] = hand
    attacker['attackKind'] = kind
    attacker['attackArc'] = attack_arc_for_kind(kind)
    attacker['attackAngle'] = float(attacker.get('attackAngle') or attacker.get('direction') or 0)
    attacker['sprinting'] = False
    attacker['parrying'] = False
    attacker['parryUntil'] = 0
    attacker['dashActive'] = False
    attacker['dashAttackPending'] = False
    attacker['lastPunchAt'] = now
    attacker['attackQueued'] = False
    attacker['attackHitConfirmed'] = False
    attacker['earlyMashCount'] = 0
    attacker['chainLocked'] = False
    attacker['attackAnimatingUntil'] = now + duration
    queue_open = now + max(windup + 0.055, duration * 0.48)
    queue_close = min(now + duration - 0.025, queue_open + 0.17)
    attacker['attackQueueOpenAt'] = queue_open
    attacker['attackQueueCloseAt'] = max(queue_open + 0.055, queue_close)
    attacker['attackActionSerial'] = int(attacker.get('attackActionSerial') or 0) + 1
    action_serial = int(attacker['attackActionSerial'])
    await broadcast_attack_start(room, attacker, target_id, style_name, style, step, kind, duration, windup, dash_attack)
    asyncio.create_task(resolve_manual_attack(room, attacker['id'], token_value, action_serial, style_name, step, target_id, dash_attack, duration, windup))


async def punch(room, attacker):
    await start_attack(room, attacker, False)


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
    release_held_object(room, player, place=True)
    player['space'] = f'room:{owner_id}'
    player['roomOwner'] = owner_id
    player['x'], player['y'] = 460, 350
    if player['id'] in room.get('boomboxes', {}):
        room['boomboxes'][player['id']].update({'mode':'held','space':player['space'],'x':player['x'],'y':player['y']})
        await broadcast_boombox_state(room, player['id'])
    player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
    await send(player['ws'], {'type':'space-change','space':player['space'],'ownerId':owner_id,'ownerName':owner_name})
    await send_world(room, player['ws'])
    await snapshot(room)

async def leave_personal_room(room, player):
    release(room, player)
    release_held_object(room, player, place=True)
    player['space'] = 'world'; player['roomOwner'] = None
    player['x'], player['y'] = ROOM_DOOR[0], ROOM_DOOR[1]-100
    if player['id'] in room.get('boomboxes', {}):
        room['boomboxes'][player['id']].update({'mode':'held','space':'world','x':player['x'],'y':player['y']})
        await broadcast_boombox_state(room, player['id'])
    player['vx'] = player['vy'] = player['moveVx'] = player['moveVy'] = 0
    await send(player['ws'], {'type':'space-change','space':'world'})
    await send_world(room, player['ws']); await snapshot(room)

async def interact(room, player):
    await physics_interact(room, player)

async def buy_item(room, player, item_id):
    item_id=str(item_id or '')
    catalog={
        'knockback-grenade':('grenadeCount',GRENADE_MAX,GRENADE_COST,'Knockback grenade'),
        'gravity-grenade':('gravityGrenadeCount',GRAVITY_GRENADE_MAX,GRAVITY_GRENADE_COST,'Gravity grenade'),
        'airstrike-phone':('airstrikeCount',AIRSTRIKE_MAX,AIRSTRIKE_COST,'Airstrike phone'),
    }
    if item_id not in catalog:
        await send(player['ws'], {'type':'purchase-result','ok':False,'message':'That shop item is unavailable.'})
        return
    field,maximum,cost,label=catalog[item_id]
    count=int(player.get(field) or 0)
    if count>=maximum:
        await send(player['ws'],{'type':'purchase-result','ok':False,'message':f'You can carry at most {maximum} {label.lower()} item(s).','grenadeCount':int(player.get('grenadeCount') or 0),'gravityGrenadeCount':int(player.get('gravityGrenadeCount') or 0),'airstrikeCount':int(player.get('airstrikeCount') or 0)})
        return
    if int(player.get('coins') or 0)<cost:
        await send(player['ws'],{'type':'purchase-result','ok':False,'message':f'You need {cost} coins.','grenadeCount':int(player.get('grenadeCount') or 0),'gravityGrenadeCount':int(player.get('gravityGrenadeCount') or 0),'airstrikeCount':int(player.get('airstrikeCount') or 0)})
        return
    player['coins']-=cost
    player[field]=count+1
    save_character(player)
    await send_progress(player,f'Bought {label.lower()}')
    await send(player['ws'],{'type':'purchase-result','ok':True,'message':f'{label} added.','grenadeCount':int(player.get('grenadeCount') or 0),'gravityGrenadeCount':int(player.get('gravityGrenadeCount') or 0),'airstrikeCount':int(player.get('airstrikeCount') or 0)})

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
    gravity_now = low_gravity_active(room, now)
    gravity_was = bool(room.get('lowGravityWasActive'))
    if gravity_was and not gravity_now:
        room['lowGravityWasActive'] = False
        asyncio.create_task(broadcast(room, {'type':'chaos-state','chaos':public_chaos_state(room)}, space='world'))
        asyncio.create_task(broadcast(room, {'type':'physics-event','event':{'kind':'low-gravity-end'}}, space='world'))
    elif gravity_now:
        room['lowGravityWasActive'] = True
    if now >= float(room.get('nextLowGravityAt') or 0) and not gravity_now:
        room['lowGravityWarningAt']=now+5.0
        room['nextLowGravityAt']=now+5.0+LOW_GRAVITY_DURATION+random.uniform(LOW_GRAVITY_INTERVAL_MIN,LOW_GRAVITY_INTERVAL_MAX)
        asyncio.create_task(broadcast(room,{'type':'physics-event','event':{'kind':'low-gravity-warning','startsInMs':5000}},space='world'))
    if room.get('lowGravityWarningAt') and now >= float(room.get('lowGravityWarningAt') or 0):
        room['lowGravityWarningAt']=0.0
        room['lowGravityUntil']=now+LOW_GRAVITY_DURATION
        room['lowGravityWasActive']=True
        asyncio.create_task(broadcast(room,{'type':'chaos-state','chaos':public_chaos_state(room)},space='world'))
        asyncio.create_task(broadcast(room,{'type':'physics-event','event':{'kind':'low-gravity-start','durationMs':int(LOW_GRAVITY_DURATION*1000)}},space='world'))
    for player in connected(room):
        if now >= player.get('nextPassiveCoinAt', now + PASSIVE_COIN_INTERVAL):
            player['nextPassiveCoinAt'] = now + PASSIVE_COIN_INTERVAL
            player['missionStats']['minutes'] = player['missionStats'].get('minutes', 0) + 1
            player['records']['minutesOnline'] = player['records'].get('minutesOnline', 0) + 1
            player['records']['coinsEarned'] = player['records'].get('coinsEarned', 0) + PASSIVE_COIN_REWARD
            asyncio.create_task(grant(player, xp=3, coins=PASSIVE_COIN_REWARD, reason='Time played'))
        if player['knockedOut'] and now >= player['respawnAt']:
            respawn(player)
        if player.get('carriedBy'):
            carrier=room.get('players',{}).get(player.get('carriedBy'))
            if not carrier or not carrier.get('connected') or carrier.get('knockedOut') or carrier.get('space','world')!=player.get('space','world'):
                if carrier and carrier.get('carriedTargetId')==player['id']: carrier['carriedTargetId']=None
                player['carriedBy']=None
            else:
                angle=float(carrier.get('direction') or 0)
                player['x']=carrier['x']-math.cos(angle)*42
                player['y']=carrier['y']-math.sin(angle)*42
                player['vx']=carrier.get('vx',0); player['vy']=carrier.get('vy',0)
                player['moveVx']=player['moveVy']=0; player['moving']=carrier.get('moving',False)
                player['downedUntil']=max(float(player.get('downedUntil') or 0),now+.25)
                continue
        if player.get('ridingCartId'):
            cart=room.get('physicsObjects',{}).get(player.get('ridingCartId'))
            if not cart or cart.get('riderId')!=player['id']:
                player['ridingCartId']=None
            else:
                player['input']=sanitize_input({}); player['moveVx']=player['moveVy']=0
                continue
        if not player.get('knockedOut') and player.get('downedUntil') and now >= float(player.get('downedUntil') or 0):
            player['downedUntil'] = 0.0
            player['downedImmunityUntil'] = now + 0.55
        if player.get('frozen') or now - float(player.get('lastInputAt') or now) > .75:
            player['input'] = sanitize_input({})

        player['parrying'] = now < float(player.get('parryUntil') or 0)
        if player.get('comboTarget') and now > float(player.get('comboDeadline') or 0) and now >= float(player.get('attackAnimatingUntil') or 0):
            cancel_combo(room, player, release_target=True)
        control = player['input']
        length = math.hypot(control['x'], control['y'])
        x = control['x'] / length if length > 1 else control['x']
        y = control['y'] / length if length > 1 else control['y']
        stunned = now < float(player.get('stunnedUntil') or 0)
        in_parry_recovery = now < float(player.get('parryRecoveryUntil') or 0)
        combo_locked = bool(player.get('comboOwner')) and stunned
        combo_attacking = bool(player.get('comboTarget'))
        downed = now < float(player.get('downedUntil') or 0)
        can_act = not player['knockedOut'] and not downed and not stunned and not in_parry_recovery
        if player.get('emote') and (now >= float(player.get('emoteUntil') or 0) or length > .08 or player['knockedOut'] or downed or stunned or combo_locked or combo_attacking or player.get('dashActive') or player.get('parrying')):
            cancel_emote(player)

        if player.get('dashActive'):
            desired_angle = player.get('dashAngle', player.get('direction', 0))
            if length > .08:
                desired_angle = math.atan2(y, x)
            current = float(player.get('dashAngle') or 0)
            diff = angle_difference(desired_angle, current)
            max_turn = DASH_TURN_RATE * dt
            current += clamp(diff, -max_turn, max_turn)
            player['dashAngle'] = current
            player['direction'] = current
            player['facing'] = 1 if math.cos(current) >= 0 else -1
            player['moving'] = True
            player['sprinting'] = False
            player['moveVx'] = math.cos(current) * DASH_SPEED
            player['moveVy'] = math.sin(current) * DASH_SPEED
            player['vx'] = player['moveVx'] + player['impulseX']
            player['vy'] = player['moveVy'] + player['impulseY']
            bound_w, bound_h = (ROOM_W, ROOM_H) if player.get('space','world').startswith('room:') else (WORLD_W, WORLD_H)
            move_with_collisions(player, player['vx'] * dt, player['vy'] * dt, bound_w, bound_h)
            player['impulseX'] *= math.exp(-8.5 * dt)
            player['impulseY'] *= math.exp(-8.5 * dt)
            if now >= float(player.get('dashEndAt') or 0):
                player['dashActive'] = False
                player['moveVx'] = player['moveVy'] = 0
                if player.get('dashAttackPending'):
                    player['dashAttackPending'] = False
                    asyncio.create_task(start_attack(room, player, True))
            continue

        held_object = room.get('physicsObjects', {}).get(player.get('heldObjectId')) if player.get('heldObjectId') else None
        burdened = bool(player.get('carriedTargetId')) or (held_object and held_object.get('type') == 'cart')
        player['sprinting'] = can_act and not combo_attacking and not burdened and control['sprint'] and length > .08 and player['stamina'] > 1 and not player['parrying']
        if player['sprinting']:
            player['stamina'] = max(0, player['stamina'] - SPRINT_DRAIN * dt)
            player['lastStaminaUseAt'] = now
        elif now - player['lastStaminaUseAt'] > STAMINA_REGEN_DELAY:
            player['stamina'] = min(STAMINA_MAX, player['stamina'] + STAMINA_REGEN * dt)

        speed = SPEED * player.get('speedMult', 1)
        if player.get('carriedTargetId'):
            speed *= .72
        elif held_object and held_object.get('type') == 'cart':
            speed *= .80
        if player['sprinting']:
            speed *= SPRINT * player.get('sprintMult', 1)
        if not can_act or player['parrying'] or combo_attacking:
            speed = 0
        target_vx = x * speed
        target_vy = y * speed
        blend = 1 - math.exp(-(18 if length > .04 else 24) * dt)
        player['moveVx'] += (target_vx - player['moveVx']) * blend
        player['moveVy'] += (target_vy - player['moveVy']) * blend
        player['moving'] = math.hypot(player['moveVx'], player['moveVy']) > 5
        if player['moving'] and can_act and not player['parrying']:
            player['direction'] = math.atan2(player['moveVy'], player['moveVx'])
            player['facing'] = 1 if math.cos(player['direction']) >= 0 else -1

        decay = math.exp((-4.7 if low_gravity_active(room, now) else -8.5) * dt)
        player['impulseX'] *= decay
        player['impulseY'] *= decay
        player['vx'] = player['moveVx'] + player['impulseX']
        player['vy'] = player['moveVy'] + player['impulseY']
        bound_w, bound_h = (ROOM_W, ROOM_H) if player.get('space','world').startswith('room:') else (WORLD_W, WORLD_H)
        move_with_collisions(player, player['vx'] * dt, player['vy'] * dt, bound_w, bound_h)

    simulate_physics(room, dt, now)

    players = connected(room)
    for i, a in enumerate(players):
        for b in players[i+1:]:
            if a.get('space','world') != b.get('space','world'):
                continue
            if a.get('ridingCartId') or b.get('ridingCartId') or a.get('carriedBy') or b.get('carriedBy'):
                continue
            if a.get('comboTarget') == b['id'] or b.get('comboTarget') == a['id']:
                continue
            dx, dy = b['x']-a['x'], b['y']-a['y']
            distance = math.hypot(dx, dy)
            minimum = RADIUS * 1.72
            if distance >= minimum:
                continue
            if distance < .001:
                dx, dy, distance = 1, 0, 1
            push = (minimum-distance) * .5
            nx, ny = dx/distance, dy/distance
            move_with_collisions(a, -nx*push, -ny*push, ROOM_W if a.get('space','world').startswith('room:') else WORLD_W, ROOM_H if a.get('space','world').startswith('room:') else WORLD_H)
            move_with_collisions(b, nx*push, ny*push, ROOM_W if b.get('space','world').startswith('room:') else WORLD_W, ROOM_H if b.get('space','world').startswith('room:') else WORLD_H)

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
    ws = web.WebSocketResponse(max_msg_size=12_000_000, heartbeat=WS_HEARTBEAT, autoping=True, compress=False)
    await ws.prepare(request)
    state = None
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                # V41 keeps gameplay, live voice, and boombox music on separate channels.
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
                    # Never kick the player who is already online. A second device may have
                    # copied the same local character identity; tell the newcomer to create
                    # a fresh identity and reconnect instead.
                    await send(ws, {'type':'duplicate-character','message':'This character identity is already online.'})
                    await ws.close(code=4009, message=b'duplicate character')
                    break
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
            elif message_type in ('attack', 'punch'):
                cancel_emote(player)
                await start_attack(room, player, False)
            elif message_type == 'parry':
                cancel_emote(player)
                await parry(room, player)
            elif message_type == 'dash':
                cancel_emote(player)
                await dash(room, player, message.get('x'), message.get('y'))
            elif message_type == 'interact' or message_type == 'physics-interact':
                await physics_interact(room, player)
            elif message_type == 'object-charge-start':
                await start_throw_charge(room, player)
            elif message_type == 'object-throw':
                await throw_held_object(room, player)
            elif message_type == 'object-kick':
                await kick_object(room, player)
            elif message_type == 'physics-carry':
                await physics_carry(room, player)
            elif message_type == 'use-grenade':
                await use_knockback_grenade(room, player)
            elif message_type == 'use-gravity-grenade':
                await use_gravity_grenade(room, player)
            elif message_type == 'target-airstrike':
                await target_airstrike(room, player, message.get('x'), message.get('y'))
            elif message_type == 'emote':
                emote = clean_emote(message.get('emote'))
                now = time.monotonic()
                if not emote:
                    await send(ws, {'type':'emote-error','message':'Unknown emote. Try /e dance, wave, cheer, laugh, point, or sit.'})
                    continue
                if player.get('knockedOut') or now < float(player.get('stunnedUntil') or 0) or player.get('comboOwner') or player.get('comboTarget') or player.get('dashActive'):
                    await send(ws, {'type':'emote-error','message':'You cannot use an emote right now.'})
                    continue
                if now - float(player.get('lastEmoteAt') or 0) < EMOTE_COOLDOWN:
                    continue
                player['lastEmoteAt'] = now
                player['emote'] = emote
                player['emoteUntil'] = now + EMOTE_DURATIONS[emote]
                player['emoteSerial'] = int(player.get('emoteSerial') or 0) + 1
                player['input'] = sanitize_input({})
                player['moving'] = player['sprinting'] = False
                player['moveVx'] = player['moveVy'] = 0
                event = {
                    'type': 'emote',
                    'id': player['id'],
                    'emote': emote,
                    'emoteSerial': player['emoteSerial'],
                    'durationMs': int(EMOTE_DURATIONS[emote] * 1000),
                }
                await broadcast(room, event, space=player.get('space','world'))
                await send(ws, {'type':'emote-started','emote':emote})
            elif message_type == 'chat':
                text = clean_chat_text(message.get('text'))
                now = time.monotonic()
                if not text:
                    continue
                if now - float(player.get('lastChatAt') or 0) < CHAT_COOLDOWN:
                    await send(ws, {'type':'chat-error','message':'You are sending messages too quickly.'})
                    continue
                player['lastChatAt'] = now
                await broadcast(room, {
                    'type':'chat',
                    'id':player['id'],
                    'name':player['name'],
                    'text':text,
                    'sentAt':int(time.time() * 1000),
                }, space=player.get('space','world'))
            elif message_type == 'boombox-control':
                await control_boombox(room, player, message.get('action'), message.get('trackName'))
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
                stop_all_audio_senders(player)
                voice_ws = player.get('voiceWs')
                music_ws = player.get('musicWs')
                player['voiceWs'] = None
                player['musicWs'] = None
                if voice_ws and not voice_ws.closed:
                    try: await voice_ws.close(code=1001, message=b'game disconnected')
                    except Exception: pass
                if music_ws and not music_ws.closed:
                    try: await music_ws.close(code=1001, message=b'game disconnected')
                    except Exception: pass
                player['ws'] = None
                if player['id'] in room.get('boomboxes', {}):
                    room['boomboxes'].pop(player['id'], None)
                    await broadcast(room, {'type':'boombox-remove','ownerId':player['id']})
                player['input'] = sanitize_input({})
                player['moving'] = player['blocking'] = player['sprinting'] = player['parrying'] = False
                release(room, player)
                release_held_object(room, player, place=True)
                save_character(player)
                await snapshot(room)
                player['remove_task'] = asyncio.create_task(remove_later(room, player))
    return ws


def audio_distance_ok(source_x, source_y, receiver, max_distance):
    try:
        dx = float(receiver.get('x') or 0) - float(source_x or 0)
        dy = float(receiver.get('y') or 0) - float(source_y or 0)
        return dx * dx + dy * dy <= max_distance * max_distance
    except Exception:
        return False


def boombox_source_position(room, player):
    boom = public_boombox(room, player['id'])
    if not boom or not boom.get('active'):
        return None
    if boom.get('mode') == 'held':
        return float(player.get('x') or 0), float(player.get('y') or 0), boom.get('space', player.get('space', 'world'))
    return float(boom.get('x') or 0), float(boom.get('y') or 0), boom.get('space', player.get('space', 'world'))


async def voice_ws_handler(request):
    ws = web.WebSocketResponse(max_msg_size=2_000_000, heartbeat=10, autoping=True, compress=False)
    await ws.prepare(request)
    player = None
    room = None
    try:
        first = await asyncio.wait_for(ws.receive(), timeout=8.0)
        if first.type != WSMsgType.TEXT:
            await ws.close(code=4001, message=b'voice join required')
            return ws
        try:
            hello = json.loads(first.data)
        except Exception:
            hello = {}
        if hello.get('type') != 'voice-join' or int(hello.get('build') or 0) != BUILD or int(hello.get('protocol') or 0) != PROTOCOL:
            await ws.close(code=4002, message=b'voice version mismatch')
            return ws
        session = token(hello.get('sessionToken'))
        for candidate_room in rooms.values():
            player_id = candidate_room.get('sessions', {}).get(session)
            candidate = candidate_room.get('players', {}).get(player_id) if player_id else None
            if candidate and candidate.get('connected'):
                room, player = candidate_room, candidate
                break
        if not player or not room:
            await ws.close(code=4003, message=b'unknown voice session')
            return ws
        old = player.get('voiceWs')
        if old and old is not ws and not old.closed:
            try: await old.close(code=4004, message=b'replaced')
            except Exception: pass
        player['voiceWs'] = ws
        start_stream_sender(player, 'voice')
        await send(ws, {'type':'voice-ready','id':player['id'],'codec':'24khz-pcm16-resampled','channel':'dedicated-voice'})
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                data = bytes(msg.data)
                if len(data) != VOICE_CLIENT_FRAME or data[:1] != b'A' or data[1] != VOICE_CODEC_VERSION:
                    continue
                now = time.monotonic()
                if now - float(player.get('lastVoiceAt') or 0) < VOICE_MIN_INTERVAL:
                    continue
                player['lastVoiceAt'] = now
                source_space = player.get('space', 'world')
                packet = data[:2] + player['id'].encode('ascii') + data[2:]
                sx, sy = player.get('x', 0), player.get('y', 0)
                for other in connected(room, source_space):
                    if other is player or not other.get('voiceWs') or other['voiceWs'].closed:
                        continue
                    if audio_distance_ok(sx, sy, other, VOICE_RELAY_DISTANCE):
                        enqueue_audio(other, packet, is_boombox=False)
            elif msg.type == WSMsgType.TEXT:
                try: message = json.loads(msg.data)
                except Exception: continue
                if message.get('type') == 'voice-ping':
                    await send(ws, {'type':'voice-pong','now':int(time.time()*1000)})
    except (asyncio.TimeoutError, ConnectionError):
        pass
    finally:
        if player and player.get('voiceWs') is ws:
            player['voiceWs'] = None
            stop_stream_sender(player, 'voice')
    return ws


async def music_ws_handler(request):
    ws = web.WebSocketResponse(max_msg_size=2_000_000, heartbeat=12, autoping=True, compress=False)
    await ws.prepare(request)
    player = None
    room = None
    try:
        first = await asyncio.wait_for(ws.receive(), timeout=8.0)
        if first.type != WSMsgType.TEXT:
            await ws.close(code=4011, message=b'music join required')
            return ws
        try:
            hello = json.loads(first.data)
        except Exception:
            hello = {}
        if hello.get('type') != 'music-join' or int(hello.get('build') or 0) != BUILD or int(hello.get('protocol') or 0) != PROTOCOL:
            await ws.close(code=4012, message=b'music version mismatch')
            return ws
        session = token(hello.get('sessionToken'))
        for candidate_room in rooms.values():
            player_id = candidate_room.get('sessions', {}).get(session)
            candidate = candidate_room.get('players', {}).get(player_id) if player_id else None
            if candidate and candidate.get('connected'):
                room, player = candidate_room, candidate
                break
        if not player or not room:
            await ws.close(code=4013, message=b'unknown music session')
            return ws
        old = player.get('musicWs')
        if old and old is not ws and not old.closed:
            try: await old.close(code=4014, message=b'replaced')
            except Exception: pass
        player['musicWs'] = ws
        start_stream_sender(player, 'music')
        await send(ws, {'type':'music-ready','id':player['id'],'codec':'32khz-adpcm-continuous','channel':'dedicated-music'})
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                data = bytes(msg.data)
                if len(data) != BOOM_CLIENT_FRAME or data[:1] != b'B' or data[1] != BOOM_CODEC_VERSION:
                    continue
                now = time.monotonic()
                if now - float(player.get('lastBoomAt') or 0) < BOOM_MIN_INTERVAL:
                    continue
                player['lastBoomAt'] = now
                source = boombox_source_position(room, player)
                if not source:
                    continue
                sx, sy, source_space = source
                packet = data[:2] + player['id'].encode('ascii') + data[2:]
                for other in connected(room, source_space):
                    if other is player or not other.get('musicWs') or other['musicWs'].closed:
                        continue
                    if audio_distance_ok(sx, sy, other, BOOM_RELAY_DISTANCE):
                        enqueue_audio(other, packet, is_boombox=True)
            elif msg.type == WSMsgType.TEXT:
                try: message = json.loads(msg.data)
                except Exception: continue
                if message.get('type') == 'music-ping':
                    await send(ws, {'type':'music-pong','now':int(time.time()*1000)})
    except (asyncio.TimeoutError, ConnectionError):
        pass
    finally:
        if player and player.get('musicWs') is ws:
            player['musicWs'] = None
            stop_stream_sender(player, 'music')
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
        'service': 'green-floor-v41-spatial-audio-pro',
        'rooms': len(rooms),
        'maxPlayers': MAX_PLAYERS,
        'players': sum(len(connected(room)) for room in rooms.values()),
        'build': BUILD,
        'voice': 'dedicated-24khz-pcm16-resampled', 'music': 'dedicated-32khz-adpcm-continuous', 'singleWorld': True, 'automaticConnection': True, 'roomCodes': False, 'persistence': 'sqlite', 'gameplay': 'multiplayer-spatial-audio-v41',
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
app.router.add_get('/ws/', ws_handler)
app.router.add_get('/voice', voice_ws_handler)
app.router.add_get('/voice/', voice_ws_handler)
app.router.add_get('/music', music_ws_handler)
app.router.add_get('/music/', music_ws_handler)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.getenv('PORT', '10000')))

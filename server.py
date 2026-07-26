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

BUILD = 30
PROTOCOL = 26
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
STAMINA_REGEN = 24
PUNCH_RANGE = 176
PUNCH_LOCK = 680
PARRY_ACTIVE = 0.22
PARRY_RECOVERY = 0.48
PARRY_COOLDOWN = 1.50
PARRY_STUN = 0.72
DASH_DURATION = 0.52
DASH_COOLDOWN = 1.45
DASH_SPEED = 690
DASH_TURN_RATE = 4.25
COMBO_RELEASE_PROTECTION = 0.34
COMBO_INPUT_GRACE = 0.62
ATTACK_QUEUE_LIMIT = 1
KO_TIME = 3.0
RECONNECT_GRACE = 25.0
INTERACT_RANGE = 145
VOICE_MAX_FRAME = 380
VOICE_MIN_INTERVAL = 0.010
CHAT_MAX_LENGTH = 140
CHAT_COOLDOWN = 0.75
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
        "advance":[18,23,18,25,34], "targetAdvance":[10,14,14,18,44],
        "recovery":0.52,"reach":1.00
    },
    "Boxer": {
        "kinds":["boxer-jab","boxer-cross","boxer-lead-hook","boxer-uppercut","boxer-long-straight"],
        "hands":["left","right","left","right","right"],
        "durations":[0.22,0.25,0.29,0.33,0.38],
        "windups":[0.065,0.075,0.095,0.115,0.13],
        "damage":[3,4,4,5,7], "knockback":[52,66,78,96,235],
        "advance":[15,20,15,20,28], "targetAdvance":[7,9,11,13,34],
        "recovery":0.36,"reach":0.94
    },
    "Kickboxer": {
        "kinds":["kickbox-jab","kickbox-cross","kickbox-low-kick","kickbox-knee","kickbox-roundhouse"],
        "hands":["left","right","right","left","right"],
        "durations":[0.25,0.29,0.36,0.39,0.49],
        "windups":[0.075,0.09,0.13,0.14,0.19],
        "damage":[4,4,6,6,9], "knockback":[66,78,112,128,315],
        "advance":[15,20,12,24,30], "targetAdvance":[9,11,15,17,40],
        "recovery":0.50,"reach":1.10
    },
    "Karate": {
        "kinds":["karate-palm","karate-reverse-punch","karate-front-kick","karate-sidekick"],
        "hands":["left","right","left","right"],
        "durations":[0.28,0.32,0.39,0.50],
        "windups":[0.09,0.105,0.145,0.20],
        "damage":[5,6,7,10], "knockback":[82,110,150,350],
        "advance":[16,23,20,32], "targetAdvance":[10,13,18,45],
        "recovery":0.56,"reach":1.07
    },
    "Heavy Weapon": {
        "kinds":["weapon-overhead","weapon-backhand","weapon-thrust-heavy","weapon-finisher"],
        "hands":["right","right","right","right"],
        "durations":[0.46,0.43,0.42,0.60],
        "windups":[0.20,0.18,0.17,0.27],
        "damage":[7,8,8,13], "knockback":[130,155,178,440],
        "advance":[23,21,30,38], "targetAdvance":[14,16,20,50],
        "recovery":0.72,"reach":1.16
    },
    "Light Weapon": {
        "kinds":["weapon-diagonal","weapon-backslash","weapon-thrust","weapon-rising-cut","weapon-spin-finisher"],
        "hands":["right","right","right","right","right"],
        "durations":[0.25,0.27,0.29,0.31,0.43],
        "windups":[0.075,0.085,0.09,0.10,0.16],
        "damage":[3,4,4,5,8], "knockback":[58,70,82,98,275],
        "advance":[16,18,24,18,30], "targetAdvance":[8,10,12,13,38],
        "recovery":0.38,"reach":1.02
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
        'x': clamp(SPAWN_X + math.cos(angle) * min(distance, 120), RADIUS, WORLD_W - RADIUS),
        'y': clamp(SPAWN_Y + math.sin(angle) * min(distance, 120), RADIUS, WORLD_H - RADIUS),
        'vx': 0, 'vy': 0, 'moveVx': 0, 'moveVy': 0,
        'direction': random.random() * math.tau, 'facing': 1,
        'moving': False, 'sprinting': False, 'blocking': False, 'parrying': False,
        'stamina': STAMINA_MAX, 'lastStaminaUseAt': 0,
        'score': 0, 'knockedOut': False, 'respawnAt': 0,
        'lastPunchAt': -10, 'attackRecoveryUntil': 0,
        'attackHand': 'right', 'attackAngle': 0, 'attackKind': 'jab',
        'impulseX': 0, 'impulseY': 0,
        'stunnedUntil': 0, 'invulnerableUntil': 0,
        'parryUntil': 0, 'parryRecoveryUntil': 0, 'parryReadyAt': 0,
        'dashActive': False, 'dashEndAt': 0, 'dashReadyAt': 0, 'dashAngle': 0, 'dashAttackPending': False,
        'comboOwner': None, 'comboTarget': None, 'comboStep': -1, 'comboLength': 0, 'comboToken': 0,
        'comboDeadline': 0, 'comboDashStarter': False,
        'attackAnimatingUntil': 0, 'attackQueueOpenAt': 0, 'attackQueued': False, 'attackActionSerial': 0,
        'space': 'world', 'roomOwner': None,
        'title': 'New Student',
        'inventory': sanitize_inventory(inventory),
        'connected': False, 'ws': None, 'input': sanitize_input({}),
        'sessionToken': session, 'remove_task': None,
        'lastVoiceAt': 0.0, 'lastBoomAt': 0.0, 'lastChatAt': 0.0,
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
    if release_target and target_id and target_id != 'training-dummy':
        target = room['players'].get(target_id)
        if target and target.get('comboOwner') == attacker['id']:
            target['comboOwner'] = None
            target['stunnedUntil'] = min(float(target.get('stunnedUntil') or 0), time.monotonic() + 0.06)
            target['invulnerableUntil'] = max(float(target.get('invulnerableUntil') or 0), time.monotonic() + COMBO_RELEASE_PROTECTION)


def public_player(player):
    excluded = {'ws', 'input', 'sessionToken', 'remove_task', 'connected', 'inventory', 'loadout', 'roomArt', 'lastVoiceAt', 'lastBoomAt', 'lastChatAt', 'lastInputAt', 'isAdmin', 'characterSecret', 'roomRef', 'nextPassiveCoinAt'}
    result = {k: v for k, v in player.items() if k not in excluded}
    result['inventoryCount'] = len(player.get('inventory') or [])
    weapon = (player.get('loadout') or {}).get('weapon')
    result['weaponLevel'] = int(weapon.get('level') or 0) if weapon else 0
    result['weaponMasteryRank'] = int(weapon.get('masteryRank') or 0) if weapon else 0
    now = time.monotonic()
    result['parrying'] = now < float(player.get('parryUntil') or 0)
    result['stunned'] = now < float(player.get('stunnedUntil') or 0)
    result['comboLocked'] = bool(player.get('comboOwner'))
    result['parryCooldown'] = max(0.0, float(player.get('parryReadyAt') or 0) - now)
    result['dashCooldown'] = max(0.0, float(player.get('dashReadyAt') or 0) - now)
    result['dashActive'] = bool(player.get('dashActive'))
    result['combatStyle'] = effective_style(player)
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
    target['knockedOut'] = True
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
    return abs(angle_difference(toward_attacker, facing_angle)) <= 1.45


async def parry(room, player):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('stunnedUntil') or 0) or player.get('comboOwner') or player.get('comboTarget') or player.get('dashActive'):
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
        'kind':'parry-start','attackerId':player['id'],'targetId':None,'angle':player.get('direction',0),'visualMs':520,
        'hit':False,'parried':False,'durationMs':round(PARRY_ACTIVE*1000),'x':player['x'],'y':player['y']-50
    }}, space=player.get('space','world'))


async def dash(room, player, raw_x=0, raw_y=0):
    now = time.monotonic()
    if player.get('knockedOut') or now < float(player.get('stunnedUntil') or 0) or now < float(player.get('parryRecoveryUntil') or 0) or player.get('comboOwner') or player.get('comboTarget'):
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
    defender['parryRecoveryUntil'] = now + 0.11
    defender['parryReadyAt'] = min(float(defender.get('parryReadyAt') or now), now + 0.42)
    attacker['stunnedUntil'] = max(float(attacker.get('stunnedUntil') or 0), now + PARRY_STUN)
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
        'durationMs':round(duration*1000),'contactMs':round(windup*1000),'style':style_name,
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


def move_timing(attacker, style, step):
    speed = style_speed(attacker)
    duration = float(style['durations'][step]) / speed
    windup = min(duration * 0.68, float(style['windups'][step]) / speed)
    return max(0.18, duration), max(0.045, windup)


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
    if final:
        target_id = attacker.get('comboTarget')
        attacker['attackQueued'] = False
        attacker['attackRecoveryUntil'] = now + float(STYLE_DATA.get(style_name, STYLE_DATA['Street Brawler']).get('recovery') or .4)
        cancel_combo(room, attacker, release_target=True)
        return
    if hit_confirmed and attacker.get('attackQueued') and attacker.get('comboTarget'):
        attacker['attackQueued'] = False
        await start_attack(room, attacker, False, from_queue=True)
        return
    if not hit_confirmed:
        attacker['attackQueued'] = False
        attacker['attackRecoveryUntil'] = now + 0.22
        cancel_combo(room, attacker, release_target=True)


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
        angle = math.atan2(ty-attacker['y'], tx-attacker['x'])
        distance = math.hypot(tx-attacker['x'], ty-attacker['y'])
        weapon = (attacker.get('loadout') or {}).get('weapon')
        reach_mult = float(attacker.get('reachMult') or 1) * float(style.get('reach') or 1)
        if weapon:
            reach_mult *= float(attacker.get('weaponReachMult') or 1)
        step_reach = (PUNCH_RANGE + (30 if dash_attack and step == 0 else 0) + min(32, step*6)) * reach_mult
        if distance <= step_reach:
            attacker['attackAngle'] = angle
            attacker['direction'] = angle
            attacker['facing'] = 1 if math.cos(angle) >= 0 else -1
            if target_id == 'training-dummy':
                hit_confirmed = True
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
                        damage = max(1, round(base_damage * damage_mult))
                        target['health'] = max(0, float(target.get('health') or 0)-damage)
                        knockback = float(style['knockback'][step]) * (1.12 if dash_attack and step == 0 else 1)
                        target['impulseX'] += math.cos(angle)*knockback
                        target['impulseY'] += math.sin(angle)*knockback
                        attacker['impulseX'] += math.cos(angle)*min(128, knockback*.30)
                        attacker['impulseY'] += math.sin(angle)*min(128, knockback*.30)
                        move_with_collisions(attacker, math.cos(angle)*float(style['advance'][step]), math.sin(angle)*float(style['advance'][step]))
                        move_with_collisions(target, math.cos(angle)*float(style['targetAdvance'][step]), math.sin(angle)*float(style['targetAdvance'][step]))
                        target['stunnedUntil'] = max(float(target.get('stunnedUntil') or 0), attacker['comboDeadline'] + 0.05)
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
                            'hit':True,'damage':damage,'knockedOut':knocked_out,'finisher':final,'dashAttack':dash_attack and step == 0,
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
    if attacker.get('knockedOut') or now < float(attacker.get('stunnedUntil') or 0) or now < float(attacker.get('parryRecoveryUntil') or 0):
        return
    if attacker.get('comboOwner'):
        return
    if attacker.get('dashActive') and not dash_attack:
        return
    if now < float(attacker.get('attackAnimatingUntil') or 0):
        if not dash_attack and not attacker.get('attackQueued'):
            attacker['attackQueued'] = True
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

    duration, windup = move_timing(attacker, style, step)
    kind = style['kinds'][step]
    hand = style.get('hands',[])[step] if step < len(style.get('hands',[])) else ('left' if step % 2 == 0 else 'right')
    attacker['attackHand'] = hand
    attacker['attackKind'] = kind
    attacker['attackAngle'] = float(attacker.get('attackAngle') or attacker.get('direction') or 0)
    attacker['sprinting'] = False
    attacker['parrying'] = False
    attacker['parryUntil'] = 0
    attacker['dashActive'] = False
    attacker['dashAttackPending'] = False
    attacker['lastPunchAt'] = now
    attacker['attackQueued'] = False
    attacker['attackAnimatingUntil'] = now + duration
    attacker['attackQueueOpenAt'] = now + min(duration*.32, 0.14)
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
        combo_locked = bool(player.get('comboOwner'))
        combo_attacking = bool(player.get('comboTarget'))
        can_act = not player['knockedOut'] and not stunned and not combo_locked and not in_parry_recovery

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

        player['sprinting'] = can_act and not combo_attacking and control['sprint'] and length > .08 and player['stamina'] > 1 and not player['parrying']
        if player['sprinting']:
            player['stamina'] = max(0, player['stamina'] - SPRINT_DRAIN * dt)
            player['lastStaminaUseAt'] = now
        elif now - player['lastStaminaUseAt'] > .36:
            player['stamina'] = min(STAMINA_MAX, player['stamina'] + STAMINA_REGEN * dt)

        speed = SPEED * player.get('speedMult', 1)
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

        decay = math.exp(-8.5 * dt)
        player['impulseX'] *= decay
        player['impulseY'] *= decay
        player['vx'] = player['moveVx'] + player['impulseX']
        player['vy'] = player['moveVy'] + player['impulseY']
        bound_w, bound_h = (ROOM_W, ROOM_H) if player.get('space','world').startswith('room:') else (WORLD_W, WORLD_H)
        move_with_collisions(player, player['vx'] * dt, player['vy'] * dt, bound_w, bound_h)

    players = connected(room)
    for i, a in enumerate(players):
        for b in players[i+1:]:
            if a.get('space','world') != b.get('space','world'):
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
            elif message_type in ('attack', 'punch'):
                await start_attack(room, player, False)
            elif message_type == 'parry':
                await parry(room, player)
            elif message_type == 'dash':
                await dash(room, player, message.get('x'), message.get('y'))
            elif message_type == 'interact':
                pass
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
                player['moving'] = player['blocking'] = player['sprinting'] = player['parrying'] = False
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
        'service': 'green-floor-v30',
        'rooms': len(rooms),
        'players': sum(len(connected(room)) for room in rooms.values()),
        'build': BUILD,
        'voice': 'mulaw-websocket-relay+boombox', 'singleWorld': True, 'automaticConnection': True, 'roomCodes': False, 'persistence': 'sqlite', 'gameplay': 'manual-click-combos-distinct-procedural-attacks-v30',
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

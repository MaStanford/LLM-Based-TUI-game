# --- Game Constants ---
GLOBAL_SPEED_MULTIPLIER = 1.5
FLAME_CHAR = "~"
SHOP_INTERACTION_SPEED_THRESHOLD = 5.0
CUTSCENE_RADIUS = 50
SHOP_COOLDOWN = 100


# --- World Generation ---
CITY_SPACING = 800
CITY_SIZE = 200
MIN_BUILDINGS_PER_CITY = 10
MAX_BUILDINGS_PER_CITY = 20
MIN_BUILDING_DIM = 10
MAX_BUILDING_DIM = 20
ROAD_WIDTH = 20
BUILDING_SHOP_BUFFER = 10
UNTARGET_RADIUS = 65
SAFE_ZONE_RADIUS = 20
DESPAWN_RADIUS = 300


# Total spawn rate for obstacles
TOTAL_SPAWN_RATE = 1.0


# --- SFX MIDI Notes (Channel 10) ---
SFX_MAP = {
    "lmg": 38,          # Acoustic Snare
    "hmg": 40,          # Electric Snare
    "flamethrower": 75, # Claves (as a hiss)
    "mine_launcher": 56,# Cowbell
    "player_hit": 48,   # High Tom
    "enemy_hit": 51,    # Ride Cymbal 1
    "explosion": 35,    # Acoustic Bass Drum
    "crash": 49,        # Crash Cymbal 1
}

# Game Balance & Mechanics
MAX_LEVEL = 50
INITIAL_XP_TO_LEVEL = 1000
XP_INCREASE_PER_LEVEL_FACTOR = 1.2
LEVEL_STAT_BONUS_PER_LEVEL = 0.05 # 5% increase per level

# Spawning
MAX_ENEMIES = 10
MAX_FAUNA = 30
MAX_OBSTACLES = 50

# UI & Rendering
MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24
MENU_WIDTH = 60
MENU_HEIGHT = 20

# Colors (Reference Names)
COLOR_PAIR_DEFAULT = "DEFAULT"
COLOR_PAIR_CAR = "CAR"
COLOR_PAIR_OBSTACLE = "OBSTACLE"
COLOR_PAIR_PARTICLE = "PARTICLE"
COLOR_PAIR_FLAME = "FLAME"
COLOR_PAIR_MENU_HIGHLIGHT = "MENU_HIGHLIGHT"
COLOR_PAIR_BUILDING_OUTLINE = "BUILDING_OUTLINE_COLOR"
COLOR_PAIR_FAUNA = "FAUNA"
COLOR_PAIR_UI_XP_BAR = "UI_XP_BAR"
COLOR_PAIR_UI_LOCATION = "UI_LOCATION"

# Ammo Types
AMMO_BULLET = "bullet"
AMMO_HEAVY_BULLET = "heavy_bullet"
AMMO_FUEL = "fuel"

# Pickup Types
PICKUP_LIFETIME = 45.0  # Seconds before a pickup despawns
PICKUP_BLINK_START = 0.5  # Start blinking at 50% lifetime remaining

PICKUP_GAS = "PICKUP_GAS"
PICKUP_REPAIR = "PICKUP_REPAIR"
PICKUP_CASH = "PICKUP_CASH"

FUEL_PRICE = 10
REPAIR_PRICE = 10

# --- Building Destruction ---
BUILDING_RAM_DAMAGE = 0.5          # Multiplier for ramming damage (speed * this)
BUILDING_DESTROY_REP_LOSS = -15    # Rep loss per building destroyed
BUILDING_RETALIATION_THRESHOLD = 3 # Buildings destroyed before enemy wave spawns
BUILDING_BOSS_THRESHOLD = 5        # Buildings destroyed before boss spawns
RETALIATION_ENEMY_COUNT = 5        # Enemies spawned in retaliation wave
GENERIC_BUILDING_DURABILITY = 200  # Default HP for generic buildings

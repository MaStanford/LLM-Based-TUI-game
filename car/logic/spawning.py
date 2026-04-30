import random
import math
from .entity_loader import ENEMY_VEHICLES, ENEMY_CHARACTERS, FAUNA, OBSTACLES, normalize_class_name
from ..data.game_constants import CITY_SPACING, CITY_SIZE, SAFE_ZONE_RADIUS, DESPAWN_RADIUS, MAX_FAUNA, MAX_OBSTACLES
from ..logic.data_loader import FACTION_DATA
from ..world.generation import get_city_faction
from .scaling import get_enemy_scaling

def _apply_faction_name(entity, unit_id, faction_id, game_state):
    """Apply LLM-generated faction name and description to a spawned entity."""
    unit_names = game_state.factions.get(faction_id, {}).get("unit_names", {})
    unit_info = unit_names.get(unit_id, {})
    if unit_info:
        entity.name = unit_info.get("name", getattr(entity, "name", "Unknown"))
        entity.description = unit_info.get("description", "")

def _get_distance_to_nearest_city_center(x, y):
    """Calculates the distance to the nearest city center."""
    grid_x = round(x / CITY_SPACING)
    grid_y = round(y / CITY_SPACING)
    city_center_x = grid_x * CITY_SPACING
    city_center_y = grid_y * CITY_SPACING
    return math.sqrt((x - city_center_x)**2 + (y - city_center_y)**2)

def spawn_initial_entities(game_state, world):
    """Spawns an initial dense field of entities around the player."""
    # Spawn a larger number of obstacles and fauna in a wider radius
    for _ in range(100): # More entities for the initial spawn
        spawn_obstacle(game_state, world, is_initial_spawn=True)
        spawn_fauna(game_state, world, is_initial_spawn=True)

def _get_spawn_coordinates(game_state):
    """
    Finds a random (x, y) coordinate that is outside the safe zone
    but inside the despawn radius, ensuring a sparse distribution.
    """
    for _ in range(30): # 30 attempts to find a valid spot
        # Pick a random point in a square around the player
        dx = random.uniform(-DESPAWN_RADIUS, DESPAWN_RADIUS)
        dy = random.uniform(-DESPAWN_RADIUS, DESPAWN_RADIUS)
        
        # Check if the point is outside the safe zone
        if dx**2 + dy**2 > SAFE_ZONE_RADIUS**2:
            return game_state.car_world_x + dx, game_state.car_world_y + dy
            
    return None, None # Failed to find a spot

def spawn_enemy(game_state, world):
    """Spawns a new enemy."""
    # --- Prevent spawning in the neutral hub city (radius-based) ---
    dist_to_origin = math.sqrt(game_state.car_world_x**2 + game_state.car_world_y**2)
    if dist_to_origin < CITY_SIZE * 1.5:
        return

    max_enemies = game_state.difficulty_mods.get("max_enemies", 5)
    if len(game_state.active_enemies) >= max_enemies:
        return

    # Determine current faction territory and player's reputation
    current_faction_id = get_city_faction(game_state.car_world_x, game_state.car_world_y, game_state.factions)
    player_rep = game_state.faction_reputation.get(current_faction_id, 0)
    faction_control = game_state.faction_control.get(current_faction_id, 50)

    # Determine spawn rate based on location and reputation
    dist_to_city = _get_distance_to_nearest_city_center(game_state.car_world_x, game_state.car_world_y)
    
    base_spawn_chance = min(1.0, max(0, dist_to_city - CITY_SIZE) / (CITY_SPACING / 2))
    
    # Modify spawn chance based on faction control
    if faction_control < 40:
        base_spawn_chance *= 1.5 # 50% increase in chaos
    if faction_control < 20:
        base_spawn_chance *= 2.0 # 100% increase in chaos

    if dist_to_city < CITY_SIZE: # Inside a city
        if player_rep >= 50: # Friendly Hub City
            spawn_chance = 0.0
        elif player_rep <= -50: # Hostile Hub City
            spawn_chance = base_spawn_chance * 2.0
        else: # Neutral or allied town
            spawn_chance = base_spawn_chance * 0.25
    else: # Wilderness
        spawn_chance = base_spawn_chance

    if random.random() > spawn_chance:
        return

    # Try faction-specific units first, then fall back to random
    faction_units = game_state.factions.get(current_faction_id, {}).get("units", [])
    all_enemy_classes = ENEMY_VEHICLES + ENEMY_CHARACTERS
    possible_units = [unit for unit in faction_units if any(normalize_class_name(e.__name__) == normalize_class_name(unit) for e in all_enemy_classes)]
    if possible_units:
        enemy_name = random.choice(possible_units)
        enemy_class = next((e for e in all_enemy_classes if normalize_class_name(e.__name__) == normalize_class_name(enemy_name)), None)
    elif random.random() < 0.7:
        enemy_class = random.choice(ENEMY_VEHICLES)
        enemy_name = enemy_class.__name__
    else:
        enemy_class = random.choice(ENEMY_CHARACTERS)
        enemy_name = enemy_class.__name__

    if not enemy_class:
        return

    sx, sy = _get_spawn_coordinates(game_state)
    if sx is None: return # Could not find a valid spawn point

    if world.get_terrain_at(sx, sy).get("passable", True):
        new_enemy = enemy_class(sx, sy)
        new_enemy.faction_id = current_faction_id
        hp_mult = game_state.difficulty_mods.get("enemy_hp_mult", 1.0)
        dmg_mult = game_state.difficulty_mods.get("enemy_dmg_mult", 1.0)
        # Apply progression scaling on top of difficulty
        prog_hp, prog_dmg, prog_reward = get_enemy_scaling(game_state)
        hp_mult *= prog_hp
        dmg_mult *= prog_dmg
        new_enemy.durability = int(new_enemy.durability * hp_mult)
        new_enemy.max_durability = new_enemy.durability
        if hasattr(new_enemy, 'collision_damage'):
            new_enemy.collision_damage = int(new_enemy.collision_damage * dmg_mult)
        else:
            new_enemy.collision_damage = int(5 * dmg_mult)
        if hasattr(new_enemy, 'shoot_damage'):
            new_enemy.shoot_damage = int(new_enemy.shoot_damage * dmg_mult)
        new_enemy.xp_value = int(new_enemy.xp_value * prog_reward)
        new_enemy.cash_value = int(new_enemy.cash_value * prog_reward)
        # Apply faction-specific vehicle names
        _apply_faction_name(new_enemy, enemy_name, current_faction_id, game_state)
        new_enemy.patrol_target_x = sx + random.uniform(-100, 100)
        new_enemy.patrol_target_y = sy + random.uniform(-100, 100)
        game_state.active_enemies.append(new_enemy)

        # Group spawning: chance to spawn additional enemies of the same type
        roll = random.random()
        extra_count = 0
        if roll < 0.05:
            extra_count = 2  # 5% chance for a trio
        elif roll < 0.20:
            extra_count = 1  # 15% chance for a pair

        for _ in range(extra_count):
            if len(game_state.active_enemies) >= max_enemies:
                break
            offset_x = sx + random.uniform(-15, 15)
            offset_y = sy + random.uniform(-15, 15)
            if world.get_terrain_at(offset_x, offset_y).get("passable", True):
                extra = enemy_class(offset_x, offset_y)
                extra.faction_id = current_faction_id
                extra.durability = int(extra.durability * hp_mult)
                extra.max_durability = extra.durability
                if hasattr(extra, 'collision_damage'):
                    extra.collision_damage = int(extra.collision_damage * dmg_mult)
                else:
                    extra.collision_damage = int(5 * dmg_mult)
                if hasattr(extra, 'shoot_damage'):
                    extra.shoot_damage = int(extra.shoot_damage * dmg_mult)
                extra.xp_value = int(extra.xp_value * prog_reward)
                extra.cash_value = int(extra.cash_value * prog_reward)
                _apply_faction_name(extra, enemy_name, current_faction_id, game_state)
                extra.patrol_target_x = offset_x + random.uniform(-100, 100)
                extra.patrol_target_y = offset_y + random.uniform(-100, 100)
                game_state.active_enemies.append(extra)

def spawn_fauna(game_state, world, is_initial_spawn=False):
    """Spawns a new fauna."""
    if not is_initial_spawn and len(game_state.active_fauna) >= MAX_FAUNA:
        return
    fauna_class = random.choice(FAUNA)
    sx, sy = _get_spawn_coordinates(game_state)
    if sx is None: return

    if world.get_terrain_at(sx, sy).get("passable", True):
        new_fauna = fauna_class(sx, sy)
        game_state.active_fauna.append(new_fauna)

def spawn_obstacle(game_state, world, is_initial_spawn=False):
    """Spawns a new obstacle."""
    if not is_initial_spawn and len(game_state.active_obstacles) >= MAX_OBSTACLES:
        return
    obstacle_class = random.choice(OBSTACLES)
    sx, sy = _get_spawn_coordinates(game_state)
    if sx is None: return

    if world.get_terrain_at(sx, sy).get("passable", True):
        new_obstacle = obstacle_class(sx, sy)
        game_state.active_obstacles.append(new_obstacle)


MAX_TURRETS_PER_CITY = 6

def spawn_turrets(game_state, world):
    """Spawn defense turrets in hostile cities when the player is nearby."""
    from ..entities.turret import Turret

    dist_to_city = _get_distance_to_nearest_city_center(game_state.car_world_x, game_state.car_world_y)
    if dist_to_city > CITY_SIZE:
        return  # Not inside a city

    faction_id = get_city_faction(game_state.car_world_x, game_state.car_world_y, game_state.factions)
    if not faction_id:
        return

    player_rep = game_state.faction_reputation.get(faction_id, 0)
    if player_rep > -50:
        return  # Only spawn in hostile cities

    # Check how many turrets from this faction already exist nearby
    existing = sum(
        1 for t in game_state.active_turrets
        if getattr(t, 'faction_id', None) == faction_id
    )
    if existing >= MAX_TURRETS_PER_CITY:
        return

    # Spawn turrets around the city perimeter
    grid_x = round(game_state.car_world_x / CITY_SPACING)
    grid_y = round(game_state.car_world_y / CITY_SPACING)
    center_x = grid_x * CITY_SPACING
    center_y = grid_y * CITY_SPACING

    count = random.randint(4, MAX_TURRETS_PER_CITY) - existing
    for i in range(count):
        angle = (2 * math.pi * i) / count + random.uniform(-0.3, 0.3)
        dist = CITY_SIZE * 0.7 + random.uniform(-5, 5)
        tx = center_x + dist * math.cos(angle)
        ty = center_y + dist * math.sin(angle)
        if world.get_terrain_at(tx, ty).get("passable", True):
            turret = Turret(tx, ty)
            turret.faction_id = faction_id
            game_state.active_turrets.append(turret)

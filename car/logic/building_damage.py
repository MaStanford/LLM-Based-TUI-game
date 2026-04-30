import random
from ..data.game_constants import (
    GENERIC_BUILDING_DURABILITY, BUILDING_DESTROY_REP_LOSS,
    BUILDING_RETALIATION_THRESHOLD, BUILDING_BOSS_THRESHOLD,
    RETALIATION_ENEMY_COUNT, CITY_SPACING
)
from ..data.buildings import BUILDING_DATA
from ..data.pickups import PICKUP_DATA, PICKUP_CASH
from ..world.generation import get_buildings_in_city


def find_building_at(x, y):
    """Find the building at world coordinates (x, y).
    Returns (city_key, building_index, building_dict) or (None, None, None).
    """
    grid_x = round(x / CITY_SPACING)
    grid_y = round(y / CITY_SPACING)
    city_buildings = get_buildings_in_city(grid_x, grid_y)
    for idx, building in enumerate(city_buildings):
        if (building['x'] <= x < building['x'] + building['w'] and
                building['y'] <= y < building['y'] + building['h']):
            return (grid_x, grid_y), idx, building
    return None, None, None


def get_building_max_durability(building):
    """Get the max durability for a building based on its type."""
    building_type = building.get("type", "GENERIC")
    building_info = BUILDING_DATA.get(building_type, {})
    return building_info.get("base_durability", GENERIC_BUILDING_DURABILITY)


def is_building_destroyed(game_state, city_key, idx):
    """Check if a specific building has been destroyed."""
    return (city_key[0], city_key[1], idx) in game_state.destroyed_buildings


def damage_building(game_state, city_key, idx, building, damage):
    """Apply damage to a building. Returns a list of notification strings."""
    notifications = []
    key = (city_key[0], city_key[1], idx)

    if key in game_state.destroyed_buildings:
        return notifications

    max_hp = get_building_max_durability(building)
    current_hp = game_state.damaged_buildings.get(key, max_hp)
    current_hp -= damage
    game_state.damaged_buildings[key] = current_hp

    building_type = building.get("type", "GENERIC")
    building_info = BUILDING_DATA.get(building_type, {})
    building_name = building_info.get("name", building.get("name", "Building"))

    if current_hp <= 0:
        # Building destroyed
        game_state.destroyed_buildings.add(key)
        city_xy = (city_key[0], city_key[1])
        count = game_state.buildings_destroyed_per_city.get(city_xy, 0) + 1
        game_state.buildings_destroyed_per_city[city_xy] = count

        # Drop loot
        cash_value = random.randint(20, 80)
        pickup_id = game_state.next_pickup_id
        game_state.next_pickup_id += 1
        game_state.active_pickups[pickup_id] = {
            "x": building["x"] + building["w"] // 2,
            "y": building["y"] + building["h"] // 2,
            "type": "cash",
            "value": cash_value,
            "char": PICKUP_DATA[PICKUP_CASH]["art"][0],
            "color": PICKUP_DATA[PICKUP_CASH]["color_pair_name"],
        }

        # Give XP
        xp_value = max_hp // 10
        game_state.gain_xp(xp_value)

        notifications.append(f"Destroyed {building_name}! (+{xp_value} XP, loot dropped)")
        faction_notifications = _apply_faction_consequences(game_state, city_key)
        notifications.extend(faction_notifications)
    else:
        # Show damage feedback every 25% HP
        hp_pct = current_hp / max_hp
        if hp_pct <= 0.25:
            notifications.append(f"{building_name} is crumbling!")
        elif hp_pct <= 0.50:
            notifications.append(f"{building_name} is heavily damaged!")
        elif hp_pct <= 0.75:
            notifications.append(f"{building_name} is taking damage!")

    return notifications


def _apply_faction_consequences(game_state, city_key):
    """Apply faction reputation loss and escalation for building destruction."""
    notifications = []
    city_xy = (city_key[0], city_key[1])
    count = game_state.buildings_destroyed_per_city.get(city_xy, 0)

    # Find the faction that controls this city
    from ..world.generation import get_city_faction
    faction_id = get_city_faction(
        city_key[0] * CITY_SPACING,
        city_key[1] * CITY_SPACING,
        game_state.factions
    )

    if not faction_id:
        return notifications

    # Apply reputation loss
    current_rep = game_state.faction_reputation.get(faction_id, 0)
    game_state.faction_reputation[faction_id] = current_rep + BUILDING_DESTROY_REP_LOSS
    faction_name = game_state.factions.get(faction_id, {}).get("name", faction_id)
    notifications.append(f"{faction_name} reputation: {BUILDING_DESTROY_REP_LOSS}")

    # Escalation thresholds
    if count == BUILDING_RETALIATION_THRESHOLD:
        notifications.append(f"{faction_name} is sending a retaliation force!")
        _spawn_retaliation_wave(game_state, faction_id)
    elif count == BUILDING_BOSS_THRESHOLD:
        notifications.append(f"{faction_name}'s boss is coming for you!")
        from ..logic.boss import spawn_faction_boss
        spawn_faction_boss(game_state, faction_id)

    return notifications


def _spawn_retaliation_wave(game_state, faction_id):
    """Spawn a wave of enemies near the player as retaliation."""
    import math
    from ..logic.entity_loader import ENEMY_VEHICLES, ENEMY_CHARACTERS, normalize_class_name

    faction_units = game_state.factions.get(faction_id, {}).get("units", [])
    all_enemy_classes = ENEMY_VEHICLES + ENEMY_CHARACTERS
    possible_vehicles = [
        e for e in all_enemy_classes
        if any(normalize_class_name(e.__name__) == normalize_class_name(unit) for unit in faction_units)
    ]
    if not possible_vehicles:
        possible_vehicles = ENEMY_VEHICLES[:1]  # Fallback

    for _ in range(RETALIATION_ENEMY_COUNT):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(40, 80)
        ex = game_state.car_world_x + dist * math.cos(angle)
        ey = game_state.car_world_y + dist * math.sin(angle)
        enemy_class = random.choice(possible_vehicles)
        new_enemy = enemy_class(ex, ey)
        new_enemy.faction_id = faction_id
        new_enemy.patrol_target_x = ex + random.uniform(-50, 50)
        new_enemy.patrol_target_y = ey + random.uniform(-50, 50)
        game_state.active_enemies.append(new_enemy)

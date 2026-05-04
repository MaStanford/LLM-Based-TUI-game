import random
import math
from .loot_generation import handle_enemy_loot_drop
from .building_damage import find_building_at, damage_building
from ..world.generation import get_buildings_in_city
from ..data.game_constants import CITY_SPACING
from ..data.quests import KillCountObjective, WaveSpawnObjective
from .ai_behaviors import _are_factions_hostile

# Collision physics constants
STOP_THRESHOLD = 2.0  # Speed below which collisions stop the car completely
DEFLECTION_FRAMES = 15  # Number of frames to apply deflection (~0.5s at 30fps)
DEFLECTION_STRENGTH = 3.0  # Base deflection velocity
COLLISION_IFRAMES = 15  # Invulnerability frames after a collision
SPEED_REDUCTION_FACTOR = 0.5  # How much speed is reduced on collision
PUSH_OUT_DISTANCE = 3.0  # Distance to push vehicles apart on collision
BOUNCE_STRENGTH = 4.0  # Base bounce strength for momentum-based collisions


def find_safe_exit_spot(world, building):
    """
    Finds a safe, non-colliding spot to place the player after exiting a building.
    It checks in a spiral pattern around the building's center.
    """
    center_x, center_y = building['x'] + building['w'] // 2, building['y'] + building['h'] // 2

    # Pre-fetch buildings for the city this building is in. The spiral stays close
    # to the building center so the city grid cell won't change.
    city_cx = round(center_x / CITY_SPACING)
    city_cy = round(center_y / CITY_SPACING)
    nearby_buildings = get_buildings_in_city(city_cx, city_cy)

    # Spiral search — capped at 400 iterations. A valid exit spot is always within
    # a few units of the building edge (the spiral covers a ~20x20 area in 400 steps),
    # which is more than enough for any building size. The old max_dist**2 cap could
    # reach 6400+ iterations with no practical benefit.
    x, y = 0, 0
    dx, dy = 0, -1
    max_iterations = 400

    for _ in range(max_iterations):
        check_x, check_y = center_x + x, center_y + y
        terrain = world.get_terrain_at(check_x, check_y)

        # Check if the spot is passable and not inside any building
        if terrain.get("passable", True) and not any(
            b['x'] <= check_x < b['x'] + b['w'] and b['y'] <= check_y < b['y'] + b['h']
            for b in nearby_buildings
        ):
            return check_x, check_y

        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1 - y):
            dx, dy = -dy, dx
        x, y = x + dx, y + dy

    return building['x'], building['y'] # Fallback

def check_collision(rect1, rect2):
    """Checks if two rectangles are colliding."""
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    return (x1 < x2 + w2 and
            x1 + w1 > x2 and
            y1 < y2 + h2 and
            y1 + h1 > y2)


def _apply_deflection(game_state, other_entity, damage):
    """
    Applies momentum-based deflection physics when the player collides with an entity.
    Both entities bounce based on relative weight and speed.
    Works with any entity type (vehicles, obstacles, fauna).
    """
    player = game_state.player_car

    # Calculate collision normal (direction from other entity to player)
    player_cx = player.x + player.width / 2
    player_cy = player.y + player.height / 2
    other_cx = other_entity.x + other_entity.width / 2
    other_cy = other_entity.y + other_entity.height / 2

    nx = player_cx - other_cx
    ny = player_cy - other_cy
    dist = math.sqrt(nx * nx + ny * ny)
    if dist > 0:
        nx /= dist
        ny /= dist
    else:
        # Fallback: push in the direction the car is facing
        adjusted_angle = game_state.car_angle - (math.pi / 2)
        nx = -math.cos(adjusted_angle)
        ny = -math.sin(adjusted_angle)

    # --- Weight-based bounce calculations ---
    player_weight = getattr(player, 'weight', 1000)
    other_weight = getattr(other_entity, 'weight', 1000)
    total_weight = player_weight + other_weight

    # Bounce ratios: lighter entity bounces more
    player_bounce_ratio = other_weight / total_weight
    other_bounce_ratio = player_weight / total_weight

    # Combined speed for bounce intensity
    player_speed = abs(game_state.car_speed)
    other_speed = math.sqrt(other_entity.vx * other_entity.vx + other_entity.vy * other_entity.vy)
    combined_speed = max(player_speed, 1) + max(other_speed, 1)

    # Apply speed-scaled damage
    speed_factor = max(0.3, player_speed / (game_state.max_speed if game_state.max_speed > 0 else 1))
    actual_damage = max(1, int(damage * speed_factor))
    if not game_state.god_mode:
        game_state.current_durability -= actual_damage

    # --- Player bounce ---
    if player_speed < STOP_THRESHOLD:
        game_state.car_speed = 0
        game_state.car_velocity_x = 0
        game_state.car_velocity_y = 0
    else:
        game_state.car_speed *= SPEED_REDUCTION_FACTOR

    # Ricochet: player bounced along +normal, scaled by weight ratio
    player_bounce = BOUNCE_STRENGTH * player_bounce_ratio * (combined_speed / 10.0)
    game_state.deflection_vx = nx * player_bounce
    game_state.deflection_vy = ny * player_bounce
    game_state.deflection_frames = DEFLECTION_FRAMES

    # Push player out of overlap
    game_state.car_world_x += nx * PUSH_OUT_DISTANCE * player_bounce_ratio
    game_state.car_world_y += ny * PUSH_OUT_DISTANCE * player_bounce_ratio
    game_state.player_car.x = game_state.car_world_x
    game_state.player_car.y = game_state.car_world_y

    # --- Other entity bounce (pushed in opposite direction) ---
    other_bounce = BOUNCE_STRENGTH * other_bounce_ratio * (combined_speed / 10.0)
    other_entity.vx = -nx * other_bounce
    other_entity.vy = -ny * other_bounce
    other_entity.x -= nx * PUSH_OUT_DISTANCE * other_bounce_ratio
    other_entity.y -= ny * PUSH_OUT_DISTANCE * other_bounce_ratio

    # If the other entity was ramming, reset its ram sub-state to backing up
    if hasattr(other_entity, 'ai_state') and "ram_substate" in other_entity.ai_state:
        other_entity.ai_state["ram_substate"] = "backing_up"
        other_entity.ai_state["ram_timer"] = 1.0

    # Set invulnerability frames
    game_state.collision_iframes = COLLISION_IFRAMES


def _parse_projectile_owner(p_state):
    """Parse projectile owner into (owner_type, faction_id).
    Handles both old 'enemy'/'player' strings and new ('enemy', faction_id) tuples.
    """
    raw = p_state[9] if len(p_state) > 9 else "player"
    if isinstance(raw, tuple):
        return raw[0], raw[1]
    return raw, None


def _apply_entity_bounce(entity_a, entity_b):
    """Apply weight-based bounce between two non-player entities.
    Both entities are pushed apart based on weight ratios.
    """
    a_cx = entity_a.x + entity_a.width / 2
    a_cy = entity_a.y + entity_a.height / 2
    b_cx = entity_b.x + entity_b.width / 2
    b_cy = entity_b.y + entity_b.height / 2

    nx = a_cx - b_cx
    ny = a_cy - b_cy
    dist = math.sqrt(nx * nx + ny * ny)
    if dist > 0:
        nx /= dist
        ny /= dist
    else:
        nx, ny = 1.0, 0.0

    weight_a = getattr(entity_a, 'weight', 1000)
    weight_b = getattr(entity_b, 'weight', 1000)
    total_weight = weight_a + weight_b

    bounce_a = BOUNCE_STRENGTH * (weight_b / total_weight)
    bounce_b = BOUNCE_STRENGTH * (weight_a / total_weight)

    entity_a.vx = nx * bounce_a
    entity_a.vy = ny * bounce_a
    entity_a.x += nx * PUSH_OUT_DISTANCE * (weight_b / total_weight)
    entity_a.y += ny * PUSH_OUT_DISTANCE * (weight_b / total_weight)

    entity_b.vx = -nx * bounce_b
    entity_b.vy = -ny * bounce_b
    entity_b.x -= nx * PUSH_OUT_DISTANCE * (weight_a / total_weight)
    entity_b.y -= ny * PUSH_OUT_DISTANCE * (weight_a / total_weight)


def _drop_meat(game_state, x, y):
    """Drops a meat pickup at the given position."""
    import time as _time
    pickup_id = game_state.next_pickup_id
    game_state.next_pickup_id += 1
    meat_value = random.randint(5, 15)
    game_state.active_pickups[pickup_id] = {
        "x": x, "y": y,
        "type": "cash",
        "value": meat_value,
        "char": "♠",
        "color": "PICKUP_CASH",
        "spawn_time": _time.time(),
    }


def _update_kill_objectives(game_state, enemy):
    """Increments kill_count on any active KillCountObjective that matches the enemy,
    and decrements wave_enemies_remaining on any active WaveSpawnObjective."""
    enemy_class_name = enemy.__class__.__name__
    for quest in game_state.active_quests:
        if quest.completed:
            continue
        for objective in quest.objectives:
            if isinstance(objective, KillCountObjective) and not objective.completed:
                if objective.target_name is None or objective.target_name == enemy_class_name:
                    objective.kill_count += 1
            elif isinstance(objective, WaveSpawnObjective) and not objective.completed:
                if objective.wave_active and objective.wave_enemies_remaining > 0:
                    objective.wave_enemies_remaining -= 1


def handle_collisions(game_state, world, audio_manager, app):
    """
    Handles all collision detection and resolution.
    Returns a list of notification messages.
    """
    notifications = []

    # --- Decrement i-frames ---
    if game_state.collision_iframes > 0:
        game_state.collision_iframes -= 1

    # --- Projectile Collisions ---
    projectiles_to_remove = set()

    for i, p_state in enumerate(game_state.active_particles):
        if i in projectiles_to_remove:
            continue
        p_x, p_y = p_state[0], p_state[1]
        p_power = p_state[4]
        p_owner_type, p_owner_faction = _parse_projectile_owner(p_state)

        # Check for collisions with terrain
        p_terrain = world.get_terrain_at(p_x, p_y)
        if not p_terrain.get("passable", True):
            # Check if this is a building and apply damage
            if "building" in p_terrain:
                city_key, b_idx, b_data = find_building_at(p_x, p_y)
                if city_key is not None:
                    bld_notifications = damage_building(game_state, city_key, b_idx, b_data, p_power)
                    notifications.extend(bld_notifications)
            projectiles_to_remove.add(i)
            continue

        # Enemy projectiles hit the player
        if p_owner_type == "enemy":
            player = game_state.player_car
            if (player.x <= p_x < player.x + player.width and
                player.y <= p_y < player.y + player.height):
                if game_state.collision_iframes <= 0 and not game_state.god_mode:
                    game_state.current_durability -= p_power
                    game_state.collision_iframes = 8  # Brief i-frames for projectile hits
                    audio_manager.play_sfx("crash")
                    notifications.append(f"Hit by enemy fire! (-{int(p_power)} HP)")
                projectiles_to_remove.add(i)
                continue

            # Enemy projectiles hit rival-faction enemies
            if p_owner_faction:
                hit_rival = False
                for enemy in game_state.active_enemies:
                    enemy_faction = getattr(enemy, 'faction_id', None)
                    if enemy_faction == p_owner_faction:
                        continue  # Don't hit friendlies
                    if not enemy_faction:
                        continue  # Skip factionless enemies
                    if (enemy.x <= p_x < enemy.x + enemy.width and
                            enemy.y <= p_y < enemy.y + enemy.height):
                        enemy.durability -= p_power
                        projectiles_to_remove.add(i)
                        if enemy.durability <= 0:
                            game_state.destroyed_this_frame.append(enemy)
                            handle_enemy_loot_drop(game_state, enemy, app)
                            xp = getattr(enemy, 'xp_value', 5)
                            game_state.gain_xp(xp)
                            _update_kill_objectives(game_state, enemy)
                            game_state.active_enemies.remove(enemy)
                        hit_rival = True
                        break
                if hit_rival:
                    continue

                # Enemy projectiles hit rival-faction turrets
                for turret in getattr(game_state, 'active_turrets', []):
                    turret_faction = getattr(turret, 'faction_id', None)
                    if turret_faction == p_owner_faction:
                        continue
                    if not turret_faction:
                        continue
                    if (turret.x <= p_x < turret.x + turret.width and
                            turret.y <= p_y < turret.y + turret.height):
                        turret.durability -= p_power
                        projectiles_to_remove.add(i)
                        if turret.durability <= 0:
                            game_state.destroyed_this_frame.append(turret)
                            xp = getattr(turret, 'xp_value', 10)
                            game_state.gain_xp(xp)
                            game_state.active_turrets.remove(turret)
                        break

        # Player projectiles hit enemies
        if p_owner_type == "player":
            hit = False
            for enemy in game_state.active_enemies:
                if (enemy.x <= p_x < enemy.x + enemy.width and
                    enemy.y <= p_y < enemy.y + enemy.height):
                    enemy.durability -= p_power
                    audio_manager.play_sfx("enemy_hit")
                    projectiles_to_remove.add(i)
                    if enemy.durability <= 0:
                        game_state.destroyed_this_frame.append(enemy)
                        handle_enemy_loot_drop(game_state, enemy, app)
                        xp = getattr(enemy, 'xp_value', 5)
                        game_state.gain_xp(xp)
                        _update_kill_objectives(game_state, enemy)
                        notifications.append(f"Destroyed {enemy.__class__.__name__}! (+{xp} XP)")
                        game_state.active_enemies.remove(enemy)
                    hit = True
                    break
            if hit:
                continue

            # Player projectiles hit turrets
            for turret in getattr(game_state, 'active_turrets', []):
                if (turret.x <= p_x < turret.x + turret.width and
                        turret.y <= p_y < turret.y + turret.height):
                    turret.durability -= p_power
                    audio_manager.play_sfx("enemy_hit")
                    projectiles_to_remove.add(i)
                    if turret.durability <= 0:
                        game_state.destroyed_this_frame.append(turret)
                        xp = getattr(turret, 'xp_value', 10)
                        game_state.gain_xp(xp)
                        notifications.append(f"Destroyed turret! (+{xp} XP)")
                        game_state.active_turrets.remove(turret)
                    hit = True
                    break
            if hit:
                continue

            # Check for collisions with obstacles
            for obstacle in game_state.active_obstacles[:]:
                if (obstacle.x <= p_x < obstacle.x + obstacle.width and
                    obstacle.y <= p_y < obstacle.y + obstacle.height):
                    obstacle.durability -= p_power
                    audio_manager.play_sfx("enemy_hit")
                    projectiles_to_remove.add(i)
                    if obstacle.durability <= 0:
                        game_state.destroyed_this_frame.append(obstacle)
                        game_state.active_obstacles.remove(obstacle)
                        game_state.gain_xp(obstacle.xp_value)
                        notifications.append(f"Destroyed {obstacle.__class__.__name__}!")
                        if obstacle.cash_value > 0:
                            game_state.player_cash += obstacle.cash_value
                    hit = True
                    break
            if hit:
                continue

            # Check for collisions with fauna
            for fauna in game_state.active_fauna[:]:
                if (fauna.x <= p_x < fauna.x + fauna.width and
                    fauna.y <= p_y < fauna.y + fauna.height):
                    fauna.durability -= p_power
                    audio_manager.play_sfx("enemy_hit")
                    projectiles_to_remove.add(i)
                    if fauna.durability <= 0:
                        game_state.active_fauna.remove(fauna)
                        xp = getattr(fauna, 'xp_value', 1)
                        game_state.gain_xp(xp)
                        game_state.karma -= 1  # Negative karma for killing fauna
                        _drop_meat(game_state, fauna.x, fauna.y)
                        notifications.append(f"Killed {fauna.__class__.__name__}! (-1 Karma)")
                    hit = True
                    break

    # Remove projectiles that have collided
    if projectiles_to_remove:
        game_state.active_particles = [p for i, p in enumerate(game_state.active_particles) if i not in projectiles_to_remove]

    # --- Flame Collisions ---
    FLAME_WIDTH = 2.0
    for flame in game_state.active_flames:
        sx, sy, ex, ey, power = flame[0], flame[1], flame[2], flame[3], flame[4]
        dx = ex - sx
        dy = ey - sy
        seg_len_sq = dx * dx + dy * dy
        for enemy in game_state.active_enemies[:]:
            ecx = enemy.x + enemy.width / 2
            ecy = enemy.y + enemy.height / 2
            if seg_len_sq == 0:
                dist = math.sqrt((ecx - sx) ** 2 + (ecy - sy) ** 2)
            else:
                t = max(0, min(1, ((ecx - sx) * dx + (ecy - sy) * dy) / seg_len_sq))
                proj_x = sx + t * dx
                proj_y = sy + t * dy
                dist = math.sqrt((ecx - proj_x) ** 2 + (ecy - proj_y) ** 2)
            if dist < FLAME_WIDTH:
                enemy.durability -= power
                if enemy.durability <= 0:
                    game_state.destroyed_this_frame.append(enemy)
                    handle_enemy_loot_drop(game_state, enemy, app)
                    xp = getattr(enemy, 'xp_value', 5)
                    game_state.gain_xp(xp)
                    _update_kill_objectives(game_state, enemy)
                    notifications.append(f"Destroyed {enemy.__class__.__name__}! (+{xp} XP)")
                    game_state.active_enemies.remove(enemy)

    # --- Player-Enemy Collision (with deflection) ---
    player = game_state.player_car
    player_rect = (player.x, player.y, player.width, player.height)

    if game_state.collision_iframes <= 0:
        for enemy in game_state.active_enemies[:]:
            enemy_rect = (enemy.x, enemy.y, enemy.width, enemy.height)
            if check_collision(player_rect, enemy_rect):
                audio_manager.play_sfx("crash")

                collision_damage = getattr(enemy, "collision_damage", 5)
                _apply_deflection(game_state, enemy, collision_damage)

                # Damage the enemy too
                enemy.durability -= getattr(player, "collision_damage", 5)

                if enemy.durability <= 0:
                    game_state.destroyed_this_frame.append(enemy)
                    handle_enemy_loot_drop(game_state, enemy, app)
                    xp = getattr(enemy, 'xp_value', 5)
                    game_state.gain_xp(xp)
                    _update_kill_objectives(game_state, enemy)
                    notifications.append(f"Destroyed {enemy.__class__.__name__}! (+{xp} XP)")
                    game_state.active_enemies.remove(enemy)
                break  # Only handle one collision per frame

    # --- Inter-Faction Enemy-vs-Enemy Collision ---
    enemies = game_state.active_enemies
    enemies_to_remove = []
    for i_e in range(len(enemies)):
        for j_e in range(i_e + 1, len(enemies)):
            a = enemies[i_e]
            b = enemies[j_e]
            fa = getattr(a, 'faction_id', None)
            fb = getattr(b, 'faction_id', None)
            if not fa or not fb or fa == fb:
                continue
            if not _are_factions_hostile(fa, fb, game_state):
                continue
            if check_collision(
                (a.x, a.y, a.width, a.height),
                (b.x, b.y, b.width, b.height)
            ):
                _apply_entity_bounce(a, b)
                dmg_a = getattr(a, 'collision_damage', 5)
                dmg_b = getattr(b, 'collision_damage', 5)
                b.durability -= dmg_a
                a.durability -= dmg_b
                if a.durability <= 0 and a not in enemies_to_remove:
                    enemies_to_remove.append(a)
                if b.durability <= 0 and b not in enemies_to_remove:
                    enemies_to_remove.append(b)

    for dead in enemies_to_remove:
        if dead in game_state.active_enemies:
            game_state.destroyed_this_frame.append(dead)
            handle_enemy_loot_drop(game_state, dead, app)
            xp = getattr(dead, 'xp_value', 5)
            game_state.gain_xp(xp)
            _update_kill_objectives(game_state, dead)
            game_state.active_enemies.remove(dead)

    # --- Obstacle Collisions (with deflection) ---
    if game_state.collision_iframes <= 0:
        player_rect = (game_state.player_car.x, game_state.player_car.y,
                       game_state.player_car.width, game_state.player_car.height)
        for obstacle in game_state.active_obstacles[:]:
            obstacle_rect = (obstacle.x, obstacle.y, obstacle.width, obstacle.height)
            if check_collision(player_rect, obstacle_rect):
                audio_manager.play_sfx("crash")

                _apply_deflection(game_state, obstacle, obstacle.damage)

                obstacle.durability -= 10
                if obstacle.durability <= 0:
                    game_state.destroyed_this_frame.append(obstacle)
                    game_state.active_obstacles.remove(obstacle)
                    game_state.gain_xp(obstacle.xp_value)
                    notifications.append(f"Destroyed {obstacle.__class__.__name__}!")
                    if obstacle.cash_value > 0:
                        game_state.player_cash += obstacle.cash_value
                break  # Only handle one collision per frame

    # --- Fauna Collisions (with deflection) ---
    if game_state.collision_iframes <= 0:
        player_rect = (game_state.player_car.x, game_state.player_car.y,
                       game_state.player_car.width, game_state.player_car.height)
        for fauna in game_state.active_fauna[:]:
            fauna_rect = (fauna.x, fauna.y, fauna.width, fauna.height)
            if check_collision(player_rect, fauna_rect):
                audio_manager.play_sfx("crash")

                fauna_damage = getattr(fauna, 'collision_damage', 1)
                _apply_deflection(game_state, fauna, fauna_damage)

                fauna.durability -= getattr(player, "collision_damage", 5)
                if fauna.durability <= 0:
                    game_state.active_fauna.remove(fauna)
                    xp = getattr(fauna, 'xp_value', 1)
                    game_state.gain_xp(xp)
                    game_state.karma -= 1
                    _drop_meat(game_state, fauna.x, fauna.y)
                    notifications.append(f"Ran over {fauna.__class__.__name__}! (-1 Karma)")
                break

    # --- Player-Turret Collisions (with deflection) ---
    if game_state.collision_iframes <= 0:
        player_rect = (game_state.player_car.x, game_state.player_car.y,
                       game_state.player_car.width, game_state.player_car.height)
        for turret in getattr(game_state, 'active_turrets', [])[:]:
            turret_rect = (turret.x, turret.y, turret.width, turret.height)
            if check_collision(player_rect, turret_rect):
                audio_manager.play_sfx("crash")
                turret_damage = getattr(turret, 'collision_damage', 3)
                _apply_deflection(game_state, turret, turret_damage)
                turret.durability -= getattr(player, "collision_damage", 5)
                if turret.durability <= 0:
                    game_state.destroyed_this_frame.append(turret)
                    xp = getattr(turret, 'xp_value', 10)
                    game_state.gain_xp(xp)
                    notifications.append(f"Destroyed turret! (+{xp} XP)")
                    game_state.active_turrets.remove(turret)
                break

    # --- Pickup Collisions ---
    # Pickups have a collection area for forgiving collection
    PICKUP_RADIUS = 5
    pickups_to_remove = []
    for pickup_id, pickup in game_state.active_pickups.items():
        dx = game_state.player_car.x + game_state.player_car.width / 2 - pickup["x"]
        dy = game_state.player_car.y + game_state.player_car.height / 2 - pickup["y"]
        if dx * dx + dy * dy < PICKUP_RADIUS * PICKUP_RADIUS:

            if pickup["type"] == "cash":
                game_state.player_cash += pickup["value"]
                notifications.append(f"Picked up {pickup['value']} cash!")
            elif pickup["type"] == "weapon":
                game_state.player_inventory.append(pickup["weapon"])
                notifications.append(f"Picked up {pickup['weapon'].name}!")
            elif pickup["type"] == "equipment":
                game_state.player_inventory.append(pickup["equipment"])
                notifications.append(f"Picked up {pickup['equipment'].name}!")
            elif pickup["type"] == "narrative":
                from ..screens.narrative_dialog import NarrativeDialogScreen
                game_state.menu_open = True
                app.push_screen(NarrativeDialogScreen(pickup["data"]))

            pickups_to_remove.append(pickup_id)

    for pickup_id in pickups_to_remove:
        del game_state.active_pickups[pickup_id]

    return notifications

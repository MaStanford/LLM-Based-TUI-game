from .vehicle_movement import update_vehicle_movement
from .weapon_systems import update_weapon_systems
from .collision_detection import handle_collisions
import math
import time

def update_physics_and_collisions(game_state, world, audio_manager, dt, app):
    """
    Handles all physics updates, weapon systems, and collision detection
    by coordinating calls to specialized modules.
    Returns a list of notification messages.
    """
    # 1. Update player vehicle movement and position
    movement_notifications = update_vehicle_movement(game_state, world, audio_manager, dt)

    # 2. Handle weapon firing and projectile updates
    update_weapon_systems(game_state, audio_manager)

    # 3. Update projectile positions and check ranges
    particles_to_keep = []
    for p_state in game_state.active_particles:
        p_x, p_y, p_angle, p_speed, p_power, max_range, p_char, origin_x, origin_y = p_state[:9]

        # Move projectile
        p_dist = p_speed * dt
        p_x += p_dist * math.cos(p_angle)
        p_y += p_dist * math.sin(p_angle)

        # Check range
        distance_traveled = math.sqrt((p_x - origin_x)**2 + (p_y - origin_y)**2)

        if distance_traveled < max_range:
            p_state[0], p_state[1] = p_x, p_y
            particles_to_keep.append(p_state)
    game_state.active_particles = particles_to_keep

    # 4. Process all collisions and their effects
    notifications = handle_collisions(game_state, world, audio_manager, app)
    notifications.extend(movement_notifications)

    # 5. Update AI and movement for all non-player entities
    for enemy in game_state.active_enemies:
        enemy.update(game_state, world, dt)
        
        # Check for combat trigger
        if getattr(enemy, "is_major_enemy", False):
            dist_sq = (enemy.x - game_state.car_world_x)**2 + (enemy.y - game_state.car_world_y)**2
            if dist_sq < 225: # 15 units aggro radius
                from ..screens.combat import CombatScreen
                game_state.combat_enemy = enemy
                game_state.menu_open = True
                game_state.boss_phase_index = 0
                game_state.boss_tier = getattr(enemy, "boss_tier", "retaliation")
                game_state.player_car.durability = game_state.current_durability
                game_state.player_car.max_durability = game_state.max_durability
                app.push_screen(CombatScreen(game_state.player_car, enemy))

    for fauna in game_state.active_fauna:
        fauna.update(game_state, world, dt)

    for turret in game_state.active_turrets:
        turret.update(game_state, world, dt)
        
    # 6. Despawn entities that are too far away
    despawn_radius_sq = game_state.despawn_radius**2

    # Collect names of quest-linked bosses that haven't been killed yet
    quest_boss_names = set()
    for quest in game_state.active_quests:
        for obj in quest.objectives:
            if hasattr(obj, 'boss_name') and not obj.completed:
                quest_boss_names.add(obj.boss_name)

    # Despawn non-boss enemies that are too far away
    game_state.active_enemies = [
        e for e in game_state.active_enemies
        if (e.x - game_state.car_world_x)**2 + (e.y - game_state.car_world_y)**2 < despawn_radius_sq
        or getattr(e, 'name', None) in quest_boss_names
        or getattr(e, 'is_faction_boss', False)
        or getattr(e, 'is_major_enemy', False)
    ]
    game_state.active_fauna = [f for f in game_state.active_fauna if (f.x - game_state.car_world_x)**2 + (f.y - game_state.car_world_y)**2 < despawn_radius_sq]
    game_state.active_obstacles = [o for o in game_state.active_obstacles if (o.x - game_state.car_world_x)**2 + (o.y - game_state.car_world_y)**2 < despawn_radius_sq]
    game_state.active_turrets = [t for t in game_state.active_turrets if (t.x - game_state.car_world_x)**2 + (t.y - game_state.car_world_y)**2 < despawn_radius_sq]

    # 6b. Despawn expired pickups
    from ..data.game_constants import PICKUP_LIFETIME
    now = time.time()
    expired = [pid for pid, p in game_state.active_pickups.items()
               if now - p.get("spawn_time", now) >= PICKUP_LIFETIME]
    for pid in expired:
        del game_state.active_pickups[pid]

    # 7. Check for game over condition
    if game_state.current_durability <= 0:
        game_state.game_over = True

    return notifications

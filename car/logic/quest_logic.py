import random
from ..data.quests import Quest, KillBossObjective, KillCountObjective, SurvivalObjective, DeliverPackageObjective, DefendLocationObjective, WaveSpawnObjective, QuestItem, QUEST_TEMPLATES
from ..logic.entity_loader import PLAYER_CARS, ENEMY_VEHICLES, ENEMY_CHARACTERS, normalize_class_name
from ..entities.base import Entity
from ..data.game_constants import CITY_SPACING
from ..world.generation import get_buildings_in_city, get_city_faction
from ..logic.data_loader import FACTION_DATA
from . import faction_logic
from .scaling import get_enemy_scaling

# Radius within which quest location objectives are active
QUEST_LOCATION_RADIUS = 80
QUEST_LOCATION_RADIUS_SQ = QUEST_LOCATION_RADIUS ** 2
# Timer for spawning quest enemies during wave/survival objectives
QUEST_ENEMY_SPAWN_INTERVAL = 2.0  # seconds between spawn checks

def get_quest_target_location(quest, game_state):
    """
    Returns (world_x, world_y, label) for the quest's current objective target,
    or (None, None, None) if no specific location can be determined.
    Used by the compass and world map to show quest markers.
    """
    if not quest:
        return None, None, None

    # If ready to turn in, point to the quest giver city
    if quest.ready_to_turn_in and quest.city_id:
        x = quest.city_id[0] * CITY_SPACING
        y = quest.city_id[1] * CITY_SPACING
        return x, y, "Turn In Quest"

    # If quest has a live boss entity, point to it
    if quest.boss:
        return quest.boss.x, quest.boss.y, quest.boss.name

    # Check uncompleted objectives for location-bearing targets
    for objective in quest.objectives:
        if objective.completed:
            continue

        if isinstance(objective, DeliverPackageObjective):
            # Resolve destination city name to world coordinates
            cities = game_state.world_details.get("cities", {})
            for key, name in cities.items():
                if name == objective.destination:
                    try:
                        gx_str, gy_str = key.split(",")
                        x = int(gx_str) * CITY_SPACING
                        y = int(gy_str) * CITY_SPACING
                        return x, y, f"Deliver to {objective.destination}"
                    except ValueError:
                        pass

        elif isinstance(objective, DefendLocationObjective):
            # Resolve landmark name to world coordinates
            for landmark in game_state.world_details.get("landmarks", []):
                if landmark.get("name") == objective.location:
                    return landmark["x"], landmark["y"], f"Defend {objective.location}"

        elif isinstance(objective, KillBossObjective):
            # Boss not spawned yet — point to quest area
            if quest.city_id:
                x = quest.city_id[0] * CITY_SPACING
                y = quest.city_id[1] * CITY_SPACING
                return x, y, f"Hunt {objective.boss_name}"

        elif isinstance(objective, KillCountObjective):
            remaining = objective.target_count - objective.kill_count
            label = f"Eliminate {remaining} more"
            if quest.city_id:
                x = quest.city_id[0] * CITY_SPACING
                y = quest.city_id[1] * CITY_SPACING
                return x, y, label

        elif isinstance(objective, SurvivalObjective):
            remaining_s = max(0, int(objective.timer))
            label = f"Survive ({remaining_s}s)"
            if quest.combat_waypoint:
                return quest.combat_waypoint[0], quest.combat_waypoint[1], label
            if quest.city_id:
                x = quest.city_id[0] * CITY_SPACING
                y = quest.city_id[1] * CITY_SPACING
                return x, y, label

        elif isinstance(objective, WaveSpawnObjective):
            remaining = objective.total_waves - objective.current_wave
            if objective.wave_enemies_remaining > 0:
                label = f"Wave {objective.current_wave}/{objective.total_waves} ({objective.wave_enemies_remaining} left)"
            else:
                label = f"Wave {objective.current_wave}/{objective.total_waves}"
            if quest.combat_waypoint:
                return quest.combat_waypoint[0], quest.combat_waypoint[1], label
            if quest.city_id:
                x = quest.city_id[0] * CITY_SPACING
                y = quest.city_id[1] * CITY_SPACING
                return x, y, label

    return None, None, None


def get_available_quests(game_state):
    """Generates a list of available quests for the current city."""
    quests = []
    quest_giver_faction_id = get_city_faction(game_state.car_world_x, game_state.car_world_y, game_state.factions)
    quest_giver_faction = game_state.factions[quest_giver_faction_id]
    
    hostile_factions = [fid for fid, rel in quest_giver_faction["relationships"].items() if rel == "Hostile"]
    if not hostile_factions:
        return []

    # Generate 3 quests
    for _ in range(3):
        target_faction_id = random.choice(hostile_factions)
        target_faction = game_state.factions[target_faction_id]

        quest_template_key = random.choice(list(QUEST_TEMPLATES.keys()))
        quest_template = QUEST_TEMPLATES[quest_template_key]

        objectives = []
        for obj_class, args in quest_template["objectives"]:
            objectives.append(obj_class(*args))

        name = quest_template["name"].format(target_faction_name=target_faction["name"])
        description = quest_template["description"].format(
            quest_giver_faction_name=quest_giver_faction["name"],
            target_faction_name=target_faction["name"]
        )

        quests.append(Quest(
            name=name,
            description=description,
            objectives=objectives,
            rewards=quest_template["rewards"],
            city_id=(round(game_state.car_world_x / CITY_SPACING), round(game_state.car_world_y / CITY_SPACING)),
            quest_giver_faction=quest_giver_faction_id,
            target_faction=target_faction_id,
            time_limit=quest_template.get("time_limit")
        ))
    return quests


def handle_quest_acceptance(game_state, quest):
    """Handles the logic for accepting a quest. Returns False if quest log is full."""
    if len(game_state.active_quests) >= 3:
        return False

    # Set the city_id if not already set
    if not quest.city_id:
        quest.city_id = (
            round(game_state.car_world_x / CITY_SPACING),
            round(game_state.car_world_y / CITY_SPACING),
        )

    game_state.active_quests.append(quest)

    # For wave/survival quests, place the combat waypoint on a road just outside the city
    has_outdoor_combat = any(
        isinstance(obj, (WaveSpawnObjective, SurvivalObjective))
        for obj in quest.objectives
    )
    if has_outdoor_combat and quest.city_id:
        cx = quest.city_id[0] * CITY_SPACING
        cy = quest.city_id[1] * CITY_SPACING
        # Pick a random cardinal direction and offset 150 units along the road
        direction = random.choice([(0, -150), (0, 150), (150, 0), (-150, 0)])
        quest.combat_waypoint = (cx + direction[0], cy + direction[1])

    # Add QuestItem to inventory for delivery quests
    for objective in quest.objectives:
        if isinstance(objective, DeliverPackageObjective):
            quest_item = QuestItem(
                name=f"Package for {objective.destination}",
                description=f"A sealed package to be delivered to {objective.destination}.",
                quest_name=quest.name,
            )
            game_state.player_inventory.append(quest_item)

    # Check if the quest has a boss and spawn it
    quest_template_key = next((k for k, v in QUEST_TEMPLATES.items() if v["name"] == quest.name.split(" ")[0]), None)
    if quest_template_key:
        quest_template = QUEST_TEMPLATES[quest_template_key]
        if "boss" in quest_template:
            boss_data = quest_template["boss"]
            target_faction = game_state.factions[quest.target_faction]
            boss_name = boss_data["name"].format(target_faction_name=target_faction["name"])
            boss_car_class = next((c for c in PLAYER_CARS if c.__name__.lower() == boss_data["car"].lower().replace(" ", "_")), None)
            if boss_car_class:
                boss_car_instance = boss_car_class(0, 0)
                boss = Boss(boss_name, boss_car_instance, boss_data["hp_multiplier"])
                boss.x = game_state.car_world_x + random.uniform(-200, 200)
                boss.y = game_state.car_world_y + random.uniform(-200, 200)
                boss.hp = boss_car_instance.durability * boss.hp_multiplier
                boss.art = boss_car_instance.art
                boss.width, boss.height = Entity.get_car_dimensions(boss.art)
                game_state.active_bosses.append(boss)
                quest.boss = boss
    return True

from ..screens.quest_complete import QuestCompleteScreen
from .quest_caching import trigger_quest_prefetching

def _get_quest_waypoint(quest):
    """Returns (x, y) for the quest's combat waypoint, or (None, None)."""
    if quest.combat_waypoint:
        return quest.combat_waypoint
    if quest.city_id:
        return quest.city_id[0] * CITY_SPACING, quest.city_id[1] * CITY_SPACING
    return None, None


def _spawn_quest_enemies(game_state, wx, wy, count, target_faction_id=None):
    """Spawn a batch of quest enemies around a waypoint location."""
    import math

    # Determine the pool of enemy classes to draw from
    all_enemy_classes = ENEMY_VEHICLES + ENEMY_CHARACTERS
    enemy_pool = all_enemy_classes  # default fallback
    if target_faction_id:
        faction_units = game_state.factions.get(target_faction_id, {}).get("units", [])
        if faction_units:
            matched = [
                cls for cls in all_enemy_classes
                if any(normalize_class_name(cls.__name__) == normalize_class_name(unit) for unit in faction_units)
            ]
            if matched:
                enemy_pool = matched

    for _ in range(count):
        enemy_class = random.choice(enemy_pool)
        # Spawn in a ring around the waypoint
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(30, 70)
        sx = wx + dist * math.cos(angle)
        sy = wy + dist * math.sin(angle)

        new_enemy = enemy_class(sx, sy)
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
        new_enemy.patrol_target_x = wx + random.uniform(-50, 50)
        new_enemy.patrol_target_y = wy + random.uniform(-50, 50)
        game_state.active_enemies.append(new_enemy)


def _despawn_quest_enemies(game_state, wx, wy):
    """Remove all non-boss enemies near a quest combat zone after objective completion."""
    import math
    despawn_radius_sq = 150 ** 2
    survivors = []
    for enemy in game_state.active_enemies:
        dist_sq = (enemy.x - wx) ** 2 + (enemy.y - wy) ** 2
        is_boss = getattr(enemy, 'is_faction_boss', False) or getattr(enemy, 'is_major_enemy', False)
        if dist_sq <= despawn_radius_sq and not is_boss:
            continue  # Remove this enemy
        survivors.append(enemy)
    game_state.active_enemies = survivors


def update_quests(game_state, audio_manager, app, dt):
    """
    Updates the state of all active quests.
    Returns a list of notification messages.
    """
    notifications = []
    quests_to_remove = []

    for quest in list(game_state.active_quests):
        wx, wy = _get_quest_waypoint(quest)

        # Calculate distance to quest waypoint (used by multiple objectives)
        dist_to_waypoint_sq = float('inf')
        if wx is not None:
            dist_to_waypoint_sq = (game_state.car_world_x - wx)**2 + (game_state.car_world_y - wy)**2
        at_waypoint = dist_to_waypoint_sq <= QUEST_LOCATION_RADIUS_SQ

        for objective in quest.objectives:
            if objective.completed:
                continue

            # --- Handle Package Delivery Objective ---
            if isinstance(objective, DeliverPackageObjective):
                grid_x = round(game_state.car_world_x / CITY_SPACING)
                grid_y = round(game_state.car_world_y / CITY_SPACING)
                city_key = f"{grid_x},{grid_y}"

                if city_key in game_state.world_details.get("cities", {}):
                    city_name = game_state.world_details["cities"][city_key]
                    if city_name == objective.destination:
                        half_city = CITY_SPACING / 2
                        city_world_x = grid_x * CITY_SPACING
                        city_world_y = grid_y * CITY_SPACING
                        if (abs(game_state.car_world_x - city_world_x) < half_city and
                            abs(game_state.car_world_y - city_world_y) < half_city):
                            objective.completed = True
                            notifications.append(f"Package delivered to {city_name}!")
                            # Remove the QuestItem from inventory
                            game_state.player_inventory = [
                                item for item in game_state.player_inventory
                                if not (isinstance(item, QuestItem) and item.quest_name == quest.name)
                            ]

            # --- Handle Defend Location Objective ---
            elif isinstance(objective, DefendLocationObjective):
                location_coords = None
                for landmark in game_state.world_details.get("landmarks", []):
                    if landmark["name"] == objective.location:
                        location_coords = (landmark["x"], landmark["y"])
                        break

                if location_coords:
                    player_x = game_state.car_world_x
                    player_y = game_state.car_world_y
                    dist_sq = (player_x - location_coords[0])**2 + (player_y - location_coords[1])**2
                    defense_radius_sq = 50**2

                    if dist_sq <= defense_radius_sq:
                        if objective.timer > 0:
                            objective.timer -= dt
                            remaining_s = int(objective.timer)
                            if remaining_s > 0 and remaining_s % 10 == 0 and abs(objective.timer - remaining_s) < 0.05:
                                notifications.append(f"Defending {objective.location}... {remaining_s}s remaining.")
                        else:
                            objective.completed = True
                            notifications.append(f"Successfully defended {objective.location}!")
                    else:
                        notifications.append(f"Return to {objective.location} to defend it!")

            # --- Handle Survival Objective ---
            elif isinstance(objective, SurvivalObjective):
                if at_waypoint and wx is not None:
                    if not objective.active:
                        objective.active = True
                        notifications.append(f"Survival zone reached! Hold out for {int(objective.timer)}s!")
                        # Spawn initial wave of enemies
                        _spawn_quest_enemies(game_state, wx, wy, 3, target_faction_id=quest.target_faction)

                    # Decrement timer using actual delta time for frame-rate independence
                    objective.timer -= dt

                    # Spawn reinforcements periodically
                    spawn_key = "survival_spawn_timer"
                    if spawn_key not in quest.__dict__:
                        quest.__dict__[spawn_key] = QUEST_ENEMY_SPAWN_INTERVAL
                    quest.__dict__[spawn_key] -= dt
                    if quest.__dict__[spawn_key] <= 0:
                        _spawn_quest_enemies(game_state, wx, wy, random.randint(1, 3), target_faction_id=quest.target_faction)
                        quest.__dict__[spawn_key] = QUEST_ENEMY_SPAWN_INTERVAL

                    remaining = max(0, int(objective.timer))
                    if remaining > 0 and remaining % 10 == 0 and abs(objective.timer - remaining) < 0.05:
                        notifications.append(f"Survive: {remaining}s remaining!")

                    if objective.timer <= 0:
                        objective.completed = True
                        notifications.append("You survived!")
                        # Despawn quest enemies near the combat zone
                        _despawn_quest_enemies(game_state, wx, wy)
                elif objective.active:
                    notifications.append("Return to the survival zone!")

            # --- Handle Wave Spawn Objective ---
            elif isinstance(objective, WaveSpawnObjective):
                if at_waypoint and wx is not None:
                    if not objective.wave_active:
                        objective.wave_active = True
                        # Start the first wave
                        objective.current_wave = 1
                        objective.wave_enemies_remaining = objective.enemies_per_wave
                        _spawn_quest_enemies(game_state, wx, wy, objective.enemies_per_wave, target_faction_id=quest.target_faction)
                        notifications.append(f"Wave {objective.current_wave}/{objective.total_waves} incoming!")

                    elif objective.wave_enemies_remaining <= 0:
                        # Current wave cleared
                        if objective.current_wave < objective.total_waves:
                            objective.current_wave += 1
                            objective.wave_enemies_remaining = objective.enemies_per_wave
                            _spawn_quest_enemies(game_state, wx, wy, objective.enemies_per_wave, target_faction_id=quest.target_faction)
                            notifications.append(f"Wave {objective.current_wave}/{objective.total_waves} incoming!")
                        else:
                            objective.completed = True
                            notifications.append("All waves cleared!")
                            # Despawn quest enemies near the combat zone
                            _despawn_quest_enemies(game_state, wx, wy)
                elif objective.wave_active:
                    notifications.append("Return to the combat zone!")

        if not quest.ready_to_turn_in:
            quest.update(game_state, dt)

        if quest.completed and not quest.ready_to_turn_in:
            if quest.requires_turn_in:
                quest.ready_to_turn_in = True
                notifications.append(f"Objective complete! Return to city to turn in '{quest.name}'.")
                trigger_quest_prefetching(app)
            else:
                app.push_screen(QuestCompleteScreen(quest))
                complete_quest(game_state, app, quest)

        elif quest.failed:
            giver_faction_id = quest.quest_giver_faction
            if giver_faction_id:
                if giver_faction_id not in game_state.faction_reputation:
                    game_state.faction_reputation[giver_faction_id] = 0
                game_state.faction_reputation[giver_faction_id] -= 5
                faction_logic.decrease_control(game_state, giver_faction_id, 2)
                notifications.append(f"Reputation with {game_state.factions[giver_faction_id]['name']} decreased.")

            notifications.append(f"Quest Failed: {quest.name}")
            game_state.story_events.append({
                "text": f"Failed '{quest.name}'. Reputation suffered.",
                "event_type": "quest_failed",
            })
            quests_to_remove.append(quest)

    for quest in quests_to_remove:
        if quest in game_state.active_quests:
            game_state.active_quests.remove(quest)
    _clamp_selected_quest(game_state)

    return notifications


def _clamp_selected_quest(game_state):
    """Ensure selected_quest_index stays in bounds."""
    if not game_state.active_quests:
        game_state.selected_quest_index = 0
    elif game_state.selected_quest_index >= len(game_state.active_quests):
        game_state.selected_quest_index = len(game_state.active_quests) - 1

def check_for_faction_takeover(game_state):
    """
    Checks if a faction's reputation and boss status allow for a takeover.
    Returns a list of notification messages.
    """
    notifications = []
    for faction_id, rep in list(game_state.faction_reputation.items()):
        if rep <= -100 and faction_id in game_state.defeated_bosses:
            # Find the faction with the highest reputation
            player_allies = [f_id for f_id, r in game_state.faction_reputation.items() if r > 0]
            if not player_allies:
                continue # No one to take over

            strongest_ally = max(player_allies, key=lambda f_id: game_state.faction_reputation[f_id])
            
            # Update faction data
            defeated_faction_name = game_state.factions[faction_id]["name"]
            victor_faction_name = game_state.factions[strongest_ally]["name"]
            
            notifications.append(f"{defeated_faction_name} has been defeated! Their territory is now controlled by {victor_faction_name}!")
            
            # Transfer control of the hub city
            game_state.factions[faction_id]["name"] = f"{victor_faction_name} (Occupied)"
            game_state.factions[faction_id]["units"] = game_state.factions[strongest_ally]["units"]
            
            # Update relationships
            for f_id in game_state.factions:
                if f_id != faction_id:
                    game_state.factions[f_id]["relationships"][faction_id] = "Defeated"
            
            del game_state.faction_reputation[faction_id]
    return notifications

def generate_quest(game_state, quest_id):
    """Generates a single Quest object from a given template ID."""
    quest_template = QUEST_TEMPLATES.get(quest_id)
    if not quest_template:
        return None

    # Faction logic mirrors get_available_quests
    quest_giver_faction_id = get_city_faction(game_state.car_world_x, game_state.car_world_y, game_state.factions)
    quest_giver_faction = game_state.factions[quest_giver_faction_id]
    hostile_factions = [fid for fid, rel in quest_giver_faction["relationships"].items() if rel == "Hostile"]
    if not hostile_factions:
        return None # Can't generate a quest without a target
    target_faction_id = random.choice(hostile_factions)
    target_faction = game_state.factions[target_faction_id]

    objectives = []
    for obj_class, args in quest_template["objectives"]:
        objectives.append(obj_class(*args))

    name = quest_template["name"].format(target_faction_name=target_faction["name"])
    description = quest_template["description"].format(
        quest_giver_faction_name=quest_giver_faction["name"],
        target_faction_name=target_faction["name"]
    )

    return Quest(
        name=name,
        description=description,
        objectives=objectives,
        rewards=quest_template["rewards"],
        city_id=(round(game_state.car_world_x / CITY_SPACING), round(game_state.car_world_y / CITY_SPACING)),
        quest_giver_faction=quest_giver_faction_id,
        target_faction=target_faction_id,
        time_limit=quest_template.get("time_limit"),
        next_quest_id=quest_template.get("next_quest_id")
    )

import json
import os

def complete_quest(game_state, app, quest=None):
    """
    Handles the logic for completing a quest.
    If the quest is part of a chain, it adds the next quest.
    Removes the completed quest from active_quests.
    """
    if quest is None:
        if not game_state.active_quests:
            return
        quest = game_state.active_quests[0]

    # --- Log the completed quest for the narrative engine ---
    quest_log_path = "temp/quest_log.json"
    try:
        with open(quest_log_path, "r+") as f:
            log = json.load(f)
            log.append(quest.to_dict())
            f.seek(0)
            json.dump(log, f, indent=4)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(quest_log_path, "w") as f:
            json.dump([quest.to_dict()], f, indent=4)

    # --- Handle Conquest ---
    if quest.is_conquest_quest:
        faction_logic.handle_faction_takeover(
            game_state, quest.quest_giver_faction, quest.target_faction
        )

    # Grant rewards
    rewards = quest.rewards
    game_state.gain_xp(rewards.get("xp", 0))
    game_state.player_cash += rewards.get("cash", 0)
    game_state.quests_completed += 1

    # Log to story journal
    giver_name = game_state.factions.get(quest.quest_giver_faction, {}).get("name", "Unknown") if quest.quest_giver_faction else "an unknown patron"
    game_state.story_events.append({
        "text": f"Completed '{quest.name}' for the {giver_name}. Earned {rewards.get('xp', 0)} XP and ${rewards.get('cash', 0)}.",
        "event_type": "quest_complete",
    })

    # Update reputation
    giver_faction_id = quest.quest_giver_faction
    if giver_faction_id:
        game_state.faction_reputation[giver_faction_id] = game_state.faction_reputation.get(giver_faction_id, 0) + 10
        faction_logic.increase_control(game_state, giver_faction_id, 5)
    target_faction_id = quest.target_faction
    if target_faction_id:
        game_state.faction_reputation[target_faction_id] = game_state.faction_reputation.get(target_faction_id, 0) - 15
        faction_logic.decrease_control(game_state, target_faction_id, 5)

    # Remove completed quest from active list
    if quest in game_state.active_quests:
        game_state.active_quests.remove(quest)

    # Remove any QuestItems associated with this quest
    game_state.player_inventory = [
        item for item in game_state.player_inventory
        if not (isinstance(item, QuestItem) and item.quest_name == quest.name)
    ]

    # Check for next quest in the chain
    if quest.next_quest_id and len(game_state.active_quests) < 3:
        next_quest = generate_quest(game_state, quest.next_quest_id)
        if next_quest:
            game_state.active_quests.append(next_quest)

    _clamp_selected_quest(game_state)
    check_for_faction_takeover(game_state)

    # If no more active quests remain from this city AND the cache is empty,
    # delete the cache entry so new quests will be generated on next visit.
    if quest.city_id:
        city_id = f"city_{quest.city_id[0]}_{quest.city_id[1]}"
        has_remaining = any(
            q.city_id == quest.city_id
            for q in game_state.active_quests
        )
        cached = game_state.quest_cache.get(city_id)
        cache_empty = isinstance(cached, list) and len(cached) == 0

        if not has_remaining and cache_empty:
            # All quests from this city done — allow regeneration
            del game_state.quest_cache[city_id]

    # Trigger pre-fetching for the next set of quests
    trigger_quest_prefetching(app)


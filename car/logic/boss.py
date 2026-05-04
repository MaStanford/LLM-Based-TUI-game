import random
from ..entities.vehicle import Vehicle
from ..logic.data_loader import FACTION_DATA
from ..logic.entity_loader import PLAYER_CARS
from ..data.quests import Quest, KillBossObjective
from ..logic.quest_logic import check_for_faction_takeover
from .scaling import get_enemy_scaling
from .combat_logic import BOSS_TIER_SCALING


def _resolve_vehicle_class(vehicle_name):
    """Find a vehicle class by name from PLAYER_CARS."""
    return next(
        (c for c in PLAYER_CARS
         if c.__name__.lower() == vehicle_name.lower().replace(" ", "_")),
        None,
    )


def _create_boss_entity(game_state, faction_id, tier):
    """Create a boss entity from faction data with tier-based scaling."""
    faction_data = game_state.factions.get(faction_id)
    if not faction_data or not faction_data.get("faction_boss"):
        return None
    boss_data = faction_data["faction_boss"]

    boss_car_class = _resolve_vehicle_class(boss_data["vehicle"])
    if not boss_car_class:
        return None

    from ..data.game_constants import CITY_SPACING
    hub_gx, hub_gy = faction_data["hub_city_coordinates"]
    boss_x = hub_gx * CITY_SPACING + random.uniform(-50, 50)
    boss_y = hub_gy * CITY_SPACING + random.uniform(-50, 50)

    boss = boss_car_class(boss_x, boss_y)
    boss.name = boss_data["name"]
    boss.is_major_enemy = True
    boss.boss_tier = tier

    # Base multipliers from faction data
    faction_hp = boss_data.get("hp_multiplier", 3.0)
    faction_dmg = boss_data.get("damage_multiplier", 2.0)

    # Tier scaling on top
    tier_scale = BOSS_TIER_SCALING.get(tier, BOSS_TIER_SCALING["retaliation"])
    boss.durability = int(boss.durability * faction_hp * tier_scale["hp_mult"])
    boss.max_durability = boss.durability
    if hasattr(boss, "collision_damage"):
        boss.collision_damage = int(boss.collision_damage * faction_dmg * tier_scale["dmg_mult"])
    if hasattr(boss, "shoot_damage"):
        boss.shoot_damage = int(boss.shoot_damage * faction_dmg * tier_scale["dmg_mult"])

    # Progression scaling
    prog_hp, prog_dmg, _ = get_enemy_scaling(game_state)
    boss.durability = int(boss.durability * prog_hp)
    boss.max_durability = boss.durability

    boss.faction_id = faction_id
    return boss


# --- Quest Boss: moderate difficulty, no faction impact ---

def spawn_quest_boss(game_state, faction_id, boss_name=None):
    """Spawn a quest-linked boss. Moderate difficulty. Does not affect the faction."""
    boss = _create_boss_entity(game_state, faction_id, "quest")
    if not boss:
        return None

    if boss_name:
        boss.name = boss_name
    boss.is_faction_boss = False
    game_state.active_enemies.append(boss)
    return boss


# --- Retaliation Boss: hard, punishes player but doesn't destroy faction ---

def spawn_retaliation_boss(game_state, faction_id):
    """Spawn a retaliation boss (triggered by building destruction).
    Hard difficulty. Lowers control + rep on defeat but does NOT destroy faction."""
    boss = _create_boss_entity(game_state, faction_id, "retaliation")
    if not boss:
        return

    boss.name = f"Enforcer {boss.name}"
    boss.is_faction_boss = False
    boss.is_retaliation_boss = True
    game_state.active_enemies.append(boss)

    # Create quest
    quest = Quest(
        name=f"Survive {boss.name}",
        description=f"The {game_state.factions[faction_id]['name']} sent their enforcer after you. Destroy them or flee.",
        objectives=[KillBossObjective(boss.name)],
        rewards={"xp": 2000, "cash": 1000},
        requires_turn_in=False,
    )
    if len(game_state.active_quests) < 3:
        game_state.active_quests.append(quest)


# --- Coup de Grâce Boss: near-unfair, destroys faction on defeat ---

def check_coup_conditions(game_state, faction_id):
    """Check if the player can attempt a faction coup de grâce.
    Requires: control < 20 AND rep <= -100 AND boss not already defeated."""
    if faction_id in game_state.defeated_bosses:
        return False
    faction_data = game_state.factions.get(faction_id, {})
    if not faction_data.get("faction_boss"):
        return False
    control = game_state.faction_control.get(faction_id, faction_data.get("control", 50))
    rep = game_state.faction_reputation.get(faction_id, 0)
    return control < 20 and rep <= -100


def spawn_coup_boss(game_state, faction_id):
    """Spawn the coup de grâce boss. Near-unfair difficulty. Destroys faction on defeat."""
    boss = _create_boss_entity(game_state, faction_id, "coup")
    if not boss:
        return

    boss.name = f"Warlord {boss.name}"
    boss.is_faction_boss = True
    game_state.active_enemies.append(boss)

    quest = Quest(
        name=f"Coup de Grâce: {game_state.factions[faction_id]['name']}",
        description=f"Destroy the {game_state.factions[faction_id]['name']} once and for all by defeating their leader in single combat.",
        objectives=[KillBossObjective(boss.name)],
        rewards={"xp": 5000, "cash": 3000},
        requires_turn_in=False,
    )
    if len(game_state.active_quests) < 3:
        game_state.active_quests.append(quest)
    else:
        for i, q in enumerate(game_state.active_quests):
            if not getattr(q, "boss_name", None):
                game_state.active_quests[i] = quest
                break


# --- Post-combat handlers ---

def handle_boss_defeat(game_state, boss_entity):
    """Route boss defeat to the appropriate handler based on tier."""
    tier = getattr(boss_entity, "boss_tier", None)
    faction_id = getattr(boss_entity, "faction_id", None)

    if not faction_id:
        return

    faction_name = game_state.factions.get(faction_id, {}).get("name", faction_id)

    if tier == "retaliation":
        # Punishment boss: lower control and rep, but faction survives
        control = game_state.faction_control.get(faction_id, 50)
        game_state.faction_control[faction_id] = max(0, control - 15)
        game_state.story_events.append({
            "text": f"Defeated the enforcer of {faction_name}. Their grip weakens.",
            "event_type": "boss_defeated",
        })

    elif tier == "coup" and getattr(boss_entity, "is_faction_boss", False):
        game_state.defeated_bosses.add(faction_id)
        game_state.story_events.append({
            "text": f"Destroyed {boss_entity.name}, ending the {faction_name} forever.",
            "event_type": "faction_destroyed",
        })
        check_for_faction_takeover(game_state)
        _check_all_factions_destroyed(game_state)

    elif tier == "apex":
        _grant_genesis_module(game_state)

    elif tier == "quest":
        game_state.story_events.append({
            "text": f"Defeated {boss_entity.name}.",
            "event_type": "boss_defeated",
        })


# --- Endgame chain ---

def _get_non_neutral_factions(game_state):
    """Return IDs of factions that have a boss (non-neutral)."""
    return [
        fid for fid, data in game_state.factions.items()
        if data.get("faction_boss") is not None
    ]


def _check_all_factions_destroyed(game_state):
    """After a coup, check if all non-neutral factions are destroyed.
    If so, queue the final boss spawn at the neutral city."""
    hostiles = _get_non_neutral_factions(game_state)
    if all(fid in game_state.defeated_bosses for fid in hostiles):
        if not game_state.final_boss_spawned:
            game_state.story_events.append({
                "text": "All factions have fallen. The wasteland trembles. "
                        "Something ancient stirs in the neutral city...",
                "event_type": "final_boss_warning",
            })
            spawn_final_boss(game_state)


def spawn_final_boss(game_state):
    """Spawn the final apex boss at the neutral city (0, 0)."""
    from ..data.game_constants import CITY_SPACING
    from ..entities.vehicles.war_rig import WarRig

    game_state.final_boss_spawned = True

    boss = WarRig(0, 0)
    boss.name = "The Genesis Engine"
    boss.is_major_enemy = True
    boss.is_faction_boss = True
    boss.boss_tier = "apex"

    tier_scale = BOSS_TIER_SCALING.get("apex", {})
    prog_hp, prog_dmg, _ = get_enemy_scaling(game_state)
    boss.durability = int(boss.durability * 10 * tier_scale.get("hp_mult", 8) * prog_hp)
    boss.max_durability = boss.durability
    boss.collision_damage = int(getattr(boss, "collision_damage", 10) * tier_scale.get("dmg_mult", 4) * prog_dmg)
    boss.shoot_damage = int(getattr(boss, "shoot_damage", 10) * tier_scale.get("dmg_mult", 4) * prog_dmg)
    boss.speed = 8
    boss.xp_value = 10000
    boss.cash_value = 5000
    boss.faction_id = None

    game_state.active_enemies.append(boss)

    quest = Quest(
        name="The Genesis Engine",
        description="An ancient war machine has awakened in the neutral city. "
                    "It guards the Genesis Module — the key to escaping the wasteland. "
                    "Destroy it to claim your freedom.",
        objectives=[KillBossObjective("The Genesis Engine")],
        rewards={"xp": 10000, "cash": 5000},
        requires_turn_in=False,
    )
    game_state.active_quests = [quest]
    game_state.selected_quest_index = 0
    game_state.waypoint = {"x": 0, "y": 0, "name": "The Genesis Engine"}


def _grant_genesis_module(game_state):
    """Grant the Genesis Module after defeating the final boss."""
    game_state.has_genesis_module = True

    game_state.max_durability *= 10
    game_state.current_durability = game_state.max_durability
    game_state.god_mode = True
    game_state.max_speed *= 3

    game_state.story_events.append({
        "text": "You rip the Genesis Module from the wreckage. "
                "Power surges through your vehicle. You are unstoppable. "
                "Now — find the Rift at the edge of the wasteland and escape.",
        "event_type": "genesis_module",
    })

    from ..data.game_constants import CITY_SPACING
    escape_x = 6 * CITY_SPACING
    escape_y = 6 * CITY_SPACING

    quest = Quest(
        name="Escape the Wasteland",
        description="The Genesis Module pulses with power. A rift has opened "
                    "at the far edge of the wasteland. Drive there to escape forever.",
        objectives=[],
        rewards={"xp": 0, "cash": 0},
        requires_turn_in=False,
    )
    game_state.active_quests = [quest]
    game_state.selected_quest_index = 0
    game_state.waypoint = {"x": escape_x, "y": escape_y, "name": "The Rift"}
    game_state.escape_target = (escape_x, escape_y)


def check_escape_reached(game_state):
    """Check if the player has reached the escape rift. Called from the game loop."""
    if not game_state.has_genesis_module:
        return False
    target = getattr(game_state, "escape_target", None)
    if not target:
        return False
    dist_sq = (game_state.car_world_x - target[0])**2 + (game_state.car_world_y - target[1])**2
    return dist_sq < 2500  # within 50 units


# --- Legacy compatibility wrapper ---

def check_challenge_conditions(game_state, faction_id, factions_data):
    """Check if the coup de grâce challenge is available at city hall."""
    return check_coup_conditions(game_state, faction_id)


def spawn_faction_boss(game_state, faction_id):
    """Legacy wrapper — called from building_damage for retaliation bosses."""
    spawn_retaliation_boss(game_state, faction_id)


def handle_faction_boss_defeat(game_state, boss_entity):
    """Legacy wrapper — called from combat screen."""
    handle_boss_defeat(game_state, boss_entity)

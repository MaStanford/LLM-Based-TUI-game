"""
Debug console command parser and executor.
Only active when dev_mode is enabled.
"""
import math
import logging

from .entity_loader import ENEMY_VEHICLES, ENEMY_CHARACTERS, FAUNA, OBSTACLES, ALL_VEHICLES, normalize_class_name

try:
    from .boss import spawn_faction_boss
except ImportError:
    spawn_faction_boss = None


def _find_entity_class(name: str, *class_lists):
    """Find an entity class by name across multiple lists."""
    normalized = normalize_class_name(name)
    for class_list in class_lists:
        for cls in class_list:
            if normalize_class_name(cls.__name__) == normalized:
                return cls
    return None


def _find_entity_by_id(game_state, entity_id: int):
    """Find an entity across all active lists by its entity_id."""
    for enemy in game_state.active_enemies:
        if enemy.entity_id == entity_id:
            return enemy, "enemy"
    for fauna in game_state.active_fauna:
        if fauna.entity_id == entity_id:
            return fauna, "fauna"
    for obstacle in game_state.active_obstacles:
        if obstacle.entity_id == entity_id:
            return obstacle, "obstacle"
    return None, None


def _default_spawn_pos(game_state, dx=None, dy=None):
    """Calculate spawn position: explicit offset or 50 units ahead of player."""
    if dx is not None and dy is not None:
        return game_state.car_world_x + dx, game_state.car_world_y + dy
    # 50 units ahead of player's facing direction
    adjusted = game_state.car_angle - (math.pi / 2)
    return (
        game_state.car_world_x + 50 * math.cos(adjusted),
        game_state.car_world_y + 50 * math.sin(adjusted),
    )


def execute_command(game_state, world, command_string: str) -> str:
    """Parse and execute a debug command. Returns a result message string."""
    parts = command_string.strip().split()
    if not parts:
        return "Empty command. Type 'help' for a list."

    cmd = parts[0].lower()

    try:
        if cmd == "help":
            return _cmd_help()
        elif cmd == "spawn":
            return _cmd_spawn(game_state, parts[1:])
        elif cmd == "kill":
            return _cmd_kill(game_state, parts[1:])
        elif cmd == "tp":
            return _cmd_teleport(game_state, parts[1:])
        elif cmd == "tp_rel":
            return _cmd_teleport_rel(game_state, parts[1:])
        elif cmd == "god":
            return _cmd_god(game_state)
        elif cmd == "heal":
            return _cmd_heal(game_state)
        elif cmd == "gas":
            return _cmd_gas(game_state)
        elif cmd == "cash":
            return _cmd_cash(game_state, parts[1:])
        elif cmd == "xp":
            return _cmd_xp(game_state, parts[1:])
        elif cmd == "level":
            return _cmd_level(game_state, parts[1:])
        elif cmd == "speed":
            return _cmd_speed(game_state, parts[1:])
        elif cmd == "ammo":
            return _cmd_ammo(game_state, parts[1:])
        elif cmd == "list":
            return _cmd_list(game_state, parts[1:])
        else:
            return f"Unknown command: '{cmd}'. Type 'help' for a list."
    except Exception as e:
        logging.error(f"Debug command error: {e}", exc_info=True)
        return f"Error: {e}"


# --- Command Implementations ---

def _cmd_help():
    return (
        "Commands: spawn, kill, tp, tp_rel, god, heal, gas, "
        "cash, xp, level, speed, ammo, list, help\n"
        "spawn enemy <class> [dx dy] | spawn boss <faction_id> | "
        "spawn fauna/obstacle <class> [dx dy]\n"
        "kill <id> | kill all | tp <x> <y> | tp_rel <dx> <dy>\n"
        "god | heal | gas | cash <n> | xp <n> | level <n> | speed <n>\n"
        "ammo <type> <n> | list enemies | list factions | list all"
    )


def _cmd_spawn(game_state, args):
    if len(args) < 2:
        return "Usage: spawn <enemy|boss|fauna|obstacle> <class_or_id> [dx dy]"

    spawn_type = args[0].lower()

    if spawn_type == "boss":
        faction_id = args[1]
        if faction_id not in game_state.factions:
            available = ", ".join(game_state.factions.keys())
            return f"Unknown faction: '{faction_id}'. Available: {available}"
        if spawn_faction_boss is None:
            return "Boss spawning unavailable (boss module not loaded)."
        try:
            spawn_faction_boss(game_state, faction_id)
            return f"Spawned boss for faction '{faction_id}'."
        except Exception as e:
            return f"Boss spawn failed: {e}"

    class_name = args[1]
    dx, dy = None, None
    if len(args) >= 4:
        dx, dy = float(args[2]), float(args[3])

    if spawn_type == "enemy":
        cls = _find_entity_class(class_name, ENEMY_VEHICLES, ENEMY_CHARACTERS)
        if not cls:
            available = [c.__name__ for c in ENEMY_VEHICLES + ENEMY_CHARACTERS]
            return f"Unknown enemy: '{class_name}'. Available: {', '.join(available)}"
        sx, sy = _default_spawn_pos(game_state, dx, dy)
        entity = cls(sx, sy)
        game_state.active_enemies.append(entity)
        return f"Spawned {cls.__name__} (id={entity.entity_id}) at ({sx:.0f}, {sy:.0f})"

    elif spawn_type == "fauna":
        cls = _find_entity_class(class_name, FAUNA)
        if not cls:
            available = [c.__name__ for c in FAUNA]
            return f"Unknown fauna: '{class_name}'. Available: {', '.join(available)}"
        sx, sy = _default_spawn_pos(game_state, dx, dy)
        entity = cls(sx, sy)
        game_state.active_fauna.append(entity)
        return f"Spawned {cls.__name__} (id={entity.entity_id}) at ({sx:.0f}, {sy:.0f})"

    elif spawn_type == "obstacle":
        cls = _find_entity_class(class_name, OBSTACLES)
        if not cls:
            available = [c.__name__ for c in OBSTACLES]
            return f"Unknown obstacle: '{class_name}'. Available: {', '.join(available)}"
        sx, sy = _default_spawn_pos(game_state, dx, dy)
        entity = cls(sx, sy)
        game_state.active_obstacles.append(entity)
        return f"Spawned {cls.__name__} (id={entity.entity_id}) at ({sx:.0f}, {sy:.0f})"

    return f"Unknown spawn type: '{spawn_type}'. Use enemy, boss, fauna, or obstacle."


def _cmd_kill(game_state, args):
    if not args:
        return "Usage: kill <id> | kill all"

    if args[0].lower() == "all":
        count = len(game_state.active_enemies)
        game_state.active_enemies.clear()
        return f"Killed all {count} enemies."

    try:
        entity_id = int(args[0])
    except ValueError:
        return f"Invalid ID: '{args[0]}'. Use a number or 'all'."

    entity, entity_type = _find_entity_by_id(game_state, entity_id)
    if entity is None:
        return f"No entity found with id={entity_id}."

    name = getattr(entity, "name", entity.__class__.__name__)
    if entity_type == "enemy":
        game_state.active_enemies.remove(entity)
    elif entity_type == "fauna":
        game_state.active_fauna.remove(entity)
    elif entity_type == "obstacle":
        game_state.active_obstacles.remove(entity)
    return f"Killed {name} (id={entity_id})."


def _cmd_teleport(game_state, args):
    if len(args) < 2:
        return "Usage: tp <x> <y>"
    x, y = float(args[0]), float(args[1])
    game_state.car_world_x = x
    game_state.car_world_y = y
    game_state.player_car.x = x
    game_state.player_car.y = y
    return f"Teleported to ({x:.0f}, {y:.0f})."


def _cmd_teleport_rel(game_state, args):
    if len(args) < 2:
        return "Usage: tp_rel <dx> <dy>"
    dx, dy = float(args[0]), float(args[1])
    game_state.car_world_x += dx
    game_state.car_world_y += dy
    game_state.player_car.x = game_state.car_world_x
    game_state.player_car.y = game_state.car_world_y
    return f"Moved by ({dx:.0f}, {dy:.0f}) → now at ({game_state.car_world_x:.0f}, {game_state.car_world_y:.0f})."


def _cmd_god(game_state):
    game_state.god_mode = not game_state.god_mode
    state = "ON" if game_state.god_mode else "OFF"
    return f"God mode: {state}"


def _cmd_heal(game_state):
    game_state.current_durability = game_state.max_durability
    return f"Healed to {game_state.max_durability:.0f} durability."


def _cmd_gas(game_state):
    game_state.current_gas = game_state.gas_capacity
    return f"Gas refilled to {game_state.gas_capacity:.0f}."


def _cmd_cash(game_state, args):
    if not args:
        return "Usage: cash <amount>"
    amount = int(args[0])
    game_state.player_cash += amount
    return f"Added ${amount}. Total: ${game_state.player_cash}."


def _cmd_xp(game_state, args):
    if not args:
        return "Usage: xp <amount>"
    amount = int(args[0])
    game_state.current_xp += amount
    return f"Added {amount} XP. Total: {game_state.current_xp}/{game_state.xp_to_next_level}."


def _cmd_level(game_state, args):
    if not args:
        return "Usage: level <n>"
    level = int(args[0])
    game_state.player_level = level
    game_state.apply_level_bonuses()
    return f"Set level to {level}. Stats recalculated."


def _cmd_speed(game_state, args):
    if not args:
        return "Usage: speed <value>"
    speed = float(args[0])
    game_state.car_speed = speed
    return f"Set speed to {speed:.1f}."


def _cmd_ammo(game_state, args):
    if len(args) < 2:
        available = ", ".join(game_state.ammo_counts.keys()) if game_state.ammo_counts else "none"
        return f"Usage: ammo <type> <amount>. Current types: {available}"
    ammo_type = args[0]
    amount = int(args[1])
    game_state.ammo_counts[ammo_type] = amount
    return f"Set {ammo_type} ammo to {amount}."


def _cmd_list(game_state, args):
    if not args:
        return "Usage: list enemies | list factions | list all"

    list_type = args[0].lower()

    if list_type == "enemies":
        if not game_state.active_enemies:
            return "No active enemies."
        lines = []
        for e in game_state.active_enemies:
            name = getattr(e, "name", e.__class__.__name__)
            boss = " [BOSS]" if getattr(e, "is_faction_boss", False) else ""
            lines.append(
                f"  id={e.entity_id} {name}{boss} "
                f"hp={e.durability:.0f}/{e.max_durability:.0f} "
                f"pos=({e.x:.0f},{e.y:.0f})"
            )
        return f"Enemies ({len(lines)}):\n" + "\n".join(lines)

    elif list_type == "factions":
        if not game_state.factions:
            return "No factions loaded."
        lines = []
        for fid, fdata in game_state.factions.items():
            name = fdata.get("name", fid)
            hub = fdata.get("hub_city_coordinates", "?")
            rep = game_state.faction_reputation.get(fid, 0)
            lines.append(f"  {fid}: {name} hub={hub} rep={rep}")
        return f"Factions ({len(lines)}):\n" + "\n".join(lines)

    elif list_type == "all":
        total = (len(game_state.active_enemies) +
                 len(game_state.active_fauna) +
                 len(game_state.active_obstacles))
        lines = [f"Total entities: {total}"]
        lines.append(f"  Enemies: {len(game_state.active_enemies)}")
        lines.append(f"  Fauna: {len(game_state.active_fauna)}")
        lines.append(f"  Obstacles: {len(game_state.active_obstacles)}")
        return "\n".join(lines)

    return f"Unknown list type: '{list_type}'. Use enemies, factions, or all."

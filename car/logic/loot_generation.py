import random
import time
from ..data.pickups import PICKUP_DATA, PICKUP_CASH
from ..data.weapons import WEAPONS_DATA
from ..data.equipment import EQUIPMENT_DATA
from .modifier_logic import generate_weapon_modifiers, generate_equipment_modifiers
from ..entities.weapon import Weapon
from ..entities.equipment import Equipment
from .llm_item_generator import generate_item_from_llm

def handle_enemy_loot_drop(game_state, enemy, app):
    """
    Handles the loot drop for a defeated enemy.
    """
    # --- Cash Drop ---
    cash_dropped = int(enemy.cash_value * game_state.player_level * game_state.difficulty_mods.get("xp_mult", 1.0))
    game_state.active_pickups[game_state.next_pickup_id] = {
        "type": "cash",
        "x": enemy.x,
        "y": enemy.y,
        "value": cash_dropped,
        "char": PICKUP_DATA[PICKUP_CASH]["art"][0],
        "color": PICKUP_DATA[PICKUP_CASH]["color_pair_name"],
        "spawn_time": time.time(),
    }
    game_state.next_pickup_id += 1

    # --- Item Drop ---
    luck_factor = 1.0
    if hasattr(enemy, "is_boss") and enemy.is_boss:
        luck_factor = 5.0

    # Determine if we should try to drop a weapon at all
    if random.random() < (0.1 * luck_factor): # 10% base chance, increased by luck
        
        # Decide whether to generate a special LLM item or a standard one
        if random.random() < (0.2 * luck_factor): # 20% base chance for special item
            base_weapon_id = random.choice(list(WEAPONS_DATA.keys()))
            item_data = generate_item_from_llm(app, game_state.theme, game_state.player_level, base_weapon_id)
            
            # If LLM generation succeeds (or provides a valid fallback)
            if item_data:
                weapon = Weapon(
                    weapon_type_id=item_data["base_item_id"],
                    modifiers=item_data["stat_modifiers"],
                    name=item_data["name"],
                    description=item_data["description"],
                    rarity=item_data["rarity"]
                )
            else: # Fallback to a standard weapon if LLM fails completely
                modifiers = generate_weapon_modifiers(game_state.player_level, luck_factor)
                weapon_id = random.choice(list(WEAPONS_DATA.keys()))
                weapon = Weapon(weapon_id, modifiers)

        else: # Generate a standard, non-LLM weapon
            modifiers = generate_weapon_modifiers(game_state.player_level, luck_factor)
            weapon_id = random.choice(list(WEAPONS_DATA.keys()))
            weapon = Weapon(weapon_id, modifiers)

        # Add the created weapon to the world as a pickup
        game_state.active_pickups[game_state.next_pickup_id] = {
            "type": "weapon",
            "x": enemy.x + 1,
            "y": enemy.y,
            "weapon": weapon,
            "char": "W",
            "color": "PICKUP_GUN",
            "spawn_time": time.time(),
        }
        game_state.next_pickup_id += 1


    # --- Equipment Drop ---
    if random.random() < (0.08 * luck_factor):
        equipment_id = random.choice(list(EQUIPMENT_DATA.keys()))
        modifiers, rarity = generate_equipment_modifiers(game_state.player_level, luck_factor)
        equipment = Equipment(equipment_id, modifiers=modifiers, rarity=rarity)

        game_state.active_pickups[game_state.next_pickup_id] = {
            "type": "equipment",
            "x": enemy.x - 1,
            "y": enemy.y + 1,
            "equipment": equipment,
            "char": "E",
            "color": "PICKUP_EQUIPMENT",
            "spawn_time": time.time(),
        }
        game_state.next_pickup_id += 1


    # --- Narrative Item Drop ---
    if random.random() < 0.05: # 5% chance to drop a narrative item
        game_state.active_pickups[game_state.next_pickup_id] = {
            "type": "narrative",
            "x": enemy.x - 1,
            "y": enemy.y,
            "data": {
                "title": "Tattered Journal",
                "text": "The journal speaks of a hidden cache of pre-war tech in a cave to the east...",
                "action": "waypoint",
                "target_x": enemy.x + 100,
                "target_y": enemy.y
            },
            "char": "?",
            "color": "PICKUP_NARRATIVE",
            "spawn_time": time.time(),
        }
        game_state.next_pickup_id += 1

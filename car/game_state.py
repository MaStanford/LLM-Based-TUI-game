import math
import random
from .entities.weapon import Weapon
from .logic.entity_loader import PLAYER_CARS
from .data.game_constants import LEVEL_STAT_BONUS_PER_LEVEL, MAX_LEVEL, SAFE_ZONE_RADIUS, DESPAWN_RADIUS, GLOBAL_SPEED_MULTIPLIER
from .data.difficulty import DIFFICULTY_MODIFIERS
from .data.equipment import EQUIPMENT_SLOTS

class GameState:
    def __init__(self, selected_car_index, difficulty, difficulty_mods, car_color_names, factions, theme=None):
        # --- Game Configuration ---
        self.selected_car_index = selected_car_index
        self.difficulty = difficulty
        self.difficulty_mods = difficulty_mods
        self.car_color_names = car_color_names
        self.factions = factions
        self.theme = theme if theme is not None else {"name": "Default", "description": "A standard wasteland adventure."}
        self.story_intro = ""
        self.world_details = {}
        
        # --- Triggers ---
        self.active_triggers = []
        self.activated_triggers = set()
        
        # --- Player Actions ---
        self.pedal_position = 0.0  # -1.0 for full brake, 1.0 for full accelerator
        self.actions = {
            "turn_left": False, "turn_right": False, "fire": False
        }
        
        # --- Player State ---
        self.player_cash = self.difficulty_mods.get("starting_cash", 300)
        
        # --- Player Car ---
        car_class = PLAYER_CARS[self.selected_car_index]
        self.player_car = car_class(0, 0)

        # --- Base Stats for Leveling ---
        self.base_max_durability = self.player_car.durability
        self.base_gas_capacity = self.player_car.fuel
        self.base_max_speed = self.player_car.speed
        self.base_acceleration_factor = self.player_car.acceleration
        self.base_turn_rate = self.player_car.handling
        self.base_braking_power = self.player_car.braking_power
        self.base_weapon_aim_speed = getattr(self.player_car, 'weapon_aim_speed', 1.0)

        # --- Effective Stats (modified by level) ---
        self.max_speed = 0.0
        self.acceleration_factor = 0.0
        self.turn_rate = 0.0
        self.max_durability = 0
        self.gas_capacity = 0
        self.braking_power = 0
        self.weapon_aim_speed = 0.0
        self.level_damage_modifier = 1.0

        # --- XP and Level Variables ---
        self.player_level = 1
        self.current_xp = 0
        self.xp_to_next_level = 100 # Placeholder
        self.level_up_message_timer = 0

        # --- Car State ---
        self.car_world_x = 0.0
        self.car_world_y = 0.0
        self.car_angle = 0.0
        self.car_velocity_x = 0.0
        self.car_velocity_y = 0.0
        self.car_speed = 0.0
        self.current_durability = 0
        self.current_gas = 0
        self.distance_traveled = 0.0
        self.weapon_angle_offset = 0.0
        self.mouse_aim_enabled = False
        self.mouse_aim_world_x = 0.0
        self.mouse_aim_world_y = 0.0

        # --- Collision Physics ---
        self.deflection_vx = 0.0
        self.deflection_vy = 0.0
        self.deflection_frames = 0
        self.collision_iframes = 0  # invulnerability frames after collision
        self.god_mode = False

        # --- Karma System ---
        self.karma = 0  # negative = evil, positive = good

        # --- Player State ---
        self.player_inventory = []
        self.attachment_points = self.player_car.attachment_points

        # Initialize all attachment points as empty
        self.mounted_weapons = {point_name: None for point_name in self.attachment_points}

        # --- Equipment Slots ---
        self.equipped_equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        self.player_scrap = 0
        
        # Equip default weapons
        for mount_point, weapon_type_id in self.player_car.default_weapons.items():
            if mount_point in self.mounted_weapons:
                self.mounted_weapons[mount_point] = Weapon(weapon_type_id, instance_id=f"{weapon_type_id}_default")

        self.ammo_counts = {}
        self.weapon_cooldowns = {}
        self.weapon_enabled = {point_name: True for point_name in self.attachment_points}

        for weapon in self.mounted_weapons.values():
            if weapon:
                self.weapon_cooldowns[weapon.instance_id] = 0
                ammo_type = weapon.ammo_type
                if ammo_type not in self.ammo_counts:
                    self.ammo_counts[ammo_type] = 0
                self.ammo_counts[ammo_type] += 100 # Starting ammo


        # --- Derived Stats ---
        self.acceleration_factor = 0.0
        self.braking_deceleration_factor = 0.0
        self.max_speed = 0.0
        self.gas_consumption_scaler = 0.01
        self.drag_coefficient = 0.03
        self.friction_coefficient = 0.08
        self.gas_consumption_rate = 0.01

        # --- World and Entity State ---
        self.active_obstacles = []
        self.obstacle_spawn_timer = 0
        self.active_particles = []
        self.active_flames = []
        self.active_explosions = []
        self.destroyed_this_frame = []
        self.active_pickups = {}
        self.next_pickup_id = 0
        self.active_fauna = []
        self.fauna_spawn_timer = 0
        self.active_enemies = []
        self.enemy_spawn_timer = 0
        self.active_turrets = []
        self.turret_spawn_timer = 0
        
        # --- Quest State ---
        self.active_quests = []         # List of Quest objects, max 3
        self.selected_quest_index = 0   # Which quest compass/map tracks
        self.faction_reputation = {}
        self.faction_control = {}
        self.waypoint = None
        self.can_challenge_boss = {}
        self.defeated_bosses = set()
        self.active_bosses = []
        self.combat_enemy = None
        self.quest_cache = {}
        self.quests_completed = 0

        # --- Story / Journal ---
        self.story_events = []  # List of {"text": str, "event_type": str}

        # --- Fast Travel ---
        self.visited_cities = {(0, 0)}  # Set of (grid_x, grid_y) tuples; start city is always visited

        # --- Building Destruction State ---
        self.damaged_buildings = {}      # {(gx,gy,idx): current_hp}
        self.destroyed_buildings = set() # {(gx,gy,idx)}
        self.buildings_destroyed_per_city = {}  # {(gx,gy): count}

        # --- UI and Game Flow State ---
        self.shop_cooldown = 0
        self.city_hall_cooldown = 100 # Start with a cooldown to prevent immediate interaction
        self.menu_toggle_cooldown = 0
        self.menu_nav_cooldown = 0
        self.game_over = False
        self.game_over_message = ""
        self.menu_open = False
        self.pause_menu_open = False
        self.selected_pause_option = 0
        self.play_again = False
        self.frame = 0
        self.menu_selected_section_idx = 0
        self.menu_selected_item_idx = 0
        self.menu_preview_angle = 0.0
        self.safe_zone_radius = SAFE_ZONE_RADIUS
        self.despawn_radius = DESPAWN_RADIUS
        self.screen_width = 0
        self.screen_height = 0
        self.notifications = []
        self.closest_entity_info = None
        self.tracked_entity = None
        self.compass_info = {"absolute_bearing": 0, "target_name": ""}

        self.world_triggers = []
        self.triggered_triggers = set()

        self.apply_level_bonuses()

    @property
    def all_entities(self):
        """Returns a combined list of all active entities."""
        return ([self.player_car] +
                self.active_obstacles +
                self.active_fauna +
                self.active_enemies +
                self.active_turrets)

    def gain_xp(self, xp):
        self.current_xp += xp
        while self.current_xp >= self.xp_to_next_level:
            if self.player_level < MAX_LEVEL:
                self.current_xp -= self.xp_to_next_level
                self.player_level += 1
                self.xp_to_next_level = int(self.xp_to_next_level * 1.5) # Placeholder
                self.apply_level_bonuses()
                self.level_up_message_timer = 60
            else:
                self.current_xp = self.xp_to_next_level
                break

    def apply_level_bonuses(self):
        level_bonus_multiplier = 1.0 + (self.player_level - 1) * LEVEL_STAT_BONUS_PER_LEVEL

        self.max_speed = self.base_max_speed * level_bonus_multiplier * GLOBAL_SPEED_MULTIPLIER
        self.acceleration_factor = self.base_acceleration_factor * level_bonus_multiplier
        self.turn_rate = self.base_turn_rate * level_bonus_multiplier
        self.braking_power = self.base_braking_power * level_bonus_multiplier
        self.weapon_aim_speed = self.base_weapon_aim_speed * level_bonus_multiplier

        new_max_durability = int(self.base_max_durability * level_bonus_multiplier)
        durability_increase = new_max_durability - self.max_durability
        self.max_durability = new_max_durability
        self.current_durability = min(self.max_durability, self.current_durability + durability_increase)
        if self.player_level == 1:
            self.current_durability = self.max_durability

        new_gas_capacity = int(self.base_gas_capacity * level_bonus_multiplier)
        gas_increase = new_gas_capacity - self.gas_capacity
        self.gas_capacity = new_gas_capacity
        self.current_gas = min(self.gas_capacity, self.current_gas + gas_increase)
        if self.player_level == 1:
            self.current_gas = self.gas_capacity

        self.level_damage_modifier = level_bonus_multiplier

        self.apply_equipment_bonuses()

    def apply_equipment_bonuses(self):
        """Applies stat modifiers from all equipped equipment.
        Bonuses stack additively: two 1.2x pieces give 1.4x, not 1.44x."""
        combined = {}
        for slot_name, equipment in self.equipped_equipment.items():
            if equipment:
                for stat, multiplier in equipment.stat_bonuses.items():
                    if stat in combined:
                        combined[stat] += (multiplier - 1.0)
                    else:
                        combined[stat] = multiplier

        if "speed" in combined:
            self.max_speed *= combined["speed"]
        if "acceleration" in combined:
            self.acceleration_factor *= combined["acceleration"]
        if "handling" in combined:
            self.turn_rate *= combined["handling"]
        if "braking" in combined:
            self.braking_power *= combined["braking"]
        if "weapon_aim_speed" in combined:
            self.weapon_aim_speed *= combined["weapon_aim_speed"]
        if "damage" in combined:
            self.level_damage_modifier *= combined["damage"]
        if "fire_rate" in combined:
            self.level_damage_modifier *= combined["fire_rate"]
        if "durability" in combined:
            new_max = int(self.max_durability * combined["durability"])
            increase = new_max - self.max_durability
            self.max_durability = new_max
            self.current_durability = min(self.max_durability, self.current_durability + increase)
        if "fuel_capacity" in combined:
            new_cap = int(self.gas_capacity * combined["fuel_capacity"])
            increase = new_cap - self.gas_capacity
            self.gas_capacity = new_cap
            self.current_gas = min(self.gas_capacity, self.current_gas + increase)
        if "fuel_efficiency" in combined:
            self.gas_consumption_rate *= max(0.1, 2.0 - combined["fuel_efficiency"])

    def to_dict(self):
        """Serializes the game state to a dictionary."""
        inventory_dict = [item.to_dict() for item in self.player_inventory]
        mounted_weapons_dict = {
            mount: weapon.to_dict() if weapon else None
            for mount, weapon in self.mounted_weapons.items()
        }

        return {
            # Game Config
            "selected_car_index": self.selected_car_index,
            "difficulty": self.difficulty,
            "car_color_names": self.car_color_names,
            "theme": self.theme,
            "story_intro": self.story_intro,
            "world_details": self.world_details,
            
            # Player State
            "player_cash": self.player_cash,
            "player_level": self.player_level,
            "current_xp": self.current_xp,
            "xp_to_next_level": self.xp_to_next_level,
            
            # Car State
            "car_world_x": self.car_world_x,
            "car_world_y": self.car_world_y,
            "car_angle": self.car_angle,
            "current_durability": self.current_durability,
            "current_gas": self.current_gas,
            "distance_traveled": self.distance_traveled,
            
            # Inventory & Weapons
            "player_inventory": inventory_dict,
            "mounted_weapons": mounted_weapons_dict,
            "ammo_counts": self.ammo_counts,
            "weapon_enabled": self.weapon_enabled,
            "equipped_equipment": {
                slot: equip.to_dict() if equip else None
                for slot, equip in self.equipped_equipment.items()
            },
            "player_scrap": self.player_scrap,
            
            # Quest & Faction State
            "faction_reputation": self.faction_reputation,
            "faction_control": self.faction_control,
            "defeated_bosses": list(self.defeated_bosses), # Convert set to list
            "activated_triggers": list(self.activated_triggers),
            "active_quests": [q.to_dict() for q in self.active_quests],
            "selected_quest_index": self.selected_quest_index,
            "quests_completed": self.quests_completed,
            "karma": self.karma,
            "story_events": self.story_events,
            "visited_cities": [list(c) for c in self.visited_cities],

            # Building Destruction
            "damaged_buildings": {f"{k[0]},{k[1]},{k[2]}": v for k, v in self.damaged_buildings.items()},
            "destroyed_buildings": [f"{k[0]},{k[1]},{k[2]}" for k in self.destroyed_buildings],
            "buildings_destroyed_per_city": {f"{k[0]},{k[1]}": v for k, v in self.buildings_destroyed_per_city.items()},
        }

    @classmethod
    def from_dict(cls, data):
        """Deserializes a dictionary back into a GameState object."""
        difficulty = data.get("difficulty", "Normal")
        difficulty_mods = DIFFICULTY_MODIFIERS.get(difficulty, DIFFICULTY_MODIFIERS["Normal"])
        
        # The data_loader ensures the correct faction data is loaded from temp/
        from .logic.data_loader import FACTION_DATA, WORLD_DETAILS_DATA, TRIGGERS_DATA
        
        gs = cls(
            selected_car_index=data.get("selected_car_index", 0),
            difficulty=difficulty,
            difficulty_mods=difficulty_mods,
            car_color_names=data.get("car_color_names", ["CAR_RED"]),
            theme=data.get("theme", {"name": "Default", "description": "A standard wasteland adventure."}),
            factions=FACTION_DATA,
        )
        
        gs.story_intro = data.get("story_intro", "The wasteland awaits.")
        gs.world_details = WORLD_DETAILS_DATA
        gs.active_triggers = TRIGGERS_DATA
        
        # --- Restore Player State ---
        gs.player_cash = data.get("player_cash", 100)
        gs.player_level = data.get("player_level", 1)
        gs.current_xp = data.get("current_xp", 0)
        gs.xp_to_next_level = data.get("xp_to_next_level", 100)
        gs.apply_level_bonuses()

        # --- Restore Car State ---
        gs.car_world_x = data.get("car_world_x", 0.0)
        gs.car_world_y = data.get("car_world_y", 0.0)
        gs.car_angle = data.get("car_angle", 0.0)
        gs.player_car.x = gs.car_world_x
        gs.player_car.y = gs.car_world_y
        gs.player_car.angle = gs.car_angle
        gs.current_durability = data.get("current_durability", gs.max_durability)
        gs.current_gas = data.get("current_gas", gs.gas_capacity)
        gs.distance_traveled = data.get("distance_traveled", 0.0)
        
        # --- Restore Inventory & Weapons ---
        from .entities.equipment import Equipment
        raw_inventory = data.get("player_inventory", [])
        gs.player_inventory = []
        for item_data in raw_inventory:
            if item_data.get("item_type") == "equipment":
                gs.player_inventory.append(Equipment.from_dict(item_data))
            else:
                gs.player_inventory.append(Weapon.from_dict(item_data))

        gs.mounted_weapons = {
            mount: Weapon.from_dict(weapon_data) if weapon_data else None
            for mount, weapon_data in data.get("mounted_weapons", {}).items()
        }
        gs.ammo_counts = data.get("ammo_counts", {})
        gs.weapon_enabled = data.get("weapon_enabled", {point: True for point in gs.mounted_weapons})

        # --- Restore Equipment Slots ---
        raw_equipment = data.get("equipped_equipment", {})
        for slot, equip_data in raw_equipment.items():
            if equip_data and slot in gs.equipped_equipment:
                gs.equipped_equipment[slot] = Equipment.from_dict(equip_data)
        gs.player_scrap = data.get("player_scrap", 0)
        gs.apply_level_bonuses()
        
        # --- Restore Quest & Faction State ---
        gs.faction_reputation = data["faction_reputation"]
        gs.faction_control = data["faction_control"]
        gs.defeated_bosses = set(data["defeated_bosses"]) # Convert list back to set
        gs.activated_triggers = set(data.get("activated_triggers", []))
        gs.karma = data.get("karma", 0)
        gs.quests_completed = data.get("quests_completed", 0)
        gs.story_events = data.get("story_events", [])
        gs.visited_cities = {tuple(c) for c in data.get("visited_cities", [(0, 0)])}

        # --- Restore Building Destruction State ---
        raw_damaged = data.get("damaged_buildings", {})
        gs.damaged_buildings = {tuple(int(x) for x in k.split(",")): v for k, v in raw_damaged.items()}
        raw_destroyed = data.get("destroyed_buildings", [])
        gs.destroyed_buildings = {tuple(int(x) for x in k.split(",")) for k in raw_destroyed}
        raw_per_city = data.get("buildings_destroyed_per_city", {})
        gs.buildings_destroyed_per_city = {tuple(int(x) for x in k.split(",")): v for k, v in raw_per_city.items()}
        
        # Multi-quest deserialization with backward compat
        from .data.quests import Quest
        gs.active_quests = [Quest.from_dict(qd) for qd in data.get("active_quests", [])]
        if not gs.active_quests and data.get("current_quest"):
            gs.active_quests = [Quest.from_dict(data["current_quest"])]
        gs.selected_quest_index = data.get("selected_quest_index", 0)
        
        return gs
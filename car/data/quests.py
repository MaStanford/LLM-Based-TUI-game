class Objective:
    def __init__(self):
        self.completed = False

    def update(self, game_state):
        pass

    def to_dict(self):
        return {
            "type": self.__class__.__name__,
            "completed": self.completed
        }

    @staticmethod
    def from_dict(data):
        pass

class KillBossObjective(Objective):
    def __init__(self, boss_name):
        super().__init__()
        self.boss_name = boss_name
        self.boss_was_seen = False

    def update(self, game_state):
        boss_alive = any(enemy.name == self.boss_name for enemy in game_state.active_enemies)
        if boss_alive:
            self.boss_was_seen = True
        elif self.boss_was_seen:
            self.completed = True

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "boss_name": self.boss_name,
            "boss_was_seen": self.boss_was_seen,
        })
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["boss_name"])
        obj.completed = data["completed"]
        obj.boss_was_seen = data.get("boss_was_seen", False)
        return obj

class KillCountObjective(Objective):
    def __init__(self, target_name_or_count, target_count=None):
        super().__init__()
        if target_count is None:
            # Called with just a count: KillCountObjective(5)
            self.target_name = None
            self.target_count = target_name_or_count
        else:
            # Called with name and count: KillCountObjective("RustySedan", 5)
            self.target_name = target_name_or_count
            self.target_count = target_count
        self.kill_count = 0

    def update(self, game_state):
        # This will be updated by an external event in game.py
        if self.kill_count >= self.target_count:
            self.completed = True

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "target_name": self.target_name,
            "target_count": self.target_count,
            "kill_count": self.kill_count
        })
        return data

    @classmethod
    def from_dict(cls, data):
        target_name = data.get("target_name")
        if target_name:
            obj = cls(target_name, data["target_count"])
        else:
            obj = cls(data["target_count"])
        obj.kill_count = data["kill_count"]
        obj.completed = data["completed"]
        return obj

class SurvivalObjective(Objective):
    def __init__(self, duration):
        super().__init__()
        self.duration = duration  # seconds
        self.timer = duration
        self.active = False  # True when player is at the quest location

    def update(self, game_state):
        # Timer is decremented externally in quest_logic.py only when
        # the player is within range of the quest waypoint.
        if self.timer <= 0:
            self.completed = True

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "duration": self.duration,
            "timer": self.timer,
            "active": self.active
        })
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["duration"])
        obj.timer = data["timer"]
        obj.active = data.get("active", False)
        obj.completed = data["completed"]
        return obj

class DeliverPackageObjective(Objective):
    def __init__(self, destination):
        super().__init__()
        self.destination = destination

    def update(self, game_state):
        # This will be updated by an external event in game.py
        pass

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "destination": self.destination
        })
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["destination"])
        obj.completed = data["completed"]
        return obj


class DefendLocationObjective(Objective):
    def __init__(self, location, duration):
        super().__init__()
        self.location = location
        self.duration = duration
        self.timer = duration

    def update(self, game_state):
        # This will be updated by an external event in game.py
        pass

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "location": self.location,
            "duration": self.duration,
            "timer": self.timer
        })
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["location"], data["duration"])
        obj.timer = data["timer"]
        obj.completed = data["completed"]
        return obj


class WaveSpawnObjective(Objective):
    """Survive multiple waves of enemies spawning at a quest waypoint."""
    def __init__(self, total_waves, enemies_per_wave):
        super().__init__()
        self.total_waves = total_waves
        self.enemies_per_wave = enemies_per_wave
        self.current_wave = 0
        self.wave_enemies_remaining = 0
        self.wave_active = False  # True once the player arrives at the location

    def update(self, game_state):
        # Wave progression is handled externally in quest_logic.py
        if self.current_wave >= self.total_waves and self.wave_enemies_remaining <= 0:
            self.completed = True

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "total_waves": self.total_waves,
            "enemies_per_wave": self.enemies_per_wave,
            "current_wave": self.current_wave,
            "wave_enemies_remaining": self.wave_enemies_remaining,
            "wave_active": self.wave_active,
        })
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["total_waves"], data["enemies_per_wave"])
        obj.current_wave = data["current_wave"]
        obj.wave_enemies_remaining = data["wave_enemies_remaining"]
        obj.wave_active = data.get("wave_active", False)
        obj.completed = data["completed"]
        return obj


class QuestItem:
    """A lightweight item added to the player's inventory for delivery quests.
    Cannot be sold at shops."""
    def __init__(self, name, description, quest_name):
        self.name = name
        self.description = description
        self.quest_name = quest_name
        self.sellable = False
        self.price = 0  # Not sellable, but shops check this attribute

class Quest:
    def __init__(self, name, description, objectives, rewards, city_id=None, quest_giver_faction=None, target_faction=None, time_limit=None, next_quest_id=None, requires_turn_in=True, dialog=None, is_conquest_quest=False):
        self.name = name
        self.description = description
        self.objectives = objectives
        self.rewards = rewards
        self.city_id = city_id
        self.quest_giver_faction = quest_giver_faction
        self.target_faction = target_faction
        self.time_limit = time_limit
        self.next_quest_id = next_quest_id
        self.requires_turn_in = requires_turn_in
        self.dialog = dialog if dialog else "An old friend has a new job for you."
        self.is_conquest_quest = is_conquest_quest
        self.combat_waypoint = None  # (x, y) tuple for wave/survival quests outside city
        self.completed = False
        self.failed = False
        self.ready_to_turn_in = False
        self.boss = None # Runtime reference to the boss entity

    def to_dict(self):
        """Serializes the quest to a dictionary for logging and saving."""
        return {
            "name": self.name,
            "description": self.description,
            "objectives": [obj.to_dict() for obj in self.objectives],
            "rewards": self.rewards,
            "city_id": self.city_id,
            "quest_giver_faction": self.quest_giver_faction,
            "target_faction": self.target_faction,
            "time_limit": self.time_limit,
            "next_quest_id": self.next_quest_id,
            "requires_turn_in": self.requires_turn_in,
            "dialog": self.dialog,
            "is_conquest_quest": self.is_conquest_quest,
            "combat_waypoint": list(self.combat_waypoint) if self.combat_waypoint else None,
            "completed": self.completed,
            "failed": self.failed,
            "ready_to_turn_in": self.ready_to_turn_in,
            # We don't save the boss entity itself, but we might need to know if it was spawned
            # For now, we'll assume if the quest is loaded, we might need to handle boss respawn or check if it's dead
            # But the boss is an entity in the world, so it should be saved with other entities if we were saving entities.
            # Since we don't save all entities yet, we might lose the boss reference on reload if we don't handle it.
            # For now, let's just save the fact that we have a boss, but reconstructing it is tricky without full world persistence.
            # However, the Objective tracks the boss name.
        }

    @classmethod
    def from_dict(cls, data):
        # Reconstruct objectives
        objectives = []
        for obj_data in data["objectives"]:
            obj_type = obj_data["type"]
            if obj_type == "KillBossObjective":
                objectives.append(KillBossObjective.from_dict(obj_data))
            elif obj_type == "KillCountObjective":
                objectives.append(KillCountObjective.from_dict(obj_data))
            elif obj_type == "SurvivalObjective":
                objectives.append(SurvivalObjective.from_dict(obj_data))
            elif obj_type == "DeliverPackageObjective":
                objectives.append(DeliverPackageObjective.from_dict(obj_data))
            elif obj_type == "DefendLocationObjective":
                objectives.append(DefendLocationObjective.from_dict(obj_data))
            elif obj_type == "WaveSpawnObjective":
                objectives.append(WaveSpawnObjective.from_dict(obj_data))
        
        quest = cls(
            name=data["name"],
            description=data["description"],
            objectives=objectives,
            rewards=data["rewards"],
            city_id=tuple(data["city_id"]) if data["city_id"] else None,
            quest_giver_faction=data["quest_giver_faction"],
            target_faction=data["target_faction"],
            time_limit=data["time_limit"],
            next_quest_id=data["next_quest_id"],
            requires_turn_in=data["requires_turn_in"],
            dialog=data["dialog"],
            is_conquest_quest=data.get("is_conquest_quest", False)
        )
        quest.completed = data["completed"]
        quest.failed = data["failed"]
        quest.ready_to_turn_in = data["ready_to_turn_in"]
        wp = data.get("combat_waypoint")
        quest.combat_waypoint = tuple(wp) if wp else None
        return quest

    def update(self, game_state, dt):
        if self.time_limit is not None:
            self.time_limit -= dt
            if self.time_limit <= 0:
                self.failed = True
                return

        all_completed = True
        for objective in self.objectives:
            objective.update(game_state)
            if not objective.completed:
                all_completed = False
        self.completed = all_completed

# --- Quest Templates ---
QUEST_TEMPLATES = {
    "raid_convoy": {
        "name": "Raid Convoy: {target_faction_name}",
        "description": "The {quest_giver_faction_name} wants you to disrupt a supply convoy from the {target_faction_name}. Destroy 5 of their transport vehicles.",
        "offer_dialog": "Their supply lines are stretched thin. A surgical strike now could cripple their operations in this sector. Can you handle it?",
        "detail_dialog": "We've received intel about a lightly-guarded supply convoy moving through this area. Your mission is to intercept and destroy five of their transport vehicles. Expect resistance, but we have faith in your abilities.",
        "completion_dialog": "Excellent work. Their supply chain is in chaos. This will give us the opening we need. Here is your payment.",
        "objectives": [
            (KillCountObjective, [5]),
        ],
        "rewards": {
            "xp": 750,
            "cash": 300,
        },
        "time_limit": 120, # 2 minutes (seconds)
        "next_quest_id": "assassinate_rival"
    },
    "assassinate_rival": {
        "name": "Assassinate: {target_faction_name} Captain",
        "description": "Take out a high-value target from the {target_faction_name}. They are leading a patrol in this sector.",
        "offer_dialog": "A rival captain has been a thorn in our side for too long. We need someone to permanently remove them from the board. Are you up for it?",
        "detail_dialog": "This won't be easy. The target is a seasoned veteran in a modified Muscle Car. They'll be heavily armed and likely have an escort. Find them, eliminate them, and send a message.",
        "completion_dialog": "They won't be bothering us anymore. You've done us a great service. Here's your reward.",
        "objectives": [
            (KillBossObjective, ["faction_captain"]),
        ],
        "rewards": {
            "xp": 1200,
            "cash": 600,
        },
        "boss": {
            "name": "{target_faction_name} Captain",
            "car": "muscle_car",
            "hp_multiplier": 2.5,
            "damage_multiplier": 1.8,
            "xp_value": 600,
            "cash_value": 300,
        },
        "time_limit": 160, # ~2.6 minutes (seconds)
    },
    "defend_outpost": {
        "name": "Defend Outpost from {target_faction_name}",
        "description": "An outpost is under attack from the {target_faction_name}. Hold them off until reinforcements arrive.",
        "offer_dialog": "We're in a tight spot! Our outpost is being overrun. We need you to hold the line until our reinforcements can get there. Can you do it?",
        "detail_dialog": "The enemy is throwing everything they have at us. Survive their assault for a few minutes. A lieutenant is leading the final wave; take them out to break their morale and secure the outpost.",
        "completion_dialog": "You saved those people! We were cutting it close, but you bought us the time we needed. We're in your debt.",
        "objectives": [
            (SurvivalObjective, [120]),  # 120 seconds
        ],
        "rewards": {
            "xp": 1000,
            "cash": 500,
        }
    },
    "defend_convoy": {
        "name": "Convoy Guardian",
        "description": "A supply convoy is heading to a nearby settlement, but intelligence reports a planned ambush by Marauders. Protect the convoy and ensure the supplies get through.",
        "offer_dialog": "We've got a convoy of essential supplies heading for the settlement at Echo Creek. Our scouts spotted a Marauder war party gathering along the route, planning to hit them at the old overpass. We need a seasoned driver to run escort and make sure that convoy arrives in one piece. Can you handle it?",
        "detail_dialog": "The convoy will be passing through the Old Overpass. Get there and hold off any attackers until the convoy is clear. It should take a couple of minutes.",
        "completion_dialog": "The convoy made it through safely. You've saved a lot of lives today. Here's your payment.",
        "objectives": [
            (DefendLocationObjective, ["Old Overpass", 120]),
        ],
        "rewards": {
            "xp": 1000,
            "cash": 2000,
        }
    },
    "wave_assault": {
        "name": "Clear the {target_faction_name} Encampment",
        "description": "The {target_faction_name} have set up an encampment nearby. Fight through multiple waves of their forces to clear them out.",
        "offer_dialog": "We've located a {target_faction_name} encampment not far from here. They're dug in and getting bolder. We need someone to go in there and wipe them out, wave after wave. Think you can handle it?",
        "detail_dialog": "Get to the encampment and engage. Expect multiple waves of resistance. Each wave will be tougher than the last. Clear all waves to complete the mission.",
        "completion_dialog": "You cleared the entire encampment. The {target_faction_name} won't be setting up shop around here again. Outstanding work.",
        "objectives": [
            (WaveSpawnObjective, [3, 4]),  # 3 waves, 4 enemies per wave
        ],
        "rewards": {
            "xp": 1500,
            "cash": 800,
        },
        "time_limit": 180,  # 3 minutes (seconds)
    },
    "courier_run": {
        "name": "Courier Run to {destination}",
        "description": "Deliver a sensitive package to {destination}. The {target_faction_name} would love to intercept it.",
        "offer_dialog": "We've got a package that needs to get to {destination}, and it needs to get there fast. The {target_faction_name} have been intercepting our deliveries lately, so expect trouble on the road.",
        "detail_dialog": "Take the package and drive to {destination}. Enter the city to complete the delivery. Watch your back — they'll be looking for you.",
        "completion_dialog": "Package delivered safe and sound. You're a lifesaver. Here's your cut.",
        "objectives": [
            (DeliverPackageObjective, ["{destination}"]),
        ],
        "rewards": {
            "xp": 600,
            "cash": 1500,
        },
        "is_delivery": True,
    },
}

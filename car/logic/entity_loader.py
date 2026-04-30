import os
import importlib

ENTITY_BASE_PATH = "car.entities"
VEHICLE_PATH = "vehicles"
CHARACTER_PATH = "characters"
OBSTACLE_PATH = "obstacles"

from ..entities.vehicles.hatchback import Hatchback
from ..entities.vehicles.sports_car import SportsCar
from ..entities.vehicles.sedan import Sedan
from ..entities.vehicles.muscle_car import MuscleCar
from ..entities.vehicles.truck import Truck
from ..entities.vehicles.van import Van
from ..entities.vehicles.hotrod import Hotrod
from ..entities.vehicles.panel_wagon import PanelWagon
from ..entities.vehicles.rusty_sedan import RustySedan
from ..entities.vehicles.raider_buggy import RaiderBuggy
from ..entities.vehicles.technical import Technical
from ..entities.vehicles.war_rig import WarRig
from ..entities.vehicles.miner import Miner
from ..entities.characters.bandit import Bandit
from ..entities.characters.marauder import Marauder
from ..entities.characters.cat import Cat
from ..entities.characters.dog import Dog
from ..entities.characters.cow import Cow
from ..entities.obstacles.rock import Rock
from ..entities.obstacles.tire_pile import TirePile
from ..entities.obstacles.scrap_barricade import ScrapBarricade
from ..entities.obstacles.wrecked_husk import WreckedHusk
from ..entities.obstacles.oil_barrel import OilBarrel

PLAYER_CARS = [
    Hatchback, SportsCar, Sedan, Truck, Van, Hotrod, PanelWagon
]

ENEMY_VEHICLES = [
    RustySedan, RaiderBuggy, Technical, WarRig, Miner
]

ENEMY_CHARACTERS = [
    Bandit, Marauder
]

FAUNA = [
    Cat, Dog, Cow
]

OBSTACLES = [
    Rock, TirePile, ScrapBarricade, WreckedHusk, OilBarrel
]

def normalize_class_name(name: str) -> str:
    """Normalize a class/unit name for matching: lowercase, no underscores."""
    return name.lower().replace("_", "")


def _populate_entities():
    """
    Dynamically discovers and loads all entities from the file system,
    populating the lists of player cars, enemies, and fauna.
    """
    # Player Cars
    player_car_names = [
        "sports_car", "sedan", "van", "truck", "panel_wagon", 
        "hotrod", "motorcycle", "hatchback"
    ]
    for name in player_car_names:
        _load_entity(VEHICLE_PATH, name, PLAYER_CARS)

    # Enemy Vehicles
    enemy_vehicle_names = [
        "armored_truck", 
        "guard_truck", 
        "muscle_car", 
        "peacekeeper", 
        "raider_buggy", 
        "rust_bucket", 
        "rusty_sedan", 
        "technical", 
        "war_rig"]
    for name in enemy_vehicle_names:
        _load_entity(VEHICLE_PATH, name, ENEMY_VEHICLES)

    # Enemy Characters
    enemy_character_names = ["bandit", "marauder"]
    for name in enemy_character_names:
        _load_entity(CHARACTER_PATH, name, ENEMY_CHARACTERS)

    # Fauna
    fauna_names = ["dog", "cat", "cow"]
    for name in fauna_names:
        _load_entity(CHARACTER_PATH, name, FAUNA)

    # Obstacles
    obstacle_names = ["rock", "oil_barrel", "tire_pile", "scrap_barricade", "wrecked_husk"]
    for name in obstacle_names:
        _load_entity(OBSTACLE_PATH, name, OBSTACLES)

def _load_entity(entity_type_path, name, entity_list):
    """Helper to load an entity class and add it to a list."""
    try:
        module_path = f"{ENTITY_BASE_PATH}.{entity_type_path}.{name}"
        module = importlib.import_module(module_path)
        class_name = "".join(word.capitalize() for word in name.split("_"))
        entity_class = getattr(module, class_name)
        if entity_class not in entity_list:
            entity_list.append(entity_class)
    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not load entity '{name}': {e}")

# Initial population of the entity lists
_populate_entities()

ALL_VEHICLES = PLAYER_CARS + ENEMY_VEHICLES

def get_enemy_vehicle_list():
    """Returns a simple list of enemy vehicle names."""
    return [v.__name__ for v in ENEMY_VEHICLES]

def get_character_list():
    """Returns a simple list of character names."""
    return [c.__name__ for c in ENEMY_CHARACTERS + FAUNA]

def get_obstacle_list():
    """Returns a simple list of obstacle names."""
    return [o.__name__ for o in OBSTACLES]

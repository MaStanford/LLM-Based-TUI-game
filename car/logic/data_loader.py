import importlib.util
import sys
import json
import os

# --- Constants for File Paths ---
DEFAULT_FACTIONS_PATH = "car/data/factions.py"
TEMP_FACTIONS_PATH = "temp/factions.py"
TEMP_WORLD_DETAILS_PATH = "temp/world_details.json"
TEMP_TRIGGERS_PATH = "temp/triggers.json"


def _normalize_hub_coordinates(faction_data):
    """Convert hub_city_coordinates to grid-space tuples.
    Handles both world coords (large values from LLM) and grid coords (small values from fallback).
    """
    from ..data.game_constants import CITY_SPACING
    for fid, fdata in faction_data.items():
        coords = fdata.get("hub_city_coordinates")
        if coords:
            x, y = coords
            if abs(x) > 50 or abs(y) > 50:
                x = round(x / CITY_SPACING)
                y = round(y / CITY_SPACING)
            fdata["hub_city_coordinates"] = (x, y)


def load_faction_data():
    """
    Dynamically loads the FACTION_DATA dictionary.
    Checks for a session-specific 'factions.py' in 'temp/' and falls back
    to the default if not found.
    """
    path_to_load = DEFAULT_FACTIONS_PATH
    if os.path.exists(TEMP_FACTIONS_PATH):
        # Check if the file is not empty
        if os.path.getsize(TEMP_FACTIONS_PATH) > 0:
            path_to_load = TEMP_FACTIONS_PATH

    spec = importlib.util.spec_from_file_location("factions_data", path_to_load)
    factions_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(factions_module)
    
    return factions_module.FACTION_DATA

def load_world_details_data():
    """
    Loads the world_details.json from the temp/ directory if it exists.
    Returns an empty dictionary if the file is not found.
    """
    if os.path.exists(TEMP_WORLD_DETAILS_PATH):
        try:
            with open(TEMP_WORLD_DETAILS_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If the file is corrupted or can't be read, return empty
            return {}
    return {}

def load_triggers_data():
    """
    Loads the triggers.json from the temp/ directory if it exists.
    Returns an empty list if the file is not found.
    """
    if os.path.exists(TEMP_TRIGGERS_PATH):
        try:
            with open(TEMP_TRIGGERS_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


# Cached data — call reload_all() to refresh after generating new content
FACTION_DATA = load_faction_data()
_normalize_hub_coordinates(FACTION_DATA)
WORLD_DETAILS_DATA = load_world_details_data()
TRIGGERS_DATA = load_triggers_data()


def reload_all():
    """Reload all data from disk. Call after generating new world content.

    Mutates the existing containers in-place so that every module which
    imported ``FACTION_DATA``, ``WORLD_DETAILS_DATA``, or ``TRIGGERS_DATA``
    at the top level automatically sees the refreshed data (their name
    bindings still point to the same dict/list objects).
    """
    global FACTION_DATA, WORLD_DETAILS_DATA, TRIGGERS_DATA

    new_factions = load_faction_data()
    _normalize_hub_coordinates(new_factions)
    FACTION_DATA.clear()
    FACTION_DATA.update(new_factions)

    new_world_details = load_world_details_data()
    WORLD_DETAILS_DATA.clear()
    WORLD_DETAILS_DATA.update(new_world_details)

    new_triggers = load_triggers_data()
    TRIGGERS_DATA.clear()
    TRIGGERS_DATA.extend(new_triggers)

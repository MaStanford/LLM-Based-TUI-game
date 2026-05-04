import logging
from typing import Any, Dict
from .llm_inference import generate_json
from .llm_schemas import VEHICLE_NAMES_SCHEMA

# Base vehicle descriptions for prompt context
VEHICLE_ROLES = {
    "armored_truck": "Heavily armored, slow, durable security truck",
    "guard_truck": "Sturdy defensive patrol truck",
    "muscle_car": "Fast, aggressive high-performance car",
    "technical": "Gun-mounted pickup truck, versatile fighter",
    "raider_buggy": "Fast, light attack buggy",
    "rust_bucket": "Volatile suicide ramming vehicle, explodes on death",
    "rusty_sedan": "Basic, expendable patrol sedan",
    "war_rig": "Massive command vehicle, boss-tier, lays mines",
    "peacekeeper": "Standard patrol car, balanced stats",
    "miner": "Heavy armored vehicle that deploys mines",
    "bandit": "On-foot fighter with a gun",
    "marauder": "Aggressive on-foot raider, fast and dangerous",
}


def generate_vehicle_names(app: Any, theme: Dict, faction_id: str, faction_info: Dict) -> Dict:
    """
    Generates thematic names and descriptions for a faction's vehicle units.
    Returns a dict of {unit_id: {"name": str, "description": str}} or {} on failure.
    """
    faction_name = faction_info.get("name", faction_id)
    faction_desc = faction_info.get("description", "A wasteland faction.")
    units = faction_info.get("units", [])

    if not units:
        return {}

    logging.info(f"Generating vehicle names for faction '{faction_name}' ({len(units)} units)...")

    with open("prompts/vehicle_names_prompt.txt", "r") as f:
        prompt = f.read()

    # Build the vehicle list with role hints
    vehicle_lines = []
    for unit_id in units:
        role = VEHICLE_ROLES.get(unit_id, "Unknown vehicle type")
        vehicle_lines.append(f"- **{unit_id}**: {role}")
    vehicle_list_str = "\n".join(vehicle_lines)

    prompt = prompt.replace("{{ theme }}", f"'{theme['name']}': {theme['description']}")
    prompt = prompt.replace("{{ faction_name }}", faction_name)
    prompt = prompt.replace("{{ faction_description }}", faction_desc)
    prompt = prompt.replace("{{ vehicle_list }}", vehicle_list_str)

    response = generate_json(app, prompt, json_schema=VEHICLE_NAMES_SCHEMA, max_tokens=512, temperature=0.8)

    if response is None:
        logging.warning(f"Vehicle naming failed for faction '{faction_name}', using defaults.")
        return {}

    # Validate: only keep entries for units that actually belong to this faction
    validated = {}
    for unit_id in units:
        if unit_id in response:
            entry = response[unit_id]
            if isinstance(entry, dict) and "name" in entry and "description" in entry:
                validated[unit_id] = {
                    "name": str(entry["name"]),
                    "description": str(entry["description"]),
                }

    logging.info(f"Generated {len(validated)} vehicle names for '{faction_name}'.")
    return validated

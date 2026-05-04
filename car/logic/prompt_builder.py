import json
import os
import logging
from ..logic.data_loader import FACTION_DATA as GLOBAL_FACTION_DATA
from ..logic.entity_loader import ALL_VEHICLES, get_enemy_vehicle_list, get_character_list, get_obstacle_list

def _format_player_state(game_state):
    """Formats the player's current status into a string for the LLM."""
    # For workers, game_state might be a SimpleNamespace with no car
    car_name = getattr(getattr(game_state, 'player_car', None), 'name', 'Unknown')
    car_color = getattr(game_state, 'car_color_names', ['Unknown'])[0]
    
    # Handle mounted weapons carefully
    mounted_weapons_dict = getattr(game_state, 'mounted_weapons', {})
    mounted_weapons = [w.name for w in mounted_weapons_dict.values() if w]

    return (
        f"- Level: {getattr(game_state, 'player_level', 1)} ({getattr(game_state, 'current_xp', 0)}/{getattr(game_state, 'xp_to_next_level', 1000)} XP)\n"
        f"- Cash: ${getattr(game_state, 'player_cash', 0)}\n"
        f"- Vehicle: {car_name} ({car_color})\n"
        f"- Durability: {getattr(game_state, 'current_durability', 100)}/{getattr(game_state, 'max_durability', 100)}\n"
        f"- Mounted Weapons: {', '.join(mounted_weapons) if mounted_weapons else 'None'}"
    )

def _format_world_state(faction_data, game_state):
    """Formats the world's faction status into a string for the LLM."""
    report = []
    for faction_id, data in faction_data.items():
        control = game_state.faction_control.get(faction_id, data.get("control", 50))
        
        # Check if 'description' exists, provide a default if not.
        vibe = data.get('description', 'No description available.')
        report.append(f"\n### {data['name']}\n- Vibe: {vibe}\n- Control: {control}% ")

        # Safely build relationships string
        relationships_list = []
        for other_id, status in data.get("relationships", {}).items():
            if other_id in faction_data:
                relationships_list.append(f"{faction_data[other_id]['name']} ({status})")
            else:
                logging.warning(f"Relationship formatting skipped for missing faction ID: {other_id}")
        
        relationships = ", ".join(relationships_list)
        report.append(f"- Relationships: {relationships}")
    return "\n".join(report)

def _format_narrative_history(game_state):
    """Formats the completed quest log into a string for the LLM."""
    quest_log = getattr(game_state, 'quest_log', [])
    
    # In a live game, the quest log might be empty, so we load from file.
    if not quest_log and os.path.exists("temp/quest_log.json"):
        with open("temp/quest_log.json", "r") as f:
            try:
                quest_log = json.load(f)
            except (json.JSONDecodeError, IndexError):
                quest_log = []

    if not quest_log:
        return "Player has not completed any quests yet."

    history = [f"- \"{item['name']}\"" for item in quest_log[-5:]]
    
    return (
        f"Player has completed {len(quest_log)} quests.\n"
        f"Recent history:\n"
        + "\n".join(history)
    )

def _format_world_details(world_details, player_grid_x=None, player_grid_y=None, nearby_radius=3):
    """Formats the world details (cities, roads, landmarks) into a string.

    When player position is provided, cities and landmarks are categorized as
    'Nearby' (within nearby_radius grid cells) or omitted for objectives.
    """
    if not world_details:
        return "No specific world details available."

    from ..data.game_constants import CITY_SPACING

    details = []
    if "cities" in world_details and world_details["cities"]:
        nearby_cities = []
        distant_cities = []
        for key, name in world_details["cities"].items():
            try:
                gx_str, gy_str = key.split(",")
                gx, gy = int(gx_str), int(gy_str)
            except ValueError:
                nearby_cities.append(name)
                continue
            if player_grid_x is not None and player_grid_y is not None:
                dist = max(abs(gx - player_grid_x), abs(gy - player_grid_y))
                if dist <= nearby_radius:
                    nearby_cities.append(name)
                else:
                    distant_cities.append(name)
            else:
                nearby_cities.append(name)

        if nearby_cities:
            details.append("Nearby Cities (use these for delivery/defend objectives):")
            for name in nearby_cities:
                details.append(f"- {name}")
        if distant_cities:
            details.append(f"\nDistant Cities ({len(distant_cities)} others, too far for quest objectives)")

    if "roads" in world_details and world_details["roads"]:
        details.append("\nMajor Roads:")
        for road in world_details["roads"]:
            details.append(f"- {road.get('name', 'Unnamed Road')}")

    if "landmarks" in world_details and world_details["landmarks"]:
        nearby_landmarks = []
        for landmark in world_details["landmarks"]:
            lx = landmark.get("x", 0)
            ly = landmark.get("y", 0)
            if player_grid_x is not None and player_grid_y is not None:
                dist = ((lx - player_grid_x * CITY_SPACING)**2 + (ly - player_grid_y * CITY_SPACING)**2)**0.5
                if dist <= nearby_radius * CITY_SPACING:
                    nearby_landmarks.append(landmark.get("name", "Unnamed Landmark"))
            else:
                nearby_landmarks.append(landmark.get("name", "Unnamed Landmark"))
        if nearby_landmarks:
            details.append("\nNearby Landmarks (use these for defend objectives):")
            for name in nearby_landmarks:
                details.append(f"- {name}")

    return "\n".join(details)


def _get_vehicle_list():
    """Returns a formatted string of available vehicles for prompts."""
    return ", ".join([vehicle.__name__ for vehicle in ALL_VEHICLES])

def build_quest_prompt(game_state, quest_giver_faction_id, faction_data_override=None):
    """
    Builds the complete, dynamic prompt for quest generation.
    Uses faction_data_override if provided, otherwise falls back to the game_state.
    """
    faction_data = faction_data_override if faction_data_override is not None else game_state.factions
    theme = getattr(game_state, 'theme', {'name': 'Default', 'description': 'A standard wasteland adventure.'})
    
    # --- Build Quest Context ---
    quest_giver_faction = faction_data[quest_giver_faction_id]
    quest_context = (
        f"You are generating a quest for the city of '{quest_giver_faction['name']}'.\n"
        f"This city is controlled by the '{quest_giver_faction['name']}' faction.\n"
        f"Their vibe is: {quest_giver_faction.get('description', 'N/A')}"
    )

    with open("prompts/game_context.txt", "r") as f:
        game_summary = f.read()
        # Replace placeholders within game_summary itself
        game_summary = game_summary.replace("{{ enemy_vehicle_list }}", ", ".join(get_enemy_vehicle_list()))
        game_summary = game_summary.replace("{{ character_list }}", ", ".join(get_character_list()))
        game_summary = game_summary.replace("{{ obstacle_list }}", ", ".join(get_obstacle_list()))
        
    player_state = _format_player_state(game_state)
    world_state = _format_world_state(faction_data, game_state)
    narrative_history = _format_narrative_history(game_state)

    # Compute player grid position for nearby filtering
    from ..data.game_constants import CITY_SPACING
    player_grid_x = round(getattr(game_state, 'car_world_x', 0) / CITY_SPACING)
    player_grid_y = round(getattr(game_state, 'car_world_y', 0) / CITY_SPACING)
    world_details_str = _format_world_details(
        getattr(game_state, 'world_details', {}),
        player_grid_x=player_grid_x,
        player_grid_y=player_grid_y,
    )
    theme_str = f"The current theme is '{theme['name']}': {theme['description']}"
    
    with open("prompts/quest_prompt.txt", "r") as f:
        prompt_template = f.read()
        
    prompt = prompt_template.replace("{{ game_summary }}", game_summary)
    prompt = prompt.replace("{{ story_intro }}", game_state.story_intro)
    prompt = prompt.replace("{{ player_state }}", player_state)
    prompt = prompt.replace("{{ world_state }}", world_state)
    prompt = prompt.replace("{{ world_details }}", world_details_str)
    prompt = prompt.replace("{{ narrative_history }}", narrative_history)
    prompt = prompt.replace("{{ theme }}", theme_str)
    prompt = prompt.replace("{{ quest_context }}", quest_context)
    # These are now handled within game_summary, but we keep them for safety if quest_prompt.txt uses them directly
    prompt = prompt.replace("{{ enemy_vehicle_list }}", ", ".join(get_enemy_vehicle_list()))
    prompt = prompt.replace("{{ character_list }}", ", ".join(get_character_list()))
    prompt = prompt.replace("{{ obstacle_list }}", ", ".join(get_obstacle_list()))
    
    logging.info(f"--- BUILT QUEST PROMPT FOR {quest_giver_faction['name']} ---")
    return prompt

def build_faction_prompt(theme: dict):
    """Builds the complete, dynamic prompt for faction generation."""
    from .llm_vehicle_namer import VEHICLE_ROLES

    with open("prompts/game_context.txt", "r") as f:
        game_context = f.read()
        game_context = game_context.replace("{{ enemy_vehicle_list }}", ", ".join(get_enemy_vehicle_list()))
        game_context = game_context.replace("{{ character_list }}", ", ".join(get_character_list()))
        game_context = game_context.replace("{{ obstacle_list }}", ", ".join(get_obstacle_list()))

    with open("prompts/faction_generation_prompt.txt", "r") as f:
        prompt_template = f.read()

    vehicle_roles_str = "\n".join(
        f"- **{vid}**: {role}" for vid, role in VEHICLE_ROLES.items()
    )

    theme_str = f"The chosen theme for this world is '{theme['name']}': {theme['description']}"
    prompt = prompt_template.replace("{{ game_context }}", game_context)
    prompt = prompt.replace("{{ vehicle_list }}", _get_vehicle_list())
    prompt = prompt.replace("{{ vehicle_roles }}", vehicle_roles_str)
    prompt = prompt.replace("{{ theme }}", theme_str)
    prompt = prompt.replace("{{ enemy_vehicle_list }}", ", ".join(get_enemy_vehicle_list()))
    prompt = prompt.replace("{{ character_list }}", ", ".join(get_character_list()))
    prompt = prompt.replace("{{ obstacle_list }}", ", ".join(get_obstacle_list()))

    logging.info(f"--- BUILT FACTION PROMPT FOR THEME {theme['name']} ---")
    return prompt

def build_city_hall_dialog_prompt(theme: dict, faction_name: str, faction_vibe: str, player_reputation: int):
    """Builds the prompt for generating city hall dialog."""
    with open("prompts/city_hall_dialog_prompt.txt", "r") as f:
        prompt_template = f.read()
    
    theme_str = f"The chosen theme for this world is '{theme['name']}': {theme['description']}"
    prompt = prompt_template.replace("{{ theme }}", theme_str)
    prompt = prompt.replace("{{ faction_name }}", faction_name)
    prompt = prompt.replace("{{ faction_vibe }}", faction_vibe)
    prompt = prompt.replace("{{ player_reputation }}", str(player_reputation))
    
    logging.info(f"--- BUILT CITY HALL DIALOG PROMPT FOR {faction_name} ---")
    return prompt

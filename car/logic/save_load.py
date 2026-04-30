import os
import shutil
import json
import logging
from ..game_state import GameState

SAVES_DIR = "saves"
TEMP_DIR = "temp"
GAME_STATE_FILE = "game_state.json"
FACTIONS_FILE = "factions.py"
QUEST_LOG_FILE = "quest_log.json"
WORLD_DETAILS_FILE = "world_details.json"
TRIGGERS_FILE = "triggers.json"

def get_save_slots():
    """Returns a list of available save slot names (which are directories)."""
    if not os.path.exists(SAVES_DIR):
        os.makedirs(SAVES_DIR)
        return []
    return sorted([d for d in os.listdir(SAVES_DIR) if os.path.isdir(os.path.join(SAVES_DIR, d))])

def save_game(game_state, save_name):
    """
    Saves the current game session to a named save slot directory.
    This copies all critical session files from temp/ into the save slot.
    """
    if not save_name or not save_name.strip():
        logging.error("Save failed: Save name cannot be empty.")
        return
        
    logging.info(f"Attempting to save game to slot: {save_name}")
    save_slot_dir = os.path.join(SAVES_DIR, save_name)
    
    # Create the save slot directory, overwriting if it exists
    if os.path.exists(save_slot_dir):
        shutil.rmtree(save_slot_dir)
    os.makedirs(save_slot_dir)

    # --- 1. Save the core GameState object ---
    game_state_dict = game_state.to_dict()
    with open(os.path.join(save_slot_dir, GAME_STATE_FILE), "w") as f:
        json.dump(game_state_dict, f, indent=4)
    logging.info(f"Saved game_state.json to {save_slot_dir}")

    # --- 2. Copy dynamic world files from temp to the save slot ---
    files_to_copy = [FACTIONS_FILE, QUEST_LOG_FILE, WORLD_DETAILS_FILE]
    for filename in files_to_copy:
        temp_path = os.path.join(TEMP_DIR, filename)
        if os.path.exists(temp_path):
            shutil.copy(temp_path, save_slot_dir)
            logging.info(f"Copied {filename} to {save_slot_dir}")
        else:
            logging.warning(f"Could not find {filename} in temp/ to save.")

def load_game(save_name):
    """
    Loads a game session from a named save slot.
    This clears the temp/ directory and copies all files from the save slot into it.
    """
    logging.info(f"Attempting to load game from slot: {save_name}")
    save_slot_dir = os.path.join(SAVES_DIR, save_name)
    if not os.path.exists(save_slot_dir):
        logging.error(f"Save slot not found: {save_slot_dir}")
        return None

    # --- 1. Clear the temp directory ---
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    logging.info(f"Cleared and recreated {TEMP_DIR}")

    # --- 2. Copy all files from the save slot to temp ---
    for item in os.listdir(save_slot_dir):
        source_path = os.path.join(save_slot_dir, item)
        dest_path = os.path.join(TEMP_DIR, item)
        if os.path.isfile(source_path):
            shutil.copy2(source_path, dest_path)
    logging.info(f"Copied all files from {save_slot_dir} to {TEMP_DIR}")
            
    # --- 3. Reload cached data so every module sees the restored files ---
    from .data_loader import reload_all
    reload_all()

    # --- 4. Load the GameState object from the new temp file ---
    game_state_path = os.path.join(TEMP_DIR, GAME_STATE_FILE)
    if not os.path.exists(game_state_path):
        logging.error(f"game_state.json not found in save slot: {save_name}")
        return None

    with open(game_state_path, "r") as f:
        game_state_dict = json.load(f)

    # The GameState's from_dict method will handle loading the factions
    # via the data_loader, which now correctly points to temp/
    logging.info("Loading GameState from dictionary...")
    game_state = GameState.from_dict(game_state_dict)
    if game_state:
        load_triggers(game_state)
    return game_state

def load_triggers(game_state):
    """Loads world triggers from the temp file into the game state."""
    triggers_path = os.path.join(TEMP_DIR, TRIGGERS_FILE)
    if os.path.exists(triggers_path):
        try:
            with open(triggers_path, 'r') as f:
                game_state.world_triggers = json.load(f)
            logging.info(f"Loaded {len(game_state.world_triggers)} world triggers.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to load or parse {TRIGGERS_FILE}: {e}")
            game_state.world_triggers = []
    else:
        logging.info(f"{TRIGGERS_FILE} not found in temp directory. No triggers loaded.")
        game_state.world_triggers = []

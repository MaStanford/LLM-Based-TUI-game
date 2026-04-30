import json
import os
import logging

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "generation_mode": "local",  # "local" or "gemini_cli"
    "model_size": "small",       # "small" (Qwen3-4B) or "large" (Qwen3-8B), used when generation_mode == "local"
    "cli_preset": "gemini",      # "gemini", "claude", or "custom" — which CLI tool to use when generation_mode == "gemini_cli"
    "custom_cli_command": "",    # command name for custom preset (e.g. "ollama")
    "custom_cli_args": "",       # extra args for custom preset (e.g. "run llama3 -p")
    "dev_mode": False,
    "dev_quick_start": False,    # skip LLM generation and use fallback data for instant game start
    "sfx_enabled": True          # enable terminal bell sound effects
}

def save_settings(settings: dict):
    """Saves the settings dictionary to the JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except IOError as e:
        logging.error(f"Error saving settings to {SETTINGS_FILE}: {e}")

def load_settings() -> dict:
    """Loads the settings dictionary from the JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # Ensure all default keys are present
            for key, value in DEFAULT_SETTINGS.items():
                settings.setdefault(key, value)
            return settings
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading settings from {SETTINGS_FILE}: {e}. Using default settings.")
        return DEFAULT_SETTINGS

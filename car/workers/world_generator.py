import logging
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace
from typing import Any, Dict

from ..logic.llm_faction_generator import generate_factions_from_llm, _get_fallback_factions
from ..logic.llm_quest_generator import generate_quest_from_llm, _get_fallback_quest
from ..logic.llm_world_details_generator import generate_world_details_from_llm
from ..logic.prompt_builder import _format_world_state
from ..logic.llm_inference import generate_text


def _generate_story_intro(app, theme, factions, neutral_faction_name):
    """Generates the introductory story text."""
    logging.info("Generating story intro...")
    mock_game_state = SimpleNamespace(faction_control={})
    world_state = _format_world_state(factions, mock_game_state)

    with open("prompts/story_intro_prompt.txt", "r") as f:
        prompt = f.read()

    prompt = prompt.replace("{{ theme }}", f"'{theme['name']}': {theme['description']}")
    prompt = prompt.replace("{{ world_state }}", world_state)
    prompt = prompt.replace("{{ neutral_city_name }}", neutral_faction_name)

    response = generate_text(app, prompt, max_tokens=512, temperature=0.8)
    if response:
        return response
    return "You arrive at the neutral city of The Junction, a beacon of tense neutrality in a world torn apart by warring factions. Your goal is simple: find the Genesis Module and escape. The road will be long and dangerous. Good luck."


def _generate_victory_story(app, theme, factions, neutral_faction_name):
    """Generates the victory narration shown when the player escapes."""
    logging.info("Generating victory story...")
    mock_game_state = SimpleNamespace(faction_control={})
    world_state = _format_world_state(factions, mock_game_state)

    faction_names = [data["name"] for data in factions.values() if data.get("faction_boss")]

    prompt = (
        "You are a master storyteller crafting the VICTORY ENDING for the post-apocalyptic RPG 'Car.'\n\n"
        f"# CONTEXT\n"
        f"- **Theme:** '{theme['name']}': {theme['description']}\n"
        f"- **Factions the player destroyed:** {', '.join(faction_names)}\n"
        f"- **Neutral city:** {neutral_faction_name}\n"
        f"- **What happened:** The player destroyed every faction's leader, then defeated "
        f"the Genesis Engine — an ancient war machine — in the neutral city. They claimed the "
        f"Genesis Module and drove through a rift at the edge of the wasteland to escape.\n\n"
        "# INSTRUCTIONS\n"
        "Write a short, triumphant ending narration (2-3 paragraphs) in a style that fits the theme.\n"
        "Reflect on the journey, the factions that fell, and the player's escape.\n"
        "End with a sense of bittersweet freedom — the wasteland is behind them, but it shaped them.\n"
        "Output *only* the text of the narration. No markdown, no explanation."
    )

    response = generate_text(app, prompt, max_tokens=512, temperature=0.8)
    if response:
        return response
    return (
        f"The factions are dust. {neutral_faction_name} stands empty. "
        "You drive through the rift, leaving the wasteland behind forever. "
        "The road ahead is unknown, but it is yours."
    )


def _update_stage(app: Any, text: str) -> None:
    """Safely update the WorldBuildingScreen title from a worker thread."""
    try:
        from ..screens.world_building import WorldBuildingScreen
        screen = app.screen
        if isinstance(screen, WorldBuildingScreen):
            app.call_from_thread(
                screen.query_one("#title").update,
                f"[bold]{text}[/bold]",
            )
    except Exception:
        pass


def generate_initial_world_worker(app: Any, new_game_settings: dict) -> Dict:
    """
    A worker that generates the complete initial state for a new world.

    Flow:
      1. Generate factions (includes vehicle names) — sequential, everything depends on this
      2. Generate world details, quests, and story intro — all in parallel
    """
    logging.info("Initial world generation worker started.")
    start_time = time.time()
    used_fallback = False

    try:
        theme = new_game_settings["theme"]
        logging.info(f"Generating world with theme: {theme['name']}")

        # --- Stage 1: Generate Factions (sequential — everything else depends on this) ---
        _update_stage(app, "Forging factions and their war machines...")
        factions, factions_fallback = generate_factions_from_llm(app, theme)
        if factions_fallback:
            used_fallback = True

        if not factions or (isinstance(factions, dict) and "error" in factions):
            raise ValueError(f"Faction generation failed: {factions.get('details', 'No details') if isinstance(factions, dict) else 'No data'}")

        neutral_faction_id = next((fid for fid, data in factions.items() if data.get("hub_city_coordinates") in ([0, 0], (0, 0))), None)
        if not neutral_faction_id:
            raise ValueError("Could not find a neutral faction at (0,0) in the generated data.")
        neutral_faction_name = factions[neutral_faction_id]['name']

        logging.info(f"Factions ready ({time.time() - start_time:.1f}s). Starting parallel generation...")
        _update_stage(app, "Building the world in parallel...")

        # --- Stage 2: Everything else in parallel ---
        mock_game_state = SimpleNamespace(
            faction_reputation={}, faction_control={}, quest_log=[],
            difficulty_mods=new_game_settings["difficulty_mods"], theme=theme,
            story_intro="The story is just beginning..."
        )

        world_details = None
        initial_quests = []
        story_intro = None
        victory_story = None

        with ThreadPoolExecutor(max_workers=6) as pool:
            future_world = pool.submit(
                generate_world_details_from_llm, app, theme, factions
            )
            future_story = pool.submit(
                _generate_story_intro, app, theme, factions, neutral_faction_name
            )
            future_victory = pool.submit(
                _generate_victory_story, app, theme, factions, neutral_faction_name
            )
            quest_futures = [
                pool.submit(
                    generate_quest_from_llm,
                    game_state=mock_game_state,
                    quest_giver_faction_id=neutral_faction_id,
                    app=app,
                    faction_data=factions,
                )
                for _ in range(3)
            ]

            world_details = future_world.result()
            story_intro = future_story.result()
            victory_story = future_victory.result()
            for qf in quest_futures:
                quest = qf.result()
                if quest:
                    initial_quests.append(quest)

        end_time = time.time()
        logging.info(f"Initial world generation finished successfully in {end_time - start_time:.2f} seconds.")

        return {
            "factions": factions,
            "quests": initial_quests,
            "neutral_city_id": neutral_faction_id,
            "story_intro": story_intro,
            "victory_story": victory_story,
            "world_details": world_details,
            "used_fallback": used_fallback,
        }

    except Exception as e:
        end_time = time.time()
        logging.error(f"Initial world generation worker failed after {end_time - start_time:.2f} seconds: {e}", exc_info=True)
        return {"error": str(e)}

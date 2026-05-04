import logging
import time
from functools import partial
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static, Header, Footer, ProgressBar
from textual.binding import Binding
from textual.worker import Worker, WorkerState

from ..game_state import GameState
from ..world import World
from ..workers.world_generator import generate_initial_world_worker
from ..data.difficulty import DIFFICULTY_MODIFIERS
from ..animations.reveal_animation import RevealAnimation

class WorldBuildingScreen(Screen):
    """A screen that shows the progress of the world being built, with flair."""

    BINDINGS = [
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
        Binding("enter", "select_button", "Select", show=True),
    ]

    def __init__(self, new_game_settings: dict) -> None:
        super().__init__()
        self.new_game_settings = new_game_settings
        self.world_data = None
        self.focusable_widgets = []
        self.current_focus_index = 0
        self.status_messages = [
            "Calibrating wasteland frequencies...",
            "Reticulating splines...",
            "Generating continental plates...",
            "Simulating tectonic shifts...",
            "Spooling up the reality matrix...",
            "Calculating factional friction...",
            "Plotting ley lines...",
            "Seeding initial conflicts...",
            "Negotiating with rogue AIs...",
            "Polishing chrome skulls...",
            "Untangling quantum supply lines...",
            "Drawing new world map... (This may take a few minutes)",
            "Finalizing timeline...",
        ]
        self.current_message_index = 0
        self.reveal_anim = RevealAnimation()
        self._status_timer = None
        self._animation_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="world-building-container"):
            yield Static(id="animation_display", classes="world-building-animation")
            yield Static("", id="title") # Title will be set dynamically
            yield ProgressBar(id="progress", total=None, show_percentage=False, show_eta=False)
            yield Static(self.status_messages[0], id="status_message")
        yield Footer()

    def on_mount(self) -> None:
        """Start the world generation process."""
        # Set the dynamic title
        theme_name = self.new_game_settings.get("theme", {}).get("name", "the Wasteland")
        self.query_one("#title", Static).update(f"[bold]Bringing '{theme_name}' to Life...[/bold]\nThis may take a few minutes.")

        self._status_timer = self.set_interval(2.5, self.update_status_message)
        self._animation_timer = self.set_interval(0.05, self.update_animation)

        # Start the world generation worker
        self.run_worker(
            partial(generate_initial_world_worker, self.app, self.new_game_settings),
            exclusive=True,
            thread=True,
            name="WorldGenerator"
        )

    def update_status_message(self) -> None:
        """Cycle through the status messages."""
        self.current_message_index = (self.current_message_index + 1) % len(self.status_messages)
        self.query_one("#status_message", Static).update(self.status_messages[self.current_message_index])

    def update_animation(self) -> None:
        """Update the reveal-crystallization animation."""
        animation_widget = self.query_one("#animation_display")
        animation_widget.update(self.reveal_anim.tick())

    def _get_cli_test_hint(self) -> str:
        """Returns a helpful hint for testing the CLI LLM tool."""
        if self.app.generation_mode == "gemini_cli":
            preset = getattr(self.app, 'cli_preset', 'gemini')
            if preset == "claude":
                return '\nTest your Claude CLI with: [bold]claude -p "say hi"[/bold]'
            elif preset == "gemini":
                return '\nTest your Gemini CLI with: [bold]gemini "say hi"[/bold]'
            else:
                return "\nCheck that your custom CLI tool is installed and working."
        return ""

    def _stop_timers(self) -> None:
        """Stop the cycling status and animation timers."""
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer = None
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = None

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        if event.worker.name == "WorldGenerator":
            if event.worker.state in (WorkerState.SUCCESS, WorkerState.ERROR):
                self._stop_timers()
            if event.worker.state == WorkerState.SUCCESS:
                self.world_data = event.worker.result
                if self.world_data:
                    if self.world_data.get("error"):
                        error_detail = self.world_data["error"]
                        logging.error(f"World generation returned error: {error_detail}")
                        cli_hint = self._get_cli_test_hint()
                        self.query_one("#status_message").update(
                            f"[bold red]Error: {error_detail}[/bold red]\n"
                            f"Check Settings > Generation Mode and ensure your LLM is configured.{cli_hint}"
                        )
                        self.query_one(ProgressBar).display = False
                        self.query_one("#world-building-container").mount(Button("Retry", id="retry", variant="error"))
                        self._refresh_focusable_widgets()
                    elif self.world_data.get("used_fallback"):
                        logging.warning("World generation used fallback data — LLM was unavailable.")
                        cli_hint = self._get_cli_test_hint()
                        self.query_one("#status_message").update(
                            "[bold yellow]Warning: LLM unavailable — using default world data.[/bold yellow]\n"
                            f"Check Settings > Generation Mode and ensure your LLM is configured.{cli_hint}\n"
                            "Press Retry to try again, or Continue to play with defaults."
                        )
                        self.query_one(ProgressBar).display = False
                        self.query_one("#world-building-container").mount(
                            Button("Continue Anyway", id="continue_fallback", variant="warning")
                        )
                        self.query_one("#world-building-container").mount(
                            Button("Retry", id="retry", variant="error")
                        )
                        self._refresh_focusable_widgets()
                    else:
                        logging.info("World generation successful. Starting game.")
                        self.start_game()
                else:
                    logging.error("World generation failed: No data returned.")
                    cli_hint = self._get_cli_test_hint()
                    self.query_one("#status_message").update(
                        "[bold red]Error: LLM returned no data.[/bold red]\n"
                        f"Check Settings > Generation Mode and ensure your LLM is configured.{cli_hint}"
                    )
                    self.query_one(ProgressBar).display = False
                    self.query_one("#world-building-container").mount(Button("Retry", id="retry", variant="error"))
                    self._refresh_focusable_widgets()
            elif event.worker.state == WorkerState.ERROR:
                error_message = str(event.worker.error)
                logging.error(f"World generator worker failed: {error_message}")
                cli_hint = self._get_cli_test_hint()
                self.query_one("#status_message").update(
                    f"[bold red]Error: {error_message}[/bold red]\n"
                    f"Check Settings > Generation Mode and ensure your LLM is configured.{cli_hint}"
                )
                self.query_one(ProgressBar).display = False
                self.query_one("#world-building-container").mount(Button("Retry", id="retry", variant="error"))
                self._refresh_focusable_widgets()

    def _refresh_focusable_widgets(self) -> None:
        """Rebuild the focusable widget list after buttons change."""
        self.focusable_widgets = list(self.query("Button"))
        self.current_focus_index = 0
        self._update_focus()

    def _update_focus(self) -> None:
        """Update which widget has focus."""
        if self.focusable_widgets:
            self.focusable_widgets[self.current_focus_index].focus()

    def action_focus_previous(self) -> None:
        """Focus the previous widget."""
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index - 1 + len(self.focusable_widgets)) % len(self.focusable_widgets)
            self._update_focus()

    def action_focus_next(self) -> None:
        """Focus the next widget."""
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index + 1) % len(self.focusable_widgets)
            self._update_focus()

    def action_select_button(self) -> None:
        """Press the focused button."""
        if self.focusable_widgets:
            self.focusable_widgets[self.current_focus_index].press()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle retry or continue button press."""
        if event.button.id == "retry":
            # Remove all dynamic buttons
            for btn in self.query("#retry, #continue_fallback"):
                btn.remove()
            self.focusable_widgets = []
            self.query_one(ProgressBar).display = True
            self.query_one("#status_message").update(self.status_messages[0])
            self.on_mount()
        elif event.button.id == "continue_fallback":
            logging.info("User chose to continue with fallback data.")
            self.start_game()

    def start_game(self) -> None:
        """Finalizes game state and switches to the intro cutscene."""
        from .intro_cutscene import IntroCutsceneScreen
        from ..logic.save_load import load_triggers
        import os
        import shutil
        import pprint
        import json

        # Save the new faction data (convert world coords to grid coords)
        if os.path.exists("temp"):
            shutil.rmtree("temp")
        os.makedirs("temp")
        from ..data.game_constants import CITY_SPACING
        factions_to_save = self.world_data["factions"]
        for fdata in factions_to_save.values():
            coords = fdata.get("hub_city_coordinates")
            if coords:
                x, y = coords
                if abs(x) > 50 or abs(y) > 50:
                    fdata["hub_city_coordinates"] = (round(x / CITY_SPACING), round(y / CITY_SPACING))
                else:
                    fdata["hub_city_coordinates"] = (x, y)
        with open("temp/factions.py", "w") as f:
            f.write("FACTION_DATA = ")
            pprint.pprint(factions_to_save, stream=f, indent=4)
            
        # Save the new world details
        with open("temp/world_details.json", "w") as f:
            json.dump(self.world_data["world_details"], f, indent=4)

        # CRITICAL: Reload the data modules to load the new factions
        self.app.reload_dynamic_data()

        difficulty = self.new_game_settings["difficulty"]
        
        # Create the game state
        game_state = GameState(
            selected_car_index=self.new_game_settings["selected_car_index"],
            difficulty=difficulty,
            difficulty_mods=self.new_game_settings["difficulty_mods"],
            car_color_names=[self.new_game_settings["car_color_name"]],
            theme=self.new_game_settings["theme"],
            factions=self.world_data["factions"],
        )
        game_state.world_details = self.world_data["world_details"]
        
        game_state.story_intro = self.world_data["story_intro"]
        game_state.victory_story = self.world_data.get("victory_story", "")
        
        # Pre-populate the quest cache
        neutral_city_id = self.world_data["neutral_city_id"]
        game_state.quest_cache[neutral_city_id] = self.world_data["quests"]
        
        # Load triggers
        load_triggers(game_state)
        
        # Set player position
        # Find a safe spawn point in the starting city (0, 0)
        from ..world.generation import get_buildings_in_city, find_safe_spawn_point
        
        buildings = get_buildings_in_city(0, 0)
        # Try to spawn near the center but safe
        start_x, start_y = 0.0, 0.0
        safe_x, safe_y = find_safe_spawn_point(start_x, start_y, buildings, game_state.player_car, max_radius=100)
        
        game_state.car_world_x = safe_x
        game_state.car_world_y = safe_y
        game_state.player_car.x = game_state.car_world_x
        game_state.player_car.y = game_state.car_world_y
        
        self.app.game_state = game_state
        self.app.world = World(seed=int(time.time()))
        self.app.world.game_state = game_state
        self.app.switch_screen(IntroCutsceneScreen(self.world_data["story_intro"]))

import math
import logging
from functools import partial
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, Button, ProgressBar
from textual.containers import Grid, Vertical
from textual.binding import Binding
from textual.message import Message
from ..widgets.dialog import Dialog
from ..logic.quest_logic import handle_quest_acceptance, complete_quest
from ..logic.llm_quest_generator import generate_quest_from_llm
from ..logic.faction_logic import get_conquest_quest
from ..logic.boss import check_challenge_conditions, spawn_faction_boss
from ..data.game_constants import CITY_SPACING
from ..world.generation import get_city_faction, get_buildings_in_city, find_safe_spawn_point
from ..workers.city_hall_dialog_generator import generate_dialog_worker
from ..workers.quest_generator import generate_quests_worker
from textual.worker import Worker, WorkerState

# Atmospheric loading messages shown while quests generate
_MAYOR_MESSAGES = [
    "The mayor shuffles through a stack of papers...",
    "He adjusts his glasses and squints at a document...",
    "He pulls out a worn ledger from under the desk...",
    "He mutters something about bandits this season...",
    "He stamps a requisition form with a heavy sigh...",
    "He flips through reports from the local patrols...",
    "He circles a few entries with a red pen...",
    "'Just a moment,' he says without looking up...",
    "He cross-references a map tacked to the wall...",
    "He finally closes the ledger and meets your eyes...",
]

class QuestsLoaded(Message):
    """A message to indicate that quests have been loaded."""
    def __init__(self, quests: list) -> None:
        self.quests = quests
        super().__init__()

class CityHallScreen(ModalScreen):
    """The city hall screen for accepting and turning in quests."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("up", "move_selection(-1)", "Up", show=False),
        Binding("down", "move_selection(1)", "Down", show=False),
        Binding("enter", "accept_quest", "Select", show=True),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.available_quests = []
        self.turnable_quests = []  # Quests ready to turn in at this city
        self.selected_index = 0
        self.can_challenge = False
        self.current_city_faction = None
        self.current_city_id = None
        self._loading_msg_index = 0
        self._loading_timer = None

    def _total_items(self):
        """Total selectable items: turn-ins + available quests."""
        return len(self.turnable_quests) + len(self.available_quests)

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        gs = self.app.game_state
        grid_x = round(gs.car_world_x / CITY_SPACING)
        grid_y = round(gs.car_world_y / CITY_SPACING)
        self.current_city_id = f"city_{grid_x}_{grid_y}"
        self.current_city_faction = get_city_faction(gs.car_world_x, gs.car_world_y, gs.factions)

        logging.info(f"CityHallScreen mounted for city: {self.current_city_id}")

        # Find quests ready to turn in at this city
        turn_in_city_tuple = (grid_x, grid_y)
        self.turnable_quests = [
            q for q in gs.active_quests
            if q.ready_to_turn_in and q.city_id == turn_in_city_tuple
        ]

        # Load available quests if player has room
        if len(gs.active_quests) < 3:
            cached_quests = gs.quest_cache.get(self.current_city_id)
            if cached_quests is None:
                logging.info("No quests in cache. Generating new quests.")
                self.generate_quests()
            elif cached_quests == "pending":
                logging.info("Quests are currently being generated.")
            else:
                logging.info(f"Found {len(cached_quests)} quests in cache.")
                self.available_quests = cached_quests

        self.can_challenge = check_challenge_conditions(gs, self.current_city_faction, gs.factions)

        self._loading_timer = self.set_interval(2.5, self._cycle_loading_message)
        self.update_quest_display()
        self.generate_dialog()

    def generate_quests(self):
        """Launch a quest generation worker for the current city."""
        gs = self.app.game_state
        gs.quest_cache[self.current_city_id] = "pending"

        worker_callable = partial(
            generate_quests_worker,
            app=self.app,
            city_id=self.current_city_id,
            city_faction_id=self.current_city_faction,
            theme=gs.theme,
            faction_data=gs.factions,
            story_intro=gs.story_intro,
        )

        worker = self.run_worker(
            worker_callable,
            exclusive=False,
            thread=True,
            name=f"QuestGenerator_{self.current_city_id}",
            group="quest_generation",
        )
        worker.city_id = self.current_city_id

    def _cycle_loading_message(self) -> None:
        """Cycle through atmospheric loading messages while quests generate."""
        loading = self.query_one("#loading_container")
        if loading.display:
            self._loading_msg_index = (self._loading_msg_index + 1) % len(_MAYOR_MESSAGES)
            self.query_one("#loading_label").update(_MAYOR_MESSAGES[self._loading_msg_index])

    def on_quests_loaded(self, message: QuestsLoaded) -> None:
        """Handle the QuestsLoaded message."""
        logging.info(f"CityHallScreen received QuestsLoaded message with {len(message.quests)} quests.")
        self.available_quests = message.quests or []
        self.update_quest_display()

    def generate_dialog(self):
        """Starts a worker to generate shopkeeper dialog."""
        gs = self.app.game_state
        faction_info = gs.factions.get(self.current_city_faction, {})
        faction_name = faction_info.get("name", "The Wasteland")
        faction_vibe = faction_info.get("description", "A desolate, lawless place.")
        player_rep = gs.faction_reputation.get(self.current_city_faction, 0)

        worker_callable = partial(
            generate_dialog_worker,
            app=self.app,
            theme=gs.theme,
            faction_name=faction_name,
            faction_vibe=faction_vibe,
            player_reputation=player_rep
        )
        self.run_worker(worker_callable, exclusive=True, name="CityHallDialogGenerator",
                        thread=True, group="dialog_generation")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle completed dialog worker."""
        logging.info(f"Worker {event.worker.name} changed state to {event.worker.state}")
        if event.worker.name == "CityHallDialogGenerator":
            if event.worker.state == WorkerState.SUCCESS:
                dialog = event.worker.result
                self.query_one(Dialog).update(dialog)
            elif event.worker.state == WorkerState.ERROR:
                logging.error(f"CityHallDialogGenerator worker failed: {event.worker.error}")
        elif event.worker.name.startswith("QuestGenerator"):
            if event.worker.state == WorkerState.SUCCESS:
                quests = event.worker.result
                logging.info(f"QuestGenerator worker succeeded with result: {quests}")
                self.app.game_state.quest_cache[self.current_city_id] = quests or []
                self.post_message(QuestsLoaded(quests or []))
            else:
                logging.error(f"QuestGenerator worker failed with state: {event.worker.state}")
                self.app.game_state.quest_cache.pop(self.current_city_id, None)
                self.post_message(QuestsLoaded([]))

    def on_unmount(self) -> None:
        """Called when the screen is unmounted."""
        if self._loading_timer:
            self._loading_timer.stop()

        gs = self.app.game_state
        gs.menu_open = False

        grid_x = round(gs.car_world_x / CITY_SPACING)
        grid_y = round(gs.car_world_y / CITY_SPACING)
        buildings = get_buildings_in_city(grid_x, grid_y)

        current_building = next((b for b in buildings if b.get("type") == "city_hall"), None)

        if current_building:
            exit_x = current_building['x'] + current_building['w'] / 2
            exit_y = current_building['y'] + current_building['h'] + 2

            safe_x, safe_y = find_safe_spawn_point(exit_x, exit_y, buildings, gs.player_car)

            gs.car_world_x = safe_x
            gs.car_world_y = safe_y
            gs.car_angle = math.pi * 1.5 # Face down (South)
            gs.player_car.x = gs.car_world_x
            gs.player_car.y = gs.car_world_y
            gs.player_car.angle = gs.car_angle

    def update_quest_display(self) -> None:
        """Update the quest display with turn-in and available sections."""
        logging.info(f"Updating quest display. {len(self.turnable_quests)} turn-ins, {len(self.available_quests)} available.")
        challenge_button = self.query_one("#challenge_boss", Button)
        challenge_button.display = self.can_challenge
        loading_container = self.query_one("#loading_container")
        quest_list_widget = self.query_one("#quest_list")
        quest_info_widget = self.query_one("#quest_info", Static)
        accept_button = self.query_one("#accept_quest", Button)

        gs = self.app.game_state
        quest_log_full = len(gs.active_quests) >= 3

        lines = []

        # --- Turn-In Section ---
        if self.turnable_quests:
            lines.append("[bold green]== Turn In ==[/bold green]")
            for i, quest in enumerate(self.turnable_quests):
                prefix = "> " if i == self.selected_index else "  "
                lines.append(f"{prefix}[green]? {quest.name}[/green]")

        # --- Available Contracts Section ---
        cached_quests = gs.quest_cache.get(self.current_city_id)
        is_loading = cached_quests == "pending" and not self.available_quests

        if is_loading and not quest_log_full:
            loading_container.display = True
        else:
            loading_container.display = False

        if quest_log_full and not self.turnable_quests:
            lines.append("\n[dim]Quest log full (3/3). Complete a quest first.[/dim]")
        elif not quest_log_full:
            if self.available_quests:
                lines.append("\n[bold]== Available Contracts ==[/bold]")
                offset = len(self.turnable_quests)
                for i, quest in enumerate(self.available_quests):
                    idx = offset + i
                    prefix = "> " if idx == self.selected_index else "  "
                    lines.append(f"{prefix}{quest.name}")
            elif not is_loading:
                # Only show empty message if generation actually finished
                cached = gs.quest_cache.get(self.current_city_id)
                if isinstance(cached, list):
                    lines.append("\n[dim]The mayor has no contracts right now. Check back later.[/dim]")

        quest_list_widget.display = True
        quest_list_widget.update("\n".join(lines) if lines else "")

        # --- Details pane ---
        total = self._total_items()
        if total > 0 and 0 <= self.selected_index < total:
            if self.selected_index < len(self.turnable_quests):
                selected_quest = self.turnable_quests[self.selected_index]
                quest_info_widget.update(f"[bold]{selected_quest.name}[/bold]\n{selected_quest.description}\n\n[green]Ready to turn in![/green]\nRewards: {selected_quest.rewards.get('xp', 0)} XP, ${selected_quest.rewards.get('cash', 0)}")
                accept_button.label = "Complete Quest"
                accept_button.disabled = False
                if selected_quest.dialog:
                    self.query_one(Dialog).update(selected_quest.dialog)
            else:
                avail_idx = self.selected_index - len(self.turnable_quests)
                if avail_idx < len(self.available_quests):
                    selected_quest = self.available_quests[avail_idx]
                    quest_info_widget.update(f"[bold]{selected_quest.name}[/bold]\n{selected_quest.description}")
                    accept_button.label = "Accept Quest"
                    accept_button.disabled = False
                    if selected_quest.dialog:
                        self.query_one(Dialog).update(selected_quest.dialog)
                else:
                    quest_info_widget.update("")
                    accept_button.disabled = True
        else:
            quest_info_widget.update("")
            accept_button.disabled = True
            accept_button.label = "Accept Quest"

    def on_click(self, event) -> None:
        """Handle clicks on the quest list."""
        try:
            panel = self.query_one("#quest_list")
            if event.widget is panel or panel in event.widget.ancestors_with_self:
                total = self._total_items()
                if total > 0 and 0 <= event.y < total:
                    self.selected_index = event.y
                    self.update_quest_display()
        except Exception:
            pass

    def action_move_selection(self, amount: int) -> None:
        """Move the selection in the quest list."""
        total = self._total_items()
        if total > 0:
            self.selected_index = (self.selected_index + amount + total) % total
            self.update_quest_display()

    def action_accept_quest(self) -> None:
        """Accept the selected quest or complete a turn-in via Enter key."""
        gs = self.app.game_state
        total = self._total_items()
        if total == 0 or self.selected_index >= total:
            return

        if self.selected_index < len(self.turnable_quests):
            # Turn in
            quest = self.turnable_quests[self.selected_index]
            complete_quest(gs, self.app, quest)
            self.turnable_quests.remove(quest)
            self.selected_index = 0
            self.update_quest_display()
            if not self.turnable_quests:
                self.app.pop_screen()
        else:
            # Accept new quest
            avail_idx = self.selected_index - len(self.turnable_quests)
            if avail_idx < len(self.available_quests):
                accept_button = self.query_one("#accept_quest", Button)
                if not accept_button.disabled:
                    selected_quest = self.available_quests[avail_idx]
                    if handle_quest_acceptance(gs, selected_quest):
                        # Remove the accepted quest from the cache list.
                        # available_quests may be the same object as the cache list,
                        # so we only need to remove once.
                        cached = gs.quest_cache.get(self.current_city_id)
                        if isinstance(cached, list) and selected_quest in cached:
                            cached.remove(selected_quest)
                        elif selected_quest in self.available_quests:
                            self.available_quests.remove(selected_quest)
                        self.selected_index = 0
                        self.update_quest_display()
                        # If quest log is now full or no more quests, exit
                        if len(gs.active_quests) >= 3 or not self.available_quests:
                            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle accept button presses."""
        gs = self.app.game_state

        if event.button.id == "challenge_boss":
            spawn_faction_boss(gs, self.current_city_faction)
            self.app.screen.query_one("#notifications").add_notification(f"Challenge issued!")
            self.app.pop_screen()
            return

        if event.button.id == "accept_quest":
            self.action_accept_quest()

    def compose(self):
        """Compose the layout of the screen."""
        yield Header(show_clock=True)
        with Grid(id="city_hall_grid"):
            with Vertical(id="quest_list_container"):
                with Vertical(id="loading_container"):
                    yield ProgressBar(id="quest_progress", total=None, show_percentage=False, show_eta=False)
                    yield Static(_MAYOR_MESSAGES[0], id="loading_label")
                yield Static("Available Contracts", id="quest_list")
            yield Static("Quest Details", id="quest_info")
            yield Dialog("")
            with Vertical():
                yield Button("Accept", id="accept_quest", variant="primary")
                yield Button("Challenge Faction Leader", id="challenge_boss", variant="error")
        yield Footer(show_command_palette=True)

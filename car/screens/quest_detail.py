from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

from ..data.quests import (
    KillBossObjective, KillCountObjective, SurvivalObjective,
    DeliverPackageObjective, DefendLocationObjective, WaveSpawnObjective,
)
from ..logic.quest_logic import get_quest_target_location


def _format_objective(obj):
    """Format a single objective into a human-readable status line."""
    status = "[green]Done[/green]" if obj.completed else "[yellow]Active[/yellow]"
    if isinstance(obj, KillBossObjective):
        return f"  {status}  Defeat {obj.boss_name}"
    elif isinstance(obj, KillCountObjective):
        return f"  {status}  Eliminate targets ({obj.kill_count}/{obj.target_count})"
    elif isinstance(obj, SurvivalObjective):
        remaining = max(0, int(obj.timer))
        active_tag = " [cyan][AT LOCATION][/cyan]" if obj.active else ""
        return f"  {status}  Survive ({remaining}s remaining){active_tag}"
    elif isinstance(obj, DeliverPackageObjective):
        return f"  {status}  Deliver package to {obj.destination}"
    elif isinstance(obj, DefendLocationObjective):
        remaining = max(0, obj.timer // 30)
        return f"  {status}  Defend {obj.location} ({remaining}s remaining)"
    elif isinstance(obj, WaveSpawnObjective):
        if obj.wave_active:
            return f"  {status}  Wave {obj.current_wave}/{obj.total_waves} ({obj.wave_enemies_remaining} enemies left)"
        else:
            return f"  {status}  Clear {obj.total_waves} waves ({obj.enemies_per_wave} enemies each)"
    return f"  {status}  Unknown objective"


class QuestDetailScreen(ModalScreen):
    """A screen to display the details of all active quests."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("up", "switch_quest(-1)", "Prev", show=True),
        Binding("down", "switch_quest(1)", "Next", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._confirm_abandon = False
        self._viewing_index = 0

    def compose(self):
        """Compose the layout of the screen."""
        yield Header(show_clock=True)
        with Vertical(id="quest-detail-container"):
            yield Static(id="quest_list_panel")
            yield Static(id="quest_title", classes="panel-title")
            yield Static(id="quest_description")
            yield Static(id="quest_objectives")
            yield Static(id="quest_rewards")
            with Horizontal(id="quest-buttons"):
                yield Button("Set to Compass", id="set_compass", variant="primary")
                yield Button("Abandon Quest", id="abandon_quest", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        gs = self.app.game_state
        self._viewing_index = gs.selected_quest_index
        if self._viewing_index >= len(gs.active_quests):
            self._viewing_index = 0
        self._update_display()

    def _update_display(self) -> None:
        """Update the display for the currently viewed quest."""
        gs = self.app.game_state
        quests = gs.active_quests

        # --- Vertical quest list ---
        if quests:
            lines = []
            for i, q in enumerate(quests):
                compass_marker = " *" if i == gs.selected_quest_index else ""
                if i == self._viewing_index:
                    lines.append(f"[bold]> {i+1}. {q.name}{compass_marker}[/bold]")
                else:
                    lines.append(f"[dim]  {i+1}. {q.name}{compass_marker}[/dim]")
            lines.append(f"\n[dim]({len(quests)}/3 quests)  * = compass target[/dim]")
            self.query_one("#quest_list_panel", Static).update("\n".join(lines))
        else:
            self.query_one("#quest_list_panel", Static).update("[dim]No active quests[/dim]")

        if not quests or self._viewing_index >= len(quests):
            self.query_one("#quest_title", Static).update("No Active Quest")
            self.query_one("#quest_description", Static).update("")
            self.query_one("#quest_objectives", Static).update("")
            self.query_one("#quest_rewards", Static).update("")
            self.query_one("#set_compass", Button).disabled = True
            self.query_one("#abandon_quest", Button).disabled = True
            return

        quest = quests[self._viewing_index]

        self.query_one("#quest_title", Static).update(f"[bold]{quest.name}[/bold]")
        self.query_one("#quest_description", Static).update(quest.description)

        # Objectives
        obj_lines = ["[bold]Objectives:[/bold]"]
        for obj in quest.objectives:
            obj_lines.append(_format_objective(obj))
        if quest.ready_to_turn_in:
            obj_lines.append("\n  [green]>> Return to city to turn in! <<[/green]")
        self.query_one("#quest_objectives", Static).update("\n".join(obj_lines))

        # Rewards
        rewards_lines = [
            "[bold]Rewards:[/bold]",
            f"  XP: {quest.rewards.get('xp', 0)}",
            f"  Cash: ${quest.rewards.get('cash', 0)}",
        ]
        self.query_one("#quest_rewards", Static).update("\n".join(rewards_lines))

        # Buttons
        qt_x, qt_y, _ = get_quest_target_location(quest, gs)
        self.query_one("#set_compass", Button).disabled = (qt_x is None)
        self.query_one("#abandon_quest", Button).disabled = False
        self.query_one("#abandon_quest", Button).label = "Abandon Quest"
        self._confirm_abandon = False

    def on_click(self, event) -> None:
        """Handle clicks on the quest list panel."""
        try:
            panel = self.query_one("#quest_list_panel")
            if event.widget is panel or panel in event.widget.ancestors_with_self:
                quests = self.app.game_state.active_quests
                if quests and 0 <= event.y < len(quests):
                    self._viewing_index = event.y
                    self._confirm_abandon = False
                    self._update_display()
        except Exception:
            pass

    def action_switch_quest(self, direction: int) -> None:
        """Switch which quest is being viewed."""
        quests = self.app.game_state.active_quests
        if not quests:
            return
        self._viewing_index = (self._viewing_index + direction) % len(quests)
        self._confirm_abandon = False
        self._update_display()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        gs = self.app.game_state
        quests = gs.active_quests

        if not quests or self._viewing_index >= len(quests):
            return

        quest = quests[self._viewing_index]

        if event.button.id == "set_compass":
            qt_x, qt_y, qt_label = get_quest_target_location(quest, gs)
            if qt_x is not None:
                gs.waypoint = {
                    "x": qt_x,
                    "y": qt_y,
                    "name": qt_label or quest.name,
                }
                gs.selected_quest_index = self._viewing_index
                self._notify(f"Compass set to: {qt_label or quest.name}")
                self.app.pop_screen()

        elif event.button.id == "abandon_quest":
            if self._confirm_abandon:
                gs.story_events.append({
                    "text": f"Abandoned '{quest.name}'.",
                    "event_type": "quest_failed",
                })
                # Remove any QuestItems associated with this quest
                from ..data.quests import QuestItem
                gs.player_inventory = [
                    item for item in gs.player_inventory
                    if not (isinstance(item, QuestItem) and item.quest_name == quest.name)
                ]
                gs.active_quests.remove(quest)
                if gs.selected_quest_index >= len(gs.active_quests):
                    gs.selected_quest_index = max(0, len(gs.active_quests) - 1)
                self._viewing_index = min(self._viewing_index, len(gs.active_quests) - 1) if gs.active_quests else 0
                gs.waypoint = None
                self._notify("Quest Abandoned.")
                if not gs.active_quests:
                    self.app.pop_screen()
                else:
                    self._update_display()
            else:
                self._confirm_abandon = True
                event.button.label = "Are you sure? (Press again)"

    def _notify(self, message: str):
        """Post a notification to the WorldScreen."""
        try:
            for screen in self.app.screen_stack:
                try:
                    notif = screen.query_one("#notifications")
                    notif.add_notification(message)
                    return
                except Exception:
                    continue
        except Exception:
            pass

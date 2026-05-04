from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Vertical, Center
from textual.binding import Binding


VICTORY_ART = r"""
    ╔══════════════════════════════════════╗
    ║                                      ║
    ║     ★  Y O U   E S C A P E D  ★     ║
    ║                                      ║
    ║   The Genesis Module tears a hole    ║
    ║   in the fabric of the wasteland.    ║
    ║                                      ║
    ║   You drive through the rift and     ║
    ║   leave this shattered world         ║
    ║   behind forever.                    ║
    ║                                      ║
    ║   The factions are dust.             ║
    ║   The roads are silent.              ║
    ║   You are free.                      ║
    ║                                      ║
    ╚══════════════════════════════════════╝
"""


class VictoryScreen(Screen):
    """The victory screen — the player has escaped the wasteland."""

    BINDINGS = [
        Binding("enter", "continue", "Continue", show=True),
    ]

    def compose(self):
        yield Header(show_clock=False)
        with Center():
            with Vertical(id="victory-container"):
                yield Static(VICTORY_ART, id="victory_art")
                yield Static(id="victory_narrative")
                yield Static(id="victory_stats")
                yield Button("Main Menu", id="main_menu", variant="primary")
                yield Button("Quit", id="quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        gs = self.app.game_state

        narrative = getattr(gs, "victory_story", "") or (
            "The factions are dust. The roads are silent. You are free."
        )
        self.query_one("#victory_narrative", Static).update(
            f"[italic]{narrative}[/italic]"
        )

        stats = (
            f"[bold]Final Stats[/bold]\n"
            f"  Level: {gs.player_level}\n"
            f"  Quests Completed: {gs.quests_completed}\n"
            f"  Factions Destroyed: {len(gs.defeated_bosses)}\n"
            f"  Karma: {gs.karma}\n"
            f"  Cash: ${gs.player_cash:,}\n"
        )
        self.query_one("#victory_stats", Static).update(stats)

    def action_continue(self) -> None:
        self.query_one("#main_menu", Button).press()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from .main_menu import MainMenuScreen
        if event.button.id == "main_menu":
            self.app.stop_game_loop()
            self.app.switch_screen(MainMenuScreen())
        elif event.button.id == "quit":
            self.app.exit()

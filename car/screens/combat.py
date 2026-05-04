import random
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Grid, Vertical, Horizontal
from textual.binding import Binding
from ..logic.combat_logic import get_current_phase, advance_phase, check_combat_end
from ..widgets.minigames import MinigameResult


class CombatScreen(ModalScreen):
    """Boss combat screen with rotating mini-game phases."""

    BINDINGS = [
        Binding("escape", "attempt_flee", "Flee", show=True),
    ]

    def __init__(self, player, enemy, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.player = player
        self.enemy = enemy
        self.combat_log: list[str] = []
        self._current_minigame = None
        self._between_phases = True

    def compose(self):
        yield Header(show_clock=True)
        with Vertical(id="combat_container"):
            with Grid(id="combat_grid"):
                with Vertical(id="player_panel"):
                    yield Static(self.player.name, id="player_name")
                    yield Static(id="player_art")
                    yield Static(id="player_stats")
                with Vertical(id="enemy_panel"):
                    yield Static(self.enemy.name, id="enemy_name")
                    yield Static(id="enemy_art")
                    yield Static(id="enemy_stats")
            yield Static(id="phase_display")
            yield Static(id="minigame_area")
            yield Static(id="combat_log")
        yield Footer()

    def on_mount(self) -> None:
        gs = self.app.game_state
        self.player.durability = gs.current_durability
        self.player.max_durability = gs.max_durability
        phase = get_current_phase(gs)
        self.combat_log.append(f"The {self.enemy.name} {phase['telegraph']}")
        self._update_hud()
        self._start_phase()

    def _update_hud(self) -> None:
        gs = self.app.game_state
        p_art = self.player.get_static_art()
        self.query_one("#player_art", Static).update("\n".join(p_art))
        self.query_one("#player_stats", Static).update(
            f"HP: {gs.current_durability}/{gs.max_durability}"
        )

        e_art = self.enemy.get_static_art()
        self.query_one("#enemy_art", Static).update("\n".join(e_art))
        self.query_one("#enemy_stats", Static).update(
            f"HP: {self.enemy.durability}/{self.enemy.max_durability}"
        )

        phase = get_current_phase(gs)
        self.query_one("#phase_display", Static).update(
            f"═══ {phase['name'].upper()} ═══\n"
            f"The {self.enemy.name} {phase['telegraph']}\n"
            f"Tip: {phase['tip']}"
        )

        log_widget = self.query_one("#combat_log", Static)
        log_widget.update("\n".join(self.combat_log[-6:]))

    def _start_phase(self) -> None:
        gs = self.app.game_state
        phase = get_current_phase(gs)

        if self._current_minigame:
            self._current_minigame.remove()
            self._current_minigame = None

        minigame_type = phase["minigame"]
        if minigame_type == "dodge":
            from ..widgets.minigames.dodge import DodgeMinigame
            mg = DodgeMinigame(self.player, self.enemy, gs)
        elif minigame_type == "timing_strike":
            from ..widgets.minigames.timing_strike import TimingStrikeMinigame
            mg = TimingStrikeMinigame(self.player, self.enemy, gs)
        elif minigame_type == "chase":
            from ..widgets.minigames.chase import ChaseMinigame
            mg = ChaseMinigame(self.player, self.enemy, gs)
        elif minigame_type == "guard_break":
            from ..widgets.minigames.guard_break import GuardBreakMinigame
            mg = GuardBreakMinigame(self.player, self.enemy, gs)
        else:
            return

        self._current_minigame = mg
        self._between_phases = False

        area = self.query_one("#minigame_area")
        area.display = False
        container = self.query_one("#combat_container")
        container.mount(mg, before=self.query_one("#combat_log"))

    def on_minigame_result(self, event: MinigameResult) -> None:
        gs = self.app.game_state

        if event.damage_dealt > 0:
            self.enemy.durability = max(0, self.enemy.durability - event.damage_dealt)
        if event.damage_taken > 0:
            gs.current_durability = max(0, gs.current_durability - event.damage_taken)

        self.combat_log.extend(event.log_lines)

        if self._current_minigame:
            self._current_minigame.remove()
            self._current_minigame = None

        end = check_combat_end(gs)
        if end:
            self._handle_combat_end(end)
            return

        next_phase = advance_phase(gs)
        self.combat_log.append("")
        self.combat_log.append(f"The {self.enemy.name} {next_phase['telegraph']}")
        self._update_hud()
        self._start_phase()

    def action_attempt_flee(self) -> None:
        gs = self.app.game_state
        player_speed = getattr(gs, "max_speed", 10)
        enemy_speed = getattr(self.enemy, "speed", 5)
        flee_chance = min(0.8, max(0.2, player_speed / (player_speed + enemy_speed)))
        if random.random() < flee_chance:
            self.combat_log.append("You successfully escaped!")
            gs.menu_open = False
            if self._current_minigame:
                self._current_minigame.remove()
            self.app.pop_screen()
        else:
            self.combat_log.append("Failed to escape!")
            self._update_hud()

    def _handle_combat_end(self, result: str):
        gs = self.app.game_state
        if result == "victory":
            xp = getattr(self.enemy, "xp_value", 50)
            cash = getattr(self.enemy, "cash_value", 100)
            gs.gain_xp(xp)
            gs.player_cash += cash
            self.combat_log.append(f"Victory! +{xp} XP, +{cash} cash")

            if self.enemy in gs.active_enemies:
                gs.active_enemies.remove(self.enemy)

            if getattr(self.enemy, "boss_tier", None):
                from ..logic.boss import handle_boss_defeat
                handle_boss_defeat(gs, self.enemy)

            for screen in self.app.screen_stack:
                notifications = screen.query("#notifications")
                if notifications:
                    notifications.first().add_notification(
                        f"You defeated the {self.enemy.name}!"
                    )
                    break

            gs.menu_open = False
            self.app.pop_screen()
        elif result == "defeat":
            gs.game_over = True
            self.app.pop_screen()

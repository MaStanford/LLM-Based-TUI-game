from textual.widget import Widget
from textual.message import Message


class MinigameResult(Message):
    """Posted when a mini-game finishes."""
    def __init__(self, damage_dealt: int, damage_taken: int, log_lines: list[str]) -> None:
        self.damage_dealt = damage_dealt
        self.damage_taken = damage_taken
        self.log_lines = log_lines
        super().__init__()


class Minigame(Widget):
    """Base class for boss fight mini-games."""

    can_focus = True

    def __init__(self, player, enemy, game_state, **kwargs):
        super().__init__(**kwargs)
        self.player = player
        self.enemy = enemy
        self.game_state = game_state

    def finish(self, damage_dealt: int, damage_taken: int, log_lines: list[str]) -> None:
        self.post_message(MinigameResult(damage_dealt, damage_taken, log_lines))

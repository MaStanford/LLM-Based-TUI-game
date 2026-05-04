"""Timing Strike — Press fire when the marker hits the sweet spot.

A cursor sweeps back and forth across a bar. The center zone is green
(critical), flanked by yellow (good), with red (miss) at the edges.
Press Space or Enter to lock in. Multiple strikes per round.
"""

import math
from textual.events import Key
from rich.text import Text
from rich.style import Style
from . import Minigame

BAR_WIDTH = 40
SWEET_SPOT_HALF = 3   # green zone: center ± 3
GOOD_ZONE_HALF = 7    # yellow zone: center ± 7
SWEEP_SPEED = 2.0     # full sweeps per second
NUM_STRIKES = 3
CRIT_MULT = 2.0
GOOD_MULT = 1.0
MISS_MULT = 0.2


class TimingStrikeMinigame(Minigame):
    """Precision timing attack."""

    def __init__(self, player, enemy, game_state, **kwargs):
        super().__init__(player, enemy, game_state, **kwargs)
        self.cursor_pos = 0.0  # 0..1 normalized
        self.direction = 1
        self.strikes_left = NUM_STRIKES
        self.results: list[str] = []  # "crit", "good", "miss"
        self.total_damage = 0
        self._timer = None
        self._showing_result = False
        self._result_timer = 0.0

    def on_mount(self) -> None:
        self.focus()
        self._timer = self.set_interval(1 / 30, self.tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def on_key(self, event: Key) -> None:
        if event.key in ("space", "enter") and not self._showing_result:
            self._resolve_strike()

    def tick(self) -> None:
        dt = 1 / 30
        if self._showing_result:
            self._result_timer -= dt
            if self._result_timer <= 0:
                self._showing_result = False
                if self.strikes_left <= 0:
                    self._end()
                    return
            self.refresh()
            return

        self.cursor_pos += self.direction * SWEEP_SPEED * dt
        if self.cursor_pos >= 1.0:
            self.cursor_pos = 1.0
            self.direction = -1
        elif self.cursor_pos <= 0.0:
            self.cursor_pos = 0.0
            self.direction = 1
        self.refresh()

    def _resolve_strike(self) -> None:
        center = BAR_WIDTH // 2
        cursor_x = int(self.cursor_pos * (BAR_WIDTH - 1))
        dist = abs(cursor_x - center)

        base_dmg = self._base_weapon_damage()

        if dist <= SWEET_SPOT_HALF:
            dmg = int(base_dmg * CRIT_MULT)
            self.results.append("crit")
        elif dist <= GOOD_ZONE_HALF:
            dmg = int(base_dmg * GOOD_MULT)
            self.results.append("good")
        else:
            dmg = int(base_dmg * MISS_MULT)
            self.results.append("miss")

        self.total_damage += dmg
        self.strikes_left -= 1
        self._showing_result = True
        self._result_timer = 0.4

    def _base_weapon_damage(self) -> int:
        total = 0
        dmg_mod = getattr(self.game_state, "level_damage_modifier", 1.0)
        for weapon in self.game_state.mounted_weapons.values():
            if weapon:
                total += weapon.damage
        return max(5, int(total * dmg_mod))

    def _end(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None

        crits = self.results.count("crit")
        goods = self.results.count("good")
        misses = self.results.count("miss")

        log = []
        if crits == NUM_STRIKES:
            log.append(f"PERFECT TIMING! All {NUM_STRIKES} critical hits for {self.total_damage} damage!")
        else:
            parts = []
            if crits:
                parts.append(f"{crits} crit")
            if goods:
                parts.append(f"{goods} good")
            if misses:
                parts.append(f"{misses} miss")
            log.append(f"Timing attack: {', '.join(parts)} — {self.total_damage} total damage!")

        self.finish(self.total_damage, 0, log)

    def render(self) -> Text:
        text = Text()
        text.append(f"  ═══ TIMING STRIKE ═══  Strikes left: {self.strikes_left}\n")

        center = BAR_WIDTH // 2
        cursor_x = int(self.cursor_pos * (BAR_WIDTH - 1))

        text.append("  ┌" + "─" * BAR_WIDTH + "┐\n")
        text.append("  │")
        for x in range(BAR_WIDTH):
            dist = abs(x - center)
            if x == cursor_x:
                ch = "▼"
                if self._showing_result:
                    last = self.results[-1] if self.results else "miss"
                    color = {"crit": "green", "good": "yellow", "miss": "red"}[last]
                else:
                    color = "white"
                text.append(ch, Style(color=color, bold=True))
            elif dist <= SWEET_SPOT_HALF:
                text.append("█", Style(color="green"))
            elif dist <= GOOD_ZONE_HALF:
                text.append("▓", Style(color="yellow"))
            else:
                text.append("░", Style(color="red"))
        text.append("│\n")
        text.append("  └" + "─" * BAR_WIDTH + "┘\n")

        if self._showing_result and self.results:
            last = self.results[-1]
            labels = {"crit": "★ CRITICAL! ★", "good": "Good.", "miss": "Miss..."}
            colors = {"crit": "green", "good": "yellow", "miss": "red"}
            text.append(f"  ", Style())
            text.append(labels[last], Style(color=colors[last], bold=True))
            text.append("\n")
        else:
            text.append("  [Space/Enter to strike!]\n")

        # Show history
        text.append("  ")
        for r in self.results:
            sym = {"crit": "★", "good": "●", "miss": "○"}[r]
            col = {"crit": "green", "good": "yellow", "miss": "red"}[r]
            text.append(sym + " ", Style(color=col, bold=True))
        text.append("\n")

        return text

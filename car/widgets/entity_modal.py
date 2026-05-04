from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.style import Style
from .tickable import GameTickable
import time
import random
import math

DESTROYED_DISPLAY_DURATION = 1.5
DESTROYED_ANIM_INTERVAL = 0.08

# 8-direction arrows for target bearing
_DIRECTIONS = [
    (  0, "\u2191", "N"),   # ↑
    ( 45, "\u2197", "NE"),  # ↗
    ( 90, "\u2192", "E"),   # →
    (135, "\u2198", "SE"),  # ↘
    (180, "\u2193", "S"),   # ↓
    (225, "\u2199", "SW"),  # ↙
    (270, "\u2190", "W"),   # ←
    (315, "\u2196", "NW"),  # ↖
]

def _bearing_to_arrow(bearing_deg):
    """Convert bearing degrees (0=North) to arrow + cardinal label."""
    a = bearing_deg % 360
    best = _DIRECTIONS[0]
    best_diff = 360
    for center, arrow, label in _DIRECTIONS:
        diff = min(abs(a - center), 360 - abs(a - center))
        if diff < best_diff:
            best_diff = diff
            best = (center, arrow, label)
    return best[1], best[2]

# Destruction animation chars (terminal-safe, no emojis)
_DESTROY_FIRE = [
    ("*", Style(color="red", bold=True)),
    ("#", Style(color="rgb(255,100,0)", bold=True)),
    ("~", Style(color="rgb(255,165,0)")),
    ("+", Style(color="yellow", bold=True)),
]
_DESTROY_SMOKE = [
    (".", Style(color="rgb(100,100,100)")),
    (":", Style(color="rgb(80,80,80)")),
    (" ", Style()),
]


class EntityModal(Widget, GameTickable):
    """A widget to display information about the nearest entity."""
    can_focus = False

    entity_name = reactive("No Target")
    hp = reactive(0)
    max_hp = reactive(0)
    art = reactive([])
    bearing = reactive(-1.0)
    description = reactive("")
    destroyed_name = reactive("")
    destroyed_timer = reactive(0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._destroy_art = []
        self._destroy_styles = []
        self._destroy_step = 0
        self._destroy_anim_accum = 0.0
        self._destroy_active = False

    def _start_destroy_animation(self, art_lines):
        self._destroy_art = [list(row) for row in art_lines]
        self._destroy_styles = [[Style() for _ in row] for row in self._destroy_art]
        self._destroy_step = 0
        self._destroy_anim_accum = 0.0
        self._destroy_active = True

    def game_tick(self, dt: float) -> None:
        """Advance the destruction animation via the game loop."""
        if not self._destroy_active:
            return
        self._destroy_anim_accum += dt
        if self._destroy_anim_accum < DESTROYED_ANIM_INTERVAL:
            return
        self._destroy_anim_accum = 0.0
        self._destroy_step += 1
        total = 12
        if self._destroy_step > total:
            self._destroy_active = False
            return

        progress = self._destroy_step / total
        for r, row in enumerate(self._destroy_art):
            for c, char in enumerate(row):
                if char != ' ' and random.random() < progress:
                    if progress < 0.5:
                        ch, st = random.choice(_DESTROY_FIRE)
                    elif progress < 0.8:
                        ch, st = random.choice(_DESTROY_FIRE + _DESTROY_SMOKE)
                    else:
                        ch, st = random.choice(_DESTROY_SMOKE)
                    self._destroy_art[r][c] = ch
                    self._destroy_styles[r][c] = st
        self.refresh()

    def watch_destroyed_name(self, value: str) -> None:
        """When a new destruction event occurs, start the animation."""
        if value and self.art:
            self._start_destroy_animation(self.art)

    def render(self) -> Panel:
        """Render the entity modal."""
        # Check for recent destruction event
        if self.destroyed_name and time.time() - self.destroyed_timer < DESTROYED_DISPLAY_DURATION:
            # Build animated destruction content
            content = Text()
            content.append(f"  DESTROYED  ", Style(color="red", bold=True))
            content.append("\n")
            if self._destroy_art:
                for r, row in enumerate(self._destroy_art):
                    for c, char in enumerate(row):
                        content.append(char, self._destroy_styles[r][c])
                    content.append("\n")
            else:
                destroyed_banner = (
                    "\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\n"
                    "\u2551 DESTROYED \u2551\n"
                    "\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d"
                )
                content.append(destroyed_banner, Style(color="red", bold=True))

            return Panel(
                content,
                title=self.destroyed_name,
                border_style="bold red",
            )

        if self.max_hp <= 0:
            # Idle state
            idle_art = (
                "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510\n"
                "\u2502  \u25ce SCAN \u2502\n"
                "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518"
            )
            return Panel(
                Text(idle_art, justify="center", style="dim"),
                title="No Target",
                border_style="dim white",
            )

        hp_percent = (self.hp / self.max_hp) * 100
        hp_bar_width = 20
        hp_filled = int(hp_bar_width * hp_percent / 100)
        hp_color = "green" if hp_percent > 50 else "yellow" if hp_percent > 25 else "red"
        hp_bar = f"HP: [{hp_color}]{'\u2588'*hp_filled}[/][dim]{'\u2591'*(hp_bar_width-hp_filled)}[/]"

        # Direction arrow to target
        if self.bearing >= 0:
            arrow, cardinal = _bearing_to_arrow(self.bearing)
            direction_line = f"[bold]{arrow}[/bold] {cardinal}"
        else:
            direction_line = ""

        art_str = "\n".join(self.art) if self.art else ""

        parts = [hp_bar]
        if self.description:
            parts.append(f"[dim italic]{self.description}[/dim italic]")
        if direction_line:
            parts.append(direction_line)
        if art_str:
            parts.append(art_str)
        content = "\n".join(parts)

        return Panel(Text.from_markup(content, justify="center"), title=self.entity_name, border_style="bold red")

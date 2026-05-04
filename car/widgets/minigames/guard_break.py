"""Guard Break — Shoot through the rotating shield gap.

A circular shield rotates around the boss. It has one or more gaps.
Press fire when a gap faces the player (bottom). The shield spins
faster at lower boss HP. Player weapon damage determines hit power.
"""

import math
from textual.events import Key
from rich.text import Text
from rich.style import Style
from . import Minigame

SHIELD_SEGMENTS = 16
GAP_SIZE = 2  # number of segments that are open
RADIUS = 5
NUM_SHOTS = 4


class GuardBreakMinigame(Minigame):
    """Rotating shield gap-shooting."""

    def __init__(self, player, enemy, game_state, **kwargs):
        super().__init__(player, enemy, game_state, **kwargs)
        self.angle = 0.0  # current rotation in radians
        self.shots_left = NUM_SHOTS
        self.hits = 0
        self.total_damage = 0
        self._timer = None
        self._flash = ""
        self._flash_timer = 0.0

        boss_hp_ratio = enemy.durability / max(1, enemy.max_durability)
        base_speed = getattr(enemy, "speed", 5) * 0.15
        self.spin_speed = max(1.0, base_speed + (1 - boss_hp_ratio) * 2.0)

        enemy_dmg = getattr(enemy, "shoot_damage", 10)
        self.retaliation_damage = max(3, int(enemy_dmg * 0.4))

    def on_mount(self) -> None:
        self.focus()
        self._timer = self.set_interval(1 / 20, self.tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def on_key(self, event: Key) -> None:
        if event.key in ("space", "enter") and self.shots_left > 0 and self._flash_timer <= 0:
            self._fire()

    def tick(self) -> None:
        dt = 1 / 20
        self.angle += self.spin_speed * dt
        if self._flash_timer > 0:
            self._flash_timer -= dt
        self.refresh()

    def _fire(self) -> None:
        self.shots_left -= 1
        player_angle = math.pi / 2  # player is at bottom (90 degrees)
        gap_center = self.angle % (2 * math.pi)
        segment_size = 2 * math.pi / SHIELD_SEGMENTS
        gap_half = GAP_SIZE * segment_size / 2

        diff = abs(((player_angle - gap_center + math.pi) % (2 * math.pi)) - math.pi)

        dmg_mod = getattr(self.game_state, "level_damage_modifier", 1.0)
        base_dmg = 0
        for weapon in self.game_state.mounted_weapons.values():
            if weapon:
                base_dmg += weapon.damage
        base_dmg = max(5, int(base_dmg * dmg_mod))

        if diff <= gap_half:
            dmg = int(base_dmg * 1.5)
            self.hits += 1
            self.total_damage += dmg
            self._flash = "HIT"
        else:
            self._flash = "BLOCKED"

        self._flash_timer = 0.3

        if self.shots_left <= 0:
            self.set_timer(0.4, lambda: self._end())

    def _end(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None

        misses = NUM_SHOTS - self.hits
        damage_taken = misses * self.retaliation_damage
        log = []
        if self.hits == NUM_SHOTS:
            log.append(f"All {NUM_SHOTS} shots through the shield! {self.total_damage} damage!")
        elif self.hits > 0:
            log.append(f"{self.hits}/{NUM_SHOTS} shots hit through the shield for {self.total_damage} damage.")
        else:
            log.append(f"All shots blocked by the shield!")
        if damage_taken > 0:
            log.append(f"The {self.enemy.name} retaliates for {damage_taken} damage!")

        self.finish(self.total_damage, damage_taken, log)

    def render(self) -> Text:
        text = Text()
        text.append(f"  ═══ GUARD BREAK ═══  Shots: {self.shots_left}/{NUM_SHOTS}\n\n")

        display_w = 22
        display_h = 11
        cx, cy = display_w // 2, display_h // 2

        grid = [[" "] * display_w for _ in range(display_h)]
        grid[cy][cx] = "◆"

        segment_size = 2 * math.pi / SHIELD_SEGMENTS
        gap_center = self.angle % (2 * math.pi)
        gap_half = GAP_SIZE * segment_size / 2

        for i in range(SHIELD_SEGMENTS):
            seg_angle = i * segment_size
            diff = abs(((seg_angle - gap_center + math.pi) % (2 * math.pi)) - math.pi)
            is_gap = diff <= gap_half

            sx = cx + int(round(RADIUS * math.cos(seg_angle)))
            sy = cy + int(round(RADIUS * 0.5 * math.sin(seg_angle)))
            if 0 <= sx < display_w and 0 <= sy < display_h:
                if is_gap:
                    grid[sy][sx] = "·"
                else:
                    grid[sy][sx] = "█"

        player_sx = cx
        player_sy = cy + int(RADIUS * 0.5) + 1
        if 0 <= player_sy < display_h:
            grid[player_sy][player_sx] = "▲"

        for row in grid:
            for ch in row:
                if ch == "◆":
                    text.append(ch, Style(color="red", bold=True))
                elif ch == "█":
                    text.append(ch, Style(color="yellow"))
                elif ch == "·":
                    text.append(ch, Style(color="green", bold=True))
                elif ch == "▲":
                    text.append(ch, Style(color="cyan", bold=True))
                else:
                    text.append(ch)
            text.append("\n")

        if self._flash_timer > 0:
            color = "green" if self._flash == "HIT" else "red"
            text.append(f"  ", Style())
            text.append(self._flash, Style(color=color, bold=True))
            text.append("\n")
        else:
            text.append("  [Space/Enter to fire!]\n")

        text.append("  ")
        for i in range(NUM_SHOTS):
            if i < NUM_SHOTS - self.shots_left:
                if i < self.hits:
                    text.append("★ ", Style(color="green", bold=True))
                else:
                    text.append("○ ", Style(color="red"))
            else:
                text.append("● ", Style(color="white"))
        text.append("\n")

        return text

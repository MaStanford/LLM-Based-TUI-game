"""Dodge Phase — Undertale-style bullet hell in a box.

The player controls a cursor (♦) inside a bordered arena.
Projectiles spawn from edges and travel across. Each hit deals damage.
Surviving with few hits deals counter-damage to the boss.
"""

import random
import math
from textual.events import Key
from rich.text import Text
from rich.style import Style
from . import Minigame

ARENA_W = 30
ARENA_H = 12
DURATION = 4.0


class DodgeMinigame(Minigame):
    """Bullet-hell dodge arena."""

    def __init__(self, player, enemy, game_state, **kwargs):
        super().__init__(player, enemy, game_state, **kwargs)
        self.px = ARENA_W // 2
        self.py = ARENA_H // 2
        self.projectiles: list[list[float]] = []  # [x, y, vx, vy]
        self.hits = 0
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self._timer = None

        enemy_dmg = getattr(enemy, "shoot_damage", 10)
        enemy_speed = getattr(enemy, "speed", 5)
        self.hit_damage = max(3, int(enemy_dmg * 0.6))
        self.projectile_speed = max(8.0, 8.0 + enemy_speed * 0.5)
        self.spawn_interval = max(0.12, 0.35 - enemy_speed * 0.015)

    def on_mount(self) -> None:
        self.focus()
        self._timer = self.set_interval(1 / 20, self.tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def on_key(self, event: Key) -> None:
        if event.key == "up" and self.py > 0:
            self.py -= 1
        elif event.key == "down" and self.py < ARENA_H - 1:
            self.py += 1
        elif event.key == "left" and self.px > 0:
            self.px -= 1
        elif event.key == "right" and self.px < ARENA_W - 1:
            self.px += 1

    def tick(self) -> None:
        dt = 1 / 20
        self.elapsed += dt

        if self.elapsed >= DURATION:
            self._end()
            return

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self._spawn_projectile()
            self.spawn_timer = self.spawn_interval

        new_projs = []
        for p in self.projectiles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            ix, iy = int(round(p[0])), int(round(p[1]))
            if ix == self.px and iy == self.py:
                self.hits += 1
                continue  # projectile consumed
            if 0 <= ix < ARENA_W and 0 <= iy < ARENA_H:
                new_projs.append(p)
        self.projectiles = new_projs
        self.refresh()

    def _spawn_projectile(self) -> None:
        side = random.choice(["top", "bottom", "left", "right"])
        if side == "top":
            x, y = random.randint(0, ARENA_W - 1), 0
            vx, vy = random.uniform(-2, 2), self.projectile_speed
        elif side == "bottom":
            x, y = random.randint(0, ARENA_W - 1), ARENA_H - 1
            vx, vy = random.uniform(-2, 2), -self.projectile_speed
        elif side == "left":
            x, y = 0, random.randint(0, ARENA_H - 1)
            vx, vy = self.projectile_speed, random.uniform(-2, 2)
        else:
            x, y = ARENA_W - 1, random.randint(0, ARENA_H - 1)
            vx, vy = -self.projectile_speed, random.uniform(-2, 2)
        self.projectiles.append([float(x), float(y), vx, vy])

    def _end(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None

        damage_taken = self.hits * self.hit_damage
        base_counter = getattr(self.enemy, "shoot_damage", 10)
        dmg_mod = getattr(self.game_state, "level_damage_modifier", 1.0)
        base_counter = int(base_counter * dmg_mod)
        if self.hits == 0:
            counter = base_counter * 2
            log = [f"Perfect dodge! You counterattack for {counter} damage!"]
        elif self.hits <= 2:
            counter = base_counter
            log = [f"Grazed {self.hits} time(s). You counter for {counter} damage."]
        else:
            counter = max(1, base_counter // 2)
            log = [f"Hit {self.hits} times for {damage_taken} damage! Weak counter for {counter}."]

        self.finish(counter, damage_taken, log)

    def render(self) -> Text:
        remaining = max(0, DURATION - self.elapsed)
        lines = [f"  ═══ DODGE! ═══  ({remaining:.1f}s)  Hits: {self.hits}"]
        lines.append("  ┌" + "─" * ARENA_W + "┐")

        grid = [[" "] * ARENA_W for _ in range(ARENA_H)]
        grid[self.py][self.px] = "♦"
        for p in self.projectiles:
            ix, iy = int(round(p[0])), int(round(p[1]))
            if 0 <= ix < ARENA_W and 0 <= iy < ARENA_H:
                grid[iy][ix] = "●"

        for row in grid:
            lines.append("  │" + "".join(row) + "│")
        lines.append("  └" + "─" * ARENA_W + "┘")
        lines.append("  [Arrow keys to dodge]")

        text = Text()
        for line in lines:
            for ch in line:
                if ch == "♦":
                    text.append(ch, Style(color="cyan", bold=True))
                elif ch == "●":
                    text.append(ch, Style(color="red", bold=True))
                else:
                    text.append(ch)
            text.append("\n")
        return text

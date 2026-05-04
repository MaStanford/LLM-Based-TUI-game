"""Chase Phase — Lane-switching pursuit.

The boss flees down a 3-lane road. Obstacles scroll toward the player.
Dodge obstacles to close the gap; hitting them slows you down.
Catch the boss to deal ram damage. Player speed stat affects catch rate.
Boss speed stat affects obstacle density.
"""

import random
from textual.events import Key
from rich.text import Text
from rich.style import Style
from . import Minigame

LANE_COUNT = 3
ROAD_WIDTH = 30
ROAD_HEIGHT = 10
DURATION = 5.0
OBSTACLE_CHARS = ["#", "X", "▓", "█"]


class ChaseMinigame(Minigame):
    """Lane-switch chase sequence."""

    def __init__(self, player, enemy, game_state, **kwargs):
        super().__init__(player, enemy, game_state, **kwargs)
        self.player_lane = 1  # 0, 1, 2
        self.gap = 100.0  # distance to boss (lower = closer)
        self.obstacles: list[dict] = []  # {"lane": int, "y": float}
        self.hits = 0
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self._timer = None

        player_speed = getattr(game_state, "max_speed", 10)
        enemy_speed = getattr(enemy, "speed", 5)
        self.close_rate = max(3.0, player_speed * 0.8 - enemy_speed * 0.3)
        self.hit_penalty = 15.0
        self.obstacle_interval = max(0.3, 0.8 - enemy_speed * 0.02)

    def on_mount(self) -> None:
        self.focus()
        self._timer = self.set_interval(1 / 20, self.tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def on_key(self, event: Key) -> None:
        if event.key in ("left", "a") and self.player_lane > 0:
            self.player_lane -= 1
        elif event.key in ("right", "d") and self.player_lane < LANE_COUNT - 1:
            self.player_lane += 1

    def tick(self) -> None:
        dt = 1 / 20
        self.elapsed += dt

        if self.elapsed >= DURATION:
            self._end()
            return

        self.gap -= self.close_rate * dt

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            lane = random.randint(0, LANE_COUNT - 1)
            self.obstacles.append({"lane": lane, "y": 0.0})
            if random.random() < 0.3:
                other_lane = random.choice([l for l in range(LANE_COUNT) if l != lane])
                self.obstacles.append({"lane": other_lane, "y": 0.0})
            self.spawn_timer = self.obstacle_interval

        scroll_speed = 15.0
        new_obs = []
        for obs in self.obstacles:
            obs["y"] += scroll_speed * dt
            if int(obs["y"]) == ROAD_HEIGHT - 1 and obs["lane"] == self.player_lane:
                self.hits += 1
                self.gap += self.hit_penalty
                continue
            if obs["y"] < ROAD_HEIGHT:
                new_obs.append(obs)
        self.obstacles = new_obs

        if self.gap <= 0:
            self.gap = 0
            self._end()
            return

        self.refresh()

    def _end(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None

        caught = self.gap <= 0
        base_ram = getattr(self.player, "collision_damage", 10)
        dmg_mod = getattr(self.game_state, "level_damage_modifier", 1.0)

        if caught:
            damage = int(base_ram * 3 * dmg_mod)
            log = [f"You caught the {self.enemy.name} and rammed for {damage} damage!"]
        elif self.gap < 30:
            damage = int(base_ram * 1.5 * dmg_mod)
            log = [f"Almost caught! Side-swipe for {damage} damage."]
        else:
            damage = int(base_ram * 0.5 * dmg_mod)
            log = [f"The {self.enemy.name} escaped! Glancing hit for {damage}."]

        taken = self.hits * 5
        if taken > 0:
            log.append(f"Hit {self.hits} obstacle(s) for {taken} damage.")

        self.finish(damage, taken, log)

    def render(self) -> Text:
        remaining = max(0, DURATION - self.elapsed)
        gap_bar_len = 20
        gap_filled = max(0, min(gap_bar_len, int((1 - self.gap / 100) * gap_bar_len)))
        gap_color = "green" if gap_filled > 14 else "yellow" if gap_filled > 7 else "red"

        text = Text()
        text.append(f"  ═══ CHASE! ═══  ({remaining:.1f}s)\n")
        text.append("  Gap: [")
        text.append("█" * gap_filled, Style(color=gap_color))
        text.append("░" * (gap_bar_len - gap_filled), Style(color="rgb(60,60,60)"))
        text.append(f"] {int(self.gap)}m\n")

        lane_w = ROAD_WIDTH // LANE_COUNT
        grid = [[" "] * ROAD_WIDTH for _ in range(ROAD_HEIGHT)]

        for obs in self.obstacles:
            oy = int(obs["y"])
            ox = obs["lane"] * lane_w + lane_w // 2
            if 0 <= oy < ROAD_HEIGHT and 0 <= ox < ROAD_WIDTH:
                grid[oy][ox] = random.choice(OBSTACLE_CHARS)

        player_y = ROAD_HEIGHT - 1
        player_x = self.player_lane * lane_w + lane_w // 2
        if 0 <= player_x < ROAD_WIDTH:
            grid[player_y][player_x] = "▲"

        boss_y = 0
        boss_x = ROAD_WIDTH // 2
        grid[boss_y][boss_x] = "◆"

        for lane in range(1, LANE_COUNT):
            x = lane * lane_w
            for y in range(ROAD_HEIGHT):
                if 0 <= x < ROAD_WIDTH:
                    grid[y][x] = "│"

        text.append("  ┌" + "─" * ROAD_WIDTH + "┐\n")
        for row in grid:
            text.append("  │")
            for ch in row:
                if ch == "▲":
                    text.append(ch, Style(color="cyan", bold=True))
                elif ch == "◆":
                    text.append(ch, Style(color="red", bold=True))
                elif ch in OBSTACLE_CHARS:
                    text.append(ch, Style(color="yellow"))
                elif ch == "│":
                    text.append(ch, Style(color="rgb(60,60,60)"))
                else:
                    text.append(ch)
            text.append("│\n")
        text.append("  └" + "─" * ROAD_WIDTH + "┘\n")
        text.append("  [Left/Right to switch lanes]\n")

        return text

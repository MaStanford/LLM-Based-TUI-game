import random
from ..character import Character
from ...logic.ai_behaviors import execute_behavior
from ...data.game_constants import GLOBAL_SPEED_MULTIPLIER

class Bandit(Character):
    def __init__(self, x, y):
        art = [
            "  _  ",
            r" / \ ",
            "|o.o|",
            r" \_/ ",
        ]
        super().__init__(x, y, art, durability=10, speed=0.25 * GLOBAL_SPEED_MULTIPLIER)
        self.xp_value = 5
        self.cash_value = 10
        self.collision_damage = 3
        self.shoot_damage = 2
        self.drop_item = "ammo_bullet"
        self.drop_rate = 0.05
        self.phases = [
            {"name": "Charge", "duration": (3, 5), "behavior": "CHASE", "next_phases": {"Shoot": 0.6, "Charge": 0.4}},
            {"name": "Shoot", "duration": (2, 4), "behavior": "SHOOT", "next_phases": {"Charge": 0.5, "Hesitate": 0.5}},
            {"name": "Hesitate", "duration": (1, 2), "behavior": "STATIONARY", "next_phases": {"Charge": 0.7, "Shoot": 0.3}}
        ]
        self._initialize_ai()

    def _initialize_ai(self):
        self.current_phase = self.phases[0]
        self.phase_timer = random.uniform(*self.current_phase["duration"])

    def update(self, game_state, world, dt):
        self.ai_state["elapsed"] = self.ai_state.get("elapsed", 0) + dt
        self.phase_timer -= dt

        if self.phase_timer <= 0:
            next_phase_options = list(self.current_phase["next_phases"].keys())
            next_phase_weights = list(self.current_phase["next_phases"].values())
            new_phase_name = random.choices(next_phase_options, weights=next_phase_weights, k=1)[0]
            self.current_phase = next((p for p in self.phases if p["name"] == new_phase_name), self.phases[0])
            self.phase_timer = random.uniform(*self.current_phase["duration"])

        execute_behavior(self.current_phase["behavior"], self, game_state, self, dt=dt)

        self._move_with_terrain_check(world, dt)

    def draw(self, stdscr, game_state, world_start_x, world_start_y, color_map):
        from ...rendering.draw_utils import draw_sprite
        draw_sprite(stdscr, self.y - world_start_y, self.x - world_start_x, self.art, color_map.get("ENEMY", 0), transparent_bg=True)

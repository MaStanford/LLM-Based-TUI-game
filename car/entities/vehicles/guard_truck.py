from ..vehicle import Vehicle

from ...data.game_constants import GLOBAL_SPEED_MULTIPLIER

class GuardTruck(Vehicle):
    """
    A slow but sturdy truck used by the Blue Syndicate for defensive purposes.
    It stays put until an enemy gets close, then gives a determined chase.
    """
    def __init__(self, x, y):
        art = {
            # North (Facing Up) - hood at top, trunk at bottom
            "N": [
                " ▄███▄ ",
                "▐█░░░█▌",
                "●█████●",
                "█▓▓▓▓▓█",
                "●█████●",
                " ▀███▀ "
            ],
            # South (Facing Down) - vertical mirror of N
            "S": [
                " ▄███▄ ",
                "●█████●",
                "█▓▓▓▓▓█",
                "●█████●",
                "▐█░░░█▌",
                " ▀███▀ "
            ],
            # East (Facing Right) - hood on right, boxy shape
            "E": [
                "●██████░█▄ ",
                "█▓█████▓░█▌",
                "●██████░█▀ "
            ],
            # West (Facing Left) - horizontal mirror of E
            "W": [
                " ▄█░██████●",
                "▐█░▓█████▓█",
                " ▀█░██████●"
            ],
            # North-East - front at upper-right
            "NE": [
                "  ▄█░██▄",
                " ●█░░▓██",
                "▐█▓▓███●",
                "█▓████▀ ",
                " ▀██▀   "
            ],
            # North-West - horizontal mirror of NE
            "NW": [
                "▄██░█▄  ",
                "██▓░░█● ",
                "●███▓▓█▌",
                " ▀████▓█",
                "   ▀██▀ "
            ],
            # South-East - vertical mirror of NE
            "SE": [
                " ▄██▄   ",
                "█▓████▄ ",
                "▐█▓▓███●",
                " ●█░░▓██",
                "  ▀█░██▀"
            ],
            # South-West - horizontal mirror of SE
            "SW": [
                "   ▄██▄ ",
                " ▄████▓█",
                "●███▓▓█▌",
                "██▓░░█● ",
                "▀██░█▀  "
            ]
        }
        super().__init__(x, y, art, durability=150, speed=3.75 * GLOBAL_SPEED_MULTIPLIER, acceleration=0.2, handling=0.2, weight=2000)
        self.name = "Guard Truck"
        self.xp_value = 30
        self.cash_value = 50
        self.drop_item = "ammo_bullet"
        self.drop_rate = 0.2
        self.collision_damage = 8
        self.shoot_damage = 3
        self.phases = [
            {"name": "Guard", "duration": (1, 2), "behavior": "STATIONARY", "next_phases": {"Shoot": 1.0}},
            {"name": "Shoot", "duration": (3, 5), "behavior": "SHOOT", "next_phases": {"Chase": 0.6, "Guard": 0.4}},
            {"name": "Chase", "duration": (10, 15), "behavior": "CHASE", "next_phases": {"Guard": 1.0}}
        ]
        self._initialize_ai()
        self.aggro_radius = 20

    def update(self, game_state, world, dt):
        import random
        from ...logic.ai_behaviors import execute_behavior

        dist_to_player = ((self.x - game_state.car_world_x)**2 + (self.y - game_state.car_world_y)**2)**0.5

        # If player is far away, always stay in Guard mode
        if dist_to_player > self.aggro_radius and self.current_phase["name"] != "Guard":
            self.current_phase = self.phases[0]
            self.phase_timer = random.uniform(*self.current_phase["duration"])

        # Guard phase handled manually (no budget needed for being stationary)
        if self.current_phase["name"] == "Guard":
            self.ai_state["elapsed"] = self.ai_state.get("elapsed", 0) + dt
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                if dist_to_player <= self.aggro_radius:
                    self.current_phase = next((p for p in self.phases if p["name"] == "Shoot"), self.phases[1])
                    self.phase_timer = random.uniform(*self.current_phase["duration"])
                else:
                    self.phase_timer = random.uniform(*self.current_phase["duration"])
        else:
            # Combat phases use budget-aware transitions
            self._advance_phase(game_state, dt)

        execute_behavior(self.current_phase["behavior"], self, game_state, self, dt=dt)

        self._move_with_terrain_check(world, dt)

    def draw(self, stdscr, game_state, world_start_x, world_start_y, color_map):
        from ...rendering.draw_utils import draw_sprite
        draw_sprite(stdscr, self.y - world_start_y, self.x - world_start_x, self.art, color_map.get("ENEMY_BLUE", 0), transparent_bg=True)

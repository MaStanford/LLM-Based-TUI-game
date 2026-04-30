from .base import Entity
import random
import logging
from ..logic.ai_behaviors import execute_behavior, BEHAVIOR_COSTS

CYCLE_LENGTH = 5
UNIVERSAL_FILLER_PHASES = [
    {"name": "_Idle", "duration": (2, 4), "behavior": "IDLE", "next_phases": {}},
    {"name": "_Patrol", "duration": (2, 3), "behavior": "PATROL", "next_phases": {}},
]

class Vehicle(Entity):
    def __init__(self, x, y, art, durability, speed, acceleration, handling, weight=1000):
        super().__init__(x, y, art, durability)
        self.speed = speed
        self.acceleration = acceleration
        self.handling = handling
        self.weight = weight
        self.fuel = 100
        self.max_fuel = 100
        self.attachment_points = {}
        self.angle = 0.0

        if isinstance(art, dict):
            self.height, self.width = Entity.get_car_dimensions(list(art.values()))
        elif isinstance(art, list):
            self.width = max(len(line) for line in art) if art else 0
            self.height = len(art) if art else 0

    def _initialize_ai(self):
        """Standard AI init — sets first phase + budget."""
        self.current_phase = self.phases[0]
        self.phase_timer = random.uniform(*self.current_phase["duration"])
        self._reset_budget(None)

    def _get_budget(self, game_state):
        """Calculate total budget from difficulty + player level."""
        base = 5
        if game_state:
            base = game_state.difficulty_mods.get("aggression_budget", 5)
            base += getattr(game_state, 'player_level', 1) // 5
        return base

    def _reset_budget(self, game_state):
        """Reset cycle counter and budget."""
        self.budget_remaining = self._get_budget(game_state)
        self.cycle_phases_remaining = CYCLE_LENGTH

    def _advance_phase(self, game_state, dt):
        """Shared phase timer + budget-aware transition logic."""
        self.ai_state["elapsed"] = self.ai_state.get("elapsed", 0) + dt
        self.phase_timer -= dt

        if self.phase_timer <= 0:
            self.cycle_phases_remaining -= 1
            if self.cycle_phases_remaining <= 0:
                self._reset_budget(game_state)

            candidates = []
            if self.current_phase.get("next_phases"):
                for phase_name, weight in self.current_phase["next_phases"].items():
                    phase = next((p for p in self.phases if p["name"] == phase_name), None)
                    if phase:
                        cost = BEHAVIOR_COSTS.get(phase["behavior"], 0)
                        if cost <= self.budget_remaining:
                            candidates.append((phase, weight))

            if candidates:
                phases, weights = zip(*candidates)
                chosen = random.choices(phases, weights=weights, k=1)[0]
            else:
                chosen = random.choice(UNIVERSAL_FILLER_PHASES)

            self.budget_remaining -= BEHAVIOR_COSTS.get(chosen["behavior"], 0)
            self.current_phase = chosen
            self.phase_timer = random.uniform(*chosen["duration"])

            # Clear ram sub-state when leaving a RAM phase
            if chosen["behavior"] != "RAM" and "ram_substate" in self.ai_state:
                del self.ai_state["ram_substate"]
                del self.ai_state["ram_timer"]

    def _check_bbox_passable(self, world, cx, cy):
        """Check if the vehicle's bounding box centered at (cx, cy) is in passable terrain."""
        half_w = self.width / 2
        half_h = self.height / 2
        corners = [
            (cx - half_w, cy - half_h),
            (cx + half_w, cy - half_h),
            (cx - half_w, cy + half_h),
            (cx + half_w, cy + half_h),
        ]
        for x, y in corners:
            if not world.get_terrain_at(x, y).get("passable", True):
                return False
        return True

    def _move_with_terrain_check(self, world, dt):
        """Move the vehicle, respecting impassable terrain (buildings, rocks, trees)."""
        next_x = self.x + self.vx * dt
        next_y = self.y + self.vy * dt

        if world is None:
            self.x = next_x
            self.y = next_y
            return

        # Check proposed position using bounding box corners
        if self._check_bbox_passable(world, next_x, next_y):
            self.x = next_x
            self.y = next_y
            return

        # Wall-slide: try X-only
        if self._check_bbox_passable(world, self.x + self.vx * dt, self.y):
            self.x += self.vx * dt
            self.vy *= 0.3
            return

        # Wall-slide: try Y-only
        if self._check_bbox_passable(world, self.x, self.y + self.vy * dt):
            self.y += self.vy * dt
            self.vx *= 0.3
            return

        # Fully blocked — stop
        self.vx = 0
        self.vy = 0

    def update(self, game_state, world, dt):
        """Default enemy vehicle update: advance phase, execute, move."""
        self._advance_phase(game_state, dt)
        execute_behavior(self.current_phase["behavior"], self, game_state, self, dt=dt)
        self._move_with_terrain_check(world, dt)

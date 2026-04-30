import sys
import time


# Minimum seconds between bell triggers per event category
_COOLDOWNS = {
    "crash": 0.4,
    "enemy_hit": 0.3,
    "player_hit": 0.3,
    "weapon": 0.5,
    "default": 0.2,
}

# How many bells to ring per event category
_BELL_COUNT = {
    "crash": 1,
    "enemy_hit": 1,
    "player_hit": 2,
    "weapon": 1,
    "default": 1,
}

# Map specific SFX names to event categories for cooldown grouping
_CATEGORY = {
    "crash": "crash",
    "enemy_hit": "enemy_hit",
    "player_hit": "player_hit",
    "flamethrower": "weapon",
}


class AudioManager:
    def __init__(self):
        self.enabled = True
        self._last_bell: dict[str, float] = {}

    def play_sfx(self, name: str):
        """Play a sound effect via terminal bell with rate limiting."""
        if not self.enabled:
            return

        category = _CATEGORY.get(name, "weapon" if name else "default")
        cooldown = _COOLDOWNS.get(category, _COOLDOWNS["default"])

        now = time.monotonic()
        last = self._last_bell.get(category, 0.0)
        if now - last < cooldown:
            return

        self._last_bell[category] = now
        count = _BELL_COUNT.get(category, _BELL_COUNT["default"])
        sys.stdout.write("\a" * count)
        sys.stdout.flush()

    def play_music(self, path):
        pass

    def stop_music(self):
        pass

from textual.widgets import Static
from .tickable import GameTickable
import time

MAX_VISIBLE = 5
MAX_HISTORY = 20
CLEANUP_INTERVAL = 0.5


class Notifications(Static, GameTickable):
    """A widget to display notifications with auto-expiry and history."""
    can_focus = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.notifications = []
        self.history = []
        self._cleanup_accumulator = 0.0
        self._manually_hidden = False

    def add_notification(self, text: str, duration: int = 3) -> None:
        self._manually_hidden = False
        entry = {
            "text": text,
            "duration": duration,
            "start_time": time.time(),
        }
        self.notifications.append(entry)
        self.history.append({"text": text})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        if len(self.notifications) > MAX_VISIBLE:
            self.notifications = self.notifications[-MAX_VISIBLE:]
        self._render_notifications()

    def toggle_history(self) -> None:
        """Toggle: if notifications are showing, hide them. If hidden, show history."""
        if self.notifications and not self._manually_hidden:
            self.notifications.clear()
            self._manually_hidden = True
        else:
            self._manually_hidden = False
            now = time.time()
            recent = self.history[-MAX_VISIBLE:]
            self.notifications = [
                {"text": n["text"], "duration": 5, "start_time": now}
                for n in recent
            ]
        self._render_notifications()

    def show_history(self) -> None:
        self.toggle_history()

    def game_tick(self, dt: float) -> None:
        """Periodic cleanup driven by the game loop."""
        if self._manually_hidden or not self.notifications:
            return
        self._cleanup_accumulator += dt
        if self._cleanup_accumulator < CLEANUP_INTERVAL:
            return
        self._cleanup_accumulator = 0.0
        now = time.time()
        before = len(self.notifications)
        self.notifications = [
            n for n in self.notifications
            if now - n["start_time"] < n["duration"]
        ]
        if len(self.notifications) != before:
            self._render_notifications()

    def _render_notifications(self) -> None:
        if not self.notifications:
            self.update("")
        else:
            self.update("\n".join(n["text"] for n in self.notifications))

    def render(self) -> str:
        if not self.notifications:
            return ""
        return "\n".join(n["text"] for n in self.notifications)

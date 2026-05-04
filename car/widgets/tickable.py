"""Game-tick driven widget updates.

Widgets that need periodic updates during gameplay should inherit from
GameTickable and implement ``game_tick(dt)``. The WorldScreen calls
``tick_widgets(dt)`` once per frame, which fans out to all GameTickable
children — no per-widget ``set_interval`` timers needed.

Usage::

    from car.widgets.tickable import GameTickable

    class MyWidget(Static, GameTickable):
        def game_tick(self, dt: float) -> None:
            # dt is seconds since last frame (~0.033 at 30fps).
            # Use accumulators for sub-frame rates:
            self._my_timer += dt
            if self._my_timer >= 0.5:   # run every 0.5s
                self._my_timer = 0.0
                self._do_periodic_work()

When to use game_tick vs set_interval:
  - Gameplay widgets on WorldScreen → game_tick (pauses when game pauses)
  - Menu/screen-scoped animations  → set_interval (dies with the screen)
  - Mini-game widgets              → set_interval (own lifecycle)
"""


class GameTickable:
    """Mixin for widgets that receive game loop ticks."""

    def game_tick(self, dt: float) -> None:
        """Called once per game frame. Override in subclasses.

        Args:
            dt: Seconds elapsed since the last frame (~0.033 at 30fps).
        """
        pass

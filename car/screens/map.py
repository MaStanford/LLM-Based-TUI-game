from textual.screen import ModalScreen
from textual.binding import Binding
from ..widgets.map_view import MapView
import time

# Brief cooldown after mounting to ignore key repeats from the press that opened this screen
_MOUNT_COOLDOWN = 0.25

class MapScreen(ModalScreen):
    """The map screen."""

    _mount_time: float = 0.0

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("m", "toggle_city_mode", "City/World", show=True),
        Binding("up", "scroll_map(0, -1)", "Scroll", show=False),
        Binding("down", "scroll_map(0, 1)", "Scroll", show=False),
        Binding("left", "scroll_map(-1, 0)", "Scroll", show=False),
        Binding("right", "scroll_map(1, 0)", "Scroll", show=False),
        Binding("w", "nav_node(0, -1)", "Up", show=True),
        Binding("s", "nav_node(0, 1)", "Down", show=True),
        Binding("a", "nav_node(-1, 0)", "Left", show=True),
        Binding("d", "nav_node(1, 0)", "Right", show=True),
        Binding("c", "center_map", "Center", show=True),
        Binding("enter", "select", "Select", show=True),
        Binding("f", "fast_travel", "Fast Travel", show=True),
    ]

    def compose(self):
        """Compose the layout of the screen."""
        yield MapView(game_state=self.app.game_state, world=self.app.world)

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self._mount_time = time.time()
        self.query_one(MapView).focus()

    def _past_cooldown(self) -> bool:
        """Check if enough time has passed since mount to accept input."""
        return time.time() - self._mount_time >= _MOUNT_COOLDOWN

    def action_go_back(self) -> None:
        """Go back: in city mode return to world map, otherwise close."""
        map_view = self.query_one(MapView)
        if map_view.city_mode:
            map_view.toggle_city_mode()
        else:
            self.app.pop_screen()

    def action_scroll_map(self, dx: int, dy: int) -> None:
        """Scroll the map."""
        if not self._past_cooldown():
            return
        self.query_one(MapView).move_camera(dx, dy)

    def action_nav_node(self, dx: int, dy: int) -> None:
        """Navigate to the nearest node in the given direction."""
        if not self._past_cooldown():
            return
        self.query_one(MapView).nav_to_nearest_node(dx, dy)

    def action_center_map(self) -> None:
        """Center the map on the player."""
        self.query_one(MapView).center_on_player()

    def action_toggle_city_mode(self) -> None:
        """Toggle between world map and city map."""
        if not self._past_cooldown():
            return
        self.query_one(MapView).toggle_city_mode()

    def action_select(self) -> None:
        """In world mode: open city view for cities, set waypoint for landmarks. In city mode: set waypoint."""
        map_view = self.query_one(MapView)
        if map_view.city_mode:
            map_view.select_waypoint()
            self.app.pop_screen()
        else:
            # Check if selected node is a city — if so, open city view; otherwise set compass
            node = None
            if 0 <= map_view.selected_node_index < len(map_view.world_nodes):
                node = map_view.world_nodes[map_view.selected_node_index]
            if node and node["type"] == "city":
                map_view.open_selected_city()
            else:
                map_view.select_waypoint()
                self.app.pop_screen()

    def action_fast_travel(self) -> None:
        """Fast travel to the selected visited city."""
        if not self._past_cooldown():
            return
        map_view = self.query_one(MapView)
        success, message = map_view.fast_travel()
        if success:
            self.app.pop_screen()
            # Post notification to the world screen
            try:
                for screen in self.app.screen_stack:
                    try:
                        notif = screen.query_one("#notifications")
                        notif.add_notification(message)
                        break
                    except Exception:
                        continue
            except Exception:
                pass
        else:
            # Show failure message as a notification on the map (brief flash)
            self.notify(message, severity="warning")

    def on_unmount(self) -> None:
        """Called when the screen is unmounted."""
        self.app.start_game_loop()

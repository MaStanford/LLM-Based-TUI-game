import math
import logging
import time

from rich.style import Style
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.containers import Horizontal, Vertical, Container

from ..data.game_constants import CITY_SPACING, CITY_SIZE
from ..widgets.entity_modal import EntityModal
from ..widgets.hud_stats import StatsHUD
from ..widgets.hud_location import HudLocation
from ..widgets.hud_compass import CompassHUD
from ..widgets.hud_quest import QuestHUD
from ..widgets.hud_weapons import WeaponHUD
from ..widgets.game_view import GameView
from ..widgets.notifications import Notifications
from ..widgets.fps_counter import FPSCounter
from ..world.generation import get_city_name, does_city_exist_at
from ..logic.spawning import spawn_initial_entities
from ..logic.debug_commands import execute_command
from ..widgets.debug_console import DebugConsole
from .inventory import InventoryScreen
from .pause_menu import PauseScreen
from .map import MapScreen
from .faction import FactionScreen
from .quest_detail import QuestDetailScreen
from .story import StoryScreen

from textual.events import Key
from textual.binding import Binding

# --- Input Constants ---
# Keys that are tracked for continuous (hold-to-act) input.
# These are handled via on_key + staleness expiry, NOT Textual bindings,
# so that multiple gameplay keys can be held simultaneously.
GAMEPLAY_KEYS = {"a", "d", "space", "left", "right"}  # continuous keys (binary hold)
PEDAL_KEYS = {"w", "s"}  # pedal keys (event-driven steps, not per-frame ramp)
KEY_STALE_THRESHOLD = 0.15  # seconds — if no repeat event arrives within this window, the key is considered released
PEDAL_STEP = 0.10           # pedal change per key event (terminal repeat provides hold behavior)

# One-shot keys for menu/UI actions.
# Handled directly in on_key for reliability (bypasses binding dispatch lag).
ONE_SHOT_ACTIONS = {
    "escape": "toggle_pause",
    "i": "toggle_inventory",
    "tab": "cycle_quest",
    "m": "show_map",
    "f": "show_factions",
    "q": "show_quests",
    "j": "show_story",
    "x": "toggle_mouse_aim",
    "enter": "show_notifications",
    "grave_accent": "toggle_console",
    "tilde": "toggle_console",
}

class WorldScreen(Screen):
    """The default screen for the game."""

    _pressed_keys: dict = {}  # key_name -> last_event_timestamp (reset in on_mount)

    # Only one-shot menu/UI keys use Textual bindings for footer display.
    # Gameplay keys (WASD, space, arrows) are handled by on_key + process_input.
    # Menu keys are ALSO handled directly in on_key for reliability.
    # Gameplay hints are hidden from footer to avoid overflow — only menu keys shown.
    BINDINGS = [
        Binding("w", "noop", "Accelerate", show=False),
        Binding("s", "noop", "Brake", show=False),
        Binding("a", "noop", "Turn Left", show=False),
        Binding("d", "noop", "Turn Right", show=False),
        Binding("left", "noop", "Aim Left", show=False),
        Binding("right", "noop", "Aim Right", show=False),
        Binding("space", "noop", "Fire", show=False),
        Binding("escape", "toggle_pause", "Pause", show=True),
        Binding("tab", "cycle_quest", "Next Quest", show=True),
        Binding("i", "toggle_inventory", "Inventory", show=True),
        Binding("m", "show_map", "Map", show=True),
        Binding("f", "show_factions", "Factions", show=True),
        Binding("q", "show_quests", "Quests", show=True),
        Binding("j", "show_story", "Journal", show=True),
        Binding("enter", "show_notifications", "Show Log", show=False),
        Binding("grave_accent", "toggle_console", "Console", show=False),
        Binding("tilde", "toggle_console", "~ Console", show=False),
    ]

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self._pressed_keys = {}  # key_name -> last_event_timestamp (gameplay)
        self._oneshot_active = {}  # key_name -> last_event_timestamp (menu keys, for debounce)
        self._last_location_name = None  # Track city transitions for entrance banner
        self.focus()
        gs = self.app.game_state

        # Synchronize the player car's entity position with the game state's world position
        gs.player_car.x = gs.car_world_x
        gs.player_car.y = gs.car_world_y

        # Spawn an initial batch of entities
        spawn_initial_entities(gs, self.app.world)

        # Hide FPS counter if not in dev mode
        if not self.app.dev_mode:
            self.query_one("#fps_counter").display = False

    def on_screen_resume(self) -> None:
        """Called when the screen is resumed."""
        self._pressed_keys = {}  # Clear stale keys from before the menu
        # Seed one-shot debounce with current time so lingering key repeats
        # (e.g. Escape still held from closing the pause menu) are ignored.
        now = time.time()
        self._oneshot_active = {k: now for k in ONE_SHOT_ACTIONS}
        for d in "123456789":
            self._oneshot_active[d] = now
        self.app.game_state.pause_menu_open = False
        self.app.game_state.menu_open = False
        self.focus()
        self.app.start_game_loop()

        # Update FPS counter visibility in case Dev Mode changed
        fps_counter = self.query_one("#fps_counter")
        if fps_counter:
            fps_counter.display = self.app.dev_mode

    def on_key(self, event: Key) -> None:
        """Handle all gameplay input directly for reliability.

        Continuous keys (arrows, space) are tracked by timestamp for
        hold-to-act behavior. Pedal keys (W/S) apply a fixed step per
        event — terminal key repeat provides natural hold-to-ramp.
        One-shot keys (menus, toggles) are debounced.
        """
        now = time.time()

        if event.key in PEDAL_KEYS:
            gs = self.app.game_state
            if event.key == "w":
                gs.pedal_position = min(1.0, gs.pedal_position + PEDAL_STEP)
            elif event.key == "s":
                gs.pedal_position = max(-1.0, gs.pedal_position - PEDAL_STEP)
        elif event.key in GAMEPLAY_KEYS:
            self._pressed_keys[event.key] = now
        elif event.key in ONE_SHOT_ACTIONS:
            # Debounce: only fire if this key wasn't already held
            last = self._oneshot_active.get(event.key, 0)
            if now - last > KEY_STALE_THRESHOLD:
                action_name = ONE_SHOT_ACTIONS[event.key]
                getattr(self, f"action_{action_name}")()
            self._oneshot_active[event.key] = now
            event.prevent_default()
        elif event.key.isdigit() and 1 <= int(event.key) <= 9:
            last = self._oneshot_active.get(event.key, 0)
            if now - last > KEY_STALE_THRESHOLD:
                self.action_toggle_weapon(int(event.key))
            self._oneshot_active[event.key] = now
            event.prevent_default()

    def process_input(self, dt: float) -> None:
        """Called each game tick to translate held keys into game actions.

        This replaces the old per-key Textual binding actions for gameplay keys.
        All gameplay keys can now be held simultaneously.
        """
        gs = self.app.game_state
        now = time.time()

        # Expire stale keys (no repeat event within threshold = key released)
        self._pressed_keys = {
            k: t for k, t in self._pressed_keys.items()
            if now - t < KEY_STALE_THRESHOLD
        }

        # --- Turning (continuous, dt-scaled via vehicle_movement.py) ---
        gs.actions["turn_left"] = "a" in self._pressed_keys
        gs.actions["turn_right"] = "d" in self._pressed_keys

        # --- Pedal is set directly by on_key events (no per-frame ramp) ---

        # --- Firing (continuous while held, gated by weapon cooldowns) ---
        gs.actions["fire"] = "space" in self._pressed_keys

        # --- Weapon Aiming (continuous swivel, stat-based) ---
        if gs.mouse_aim_enabled:
            # Mouse aim: rotate weapon_angle_offset toward mouse at swivel speed
            dx = gs.mouse_aim_world_x - gs.car_world_x
            dy = gs.mouse_aim_world_y - gs.car_world_y
            target_world_angle = math.atan2(dy, dx) + math.pi / 2  # convert to game coords (0=N)
            desired_offset = (target_world_angle - gs.car_angle + math.pi) % (2 * math.pi) - math.pi
            delta = (desired_offset - gs.weapon_angle_offset + math.pi) % (2 * math.pi) - math.pi
            max_step = gs.weapon_aim_speed * dt
            if abs(delta) <= max_step:
                gs.weapon_angle_offset = desired_offset
            elif delta > 0:
                gs.weapon_angle_offset += max_step
            else:
                gs.weapon_angle_offset -= max_step
        else:
            # Keyboard aim
            if "left" in self._pressed_keys:
                gs.weapon_angle_offset -= gs.weapon_aim_speed * dt
            if "right" in self._pressed_keys:
                gs.weapon_angle_offset += gs.weapon_aim_speed * dt

    # --- One-shot menu actions (still use Textual bindings) ---

    def action_noop(self) -> None:
        """No-op action for gameplay keys displayed in footer.
        Actual input is handled by on_key + process_input."""
        pass

    def action_toggle_mouse_aim(self) -> None:
        """Toggle mouse aim on/off."""
        gs = self.app.game_state
        gs.mouse_aim_enabled = not gs.mouse_aim_enabled
        state = "ON" if gs.mouse_aim_enabled else "OFF"
        notifications = self.query_one("#notifications", Notifications)
        notifications.add_notification(f"Mouse Aim: {state}")

    def action_toggle_weapon(self, slot: int) -> None:
        """Toggle weapon on/off by slot number (1-indexed)."""
        gs = self.app.game_state
        point_names = list(gs.mounted_weapons.keys())
        idx = slot - 1
        if idx < 0 or idx >= len(point_names):
            return
        point_name = point_names[idx]
        current = gs.weapon_enabled.get(point_name, True)
        gs.weapon_enabled[point_name] = not current
        weapon = gs.mounted_weapons.get(point_name)
        weapon_label = weapon.name if weapon else "Empty"
        state = "ON" if not current else "OFF"
        notifications = self.query_one("#notifications", Notifications)
        notifications.add_notification(f"[{slot}] {weapon_label}: {state}")

    def action_toggle_pause(self) -> None:
        """Toggle the pause menu."""
        if self.app.game_state.pause_menu_open:
            self.app.pop_screen()
        else:
            self.app.stop_game_loop()
            self.app.game_state.pause_menu_open = True
            self.app.push_screen(PauseScreen())

    def action_toggle_inventory(self) -> None:
        """Toggle the inventory screen."""
        if self.app.game_state.menu_open:
            self.app.pop_screen()
        else:
            self.app.game_state.menu_open = True
            self.app.push_screen(InventoryScreen())

    def action_show_map(self) -> None:
        """Pushes the map screen."""
        self.app.stop_game_loop()
        self.app.push_screen(MapScreen())

    def action_show_factions(self) -> None:
        """Pushes the faction screen."""
        self.app.push_screen(FactionScreen())

    def action_show_quests(self) -> None:
        """Pushes the quest detail screen."""
        self.app.push_screen(QuestDetailScreen())

    def action_cycle_quest(self) -> None:
        """Cycle to the next active quest and update compass."""
        gs = self.app.game_state
        if not gs.active_quests:
            return
        gs.selected_quest_index = (gs.selected_quest_index + 1) % len(gs.active_quests)
        quest = gs.active_quests[gs.selected_quest_index]
        from ..logic.quest_logic import get_quest_target_location
        tx, ty, label = get_quest_target_location(quest, gs)
        if tx is not None:
            gs.waypoint = {"x": tx, "y": ty, "name": label or quest.name}
        notifications = self.query_one("#notifications", Notifications)
        notifications.add_notification(f"Tracking: {quest.name}")
        quest_hud = self.query_one("#quest_hud", QuestHUD)
        quest_hud.selected_index = gs.selected_quest_index

    def action_show_story(self) -> None:
        """Pushes the story journal screen."""
        self.app.push_screen(StoryScreen())

    def action_show_notifications(self) -> None:
        """Re-show recent notification history."""
        self.query_one("#notifications", Notifications).show_history()

    def action_toggle_console(self) -> None:
        """Toggle the debug console (dev mode only)."""
        if not self.app.dev_mode:
            self.notify("Console requires dev mode", severity="warning")
            return
        existing = self.query("#debug_console")
        if existing:
            existing.first().remove()
        else:
            self.mount(DebugConsole())
            self.notify("Debug console opened")

    def on_debug_console_command_submitted(self, event: DebugConsole.CommandSubmitted) -> None:
        """Handle a submitted debug command."""
        result = execute_command(self.app.game_state, self.app.world, event.command)
        notifications = self.query_one("#notifications", Notifications)
        for line in result.split("\n"):
            notifications.add_notification(line)

    def compose(self):
        """Compose the layout of the screen."""
        yield GameView(id="game_view", game_state=self.app.game_state, world=self.app.world)

        with Vertical(id="top_hud"):
            yield FPSCounter(id="fps_counter")
            yield HudLocation(id="location_hud")
            yield CompassHUD(id="compass_hud")
            yield Notifications(id="notifications")

        with Vertical(id="right_hud"):
            yield WeaponHUD(id="weapon_hud")
            yield Static("", id="right_spacer")
            yield EntityModal(id="entity_modal")

        with Horizontal(id="bottom_hud"):
            yield QuestHUD(id="quest_hud")
            yield StatsHUD(id="stats_hud")

        yield Footer(show_command_palette=True)

    def update_widgets(self):
        """Update the screen widgets."""
        game_view = self.query_one("#game_view", GameView)
        game_view.refresh()

        gs = self.app.game_state

        stats_hud = self.query_one("#stats_hud", StatsHUD)
        stats_hud.cash = gs.player_cash
        stats_hud.durability = int(gs.current_durability)
        stats_hud.max_durability = int(gs.max_durability)
        stats_hud.gas = gs.current_gas
        stats_hud.gas_capacity = int(gs.gas_capacity)
        stats_hud.speed = gs.car_speed
        stats_hud.level = gs.player_level
        stats_hud.xp = gs.current_xp
        stats_hud.xp_to_next_level = gs.xp_to_next_level
        stats_hud.pedal_position = gs.pedal_position

        # Update Weapon HUD
        weapon_hud = self.query_one("#weapon_hud", WeaponHUD)
        weapons_info = []
        for slot_idx, (point_name, weapon) in enumerate(gs.mounted_weapons.items(), start=1):
            point_data = gs.attachment_points.get(point_name, {})
            mount_label = point_data.get("name", point_name)
            enabled = gs.weapon_enabled.get(point_name, True)
            if weapon:
                weapons_info.append({
                    "mount_name": mount_label,
                    "weapon_name": weapon.name,
                    "ammo_type": weapon.ammo_type,
                    "ammo": gs.ammo_counts.get(weapon.ammo_type, 0),
                    "empty": False,
                    "enabled": enabled,
                    "slot": slot_idx,
                })
            else:
                weapons_info.append({
                    "mount_name": mount_label,
                    "weapon_name": "",
                    "ammo_type": "",
                    "ammo": 0,
                    "empty": True,
                    "enabled": enabled,
                    "slot": slot_idx,
                })
        weapon_hud.weapons_data = weapons_info

        quest_hud = self.query_one("#quest_hud", QuestHUD)
        quest_hud.quest_names = [q.name for q in gs.active_quests]
        quest_hud.selected_index = gs.selected_quest_index

        # Update Location HUD with proper city detection
        location = self.query_one("#location_hud", HudLocation)
        grid_x = round(gs.car_world_x / CITY_SPACING)
        grid_y = round(gs.car_world_y / CITY_SPACING)
        city_center_x = grid_x * CITY_SPACING
        city_center_y = grid_y * CITY_SPACING
        half_city = CITY_SIZE / 2

        # Check if player is actually inside a city
        in_city = (does_city_exist_at(grid_x, grid_y, self.app.world.seed, gs.factions)
                   and abs(gs.car_world_x - city_center_x) < half_city
                   and abs(gs.car_world_y - city_center_y) < half_city)

        if in_city:
            location_name = get_city_name(grid_x, grid_y, gs.factions, gs.world_details)
        else:
            from ..world.generation import get_city_faction
            faction_id = get_city_faction(gs.car_world_x, gs.car_world_y, gs.factions)
            location_name = gs.factions.get(faction_id, {}).get("name", "The Wasteland")

        location.update_location(location_name, int(gs.car_world_x), int(gs.car_world_y))

        # City entrance banner
        if location_name != self._last_location_name:
            if in_city and self._last_location_name is not None:
                notifications = self.query_one("#notifications", Notifications)
                notifications.add_notification(
                    f"── Entering {location_name} ──", duration=4
                )
            self._last_location_name = location_name

        compass = self.query_one("#compass_hud", CompassHUD)
        compass.absolute_bearing = gs.compass_info["absolute_bearing"]
        compass.target_name = gs.compass_info["target_name"]

        # Update Entity Modal (always visible)
        entity_modal = self.query_one("#entity_modal", EntityModal)
        closest_entity = gs.closest_entity_info
        if closest_entity:
            entity_modal.entity_name = closest_entity["name"]
            entity_modal.hp = closest_entity["hp"]
            entity_modal.max_hp = closest_entity["max_hp"]
            entity_modal.art = closest_entity["art"]
            entity_modal.description = closest_entity.get("description", "")
            # Compute bearing from player to target entity
            dx = closest_entity["x"] - gs.car_world_x
            dy = closest_entity["y"] - gs.car_world_y
            angle = math.atan2(dy, dx)
            entity_modal.bearing = (math.degrees(angle) + 90) % 360
        else:
            entity_modal.entity_name = "No Target"
            entity_modal.hp = 0
            entity_modal.max_hp = 0
            entity_modal.art = []
            entity_modal.bearing = -1.0
            entity_modal.description = ""

        # Handle explosions — add to game_state for canvas-based rendering
        for destroyed in gs.destroyed_this_frame:
            art = destroyed.get_static_art()
            gs.active_explosions.append({
                "x": destroyed.x,
                "y": destroyed.y,
                "art": [list(row) for row in art],
                "original_art": [list(row) for row in art],
                "styles": [[Style() for _ in row] for row in art],
                "step": 0,
                "total_steps": 10,
                "last_update": time.time(),
            })
            # Show destruction feedback in entity modal
            entity_modal.destroyed_name = getattr(destroyed, "name", destroyed.__class__.__name__.replace("_", " ").title())
            entity_modal.destroyed_timer = time.time()
        gs.destroyed_this_frame.clear()

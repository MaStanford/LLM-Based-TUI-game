from textual.widget import Widget
from rich.text import Text
from rich.style import Style
from ..data.game_constants import CITY_SPACING, CITY_SIZE
from ..world.generation import does_city_exist_at, get_buildings_in_city, get_city_name
from ..data.buildings import BUILDING_DATA
import time
import random
import math

# Color mapping for building types on the city map
_BUILDING_STYLES = {
    "mechanic_shop": Style(color="rgb(255,140,0)", bold=True),   # Orange
    "gas_station":   Style(color="rgb(0,200,200)", bold=True),   # Teal
    "weapon_shop":   Style(color="rgb(0,255,0)", bold=True),     # Green
    "city_hall":     Style(color="rgb(255,255,0)", bold=True),   # Yellow
}
_BUILDING_LABELS = {
    "mechanic_shop": "REPAIR",
    "gas_station":   "GAS",
    "weapon_shop":   "AMMO",
    "city_hall":     "HALL",
}
_GENERIC_STYLE = Style(color="rgb(160,160,160)")
_DAMAGED_STYLE = Style(color="rgb(255,165,0)")   # Orange for damaged
_RUBBLE_STYLE = Style(color="rgb(100,100,90)")    # Grey for destroyed


class MapView(Widget):
    """A widget to display the world map or city map."""
    can_focus = True
    WORLD_MAP_SCALE = 80  # World units per screen character

    def __init__(self, game_state, world, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_state = game_state
        self.world = world
        self.camera_x = 0
        self.camera_y = 0
        self.map_data = {}
        self.blink_state = True
        self.cached_map = None
        self.cached_styles = None
        self.city_mode = False
        self.city_grid_x = 0
        self.city_grid_y = 0
        self.world_nodes = []       # List of node dicts with x, y, short_name, long_name, type, grid_x, grid_y
        self.selected_node_index = -1  # -1 = no selection

    def on_mouse_down(self, event) -> None:
        """Start drag tracking."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._drag_camera_x = self.camera_x
        self._drag_camera_y = self.camera_y
        self._dragged = False

    def on_mouse_move(self, event) -> None:
        """Pan the map while dragging."""
        if not hasattr(self, "_drag_start_x") or self._drag_start_x is None:
            return
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        if abs(dx) > 1 or abs(dy) > 1:
            self._dragged = True
        if self.city_mode:
            return
        scale = self.WORLD_MAP_SCALE
        self.camera_x = self._drag_camera_x - dx * scale
        self.camera_y = self._drag_camera_y - dy * scale
        self.refresh()

    def on_mouse_up(self, event) -> None:
        """End drag. If it was a click (no drag), select/open the clicked node."""
        dragged = getattr(self, "_dragged", False)
        self._drag_start_x = None

        if dragged:
            return

        if self.city_mode:
            self._handle_city_click(event.x, event.y)
        else:
            self._handle_world_click(event.x, event.y)

    def _handle_world_click(self, sx, sy):
        """Select the node nearest to the click. Double-click (already selected) opens city."""
        if not self.world_nodes:
            return
        w, h = self.size
        scale = self.WORLD_MAP_SCALE
        click_world_x = self.camera_x + (sx - w / 2) * scale
        click_world_y = self.camera_y + (sy - h / 2) * scale

        best_i = -1
        best_dist = float("inf")
        click_radius = 3 * scale

        for i, node in enumerate(self.world_nodes):
            d = (node["x"] - click_world_x) ** 2 + (node["y"] - click_world_y) ** 2
            if d < best_dist and d < click_radius ** 2:
                best_dist = d
                best_i = i

        if best_i >= 0:
            if best_i == self.selected_node_index:
                node = self.world_nodes[best_i]
                if node["type"] == "city":
                    self.open_selected_city()
                    return
            self.selected_node_index = best_i
            self.refresh()

    def _handle_city_click(self, sx, sy):
        """In city view, click a building to set a waypoint to it."""
        w, h = self.size
        margin_x, margin_y = 2, 2
        draw_w = w - margin_x * 2
        draw_h = h - margin_y * 2
        if draw_w <= 0 or draw_h <= 0:
            return

        scale_x = CITY_SIZE / draw_w
        scale_y = CITY_SIZE / draw_h
        gx, gy = self.city_grid_x, self.city_grid_y
        city_min_x = gx * CITY_SPACING - CITY_SIZE // 2
        city_min_y = gy * CITY_SPACING - CITY_SIZE // 2

        click_wx = city_min_x + (sx - margin_x) * scale_x
        click_wy = city_min_y + (sy - margin_y) * scale_y

        self.game_state.waypoint = {
            "x": click_wx,
            "y": click_wy,
            "name": get_city_name(gx, gy, self.game_state.factions, self.game_state.world_details),
        }
        self.refresh()

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.camera_x = self.game_state.car_world_x
        self.camera_y = self.game_state.car_world_y
        w, h = self.size
        self.cached_map = [[' ' for _ in range(w)] for _ in range(h)]
        self.cached_styles = [[Style() for _ in range(w)] for _ in range(h)]
        self._generate_map_chunk()
        self._build_node_list()
        self.blink_timer = self.set_interval(0.5, self.toggle_blink)

    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        self.blink_timer.stop()

    def toggle_blink(self) -> None:
        """Toggle the blink state for the player marker."""
        self.blink_state = not self.blink_state
        self.refresh()

    def toggle_city_mode(self) -> None:
        """Toggle between world map and city map."""
        self.city_mode = not self.city_mode
        if self.city_mode:
            # Snap to the nearest city grid
            self.city_grid_x = round(self.game_state.car_world_x / CITY_SPACING)
            self.city_grid_y = round(self.game_state.car_world_y / CITY_SPACING)
        self.refresh()

    def move_camera(self, dx: int, dy: int):
        """Move the camera."""
        if self.city_mode:
            # In city mode, arrow keys cycle between cities
            self.city_grid_x += dx
            self.city_grid_y += dy
        else:
            self.camera_x += dx * 80
            self.camera_y += dy * 80
            self.selected_node_index = -1
        self.refresh()

    def center_on_player(self):
        """Re-center the map on the player."""
        self.camera_x = self.game_state.car_world_x
        self.camera_y = self.game_state.car_world_y
        if self.city_mode:
            self.city_grid_x = round(self.camera_x / CITY_SPACING)
            self.city_grid_y = round(self.camera_y / CITY_SPACING)
        self.selected_node_index = -1
        self.refresh()

    def _build_node_list(self):
        """Build a list of all selectable nodes (cities + landmarks) with short/long names."""
        gs = self.game_state
        nodes = []

        # Add cities: short_name is city name, long_name includes faction info
        for (gx_jitter, gy_jitter), (symbol, orig_gx, orig_gy) in self.map_data.items():
            city_world_x = orig_gx * CITY_SPACING
            city_world_y = orig_gy * CITY_SPACING
            city_name = get_city_name(orig_gx, orig_gy, gs.factions, gs.world_details)

            # Build long description from faction data
            long_desc = city_name
            for fid, fdata in gs.factions.items():
                if fdata.get("hub_city_coordinates") == (orig_gx, orig_gy):
                    long_desc = f"{city_name} -- Capital of {fdata.get('name', 'Unknown')}"
                    break

            nodes.append({
                "x": city_world_x,
                "y": city_world_y,
                "short_name": city_name,
                "long_name": long_desc,
                "type": "city",
                "grid_x": orig_gx,
                "grid_y": orig_gy,
            })

        # Add landmarks
        if gs.world_details and "landmarks" in gs.world_details:
            for landmark in gs.world_details["landmarks"]:
                try:
                    lx, ly = landmark["x"], landmark["y"]
                    short = landmark.get("name", "Landmark")
                    desc = landmark.get("description", short)
                    nodes.append({
                        "x": lx,
                        "y": ly,
                        "short_name": short,
                        "long_name": f"{short} -- {desc}" if desc != short else short,
                        "type": "landmark",
                        "grid_x": None,
                        "grid_y": None,
                    })
                except (ValueError, KeyError):
                    continue

        self.world_nodes = nodes

        # Set initial selection: nearest city to the player (don't move camera)
        self.selected_node_index = -1
        if nodes:
            px, py = gs.car_world_x, gs.car_world_y
            best_i = 0
            best_dist = float('inf')
            for i, node in enumerate(nodes):
                if node["type"] == "city":
                    d = (node["x"] - px) ** 2 + (node["y"] - py) ** 2
                    if d < best_dist:
                        best_dist = d
                        best_i = i
            self.selected_node_index = best_i

    def nav_to_nearest_node(self, dx: int, dy: int):
        """Navigate to the nearest node in the given direction from the current selection."""
        if not self.world_nodes:
            return

        # Get origin point
        if 0 <= self.selected_node_index < len(self.world_nodes):
            origin = self.world_nodes[self.selected_node_index]
            ox, oy = origin["x"], origin["y"]
        else:
            ox, oy = self.game_state.car_world_x, self.game_state.car_world_y

        best_i = -1
        best_score = float('inf')

        for i, node in enumerate(self.world_nodes):
            if i == self.selected_node_index:
                continue

            rel_x = node["x"] - ox
            rel_y = node["y"] - oy

            # Check if this node is in the requested direction
            # dx/dy define the direction: (0,-1)=up, (0,1)=down, (-1,0)=left, (1,0)=right
            if dx != 0:
                # Horizontal: node must be in the correct x direction
                if dx > 0 and rel_x <= 0:
                    continue
                if dx < 0 and rel_x >= 0:
                    continue
            if dy != 0:
                # Vertical: node must be in the correct y direction
                if dy > 0 and rel_y <= 0:
                    continue
                if dy < 0 and rel_y >= 0:
                    continue

            # Score: distance, but penalize nodes that are far off the primary axis
            dist = math.sqrt(rel_x ** 2 + rel_y ** 2)
            if dist == 0:
                continue

            # Angle alignment: how well does the direction match?
            # For dx=1,dy=0 (right), ideal angle is 0. For dx=0,dy=-1 (up), ideal angle is -pi/2
            ideal_angle = math.atan2(dy, dx)
            actual_angle = math.atan2(rel_y, rel_x)
            angle_diff = abs(actual_angle - ideal_angle)
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff

            # Only consider nodes within 90 degrees of the direction
            if angle_diff > math.pi / 2:
                continue

            # Score: closer + more aligned = better
            score = dist * (1 + angle_diff)
            if score < best_score:
                best_score = score
                best_i = i

        if best_i >= 0:
            self.selected_node_index = best_i
            node = self.world_nodes[best_i]
            # Only move camera if the node is near the edge of the screen
            w, h = self.size
            scale = self.WORLD_MAP_SCALE
            screen_x = (node["x"] - self.camera_x) / scale + w / 2
            screen_y = (node["y"] - self.camera_y) / scale + h / 2
            margin_x = w * 0.25
            margin_y = h * 0.25
            if (screen_x < margin_x or screen_x > w - margin_x or
                    screen_y < margin_y or screen_y > h - margin_y):
                self.camera_x = node["x"]
                self.camera_y = node["y"]
            self.refresh()

    def open_selected_city(self):
        """Switch to city map mode for the currently selected node (if it's a city)."""
        if self.selected_node_index >= 0 and self.selected_node_index < len(self.world_nodes):
            node = self.world_nodes[self.selected_node_index]
            if node["type"] == "city" and node["grid_x"] is not None:
                self.city_grid_x = node["grid_x"]
                self.city_grid_y = node["grid_y"]
                self.city_mode = True
                self.refresh()
                return
        # Fallback: open the nearest city to the camera
        self.city_grid_x = round(self.camera_x / CITY_SPACING)
        self.city_grid_y = round(self.camera_y / CITY_SPACING)
        self.city_mode = True
        self.refresh()

    def select_waypoint(self):
        """Sets a waypoint to the selected node or nearest city."""
        if self.city_mode:
            self.game_state.waypoint = {
                "x": self.city_grid_x * CITY_SPACING,
                "y": self.city_grid_y * CITY_SPACING,
                "name": get_city_name(self.city_grid_x, self.city_grid_y, self.game_state.factions, self.game_state.world_details),
            }
            return

        # Use selected node if one is highlighted
        if self.selected_node_index >= 0 and self.selected_node_index < len(self.world_nodes):
            node = self.world_nodes[self.selected_node_index]
            self.game_state.waypoint = {
                "x": node["x"],
                "y": node["y"],
                "name": node["short_name"],
            }
            return

        # Fallback: nearest city to camera center
        min_dist = float('inf')
        closest_city_coords = None

        for (gx, gy), _ in self.map_data.items():
            city_world_x = gx * CITY_SPACING
            city_world_y = gy * CITY_SPACING
            dist = math.sqrt((self.camera_x - city_world_x)**2 + (self.camera_y - city_world_y)**2)

            if dist < min_dist:
                min_dist = dist
                closest_city_coords = (city_world_x, city_world_y)

        if closest_city_coords:
            self.game_state.waypoint = {
                "x": closest_city_coords[0],
                "y": closest_city_coords[1],
                "name": "Waypoint"
            }

    def fast_travel(self):
        """Attempt to fast travel to the selected city. Returns (success, message)."""
        gs = self.game_state

        # Determine target city
        target_gx, target_gy = None, None
        if self.city_mode:
            target_gx = self.city_grid_x
            target_gy = self.city_grid_y
        elif self.selected_node_index >= 0 and self.selected_node_index < len(self.world_nodes):
            node = self.world_nodes[self.selected_node_index]
            if node["type"] == "city" and node["grid_x"] is not None:
                target_gx = node["grid_x"]
                target_gy = node["grid_y"]

        if target_gx is None:
            return False, "No city selected."

        # Check if visited
        if (target_gx, target_gy) not in gs.visited_cities:
            return False, "You haven't visited this city yet."

        # Check if already there
        player_gx = round(gs.car_world_x / CITY_SPACING)
        player_gy = round(gs.car_world_y / CITY_SPACING)
        if target_gx == player_gx and target_gy == player_gy:
            return False, "You're already here."

        # Calculate gas cost based on distance
        target_wx = target_gx * CITY_SPACING
        target_wy = target_gy * CITY_SPACING
        dist = math.sqrt((gs.car_world_x - target_wx)**2 + (gs.car_world_y - target_wy)**2)
        gas_cost = dist * gs.gas_consumption_rate * 0.5  # Half the gas of driving there

        if gs.current_gas < gas_cost:
            return False, f"Not enough gas. Need {gas_cost:.0f}, have {gs.current_gas:.0f}."

        # Perform fast travel
        gs.current_gas -= gas_cost
        gs.car_world_x = float(target_wx)
        gs.car_world_y = float(target_wy)
        gs.car_speed = 0
        gs.car_velocity_x = 0
        gs.car_velocity_y = 0
        gs.pedal_position = 0.0
        gs.player_car.x = gs.car_world_x
        gs.player_car.y = gs.car_world_y

        # Clear enemies and obstacles (they'd be from the old location)
        gs.active_enemies.clear()
        gs.active_obstacles.clear()
        gs.active_fauna.clear()

        city_name = get_city_name(target_gx, target_gy, gs.factions, gs.world_details)
        return True, f"Fast traveled to {city_name}. Used {gas_cost:.0f} gas."


    def _generate_map_chunk(self):
        """Generates a large chunk of the map around the player."""
        gs = self.game_state
        chunk_size = 20000 # World units for the chunk

        center_grid_x = round(self.camera_x / CITY_SPACING)
        center_grid_y = round(self.camera_y / CITY_SPACING)

        grid_radius = int((chunk_size / 2) / CITY_SPACING)

        for gx in range(center_grid_x - grid_radius, center_grid_x + grid_radius):
            for gy in range(center_grid_y - grid_radius, center_grid_y + grid_radius):
                if does_city_exist_at(gx, gy, self.world.seed, gs.factions):
                    is_hub = any(faction.get("hub_city_coordinates") == (gx, gy) for faction in gs.factions.values())

                    local_random = random.Random(f"{self.world.seed}-{gx}-{gy}")
                    jitter_x = local_random.uniform(-0.3, 0.3)
                    jitter_y = local_random.uniform(-0.3, 0.3)

                    self.map_data[(gx + jitter_x, gy + jitter_y)] = ("★" if is_hub else "■", gx, gy)


    def render(self) -> Text:
        """Render the appropriate map mode."""
        if self.city_mode:
            return self._render_city()
        return self._render_world()

    def _render_city(self) -> Text:
        """Render the city-level map, scaled to fit the screen."""
        w, h = self.size
        gs = self.game_state
        gx, gy = self.city_grid_x, self.city_grid_y

        canvas = [[' ' for _ in range(w)] for _ in range(h)]
        styles = [[Style(bgcolor="rgb(20,20,20)") for _ in range(w)] for _ in range(h)]

        # City bounds in world coordinates
        city_center_x = gx * CITY_SPACING
        city_center_y = gy * CITY_SPACING
        half = CITY_SIZE // 2
        city_min_x = city_center_x - half
        city_min_y = city_center_y - half

        # Leave 2-char margin on each side for labels, 1 row for title
        margin_x = 2
        margin_y = 2
        draw_w = w - margin_x * 2
        draw_h = h - margin_y * 2

        if draw_w <= 0 or draw_h <= 0:
            return Text("Screen too small")

        # Scale: world units per screen character
        scale_x = CITY_SIZE / draw_w
        scale_y = CITY_SIZE / draw_h

        def world_to_screen(wx, wy):
            sx = int((wx - city_min_x) / scale_x) + margin_x
            sy = int((wy - city_min_y) / scale_y) + margin_y
            return sx, sy

        # Draw city ground
        for sy in range(margin_y, margin_y + draw_h):
            for sx in range(margin_x, margin_x + draw_w):
                canvas[sy][sx] = '.'
                styles[sy][sx] = Style(color="rgb(60,60,60)", bgcolor="rgb(20,20,20)")

        # Draw title
        city_name = get_city_name(gx, gy, gs.factions, gs.world_details)
        title = f"[ {city_name} ({gx * CITY_SPACING},{gy * CITY_SPACING}) ]"
        title_x = max(0, (w - len(title)) // 2)
        self._draw_text(canvas, styles, title_x, 0, title, Style(color="white", bold=True))

        # Draw mode hint
        hint = "Esc: World Map | Arrows: Scroll | C: Center | Enter: Set Waypoint | F: Fast Travel"
        hint_x = max(0, (w - len(hint)) // 2)
        self._draw_text(canvas, styles, hint_x, h - 1, hint, Style(color="rgb(100,100,100)"))

        # Get buildings
        buildings = get_buildings_in_city(gx, gy)

        # Check if any active quest targets this city (for City Hall flashing)
        quest_flash_style = None
        quest_flash_marker = None
        for quest in gs.active_quests:
            if quest.city_id == (gx, gy):
                if quest.ready_to_turn_in:
                    quest_flash_style = Style(color="green", bold=True)
                    quest_flash_marker = "?"
                    break  # Turn-in takes priority
                else:
                    quest_flash_style = Style(color="yellow", bold=True)
                    quest_flash_marker = "!"

        for idx, building in enumerate(buildings):
            btype = building.get("type", "GENERIC")
            bld_key = (gx, gy, idx)
            is_destroyed = bld_key in gs.destroyed_buildings

            # Get the label for minimum size calculation
            label = _BUILDING_LABELS.get(btype, building.get("name", "")[:8])
            # Minimum screen size: width = label + 2 (borders), height = 3 (border + label + border)
            # For damaged buildings with HP bar, need height 4
            min_w = len(label) + 2 if label else 3
            min_h = 4

            # Building screen rect
            bx1, by1 = world_to_screen(building['x'], building['y'])
            bx2, by2 = world_to_screen(building['x'] + building['w'], building['y'] + building['h'])

            # Enforce minimum screen size, expanding from center
            actual_w = bx2 - bx1
            actual_h = by2 - by1
            if actual_w < min_w:
                mid_x = (bx1 + bx2) // 2
                bx1 = mid_x - min_w // 2
                bx2 = bx1 + min_w
            if actual_h < min_h:
                mid_y = (by1 + by2) // 2
                by1 = mid_y - min_h // 2
                by2 = by1 + min_h

            # Clamp to drawable area
            bx1 = max(margin_x, min(bx1, margin_x + draw_w - 1))
            by1 = max(margin_y, min(by1, margin_y + draw_h - 1))
            bx2 = max(margin_x + 1, min(bx2, margin_x + draw_w))
            by2 = max(margin_y + 1, min(by2, margin_y + draw_h))

            if bx2 <= bx1 or by2 <= by1:
                continue

            if is_destroyed:
                # Draw rubble
                for sy in range(by1, by2):
                    for sx in range(bx1, bx2):
                        canvas[sy][sx] = '~'
                        styles[sy][sx] = _RUBBLE_STYLE
                # Label
                label = "RUBBLE"
                lx = bx1 + max(0, (bx2 - bx1 - len(label)) // 2)
                ly = by1 + (by2 - by1) // 2
                self._draw_text(canvas, styles, lx, ly, label, _RUBBLE_STYLE)
                continue

            # Check damage state
            is_damaged = bld_key in gs.damaged_buildings
            if is_damaged:
                max_hp = BUILDING_DATA.get(btype, {}).get("base_durability", 200)
                current_hp = gs.damaged_buildings[bld_key]
                hp_pct = current_hp / max_hp if max_hp > 0 else 1.0
            else:
                hp_pct = 1.0

            # Choose style based on type and damage
            if btype in _BUILDING_STYLES and hp_pct > 0.5:
                fill_style = _BUILDING_STYLES[btype]
            elif hp_pct <= 0.5:
                fill_style = _DAMAGED_STYLE
            else:
                fill_style = _GENERIC_STYLE

            # Flash City Hall border when a quest targets this city
            is_quest_flash = (btype == "city_hall" and quest_flash_style and self.blink_state)

            # Draw building outline
            for sy in range(by1, by2):
                for sx in range(bx1, bx2):
                    if sy == by1 or sy == by2 - 1 or sx == bx1 or sx == bx2 - 1:
                        # Border
                        if sy == by1 and sx == bx1:
                            canvas[sy][sx] = '┌'
                        elif sy == by1 and sx == bx2 - 1:
                            canvas[sy][sx] = '┐'
                        elif sy == by2 - 1 and sx == bx1:
                            canvas[sy][sx] = '└'
                        elif sy == by2 - 1 and sx == bx2 - 1:
                            canvas[sy][sx] = '┘'
                        elif sy == by1 or sy == by2 - 1:
                            canvas[sy][sx] = '─'
                        else:
                            canvas[sy][sx] = '│'
                        styles[sy][sx] = quest_flash_style if is_quest_flash else fill_style
                    else:
                        # Interior
                        canvas[sy][sx] = '░'
                        styles[sy][sx] = Style(color=fill_style.color, dim=True)

            # Draw label inside the building
            interior_w = bx2 - bx1 - 2
            if interior_w >= len(label) and by2 - by1 > 2:
                lx = bx1 + 1 + max(0, (interior_w - len(label)) // 2)
                ly = by1 + (by2 - by1) // 2
                self._draw_text(canvas, styles, lx, ly, label, Style(color="white", bold=True))
                # Draw quest marker next to City Hall label
                if btype == "city_hall" and quest_flash_marker:
                    marker_x = lx + len(label)
                    if marker_x < bx2 - 1:
                        canvas[ly][marker_x] = quest_flash_marker
                        styles[ly][marker_x] = quest_flash_style if quest_flash_style else fill_style

            # Show HP bar for damaged buildings
            if is_damaged and by2 - by1 > 3 and interior_w >= 3:
                bar_w = min(interior_w, 8)
                filled = max(1, int(hp_pct * bar_w))
                bar = '█' * filled + '░' * (bar_w - filled)
                bar_x = bx1 + 1 + max(0, (interior_w - bar_w) // 2)
                bar_y = by1 + (by2 - by1) // 2 + 1
                if bar_y < by2 - 1:
                    bar_color = "green" if hp_pct > 0.5 else "yellow" if hp_pct > 0.25 else "red"
                    self._draw_text(canvas, styles, bar_x, bar_y, bar, Style(color=bar_color))

        # Draw player position
        px, py = world_to_screen(gs.car_world_x, gs.car_world_y)
        if 0 <= py < h and 0 <= px < w:
            if self.blink_state:
                canvas[py][px] = '●'
                styles[py][px] = Style(color="red", bold=True)

        # Convert to Rich Text
        text = Text()
        for y, row in enumerate(canvas):
            for x, char in enumerate(row):
                text.append(char, styles[y][x])
            if y < h - 1:
                text.append("\n")
        return text

    def _render_world(self) -> Text:
        """Render the world-level map."""
        w, h = self.size

        canvas = [[' ' for _ in range(w)] for _ in range(h)]
        styles = [[Style(bgcolor="black") for _ in range(w)] for _ in range(h)]

        gs = self.game_state
        scale = self.WORLD_MAP_SCALE
        map_start_x = self.camera_x - (w / 2) * scale
        map_start_y = self.camera_y - (h / 2) * scale

        # Get selected node info for highlighting
        selected_node = None
        if 0 <= self.selected_node_index < len(self.world_nodes):
            selected_node = self.world_nodes[self.selected_node_index]

        # Draw Roads (L-shaped: horizontal then vertical segments)
        if gs.world_details and "roads" in gs.world_details:
            road_style = Style(color="rgb(80,70,40)", dim=True)
            for road in gs.world_details["roads"]:
                try:
                    from_x_str, from_y_str = road["from"].split(',')
                    to_x_str, to_y_str = road["to"].split(',')
                    from_gx, from_gy = int(from_x_str), int(from_y_str)
                    to_gx, to_gy = int(to_x_str), int(to_y_str)

                    from_wx = from_gx * CITY_SPACING
                    from_wy = from_gy * CITY_SPACING
                    to_wx = to_gx * CITY_SPACING
                    to_wy = to_gy * CITY_SPACING

                    sx1 = int((from_wx - map_start_x) / scale)
                    sy1 = int((from_wy - map_start_y) / scale)
                    sx2 = int((to_wx - map_start_x) / scale)
                    sy2 = int((to_wy - map_start_y) / scale)

                    # Draw horizontal segment first, then vertical
                    self._draw_line(canvas, styles, sx1, sy1, sx2, sy1, "·", road_style)
                    self._draw_line(canvas, styles, sx2, sy1, sx2, sy2, "·", road_style)
                except (ValueError, KeyError):
                    continue

        # Draw Landmarks
        if gs.world_details and "landmarks" in gs.world_details:
            for landmark in gs.world_details["landmarks"]:
                try:
                    lx, ly = landmark["x"], landmark["y"]
                    sx = int((lx - map_start_x) / scale)
                    sy = int((ly - map_start_y) / scale)

                    if 0 <= sy < h and 0 <= sx < w:
                        is_selected = (selected_node and selected_node["type"] == "landmark"
                                       and selected_node["x"] == lx and selected_node["y"] == ly)
                        short_name = landmark.get("name", "")
                        if is_selected:
                            canvas[sy][sx] = "◊"
                            styles[sy][sx] = Style(color="white", bold=True, bgcolor="magenta")
                            self._draw_text(canvas, styles, sx + 2, sy, short_name,
                                            Style(color="white", bold=True))
                        else:
                            canvas[sy][sx] = "◊"
                            styles[sy][sx] = Style(color="magenta", bold=True)
                            if short_name:
                                self._draw_text(canvas, styles, sx + 2, sy, short_name,
                                                Style(color="magenta"))
                except (ValueError, KeyError):
                    continue

        # Draw Cities
        for (gx, gy), (symbol, orig_gx, orig_gy) in self.map_data.items():
            city_world_x = orig_gx * CITY_SPACING
            city_world_y = orig_gy * CITY_SPACING

            sx = int((city_world_x - map_start_x) / scale)
            sy = int((city_world_y - map_start_y) / scale)

            if 0 <= sy < h and 0 <= sx < w:
                is_selected = (selected_node and selected_node["type"] == "city"
                               and selected_node["grid_x"] == orig_gx and selected_node["grid_y"] == orig_gy)
                is_visited = (orig_gx, orig_gy) in gs.visited_cities
                city_name = get_city_name(orig_gx, orig_gy, gs.factions, gs.world_details)
                if is_selected:
                    canvas[sy][sx] = symbol
                    styles[sy][sx] = Style(color="white", bold=True, bgcolor="cyan")
                    self._draw_text(canvas, styles, sx + 2, sy, city_name,
                                    Style(color="white", bold=True))
                elif is_visited:
                    canvas[sy][sx] = symbol
                    styles[sy][sx] = Style(color="green", bold=True)
                    self._draw_text(canvas, styles, sx + 2, sy, city_name,
                                    Style(color="green"))
                else:
                    canvas[sy][sx] = symbol
                    styles[sy][sx] = Style(color="rgb(100,100,100)")
                    self._draw_text(canvas, styles, sx + 2, sy, city_name,
                                    Style(color="rgb(100,100,100)"))

        # Draw Waypoint Marker
        quest_screen_pos = None
        if gs.waypoint:
            wp_sx = int((gs.waypoint["x"] - map_start_x) / scale)
            wp_sy = int((gs.waypoint["y"] - map_start_y) / scale)
            if 0 <= wp_sy < h - 1 and 0 <= wp_sx < w:
                wp_style = Style(color="rgb(255,100,255)", bold=True)
                canvas[wp_sy][wp_sx] = "⊕"
                styles[wp_sy][wp_sx] = wp_style
                wp_name = gs.waypoint.get("name", "Waypoint")
                self._draw_text(canvas, styles, wp_sx + 2, wp_sy, wp_name, wp_style)

        # Draw Quest Objective Markers
        if gs.active_quests:
            from ..logic.quest_logic import get_quest_target_location
            selected_idx = min(gs.selected_quest_index, len(gs.active_quests) - 1)
            for i, quest in enumerate(gs.active_quests):
                qt_x, qt_y, qt_label = get_quest_target_location(quest, gs)
                if qt_x is not None:
                    qsx = int((qt_x - map_start_x) / scale)
                    qsy = int((qt_y - map_start_y) / scale)
                    if 0 <= qsy < h - 1 and 0 <= qsx < w:
                        is_selected = (i == selected_idx)
                        if quest.ready_to_turn_in:
                            marker_char = "?"
                            marker_style = Style(color="green", bold=is_selected)
                        else:
                            marker_char = "!"
                            marker_style = Style(color="yellow" if is_selected else "rgb(120,120,60)", bold=is_selected)
                        canvas[qsy][qsx] = marker_char
                        styles[qsy][qsx] = marker_style
                        if qt_label and is_selected:
                            self._draw_text(canvas, styles, qsx + 2, qsy, qt_label, marker_style)

        # Draw Player
        player_x = int((self.game_state.car_world_x - map_start_x) / scale)
        player_y = int((self.game_state.car_world_y - map_start_y) / scale)
        if 0 <= player_y < h and 0 <= player_x < w:
            if self.blink_state:
                canvas[player_y][player_x] = "●"
                styles[player_y][player_x] = Style(color="red", bold=True)

        # Bottom bar: selected node info or hint
        if selected_node:
            # Show name and distance
            dist = math.sqrt((gs.car_world_x - selected_node["x"])**2 +
                             (gs.car_world_y - selected_node["y"])**2)
            dist_str = f"{dist:.0f}m" if dist < 10000 else f"{dist/1000:.1f}km"
            node_type_label = selected_node["type"].upper()
            # Show visited/fast travel status for cities
            ft_tag = ""
            if selected_node["type"] == "city" and selected_node["grid_x"] is not None:
                if (selected_node["grid_x"], selected_node["grid_y"]) in gs.visited_cities:
                    ft_tag = " [F: Fast Travel]"
                else:
                    ft_tag = " (Not Visited)"
            info = f" [{node_type_label}] {selected_node['long_name']}  --  {dist_str}{ft_tag} "
            idx_str = f" {self.selected_node_index + 1}/{len(self.world_nodes)} "
            # Draw info bar background
            for sx in range(w):
                canvas[h - 1][sx] = ' '
                styles[h - 1][sx] = Style(bgcolor="rgb(40,40,40)")
            self._draw_text(canvas, styles, 0, h - 1, info,
                            Style(color="white", bold=True, bgcolor="rgb(40,40,40)"))
            self._draw_text(canvas, styles, w - len(idx_str), h - 1, idx_str,
                            Style(color="rgb(150,150,150)", bgcolor="rgb(40,40,40)"))
        else:
            hint = "WASD: Navigate | Arrows: Scroll | M: City Map | Enter: View City | F: Fast Travel"
            hint_x = max(0, (w - len(hint)) // 2)
            self._draw_text(canvas, styles, hint_x, h - 1, hint, Style(color="rgb(100,100,100)"))

        # Convert to Rich Text
        text = Text()
        for y, row in enumerate(canvas):
            for x, char in enumerate(row):
                text.append(char, styles[y][x])
            if y < h - 1:
                text.append("\n")
        return text

    def _draw_text(self, canvas, styles, x, y, text, style):
        """Draws text onto the canvas."""
        for i, char in enumerate(text):
            if 0 <= y < len(canvas) and 0 <= x + i < len(canvas[0]):
                canvas[y][x + i] = char
                styles[y][x + i] = style

    def _draw_line(self, canvas, styles, x1, y1, x2, y2, char, style):
        """Draws a line onto the canvas using Bresenham's algorithm."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= y1 < len(canvas) and 0 <= x1 < len(canvas[0]):
                canvas[y1][x1] = char
                styles[y1][x1] = style

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

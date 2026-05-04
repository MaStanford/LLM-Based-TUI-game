from textual.app import App
from textual.reactive import reactive
from textual.events import Key
import logging
from .screens.world import WorldScreen
from .screens.main_menu import MainMenuScreen
from .screens.pause_menu import PauseScreen
from .screens.inventory import InventoryScreen
from .screens.shop import ShopScreen
from .screens.city_hall import CityHallScreen
from .screens.game_over import GameOverScreen
from .screens.map import MapScreen
from .game_state import GameState
from .world import World
from .logic.spawning import spawn_enemy, spawn_fauna, spawn_obstacle, spawn_turrets
from .logic.physics import update_physics_and_collisions
from .logic.quest_logic import update_quests
from .logic.trigger_logic import check_triggers
from .audio.audio import AudioManager
from .data.game_constants import CUTSCENE_RADIUS, UNTARGET_RADIUS, CITY_SPACING, SHOP_INTERACTION_SPEED_THRESHOLD
from .widgets.entity_modal import EntityModal
from .widgets.notifications import Notifications
from .widgets.fps_counter import FPSCounter
from .world.generation import get_buildings_in_city, does_city_exist_at
from .data import factions as faction_data_module
from .config import load_settings
import random
import math
import time
import importlib
from . import data as game_data

class GenesisModuleApp(App):
    """The main application class for the Genesis Module RPG."""

    CSS_PATH = "app.css"
    
    llm_pipeline = reactive(None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Game state will be initialized upon starting a new game
        self.game_state = None
        self.world = None
        self.frame_count = 0
        self.last_update_time = time.time()
        self.game_loop = None
        self.game_settings = load_settings()
        self.audio_manager = AudioManager()
        self.audio_manager.enabled = self.game_settings.get("sfx_enabled", True)
        self.dev_mode = self.game_settings.get("dev_mode", False)
        self.data = game_data
        self.generation_mode = self.game_settings.get("generation_mode", "local")
        self.model_size = self.game_settings.get("model_size", "small")
        self.cli_preset = self.game_settings.get("cli_preset", "gemini")
        self.custom_cli_command = self.game_settings.get("custom_cli_command", "")
        self.custom_cli_args = self.game_settings.get("custom_cli_args", "")
        self.dev_quick_start = self.game_settings.get("dev_quick_start", False)
        self.last_grid_pos = (None, None)
        self.current_save_name = None

    def reload_dynamic_data(self):
        """Forces a reload of the data modules to pick up generated content."""
        try:
            from .logic.data_loader import reload_all
            reload_all()
            importlib.reload(self.data)
            logging.info("Dynamic game data reloaded successfully.")
        except Exception as e:
            logging.error(f"Failed to reload dynamic data: {e}", exc_info=True)

    def stop_game_loop(self):
        """Stops the game loop timer."""
        if self.game_loop:
            self.game_loop.stop()

    def start_game_loop(self):
        """Starts the game loop timer."""
        # Ensure any old timer is stopped before creating a new one.
        if self.game_loop:
            self.game_loop.stop()
        # Reset the timestamp so the first tick after resuming doesn't
        # accumulate all the time spent in menus/map as one giant dt.
        self.last_update_time = time.time()
        self.game_loop = self.set_interval(1 / 30, self.update_game)

    def on_key(self, event: Key) -> None:
        """Global key handler — intercepts F12 for boss key from any screen."""
        from .screens.boss_key import BossKeyScreen
        if event.key == "f12":
            event.prevent_default()
            event.stop()
            if isinstance(self.screen, BossKeyScreen):
                self.pop_screen()
            else:
                self.stop_game_loop()
                self.push_screen(BossKeyScreen())

    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        self.push_screen(MainMenuScreen())

    def switch_screen(self, screen) -> None:
        """Switch to a new screen."""
        if screen == "main_menu":
            super().switch_screen(MainMenuScreen())
        else:
            super().switch_screen(screen)



    def update_game(self) -> None:
        """The main game loop, called by a timer."""
        if not isinstance(self.screen, WorldScreen):
            return

        # Cache the WorldScreen reference. Physics/triggers may push new screens
        # mid-tick (CombatScreen, NarrativeDialogScreen, etc.), which would change
        # self.screen and cause NoMatches errors when querying WorldScreen widgets.
        world_screen = self.screen
        gs = self.game_state
        
        # --- Delta Time Calculation ---
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Decrement cooldowns
        if gs.menu_nav_cooldown > 0:
            gs.menu_nav_cooldown -= 1
        
        if not gs.pause_menu_open and not gs.menu_open:
            if gs.game_over:
                self.stop_game_loop()
                self.push_screen(GameOverScreen())
                return

            # Process continuous input (held keys) before physics
            world_screen.process_input(dt)

            notifications = update_physics_and_collisions(gs, self.world, self.audio_manager, dt, self)
            for notification in notifications:
                world_screen.query_one("#notifications", Notifications).add_notification(notification)

            # Spawning logic
            spawn_rate = gs.difficulty_mods.get("spawn_rate_mult", 1.0)
            gs.enemy_spawn_timer -= dt
            if gs.enemy_spawn_timer <= 0:
                spawn_enemy(gs, self.world)
                gs.enemy_spawn_timer = random.uniform(1.5, 3.5) / spawn_rate

            gs.fauna_spawn_timer -= dt
            if gs.fauna_spawn_timer <= 0:
                spawn_fauna(gs, self.world)
                gs.fauna_spawn_timer = random.uniform(2.0, 4.0)

            gs.obstacle_spawn_timer -= dt
            if gs.obstacle_spawn_timer <= 0:
                spawn_obstacle(gs, self.world)
                gs.obstacle_spawn_timer = random.uniform(1.0, 2.5)

            gs.turret_spawn_timer -= dt
            if gs.turret_spawn_timer <= 0:
                spawn_turrets(gs, self.world)
                gs.turret_spawn_timer = 5.0
            
            quest_notifications = update_quests(gs, self.audio_manager, self, dt)
            for notification in quest_notifications:
                world_screen.query_one("#notifications", Notifications).add_notification(notification)

            # --- Throttled UI Updates ---
            # These calculations are expensive, so we only run them a few times per second.
            if self.frame_count % 8 == 0:
                gs.closest_entity_info = self.find_closest_entity()
            
            if self.frame_count % 12 == 0:
                self.update_compass_data()

            # --- Proximity Quest Generation ---
            # Check if we've moved to a new grid cell
            current_grid_x = round(gs.car_world_x / CITY_SPACING)
            current_grid_y = round(gs.car_world_y / CITY_SPACING)
            if (current_grid_x, current_grid_y) != self.last_grid_pos:
                self.check_and_cache_quests_for_nearby_cities()
                self.last_grid_pos = (current_grid_x, current_grid_y)
                # Mark city as visited for fast travel
                if does_city_exist_at(current_grid_x, current_grid_y, self.world.seed, gs.factions):
                    gs.visited_cities.add((current_grid_x, current_grid_y))
            
            # Fallback timer to retry failed generations or catch edge cases
            if self.frame_count % 300 == 0: # Every 10 seconds (assuming 30 FPS)
                self.check_and_cache_quests_for_nearby_cities()

            # --- Update UI Widgets ---
            world_screen.update_widgets()

            # Check for building interactions
            self.check_building_interaction()
            
            # Check for world triggers
            check_triggers(self, gs)

        # Update FPS counter
        self.frame_count += 1
        if isinstance(self.screen, WorldScreen):
            # Use a simple moving average for FPS to smooth it out
            # This part of the code is for display only and doesn't affect game logic timing
            if current_time - world_screen.query_one("#fps_counter").last_fps_update_time >= 1.0:
                fps = self.frame_count / (current_time - world_screen.query_one("#fps_counter").last_fps_update_time)
                world_screen.query_one("#fps_counter").fps = fps
                world_screen.query_one("#fps_counter").last_fps_update_time = current_time
                self.frame_count = 0

    def check_building_interaction(self):
        """Checks if the player is inside a building and pushes the appropriate screen."""
        gs = self.game_state

        # Player must be slow enough to enter a building
        if abs(gs.car_speed) > SHOP_INTERACTION_SPEED_THRESHOLD:
            return

        car_cx = gs.car_world_x + gs.player_car.width / 2
        car_cy = gs.car_world_y + gs.player_car.height / 2
        grid_x = round(car_cx / CITY_SPACING)
        grid_y = round(car_cy / CITY_SPACING)
        buildings = get_buildings_in_city(grid_x, grid_y)
        for idx, building in enumerate(buildings):
            # Skip destroyed buildings
            if (grid_x, grid_y, idx) in gs.destroyed_buildings:
                continue
            if (building['x'] <= car_cx < building['x'] + building['w'] and
                building['y'] <= car_cy < building['y'] + building['h']):
                
                building_type = building.get("type")
                if building_type in ["mechanic_shop", "gas_station", "weapon_shop"]:
                    gs.menu_open = True
                    self.push_screen(ShopScreen(shop_type=building_type))
                elif building_type == 'city_hall':
                    gs.menu_open = True
                    self.push_screen(CityHallScreen())
                return

    def find_closest_entity(self):
        """Finds the closest enemy, obstacle, or fauna to the player.
        Respects a manually click-targeted entity if it's still alive and in range.
        """
        gs = self.game_state
        radius_sq = CUTSCENE_RADIUS**2

        def _make_info(entity, name=None, desc=None):
            return {
                "name": name or getattr(entity, "name", entity.__class__.__name__.replace("_", " ").title()),
                "hp": entity.durability, "max_hp": entity.max_durability,
                "art": entity.get_static_art(), "x": entity.x, "y": entity.y,
                "description": desc or getattr(entity, "description", ""),
            }

        # Manual click-target takes priority
        tracked = gs.tracked_entity
        if tracked is not None:
            all_active = gs.active_enemies + gs.active_turrets + gs.active_obstacles + gs.active_fauna
            if tracked in all_active and getattr(tracked, "durability", 0) > 0:
                dist_sq = (tracked.x - gs.car_world_x)**2 + (tracked.y - gs.car_world_y)**2
                if dist_sq < radius_sq:
                    return _make_info(tracked)
            gs.tracked_entity = None

        def _find_nearest(entities, filter_fn=None):
            best, best_dist = None, radius_sq
            for e in entities:
                if filter_fn and not filter_fn(e):
                    continue
                d = (e.x - gs.car_world_x)**2 + (e.y - gs.car_world_y)**2
                if d < best_dist:
                    best_dist = d
                    best = e
            return best

        boss = _find_nearest(gs.active_enemies, lambda e: getattr(e, "is_faction_boss", False))
        if boss:
            return _make_info(boss)

        enemy = _find_nearest(gs.active_enemies)
        if enemy:
            return _make_info(enemy)

        obstacle = _find_nearest(gs.active_obstacles, lambda o: o.durability < o.max_durability)
        if obstacle:
            return _make_info(obstacle)

        fauna = _find_nearest(gs.active_fauna, lambda f: f.durability < f.max_durability)
        if fauna:
            return _make_info(fauna)

        turret = _find_nearest(gs.active_turrets)
        if turret:
            return _make_info(turret, desc="Defense turret")

        return None

    def update_compass_data(self):
        """Calculates the compass direction and caches it in the game state."""
        from .logic.quest_logic import get_quest_target_location
        gs = self.game_state
        target_x, target_y, target_name = None, None, None

        if gs.waypoint:
            target_x = gs.waypoint["x"]
            target_y = gs.waypoint["y"]
            target_name = gs.waypoint.get("name", "Waypoint")
        elif gs.active_quests:
            idx = min(gs.selected_quest_index, len(gs.active_quests) - 1)
            target_x, target_y, target_name = get_quest_target_location(gs.active_quests[idx], gs)

        if target_x is not None:
            # atan2 gives angle in screen coords: 0=east, pi/2=south, -pi/2=north
            angle_to_target = math.atan2(target_y - gs.car_world_y, target_x - gs.car_world_x)
            # Convert to compass degrees: 0=north, 90=east, 180=south, 270=west
            compass_deg = (math.degrees(angle_to_target) + 90) % 360
            gs.compass_info = {
                "absolute_bearing": compass_deg,
                "target_name": target_name
            }
        else:
            gs.compass_info = {"absolute_bearing": 0, "target_name": ""}

    def on_worker_state_changed(self, event: "Worker.StateChanged") -> None:
        """Handles completed quest generation workers."""
        from textual.worker import WorkerState
        if event.worker.name.startswith("QuestGenerator"):
            if event.worker.state == WorkerState.SUCCESS:
                city_id = event.worker.city_id
                quests = event.worker.result
                if quests:
                    self.game_state.quest_cache[city_id] = quests
                    logging.info(f"Successfully cached {len(quests)} quests for city {city_id}.")
                else:
                    self.game_state.quest_cache.pop(city_id, None)
                    logging.warning(f"Quest generation failed for city {city_id}. No quests cached.")

                from .screens.city_hall import CityHallScreen, QuestsLoaded
                if isinstance(self.screen, CityHallScreen) and self.screen.current_city_id == city_id:
                    logging.info(f"Posting QuestsLoaded message to CityHallScreen for city {city_id}")
                    self.screen.post_message(QuestsLoaded(quests or []))
            elif event.worker.state == WorkerState.ERROR:
                city_id = getattr(event.worker, 'city_id', None)
                if city_id:
                    self.game_state.quest_cache.pop(city_id, None)
                    logging.error(f"Quest generation worker failed for city {city_id}: {event.worker.error}")

    def trigger_initial_quest_cache(self):
        """Kicks off the quest caching for the player's starting area."""
        self.check_and_cache_quests_for_nearby_cities()

    def check_and_cache_quests_for_nearby_cities(self):
        """
        Checks for cities near the player and dispatches workers to generate quests
        for them if they aren't already cached. Prioritizes the current city.
        """
        from .workers.quest_generator import generate_quests_worker
        from .world.generation import get_city_faction
        from functools import partial

        gs = self.game_state
        player_grid_x = round(gs.car_world_x / CITY_SPACING)
        player_grid_y = round(gs.car_world_y / CITY_SPACING)

        # Build list of cities to check, current city first
        cities_to_check = [(player_grid_x, player_grid_y)]
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                cities_to_check.append((player_grid_x + dx, player_grid_y + dy))

        for check_x, check_y in cities_to_check:
                city_id = f"city_{check_x}_{check_y}"

                # Don't generate quests for cities that are already cached or pending
                if city_id in gs.quest_cache:
                    continue

                # Mark as pending to prevent re-dispatching
                gs.quest_cache[city_id] = "pending"

                city_faction_id = get_city_faction(check_x * CITY_SPACING, check_y * CITY_SPACING, gs.factions)

                logging.info(f"No quests cached for nearby city {city_id}. Starting pre-fetch worker.")

                worker_callable = partial(
                    generate_quests_worker,
                    app=self,
                    city_id=city_id,
                    city_faction_id=city_faction_id,
                    theme=gs.theme,
                    faction_data=gs.factions,
                    story_intro=gs.story_intro
                )

                worker = self.run_worker(
                    worker_callable,
                    exclusive=False, # Allow multiple quest generators to run
                    thread=True,
                    name=f"QuestGenerator_{city_id}"
                )
                # Pass the city_id to the worker's custom attribute to know where to store the result
                worker.city_id = city_id

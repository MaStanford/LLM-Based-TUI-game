import random
import math
from .generation import get_buildings_in_city
from ..data.game_constants import CITY_SPACING, ROAD_WIDTH, CITY_SIZE
from ..data.terrain import TERRAIN_DATA
from ..data.buildings import BUILDING_DATA

class World:
    def __init__(self, seed):
        self.seed = seed
        self.random = random.Random(seed)
        self.terrain_data = TERRAIN_DATA
        self.building_data = BUILDING_DATA
        self.city_spacing = CITY_SPACING
        self.game_state = None

    def get_terrain_at(self, x, y):
        grid_x = round(x / CITY_SPACING)
        grid_y = round(y / CITY_SPACING)

        city_center_x = grid_x * CITY_SPACING
        city_center_y = grid_y * CITY_SPACING
        in_city = abs(x - city_center_x) < CITY_SIZE / 2 and abs(y - city_center_y) < CITY_SIZE / 2

        # Only check buildings when inside a city bounds
        if in_city:
            city_buildings = get_buildings_in_city(grid_x, grid_y)
            for idx, building in enumerate(city_buildings):
                if building['x'] <= x < building['x'] + building['w'] and \
                   building['y'] <= y < building['y'] + building['h']:
                    if self.game_state and (grid_x, grid_y, idx) in self.game_state.destroyed_buildings:
                        return TERRAIN_DATA["RUBBLE"]
                    building_data = BUILDING_DATA.get(building["type"], {})
                    return {**TERRAIN_DATA["BUILDING_WALL"], "building": {**building_data, **building}}
            return TERRAIN_DATA["CITY_GROUND"]

        # Check for roads
        if abs(x % CITY_SPACING) < ROAD_WIDTH / 2 or abs(y % CITY_SPACING) < ROAD_WIDTH / 2:
            return TERRAIN_DATA["ROAD"]

        # Default to wilderness
        return TERRAIN_DATA["GRASS"]

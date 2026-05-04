import math
from functools import partial
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.worker import Worker, WorkerState

from ..widgets.item_list import ItemListWidget
from ..widgets.item_info import ItemInfoWidget
from ..widgets.menu_stats_hud import MenuStatsHUD
from ..logic.shop_logic import get_shop_inventory, purchase_item, calculate_sell_price
from ..world.generation import get_city_faction, get_buildings_in_city, find_safe_spawn_point
from ..data.game_constants import CITY_SPACING
from ..workers.dialog_generator import generate_dialog_worker

class ShopScreen(Screen):
    """The shop screen."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("up", "move_selection(-1)", "Up", show=True),
        Binding("down", "move_selection(1)", "Down", show=True),
        Binding("left", "switch_focus", "Switch", show=True),
        Binding("right", "switch_focus", "Switch", show=True),
        Binding("enter", "select_item", "Select", show=True),
        Binding("shift+up", "scroll_pane(-3)", "Scroll Up", show=True),
        Binding("shift+down", "scroll_pane(3)", "Scroll Down", show=True),
    ]

    def __init__(self, shop_type: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.shop_type = shop_type
        self.shop_inventory = []
        self.focused_list = "shop"  # "shop" or "player"
        self.sell_confirmation_item = None
        self.no_cash_dialog = "Not enough cash!"

    def _notify(self, message: str):
        """Post a notification to the WorldScreen."""
        try:
            self.app.screen_stack[-2].query_one("#notifications").add_notification(message)
        except Exception:
            pass # Fail silently

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.add_class(self.shop_type.replace("_", "-"))
        self.update_displays()
        self.update_focus()
        self.generate_dialog()

    def generate_dialog(self):
        """Starts a worker to generate shopkeeper dialog."""
        gs = self.app.game_state
        
        city_faction_id = get_city_faction(gs.car_world_x, gs.car_world_y, gs.factions)
        faction_info = gs.factions.get(city_faction_id, {})
        faction_name = faction_info.get("name", "The Wasteland")
        faction_vibe = faction_info.get("description", "A desolate, lawless place.")
        player_rep = gs.faction_reputation.get(city_faction_id, 0)

        worker_callable = partial(
            generate_dialog_worker,
            app=self.app,
            theme=gs.theme,
            shop_type=self.shop_type,
            faction_name=faction_name,
            faction_vibe=faction_vibe,
            player_reputation=player_rep
        )
        self.run_worker(worker_callable, exclusive=True, name="DialogGenerator", thread=True)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle completed dialog worker."""
        if event.worker.name == "DialogGenerator" and event.worker.state == WorkerState.SUCCESS:
            dialog = event.worker.result
            if isinstance(dialog, dict):
                self.query_one("#shop_dialog", Static).update(dialog.get("greeting", "..."))
                self.no_cash_dialog = dialog.get("no_cash", "Not enough cash!")
            else:
                self.query_one("#shop_dialog", Static).update(str(dialog))

    def on_unmount(self) -> None:
        """Called when the screen is unmounted."""
        gs = self.app.game_state
        gs.menu_open = False
        
        grid_x = round(gs.car_world_x / CITY_SPACING)
        grid_y = round(gs.car_world_y / CITY_SPACING)
        buildings = get_buildings_in_city(grid_x, grid_y)
        
        current_building = next((b for b in buildings if b.get("type") == self.shop_type), None)
        
        if current_building:
            exit_x = current_building['x'] + current_building['w'] / 2
            exit_y = current_building['y'] + current_building['h'] + 2
            
            safe_x, safe_y = find_safe_spawn_point(exit_x, exit_y, buildings, gs.player_car)
            
            gs.car_world_x = safe_x
            gs.car_world_y = safe_y
            gs.car_angle = math.pi * 1.5 # Face down (South)
            gs.player_car.x = gs.car_world_x
            gs.player_car.y = gs.car_world_y
            gs.player_car.angle = gs.car_angle

    def update_displays(self) -> None:
        """Update all display widgets."""
        gs = self.app.game_state
        
        # Shop Inventory
        self.shop_inventory = get_shop_inventory(self.shop_type, gs)
        shop_widget = self.query_one("#shop_inventory", ItemListWidget)
        shop_widget.items = self.shop_inventory
        
        # Player Inventory (copy list so reactive detects the change)
        player_widget = self.query_one("#player_inventory", ItemListWidget)
        player_widget.items = list(gs.player_inventory)
        
        # Stats
        self.query_one(MenuStatsHUD).update_stats(gs)
        
        self.update_item_info()
        self.update_action_button()

    def update_focus(self) -> None:
        """Update the visual focus indicator."""
        shop_pane = self.query_one("#shop_inventory_pane", Vertical)
        player_pane = self.query_one("#player_inventory_pane", Vertical)

        if self.focused_list == "shop":
            shop_pane.border_title = "Shop (Selected)"
            player_pane.border_title = "Your Inventory"
            shop_pane.styles.border = ("heavy", "yellow")
            player_pane.styles.border = ("heavy", "white")
        else:
            shop_pane.border_title = "Shop"
            player_pane.border_title = "Your Inventory (Selected)"
            shop_pane.styles.border = ("heavy", "white")
            player_pane.styles.border = ("heavy", "yellow")

    def update_action_button(self) -> None:
        """Update the main action button's label and state."""
        button = self.query_one("#action_button", Button)
        can_sell = self.shop_type == "weapon_shop"

        if self.focused_list == "shop":
            button.label = "Buy"
            button.disabled = not self.shop_inventory
        elif can_sell:
            player_widget = self.query_one("#player_inventory", ItemListWidget)
            selected_item = player_widget.selected_item
            if self.sell_confirmation_item == selected_item and selected_item is not None:
                price = calculate_sell_price(selected_item, self.app.game_state)
                button.label = f"Confirm Sell (${price:,})?"
            else:
                button.label = "Sell"
            button.disabled = not player_widget.items
        else: # Player focus, but can't sell
            button.label = "Sell"
            button.disabled = True

    def action_move_selection(self, amount: int) -> None:
        """Move the selection in the currently focused list."""
        self.sell_confirmation_item = None # Reset confirmation on move
        if self.focused_list == "shop":
            widget = self.query_one("#shop_inventory", ItemListWidget)
        else:
            widget = self.query_one("#player_inventory", ItemListWidget)
        
        if widget.items:
            widget.selected_index = (widget.selected_index + amount + len(widget.items)) % len(widget.items)
            self.update_item_info()
            self.update_action_button()

    def update_item_info(self) -> None:
        """Update the item info panel based on the current selection."""
        if self.focused_list == "shop":
            widget = self.query_one("#shop_inventory", ItemListWidget)
            item_to_display = widget.selected_item
        else:
            widget = self.query_one("#player_inventory", ItemListWidget)
            item_to_display = widget.selected_item

        self.query_one(ItemInfoWidget).display_item(item_to_display)

    def action_switch_focus(self) -> None:
        """Switch focus between the shop and player inventory lists."""
        self.sell_confirmation_item = None # Reset confirmation on switch
        self.focused_list = "player" if self.focused_list == "shop" else "shop"
        self.update_focus()
        self.update_item_info()
        self.update_action_button()

    def action_select_item(self) -> None:
        """Handle buying or selling the selected item."""
        if self.focused_list == "shop":
            self._buy_item()
        else:
            self._sell_item()
        self.update_action_button()

    def action_scroll_pane(self, amount: int) -> None:
        """Scroll the focused inventory pane."""
        if self.focused_list == "shop":
            pane = self.query_one("#shop_inventory_pane")
        else:
            pane = self.query_one("#player_inventory_pane")
        pane.scroll_relative(y=amount)

    def on_item_list_widget_item_clicked(self, event) -> None:
        """Handle mouse click on a shop item list."""
        self.sell_confirmation_item = None
        wid = event.widget_id
        if wid == "shop_inventory":
            self.focused_list = "shop"
        elif wid == "player_inventory":
            self.focused_list = "player"
        self.update_focus()
        self.update_item_info()
        self.update_action_button()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the action button being clicked."""
        if event.button.id == "action_button":
            self.action_select_item()

    def _buy_item(self):
        """Logic for purchasing an item."""
        gs = self.app.game_state
        shop_widget = self.query_one("#shop_inventory", ItemListWidget)
        selected_item = shop_widget.selected_item
        if not selected_item: return

        price = selected_item.get("price", 0)
        if gs.player_cash >= price:
            gs.player_cash -= price
            purchase_item(gs, selected_item)
            self._notify(f"Purchased {selected_item['name']}!")
            self.update_displays()
        else:
            self.query_one("#shop_dialog", Static).update(self.no_cash_dialog)
            self._notify("Not enough cash!")

    def _sell_item(self):
        """Logic for selling an item."""
        if self.shop_type != "weapon_shop":
            self._notify("You cannot sell items at this shop.")
            return

        gs = self.app.game_state
        player_widget = self.query_one("#player_inventory", ItemListWidget)
        selected_item = player_widget.selected_item
        if not selected_item: return

        if self.sell_confirmation_item == selected_item:
            # Second press: confirm sell
            # Block selling quest items
            from ..data.quests import QuestItem
            if isinstance(selected_item, QuestItem):
                self._notify("Quest items cannot be sold!")
                self.sell_confirmation_item = None
                return
            price = calculate_sell_price(selected_item, gs)
            gs.player_cash += price
            gs.player_inventory.remove(selected_item)
            self._notify(f"Sold {selected_item.name} for ${price:,}!")
            self.sell_confirmation_item = None
            self.update_displays()
        else:
            # First press: stage for confirmation
            self.sell_confirmation_item = selected_item

    def compose(self):
        """Compose the layout of the screen."""
        yield Header(show_clock=True)
        with Vertical(id="shop_page"):
            # Top: inventory lists side by side
            with Horizontal(id="shop_lists_row"):
                with Vertical(id="shop_inventory_pane"):
                    yield ItemListWidget(id="shop_inventory")
                with Vertical(id="player_inventory_pane"):
                    yield ItemListWidget(id="player_inventory")
            # Bottom: 2-column detail area
            with Horizontal(id="shop_detail_row"):
                with Vertical(id="shop_left_col"):
                    yield Static("Welcome, traveler!", id="shop_dialog")
                    yield ItemInfoWidget()
                with Vertical(id="shop_right_col"):
                    yield MenuStatsHUD()
                    btn = Button("Buy", id="action_button", variant="primary")
                    btn.can_focus = False
                    yield btn
        yield Footer()
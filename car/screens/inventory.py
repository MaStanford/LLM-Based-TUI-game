from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static
from textual.containers import Grid, Vertical, ScrollableContainer
from textual.binding import Binding
from ..widgets.item_list import ItemListWidget
from ..widgets.item_info import ItemInfoWidget
from ..widgets.menu_stats_hud import MenuStatsHUD
from ..logic.entity_loader import PLAYER_CARS
from ..logic.salvage_logic import calculate_scrap_value, salvage_item
from ..data.equipment import EQUIPMENT_SLOTS

class InventoryScreen(ModalScreen):
    """The inventory screen."""

    BINDINGS = [
        Binding("escape", "cancel_equip", "Back", show=True),
        Binding("up", "move_selection(-1)", "Up", show=True),
        Binding("down", "move_selection(1)", "Down", show=True),
        Binding("left", "switch_focus", "Switch", show=True),
        Binding("right", "switch_focus", "Switch", show=True),
        Binding("a", "rotate_preview(-1)", "Rotate Left", show=True),
        Binding("d", "rotate_preview(1)", "Rotate Right", show=True),
        Binding("enter", "select_item", "Select", show=True),
        Binding("s", "salvage_item", "Salvage", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.focused_list = "inventory"  # "inventory", "attachments", or "equipment_slots"
        self.selected_weapon_to_mount = None
        self.selected_slot_to_fill = None
        self.unequip_confirmation_slot = None
        self.salvage_confirmation_item = None
        self.preview_angle = 0
        self.blink_timer = None
        self.blink_state = True

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.update_inventory()
        self.update_focus()
        self.blink_timer = self.set_interval(0.5, self.toggle_blink)

    def on_unmount(self) -> None:
        """Called when the screen is unmounted."""
        if self.blink_timer:
            self.blink_timer.stop()
        self.app.game_state.menu_open = False

    def toggle_blink(self) -> None:
        """Toggle the blink state for the attachment point marker."""
        self.blink_state = not self.blink_state
        self.update_inventory()

    def update_inventory(self) -> None:
        """Update the inventory display."""
        gs = self.app.game_state

        # Car Preview
        car_preview = self.query_one("#car_preview", Static)
        car_class = PLAYER_CARS[gs.selected_car_index]
        car_instance = car_class(0, 0)
        color = gs.car_color_names[0].lower().replace("car_", "")
        colored_art_dict = {}
        for direction, art_lines in car_instance.art.items():
            colored_art_dict[direction] = [f"[{color}]{line}[/]" for line in art_lines]
        car_instance.art = colored_art_dict
        art = self.get_art_for_angle(car_instance, self.preview_angle)
        art = self._overlay_attachment_points(art, car_instance)
        car_preview.update(art)

        # Attachments
        attachments_widget = self.query_one("#attachments", ItemListWidget)
        attachments_widget.items = [
            {"name": f"{i+1}. {point_data['name']}: {weapon.name if weapon else '(' + point_data['level'] + ')'}"}
            for i, (point_data, weapon) in enumerate(zip(gs.attachment_points.values(), gs.mounted_weapons.values()))
        ]

        # Equipment Slots
        equip_widget = self.query_one("#equipment_slots", ItemListWidget)
        equip_items = []
        for slot_id, slot_data in EQUIPMENT_SLOTS.items():
            equipped = gs.equipped_equipment.get(slot_id)
            equip_items.append({
                "name": f"{slot_data['name']}: {equipped.name if equipped else '(empty)'}",
                "slot_id": slot_id,
            })
        equip_widget.items = equip_items

        # Inventory
        inventory_widget = self.query_one("#inventory", ItemListWidget)
        inventory_widget.items = list(gs.player_inventory)

        # Stats
        self.query_one(MenuStatsHUD).update_stats(gs)

    def get_art_for_angle(self, car_instance, angle):
        """Gets the correct vehicle art for a given angle."""
        angle = angle % 360
        if 337.5 <= angle or angle < 22.5: direction = "N"
        elif 22.5 <= angle < 67.5: direction = "NE"
        elif 67.5 <= angle < 112.5: direction = "E"
        elif 112.5 <= angle < 157.5: direction = "SE"
        elif 157.5 <= angle < 202.5: direction = "S"
        elif 202.5 <= angle < 247.5: direction = "SW"
        elif 247.5 <= angle < 292.5: direction = "W"
        else: direction = "NW"
        return "\n".join(car_instance.art.get(direction, [""]))

    def _overlay_attachment_points(self, art_str: str, car_instance) -> str:
        """Overlays attachment point indicators onto the car art."""
        from rich.text import Text
        art_text = Text.from_markup(art_str)
        art_lines = art_text.wrap(self.app.console, width=999)
        art_height = len(art_lines)
        art_width = max(line.cell_len for line in art_lines) if art_lines else 0

        # Create a mutable grid of characters
        grid = [list(line) for line in art_lines]

        attachments_widget = self.query_one("#attachments", ItemListWidget)
        selected_slot_index = attachments_widget.selected_index

        for i, (point_name, point_data) in enumerate(car_instance.attachment_points.items()):
            px = int(art_width / 2 + point_data["offset_x"])
            py = int(art_height / 2 + point_data["offset_y"])

            if 0 <= py < len(grid) and 0 <= px < len(grid[py]):
                marker = str(i + 1)
                if self.focused_list == "attachments" and i == selected_slot_index:
                    marker = "●" if self.blink_state else str(i + 1)

                grid[py][px] = f"[yellow]{marker}[/]"

        return "\n".join("".join(map(str, row)) for row in grid)

    def update_focus(self) -> None:
        """Update the visual focus indicator."""
        inv_widget = self.query_one("#inventory", ItemListWidget)
        att_widget = self.query_one("#attachments", ItemListWidget)
        equip_widget = self.query_one("#equipment_slots", ItemListWidget)

        inv_widget.border_title = "Inventory"
        att_widget.border_title = "Loadout"
        equip_widget.border_title = "Equipment"

        if self.focused_list == "inventory":
            inv_widget.border_title = "Inventory (Selected)"
        elif self.focused_list == "attachments":
            att_widget.border_title = "Loadout (Selected)"
        elif self.focused_list == "equipment_slots":
            equip_widget.border_title = "Equipment (Selected)"

    def action_move_selection(self, amount: int) -> None:
        """Move the selection in the currently focused list."""
        self.unequip_confirmation_slot = None
        self.salvage_confirmation_item = None
        if self.focused_list == "inventory":
            widget = self.query_one("#inventory", ItemListWidget)
        elif self.focused_list == "attachments":
            widget = self.query_one("#attachments", ItemListWidget)
        else:
            widget = self.query_one("#equipment_slots", ItemListWidget)

        if widget.items:
            widget.selected_index = (widget.selected_index + amount + len(widget.items)) % len(widget.items)
            self.update_item_info()

    def update_item_info(self) -> None:
        """Update the weapon info panel based on the current selection."""
        item_to_display = None

        if self.focused_list == "inventory":
            widget = self.query_one("#inventory", ItemListWidget)
            item_to_display = widget.selected_item
        elif self.focused_list == "attachments":
            widget = self.query_one("#attachments", ItemListWidget)
            if widget.items:
                slot_name = list(self.app.game_state.mounted_weapons.keys())[widget.selected_index]
                item_to_display = self.app.game_state.mounted_weapons[slot_name]
        elif self.focused_list == "equipment_slots":
            widget = self.query_one("#equipment_slots", ItemListWidget)
            if widget.items:
                slot_ids = list(EQUIPMENT_SLOTS.keys())
                if widget.selected_index < len(slot_ids):
                    slot_id = slot_ids[widget.selected_index]
                    item_to_display = self.app.game_state.equipped_equipment.get(slot_id)

        self.query_one(ItemInfoWidget).display_item(item_to_display)
        self._update_inventory_prompt()

    def _update_inventory_prompt(self):
        """Update the contextual prompt based on the current state."""
        prompt_widget = self.query_one("#inventory_prompt")
        if self.salvage_confirmation_item:
            scrap = calculate_scrap_value(self.salvage_confirmation_item)
            prompt_widget.update(f"Press 's' again to salvage for [yellow]{scrap} scrap[/yellow].")
        elif self.selected_weapon_to_mount:
            prompt_widget.update(f"Select a slot to equip [yellow]{self.selected_weapon_to_mount.name}[/yellow]...")
        elif self.selected_slot_to_fill:
            prompt_widget.update(f"Select a weapon for [yellow]{self.selected_slot_to_fill}[/yellow]...")
        elif self.unequip_confirmation_slot:
            prompt_widget.update(f"Press Enter again to unequip from [yellow]{self.unequip_confirmation_slot}[/yellow].")
        else:
            prompt_widget.update("Arrows: Navigate | Enter: Select | S: Salvage | L/R: Switch pane")

    def action_rotate_preview(self, direction: int) -> None:
        """Rotate the car preview."""
        self.preview_angle += 45 * direction
        self.update_inventory()

    def action_switch_focus(self) -> None:
        """Switch focus between the inventory, attachment, and equipment lists."""
        self.unequip_confirmation_slot = None
        self.salvage_confirmation_item = None
        if self.selected_weapon_to_mount or self.selected_slot_to_fill:
            return
        # Cycle: inventory -> attachments -> equipment_slots -> inventory
        if self.focused_list == "inventory":
            self.focused_list = "attachments"
        elif self.focused_list == "attachments":
            self.focused_list = "equipment_slots"
        else:
            self.focused_list = "inventory"
        self.update_focus()
        self._update_inventory_prompt()

    def action_cancel_equip(self) -> None:
        """Cancel the current equip/unequip action."""
        if self.selected_weapon_to_mount or self.selected_slot_to_fill:
            self.selected_weapon_to_mount = None
            self.selected_slot_to_fill = None
            self.unequip_confirmation_slot = None
            self.focused_list = "inventory"
            self.update_focus()
            self._update_inventory_prompt()
        else:
            self.app.pop_screen()

    def action_salvage_item(self) -> None:
        """Salvage the selected inventory item for scrap."""
        if self.focused_list != "inventory":
            return
        inv_widget = self.query_one("#inventory", ItemListWidget)
        if not inv_widget.items:
            return
        selected = inv_widget.selected_item
        if not selected or not hasattr(selected, 'type'):
            return

        if self.salvage_confirmation_item == selected:
            # Confirmed — salvage it
            scrap = salvage_item(self.app.game_state, selected)
            self.salvage_confirmation_item = None
            self.update_inventory()
            self._update_inventory_prompt()
        else:
            # First press — stage for confirmation
            self.salvage_confirmation_item = selected
            self._update_inventory_prompt()

    def action_select_item(self) -> None:
        """Select an item to mount or a slot to mount it to."""
        gs = self.app.game_state
        self.salvage_confirmation_item = None

        if self.focused_list == "inventory":
            # --- INVENTORY focused ---
            inv_widget = self.query_one("#inventory", ItemListWidget)
            if not inv_widget.items: return

            selected_item = inv_widget.selected_item

            if self.selected_slot_to_fill:
                # Equip selected weapon to staged attachment slot
                if getattr(selected_item, 'type', None) != 'weapon':
                    return
                slot_name = self.selected_slot_to_fill
                currently_mounted = gs.mounted_weapons[slot_name]
                gs.mounted_weapons[slot_name] = selected_item
                gs.player_inventory.remove(selected_item)
                if currently_mounted:
                    gs.player_inventory.append(currently_mounted)

                self.selected_slot_to_fill = None
                self.focused_list = "attachments"
            else:
                # Stage selected item for equipping
                if getattr(selected_item, 'type', None) == 'weapon':
                    self.selected_weapon_to_mount = selected_item
                    self.focused_list = "attachments"
                elif getattr(selected_item, 'type', None) == 'equipment':
                    # Auto-equip to matching slot
                    slot = selected_item.slot
                    currently_equipped = gs.equipped_equipment.get(slot)
                    gs.equipped_equipment[slot] = selected_item
                    gs.player_inventory.remove(selected_item)
                    if currently_equipped:
                        gs.player_inventory.append(currently_equipped)
                    gs.apply_level_bonuses()

        elif self.focused_list == "attachments":
            # --- ATTACHMENTS focused ---
            att_widget = self.query_one("#attachments", ItemListWidget)
            slot_index = att_widget.selected_index
            slot_name = list(gs.mounted_weapons.keys())[slot_index]

            if self.selected_weapon_to_mount:
                # Equip staged weapon to selected slot
                currently_mounted = gs.mounted_weapons[slot_name]
                gs.mounted_weapons[slot_name] = self.selected_weapon_to_mount
                gs.player_inventory.remove(self.selected_weapon_to_mount)
                if currently_mounted:
                    gs.player_inventory.append(currently_mounted)

                self.selected_weapon_to_mount = None
                self.focused_list = "inventory"
            else:
                # No weapon staged, so either unequip or stage the slot
                if gs.mounted_weapons[slot_name]:
                    if self.unequip_confirmation_slot == slot_name:
                        weapon_to_unequip = gs.mounted_weapons[slot_name]
                        gs.mounted_weapons[slot_name] = None
                        gs.player_inventory.append(weapon_to_unequip)
                        self.unequip_confirmation_slot = None
                    else:
                        self.unequip_confirmation_slot = slot_name
                else:
                    self.selected_slot_to_fill = slot_name
                    self.focused_list = "inventory"

        elif self.focused_list == "equipment_slots":
            # --- EQUIPMENT SLOTS focused ---
            equip_widget = self.query_one("#equipment_slots", ItemListWidget)
            slot_ids = list(EQUIPMENT_SLOTS.keys())
            if equip_widget.selected_index >= len(slot_ids):
                return
            slot_id = slot_ids[equip_widget.selected_index]

            if gs.equipped_equipment.get(slot_id):
                # Unequip with confirmation
                if self.unequip_confirmation_slot == slot_id:
                    equipment_to_unequip = gs.equipped_equipment[slot_id]
                    gs.equipped_equipment[slot_id] = None
                    gs.player_inventory.append(equipment_to_unequip)
                    gs.apply_level_bonuses()
                    self.unequip_confirmation_slot = None
                else:
                    self.unequip_confirmation_slot = slot_id

        self.update_inventory()
        self.update_focus()
        self._update_inventory_prompt()

    def on_item_list_widget_item_clicked(self, event: ItemListWidget.ItemClicked) -> None:
        """Handle mouse click on an item list."""
        self.unequip_confirmation_slot = None
        self.salvage_confirmation_item = None
        wid = event.widget_id
        if wid == "inventory":
            self.focused_list = "inventory"
        elif wid == "attachments":
            self.focused_list = "attachments"
        elif wid == "equipment_slots":
            self.focused_list = "equipment_slots"
        self.update_focus()
        self.update_item_info()

    def compose(self):
        """Compose the layout of the screen."""
        yield Header(show_clock=True)
        with Grid(id="inventory_grid"):
            with Vertical():
                yield Static("Car Preview", id="car_preview")
                yield ItemListWidget(id="attachments")
                yield ItemListWidget(id="equipment_slots")
            with Vertical():
                with ScrollableContainer():
                    yield ItemListWidget(id="inventory")
                yield Static(id="inventory_prompt", classes="panel")
                yield ItemInfoWidget(id="item_info")
                yield MenuStatsHUD(id="stats")
        yield Footer()

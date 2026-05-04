from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message
from rich.table import Table
from rich.text import Text
from ..data.modifiers import RARITY_TIERS

RARITY_COLORS = {r: d["color"] for r, d in RARITY_TIERS.items()}

class ItemListWidget(Static):
    """A widget to display a list of items with prices."""

    class ItemClicked(Message):
        """Posted when the user clicks an item row."""
        def __init__(self, widget_id: str, index: int) -> None:
            self.widget_id = widget_id
            self.index = index
            super().__init__()

    items = reactive([])
    selected_index = reactive(0)

    def on_click(self, event) -> None:
        """Select the clicked row."""
        if self.items and 0 <= event.y < len(self.items):
            self.selected_index = event.y
            self.post_message(self.ItemClicked(self.id or "", event.y))

    @property
    def selected_item(self):
        """Returns the currently selected item data, or None."""
        if self.items and 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update_render()

    def watch_items(self, new_items) -> None:
        """Called when the items list changes."""
        # Clamp selection to valid range instead of resetting to 0
        if new_items:
            if self.selected_index >= len(new_items):
                self.selected_index = len(new_items) - 1
        else:
            self.selected_index = 0
        self.update_render()

    def watch_selected_index(self, new_index) -> None:
        """Called when the selected index changes."""
        self.update_render()

    def update_render(self) -> None:
        """Update the displayed list."""
        table = Table(show_header=False, expand=True, box=None, padding=0)
        table.add_column("Name", justify="left", no_wrap=True)
        table.add_column("Type", justify="left", no_wrap=True, width=8)
        table.add_column("Price", justify="right", no_wrap=True)

        for i, item_data in enumerate(self.items):
            name = ""
            price_str = ""
            type_str = ""
            rarity = "common"

            # Handle both dicts from shops and Weapon/Equipment objects from inventory
            if isinstance(item_data, dict):
                name = item_data.get("name", "Unknown")
                price = item_data.get("price")
                if price is not None:
                    price_str = f"${price:,}"
                item_type = item_data.get("type", "")
                rarity = item_data.get("rarity", "common")
                if item_type == "equipment":
                    type_str = item_data.get("slot", "equip")[:6]
                elif item_type == "weapon":
                    type_str = item_data.get("ammo_type", "")[:6]
                else:
                    type_str = item_type[:6]
            elif hasattr(item_data, "name"):
                name = item_data.name
                if hasattr(item_data, "price"):
                     price_str = f"${item_data.price:,}"
                rarity = getattr(item_data, "rarity", "common")
                item_type = getattr(item_data, "type", "")
                if item_type == "equipment":
                    type_str = getattr(item_data, "slot", "equip")[:6]
                elif item_type == "weapon":
                    type_str = getattr(item_data, "ammo_type", "")[:6]

            rarity_color = RARITY_COLORS.get(rarity, "white")
            row_style = "reverse" if i == self.selected_index else ""
            name_style = f"{rarity_color} {row_style}".strip()

            table.add_row(
                Text(name, style=name_style),
                Text(type_str, style=row_style),
                Text(price_str, style=row_style)
            )
        self.update(table)
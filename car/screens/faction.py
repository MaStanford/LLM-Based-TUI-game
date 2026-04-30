from textual.screen import ModalScreen
from textual.widgets import Header, Footer, DataTable, Static, ProgressBar
from textual.containers import Grid, Vertical
from textual.binding import Binding
from rich.text import Text
from ..world.generation import get_city_name
from ..logic.entity_loader import ALL_VEHICLES, ENEMY_CHARACTERS, normalize_class_name

class ReputationBar(ProgressBar):
    """A progress bar that displays reputation from -100 to 100."""
    def get_renderable(self):
        # Override to show the correct percentage
        normalized_progress = self.progress - 100
        return f"{normalized_progress}%"

def _create_bar(value: int, total: int, width: int = 10) -> str:
    """Creates a text-based progress bar."""
    filled_width = int(width * value / total)
    bar = "█" * filled_width + "─" * (width - filled_width)
    return f"[{bar}]"

class FactionScreen(ModalScreen):
    """A modal screen to display faction intelligence."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.faction_data = {}

    def compose(self):
        """Compose the layout of the screen."""
        yield Header(show_clock=True)
        with Grid(id="faction_grid"):
            yield DataTable(id="faction_list")
            with Vertical(id="faction_details_container"):
                yield Static(id="faction_details_header")
                yield Static("Control", classes="progress_bar_label")
                yield ProgressBar(id="faction_control_bar", total=100, show_eta=False, show_percentage=True)
                yield Static("Reputation", classes="progress_bar_label")
                yield ReputationBar(id="faction_rep_bar", total=200, show_eta=False)
                yield Static(id="faction_description")
                yield Static(id="faction_relationships")
        yield Footer(show_command_palette=True)

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        gs = self.app.game_state
        self.faction_data = gs.factions
        
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("Faction", width=25)
        table.add_column("Control", width=20)
        table.add_column("Reputation", width=20)
        
        for faction_id, data in self.faction_data.items():
            control = gs.faction_control.get(faction_id, 50)
            reputation = gs.faction_reputation.get(faction_id, 0)
            
            control_bar_str = _create_bar(control, 100)
            rep_bar_str = _create_bar(reputation + 100, 200) # Normalize to 0-200 for the bar

            table.add_row(data["name"], f"{control_bar_str} {control}%", f"{rep_bar_str} {reputation}", key=faction_id)
            
        if table.row_count > 0:
            table.move_cursor(row=0, animate=False)
            initial_faction_name = table.get_cell_at((0, 0))
            self.update_details(initial_faction_name)
        table.focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Event handler for when a row is highlighted in the DataTable."""
        table = self.query_one(DataTable)
        faction_name = table.get_cell_at((event.cursor_row, 0))
        self.update_details(faction_name)

    def update_details(self, faction_name: str) -> None:
        """Update the faction detail panel."""
        gs = self.app.game_state
        header_panel = self.query_one("#faction_details_header")
        control_bar = self.query_one("#faction_control_bar")
        rep_bar = self.query_one("#faction_rep_bar")
        description_panel = self.query_one("#faction_description")
        relationships_panel = self.query_one("#faction_relationships")
        
        # Find the faction data
        faction_id = next((fid for fid, data in self.faction_data.items() if data["name"] == faction_name), None)
        if not faction_id:
            header_panel.update("Select a faction.")
            description_panel.update("")
            relationships_panel.update("")
            return
            
        faction_data = self.faction_data[faction_id]
        rep = gs.faction_reputation.get(faction_id, 0)
        control = gs.faction_control.get(faction_id, 50)
        
        # Update Control Bar
        control_bar.progress = control
        if control < 33:
            control_bar.bar_style = "red"
        elif control < 66:
            control_bar.bar_style = "yellow"
        else:
            control_bar.bar_style = "green"

        # Update Reputation Bar
        rep_bar.progress = rep + 100 # Offset to fit in 0-200 range
        if rep < -33:
            rep_bar.bar_style = "red"
        elif rep < 33:
            rep_bar.bar_style = "yellow"
        else:
            rep_bar.bar_style = "green"
            
        hub_x, hub_y = faction_data["hub_city_coordinates"]
        capital_name = get_city_name(hub_x, hub_y, gs.factions, gs.world_details)
        
        unit_names = []
        for unit_id in faction_data.get("units", []):
            all_classes = list(ALL_VEHICLES) + list(ENEMY_CHARACTERS)
            matched_class = next((v for v in all_classes if normalize_class_name(v.__name__) == normalize_class_name(unit_id)), None)
            if matched_class:
                unit_names.append(matched_class(0,0).name)
            else:
                unit_names.append(unit_id.replace("_", " ").title())
        units_str = ", ".join(unit_names) if unit_names else "N/A"

        header = f"[bold]{faction_name}[/bold]\n\n"
        header += f"Capital: {capital_name}\n"
        header += f"Control: {control}%\n"
        header += f"Reputation: {rep}\n\n"
        header += f"[bold]Known Units:[/bold]\n{units_str}\n\n"
        
        description = f"[bold]Description:[/bold]\n{faction_data.get('description', 'N/A')}\n\n"
        
        relationships_text = Text("Relationships:\n", style="bold")
        for other_id, status in faction_data.get("relationships", {}).items():
            if other_id in self.faction_data:
                other_name = self.faction_data[other_id]["name"]
                style = ""
                if status == "Hostile":
                    style = "on red"
                elif status == "Neutral":
                    style = "on yellow"
                elif status == "Allied":
                    style = "on green"
                relationships_text.append(f"- {other_name}: ")
                relationships_text.append(f"{status}\n", style=style)
            
        header_panel.update(header)
        description_panel.update(description)
        relationships_panel.update(relationships_text)

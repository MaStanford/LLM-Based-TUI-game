from textual.app import ComposeResult
from textual.containers import Vertical, Center
from textual.screen import Screen
from textual.widgets import Button, Header, Footer, Static
from textual.binding import Binding

from ..config import load_settings, save_settings
from ..logic.gemini_cli import CLI_PRESETS, check_cli_auth

class SettingsScreen(Screen):
    """A screen for changing game settings."""

    BINDINGS = [
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
        Binding("enter", "select_button", "Select", show=True),
        Binding("escape", "app.pop_screen", "Back", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.focusable_widgets = []
        self.current_focus_index = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Center():
            with Vertical(id="settings-container"):
                yield Static("[bold]Settings[/bold]", id="title")

                yield Static("LLM Engine", classes="setting-label")
                yield Button(self._mode_label(), id="toggle_mode")

                yield Static("", id="sub_option_label", classes="setting-label")
                yield Button("", id="toggle_sub_option")

                yield Static("Sound Effects", classes="setting-label")
                yield Button(self._sfx_label(), id="toggle_sfx")

                yield Static("Dev Mode", classes="setting-label")
                yield Button(self._dev_mode_label(), id="toggle_dev_mode")

                yield Static("Quick Start (Skip LLM)", classes="setting-label", id="quick_start_label")
                yield Button(self._quick_start_label(), id="toggle_quick_start")

                yield Button("Back", id="back", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Update the sub-option to match the current mode."""
        self._refresh_sub_option()
        self.focusable_widgets = list(self.query("Button"))
        self.current_focus_index = 0
        self._update_focus()

    def _update_focus(self) -> None:
        """Update which widget has focus."""
        if self.focusable_widgets:
            self.focusable_widgets[self.current_focus_index].focus()

    def action_focus_previous(self) -> None:
        """Focus the previous widget."""
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index - 1 + len(self.focusable_widgets)) % len(self.focusable_widgets)
            self._update_focus()

    def action_focus_next(self) -> None:
        """Focus the next widget."""
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index + 1) % len(self.focusable_widgets)
            self._update_focus()

    def action_select_button(self) -> None:
        """Press the focused button."""
        if self.focusable_widgets:
            self.focusable_widgets[self.current_focus_index].press()

    # --- Label helpers ---

    def _mode_label(self) -> str:
        mode = self.settings.get("generation_mode", "local")
        return "Engine: Local (On-Device)" if mode == "local" else "Engine: Command Line"

    def _sub_option_label_text(self) -> str:
        mode = self.settings.get("generation_mode", "local")
        if mode == "local":
            return "Model Size"
        return "CLI Provider"

    def _sub_option_button_label(self) -> str:
        mode = self.settings.get("generation_mode", "local")
        if mode == "local":
            size = self.settings.get("model_size", "small")
            names = {"small": "Small (Qwen3-4B)", "large": "Large (Qwen3-8B)"}
            return names.get(size, size)
        else:
            preset = self.settings.get("cli_preset", "gemini")
            labels = {"gemini": "Google Gemini", "claude": "Anthropic Claude"}
            return labels.get(preset, preset)

    def _sfx_label(self) -> str:
        enabled = self.settings.get("sfx_enabled", True)
        return f"Sound Effects: {'On' if enabled else 'Off'}"

    def _dev_mode_label(self) -> str:
        dev_mode = self.settings.get("dev_mode", False)
        return f"Dev Mode: {'On' if dev_mode else 'Off'}"

    def _quick_start_label(self) -> str:
        qs = self.settings.get("dev_quick_start", False)
        return f"Quick Start: {'On' if qs else 'Off'}"

    def _refresh_sub_option(self) -> None:
        """Update the sub-option label and button to match the current mode."""
        self.query_one("#sub_option_label", Static).update(self._sub_option_label_text())
        self.query_one("#toggle_sub_option", Button).label = self._sub_option_button_label()

    # --- Button handlers ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "toggle_mode":
            current_mode = self.settings.get("generation_mode", "local")
            new_mode = "gemini_cli" if current_mode == "local" else "local"

            if new_mode == "gemini_cli":
                preset = self.settings.get("cli_preset", "gemini")
                if not check_cli_auth(preset):
                    tool_name = {"gemini": "Google Gemini", "claude": "Anthropic Claude"}.get(preset, preset)
                    self.notify(f"Warning: {tool_name} CLI not found or not authenticated!", severity="warning", timeout=5.0)

            self.settings["generation_mode"] = new_mode
            save_settings(self.settings)
            event.button.label = self._mode_label()
            self.app.generation_mode = new_mode
            self._refresh_sub_option()

        elif event.button.id == "toggle_sub_option":
            mode = self.settings.get("generation_mode", "local")

            if mode == "local":
                # Toggle between small and large
                current = self.settings.get("model_size", "small")
                new_size = "large" if current == "small" else "small"
                self.settings["model_size"] = new_size
                save_settings(self.settings)
                self.app.model_size = new_size
                self.app.llm_pipeline = None
                self.notify("Model size changed. Will reload on return to main menu.", severity="information", timeout=3.0)
            else:
                # Toggle between gemini and claude
                current = self.settings.get("cli_preset", "gemini")
                new_preset = "claude" if current == "gemini" else "gemini"
                self.settings["cli_preset"] = new_preset
                save_settings(self.settings)
                self.app.cli_preset = new_preset

                tool_name = {"gemini": "Google Gemini", "claude": "Anthropic Claude"}.get(new_preset, new_preset)
                if not check_cli_auth(new_preset):
                    self.notify(f"{tool_name} CLI not found or not authenticated.", severity="warning", timeout=5.0)
                else:
                    self.notify(f"CLI provider set to {tool_name}.", severity="information", timeout=3.0)

            event.button.label = self._sub_option_button_label()

        elif event.button.id == "toggle_sfx":
            current = self.settings.get("sfx_enabled", True)
            new_val = not current
            self.settings["sfx_enabled"] = new_val
            save_settings(self.settings)
            event.button.label = self._sfx_label()
            self.app.audio_manager.enabled = new_val

        elif event.button.id == "toggle_dev_mode":
            current_dev_mode = self.settings.get("dev_mode", False)
            new_dev_mode = not current_dev_mode
            self.settings["dev_mode"] = new_dev_mode
            save_settings(self.settings)
            event.button.label = self._dev_mode_label()
            self.app.dev_mode = new_dev_mode

        elif event.button.id == "toggle_quick_start":
            current_qs = self.settings.get("dev_quick_start", False)
            new_qs = not current_qs
            self.settings["dev_quick_start"] = new_qs
            save_settings(self.settings)
            event.button.label = self._quick_start_label()
            self.app.dev_quick_start = new_qs

        elif event.button.id == "back":
            self.app.pop_screen()

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen
from senseibox_onboarding.screens.connecting import ConnectingScreen


class PasswordScreen(WizardScreen):
    def setup_title(self) -> str:
        return "Network Setup" if self.app.wifi_only else "Step 1 of 3: Network Setup"

    def compose(self) -> ComposeResult:
        network = self.app.selected_network
        name = network.ssid if network else "this network"
        with self.page():
            yield StepHeader(
                self.setup_title(),
                f"Enter the password for {name}.",
            )
            if network and network.signal < self.app.config.weak_signal_threshold:
                yield Static(
                    "This signal looks weak. Setup may still work, but moving Senseibox closer to the router can help.",
                    classes="status",
                )
            yield Input(placeholder="WiFi password", password=False, id="wifi_password")
            with Horizontal(classes="actions"):
                yield Button("Connect", id="connect_password")
                yield Button("Cancel", id="cancel_password")
        yield HintBar("[Tab] Move   [Enter] Activate   [Esc] Exit")

    def on_mount(self) -> None:
        self.query_one("#wifi_password", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect_password":
            self._connect()
        elif event.button.id == "cancel_password":
            self.app.pop_screen()

    def _connect(self) -> None:
        password = self.query_one("#wifi_password", Input).value
        self.app.wifi_password = password
        self.app.state.step = "connecting"
        self.app.save_state()
        self.app.push_screen(ConnectingScreen())

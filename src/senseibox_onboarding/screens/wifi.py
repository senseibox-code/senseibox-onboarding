from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from senseibox_onboarding.models import WifiNetwork
from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen
from senseibox_onboarding.screens.connecting import ConnectingScreen
from senseibox_onboarding.screens.password import PasswordScreen


SSID_WIDTH = 30
SIGNAL_WIDTH = 4
SECURITY_WIDTH = 8
SIGNAL_CELLS = 5
STRENGTH_WIDTH = 8
STATUS_WIDTH = 14
MAX_VISIBLE_NETWORKS = 12


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"


def _signal_style(signal: int) -> str:
    if signal >= 65:
        return "green"
    if signal >= 35:
        return "dark_orange"
    return "deep_pink3"


def _signal_meter(signal: int) -> str:
    filled = max(1, min(SIGNAL_CELLS, round(signal / 100 * SIGNAL_CELLS)))
    return "█" * filled + "░" * (SIGNAL_CELLS - filled)


def _network_row(network: WifiNetwork) -> Text:
    ssid = _truncate(network.ssid, SSID_WIDTH)
    security = "secured" if network.needs_password else "open"
    status = "Connected" if network.in_use else "-"

    row = Text()
    row.append(f"{ssid:<{SSID_WIDTH}}  ")
    row.append(f"{_signal_meter(network.signal):<{STRENGTH_WIDTH}}", style=_signal_style(network.signal))
    row.append(
        f"  {network.signal:>{SIGNAL_WIDTH}}%  {security:<{SECURITY_WIDTH}}"
    )
    row.append(f"  {status:<{STATUS_WIDTH}}", style="dim")
    return row


def _network_header() -> Text:
    header = Text()
    header.append(f"{'SSID':<{SSID_WIDTH}}  ", style="bold")
    header.append(f"{'Strength':<{STRENGTH_WIDTH}}  ", style="bold")
    header.append(f"{'Quality':>{SIGNAL_WIDTH + 1}}  ", style="bold")
    header.append(f"{'Security':<{SECURITY_WIDTH}}", style="bold")
    header.append(f"  {'Status':<{STATUS_WIDTH}}", style="bold")
    return header


class NetworkItem(ListItem):
    def __init__(self, network: WifiNetwork) -> None:
        self.network = network
        super().__init__(Label(_network_row(network)))


class WifiScreen(WizardScreen):
    BINDINGS = [
        ("r", "refresh_networks", "Refresh networks"),
        ("h", "hidden", "Hidden network"),
    ]

    networks: list[WifiNetwork]

    def setup_title(self) -> str:
        return "Network Setup" if self.app.wifi_only else "Step 1 of 3: Network Setup"

    def compose(self) -> ComposeResult:
        with self.page():
            yield StepHeader(
                self.setup_title(),
                "Select your local Wi-Fi network and enter the password.",
            )
            yield Static("Scanning...", id="wifi_status", classes="status")
            with Vertical(classes="wifi-box"):
                yield Static(_network_header(), id="wifi_header")
                yield ListView(id="wifi_list")
        yield HintBar("[↓][↑] Choose   [Enter] Select   [r] Refresh networks   [h] Hidden network   [Esc] Exit")

    def on_mount(self) -> None:
        self.networks = []
        if self.app.pending_wifi_networks is None and self.app.pending_wifi_scan_error is None:
            self.action_refresh_networks()
            return

        self.networks = self.app.pending_wifi_networks or []
        scan_error = self.app.pending_wifi_scan_error
        self.app.pending_wifi_networks = None
        self.app.pending_wifi_scan_error = None
        self.run_worker(
            self._show_scanned_networks(scan_error),
            name="wifi-show-scanned-networks",
            exclusive=True,
        )

    def action_refresh_networks(self) -> None:
        status = self.query_one("#wifi_status", Static)
        status.remove_class("error")
        status.update("Scanning for nearby networks...")
        self.networks = []
        self.query_one("#wifi_header", Static).add_class("hidden")
        self.query_one("#wifi_list", ListView).clear()
        self.query_one("#wifi_list", ListView).styles.height = 0
        self.query_one(".wifi-box", Vertical).styles.height = 0
        self.run_worker(self._scan(), name="wifi-scan", exclusive=True)

    async def _scan(self) -> None:
        try:
            self.networks = await self.app.network_service.scan_wifi()
        except Exception as error:
            status = self.query_one("#wifi_status", Static)
            status.update(str(error) or "Senseibox could not scan right now. Press r to refresh networks.")
            status.add_class("error")
            self.app.log_exception("WiFi scan failed")
            return

        await self._show_scanned_networks()

    async def _show_scanned_networks(self, scan_error: str | None = None) -> None:
        list_view = self.query_one("#wifi_list", ListView)
        list_view.clear()
        if not self.networks:
            self.query_one("#wifi_header", Static).add_class("hidden")
            self.query_one("#wifi_list", ListView).styles.height = 0
            self.query_one(".wifi-box", Vertical).styles.height = 0
            status = self.query_one("#wifi_status", Static)
            status.update(
                scan_error
                or "No WiFi networks were found. Move closer to your router or press r to refresh networks."
            )
            if scan_error:
                status.add_class("error")
            return

        status = self.query_one("#wifi_status", Static)
        status.remove_class("error")
        self.query_one("#wifi_header", Static).remove_class("hidden")
        self._resize_network_list()
        for network in self.networks:
            await list_view.append(NetworkItem(network))
            await asyncio.sleep(0.05)
        connected = next((network for network in self.networks if network.in_use), None)
        if connected:
            status.update(
                f"Connected to {connected.ssid}. Choose a different network to change Wi-Fi."
            )
        else:
            status.update("Select a network.")
        list_view.focus()

    def _resize_network_list(self) -> None:
        visible_rows = min(max(len(self.networks), 1), MAX_VISIBLE_NETWORKS)
        self.query_one("#wifi_list", ListView).styles.height = visible_rows
        self.query_one(".wifi-box", Vertical).styles.height = visible_rows + 3

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, NetworkItem):
            network = event.item.network
            if network.in_use:
                self.query_one("#wifi_status", Static).update(
                    f"Already connected to {network.ssid}. Choose a different network to change Wi-Fi."
                )
                return

            self.app.selected_network = network
            self.app.hidden_network = False
            self.app.state.selected_ssid = network.ssid
            self.app.state.step = "password" if network.needs_password else "connecting"
            self.app.save_state()
            if network.needs_password:
                self.app.push_screen(PasswordScreen())
            else:
                self.app.wifi_password = None
                self.app.push_screen(ConnectingScreen())

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        for item in self.query(NetworkItem):
            item.remove_class("selected")
        if isinstance(event.item, NetworkItem):
            event.item.add_class("selected")

    def action_hidden(self) -> None:
        self.app.push_screen("hidden_wifi")


class HiddenWifiScreen(WizardScreen):
    def setup_title(self) -> str:
        return "Network Setup" if self.app.wifi_only else "Step 1 of 3: Network Setup"

    def compose(self) -> ComposeResult:
        with self.page():
            yield StepHeader(
                self.setup_title(),
                "Enter the exact network name and password.",
            )
            yield Input(placeholder="Network name", id="hidden_ssid")
            yield Input(placeholder="WiFi password", password=False, id="hidden_password")
            with Horizontal(classes="actions"):
                yield Button("Connect", id="connect_hidden")
                yield Button("Cancel", id="cancel_hidden")
        yield HintBar("[Tab] Move   [Enter] Activate   [Esc] Exit")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "hidden_password":
            self.query_one("#hidden_password", Input).focus()
            return
        ssid = self.query_one("#hidden_ssid", Input).value.strip()
        password = self.query_one("#hidden_password", Input).value
        if not ssid:
            return
        self.app.selected_network = WifiNetwork(
            ssid=ssid,
            bssid=None,
            signal=0,
            security=self.app.secured_security,
        )
        self.app.wifi_password = password
        self.app.hidden_network = True
        self.app.push_screen(ConnectingScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect_hidden":
            ssid = self.query_one("#hidden_ssid", Input).value.strip()
            if ssid:
                self.app.selected_network = WifiNetwork(
                    ssid=ssid,
                    bssid=None,
                    signal=0,
                    security=self.app.secured_security,
                )
                self.app.wifi_password = self.query_one("#hidden_password", Input).value
                self.app.hidden_network = True
                self.app.push_screen(ConnectingScreen())
        elif event.button.id == "cancel_hidden":
            self.app.pop_screen()

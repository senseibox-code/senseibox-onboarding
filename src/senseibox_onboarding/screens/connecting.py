from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from senseibox_onboarding.screens.base import CommandLog, HintBar, StepHeader, WizardScreen


JOINING_WIFI = "Joining WiFi..."
CHECKING_INTERNET = "Checking internet access..."
EXIT_HINT = "Press Esc to exit"
SUCCESS_MARK = "✓"
WARNING_MARK = "!"
TEXT_STYLE = "#ffffff"
ERROR_STYLE = "#ff7a7a"
SUCCESS_STYLE = "#00d26a bold"
WARNING_STYLE = "#f2c94c bold"
TROUBLESHOOTING_PREFIX = "For troubleshooting, check the log file at"


@dataclass(frozen=True)
class StatusLine:
    message: str
    marker: str | None = None
    marker_style: str = SUCCESS_STYLE


class ConnectingScreen(WizardScreen):
    def __init__(self) -> None:
        super().__init__()
        self._show_troubleshooting_hint = False

    def setup_title(self) -> str:
        return "Network Setup" if self.app.wifi_only else "Step 1 of 3: Network Setup"

    def compose(self) -> ComposeResult:
        network = self.app.selected_network
        name = network.ssid if network else "the network"
        with self.page():
            yield StepHeader(
                self.setup_title(),
                "This can take a few moments. Senseibox will check internet access after WiFi connects.",
            )
            if self.app.remote_session:
                yield Static(
                    "Changing WiFi can disconnect this remote session. If that happens, reconnect after Senseibox joins the network.",
                    classes="warning",
                )
            yield Static(f"Connecting to {name}.", classes="status")
            yield CommandLog(id="command_log")
            yield Static(
                self._status_text([StatusLine(JOINING_WIFI)]),
                id="connect_status",
                classes="status",
            )
            with Horizontal(classes="actions"):
                yield Button("Try again", id="retry_connect", classes="connection-action hidden")
                yield Button("Choose network", id="choose_network", classes="connection-action hidden")
        yield HintBar("[Tab] Move   [Enter] Activate   [Esc] Exit")

    def on_mount(self) -> None:
        self._show_troubleshooting_hint = False
        self.app.clear_command_output()
        self.set_interval(0.2, self._refresh_command_log)
        self.run_worker(self._connect(), name="wifi-connect", exclusive=True)

    async def _connect(self) -> None:
        network = self.app.selected_network
        if network is None:
            self.app.push_screen("wifi")
            return

        result = await self.app.network_service.connect_wifi(
            network,
            self.app.wifi_password,
            hidden=self.app.hidden_network,
        )
        if not result.ok:
            self.app.state.connection_failures += 1
            self.app.save_state()
            self._show_troubleshooting_hint = True
            self._show_error(result.message)
            self._refresh_command_log()
            self._show_connection_actions(True)
            return

        self.app.state.connection_failures = 0
        self.app.save_state()
        self._show_connection_actions(False)
        self._status_widget().remove_class("error")

        local_ip = await self.app.network_service.get_local_ip()
        ip_text = f"(Local IP is {local_ip})" if local_ip else ""
        self._show_progress(ip_text)

        online = await self.app.connectivity_service.has_internet()
        if self.app.wifi_only:
            self._show_complete(ip_text, online)
            self._refresh_command_log()
            return

        if online:
            self.app.state.step = "linux_account"
            self.app.save_state()
            self.app.push_screen("linux_account")
        else:
            self._show_offline(ip_text)
        self._refresh_command_log()

    def action_cancel(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "retry_connect":
            self._show_troubleshooting_hint = False
            self._status_widget().remove_class("error")
            self._status_widget().update(self._status_text([StatusLine(JOINING_WIFI)]))
            self._show_connection_actions(False)
            self.app.clear_command_output()
            self.run_worker(self._connect(), name="wifi-connect", exclusive=True)
        elif event.button.id == "choose_network":
            self.app.selected_network = None
            self.app.wifi_password = None
            self.app.hidden_network = False
            self.app.switch_screen("wifi")

    def _show_connection_actions(self, visible: bool) -> None:
        for button in self.query(".connection-action"):
            if visible:
                button.remove_class("hidden")
            else:
                button.add_class("hidden")

    def _refresh_command_log(self) -> None:
        log = self.query_one("#command_log", CommandLog)
        output = self.app.command_output_text()
        if self._show_troubleshooting_hint:
            log_path = self.app.config.paths.log_file
            hint = f"{TROUBLESHOOTING_PREFIX} {log_path}"
            output = f"{output}\n\n{hint}" if output else hint
        log.set_log_text(output, follow=self.app.command_running)

    def _status_widget(self) -> Static:
        return self.query_one("#connect_status", Static)

    def _show_error(self, message: str) -> None:
        self._status_widget().update(Text(message, style=ERROR_STYLE))
        self._status_widget().add_class("error")

    def _show_progress(self, ip_text: str) -> None:
        self._status_widget().update(
            self._status_text(
                [
                    StatusLine(JOINING_WIFI),
                    StatusLine(f"WiFi connected {ip_text}".strip(), SUCCESS_MARK),
                    StatusLine(CHECKING_INTERNET),
                ]
            )
        )

    def _show_complete(self, ip_text: str, online: bool) -> None:
        lines = [
            StatusLine(JOINING_WIFI),
            StatusLine(f"WiFi connected {ip_text}".strip(), SUCCESS_MARK),
        ]
        if online:
            lines.append(StatusLine("Internet access verified", SUCCESS_MARK))
        else:
            lines.append(
                StatusLine(
                    "Internet access could not be verified",
                    WARNING_MARK,
                    WARNING_STYLE,
                )
            )
        self._status_widget().update(self._status_text(lines, exit_hint=True))

    def _show_offline(self, ip_text: str) -> None:
        self._status_widget().update(
            self._status_text(
                [
                    StatusLine(JOINING_WIFI),
                    StatusLine(f"WiFi connected {ip_text}".strip(), SUCCESS_MARK),
                    StatusLine(
                        "Internet access could not be verified",
                        WARNING_MARK,
                        WARNING_STYLE,
                    ),
                    StatusLine("You can continue, or go back and choose another network."),
                ]
            )
        )

    def _status_text(self, lines: list[StatusLine], *, exit_hint: bool = False) -> Text:
        text = Text()
        for line in lines:
            if text.plain:
                text.append("\n")
            if line.marker:
                text.append(line.marker, style=line.marker_style)
                text.append(" ")
            text.append(line.message, style=TEXT_STYLE)
            if line.message == JOINING_WIFI and len(lines) > 1:
                text.append("\n", style=TEXT_STYLE)
        if exit_hint:
            text.append(f"\n\n{EXIT_HINT}", style=TEXT_STYLE)
        return text

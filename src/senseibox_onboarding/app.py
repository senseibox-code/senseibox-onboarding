from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time

from textual.app import App
from textual.binding import Binding

from senseibox_onboarding.config import RuntimeConfig
from senseibox_onboarding.logging_config import configure_logging
from senseibox_onboarding.models import Security, WifiNetwork
from senseibox_onboarding.screens.account import LinuxAccountScreen
from senseibox_onboarding.screens.checks import ChecksScreen
from senseibox_onboarding.screens.complete import CompleteScreen
from senseibox_onboarding.screens.connecting import ConnectingScreen
from senseibox_onboarding.screens.password import PasswordScreen
from senseibox_onboarding.screens.splash import SplashScreen
from senseibox_onboarding.screens.welcome import WelcomeScreen
from senseibox_onboarding.screens.wifi import HiddenWifiScreen, WifiScreen
from senseibox_onboarding.services.connectivity import ConnectivityService
from senseibox_onboarding.services.fake import (
    FakeConnectivityService,
    FakeNetworkManagerService,
    FakeSystemService,
)
from senseibox_onboarding.services.network import NetworkManagerService
from senseibox_onboarding.services.process import CommandRunner
from senseibox_onboarding.services.system import SystemService
from senseibox_onboarding.state import OnboardingState

LOG = logging.getLogger(__name__)
MAX_COMMAND_OUTPUT_LINES = 200


def reset_onboarding_state(config: RuntimeConfig) -> None:
    """Clear resumable onboarding state without deleting Linux users."""

    for path in (config.paths.complete_marker, config.paths.state_file):
        try:
            path.unlink()
        except FileNotFoundError:
            continue


class SenseiboxOnboardingApp(App[None]):
    """Terminal-native onboarding wizard for first boot."""

    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("escape", "exit_setup", "Exit", priority=True),
    ]
    CSS = """
    Screen {
        background: black;
        scrollbar-size: 1 1;
    }
    """

    SCREENS = {
        "welcome": WelcomeScreen,
        "checks": ChecksScreen,
        "wifi_splash": SplashScreen,
        "wifi": WifiScreen,
        "hidden_wifi": HiddenWifiScreen,
        "password": PasswordScreen,
        "connecting": ConnectingScreen,
        "linux_account": LinuxAccountScreen,
        "complete": CompleteScreen,
    }

    def __init__(self, config: RuntimeConfig | None = None, *, wifi_only: bool = False) -> None:
        super().__init__()
        self.wifi_only = wifi_only
        self.config = config or RuntimeConfig()
        configure_logging(self.config.paths.log_file)
        self.state = OnboardingState.load(self.config.paths.state_file)
        self.command_output_lines: list[str] = []
        self.command_running = False
        self.command_started_at = 0.0
        self.remote_session = bool(
            os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT")
        )
        self.runner = CommandRunner(
            on_output=self.record_command_output,
            on_running=self.set_command_running,
        )
        if os.environ.get("SENSEIBOX_ONBOARDING_FAKE_NETWORK") == "1":
            LOG.info("Using fake onboarding services")
            self.network_service = FakeNetworkManagerService()
            self.connectivity_service = FakeConnectivityService()
            self.system_service = FakeSystemService(self.runner)
        else:
            self.network_service = NetworkManagerService(self.runner, self.config)
            self.connectivity_service = ConnectivityService(self.runner, self.config)
            self.system_service = SystemService(self.runner)
        self.selected_network: WifiNetwork | None = None
        self.pending_wifi_networks: list[WifiNetwork] | None = None
        self.pending_wifi_scan_error: str | None = None
        self.pending_wired_connected = False
        self.pending_wired_local_ip: str | None = None
        self.wifi_password: str | None = None
        self.hidden_network = False
        self.secured_security = Security.SECURED
        self.login_after_exit: str | None = None

    def on_mount(self) -> None:
        if self.wifi_only:
            LOG.info("Senseibox WiFi setup starting")
            self.push_screen("wifi_splash")
            return

        LOG.info("Senseibox onboarding starting at step=%s", self.state.step)
        if self.state.completed:
            self.push_screen("complete")
            return
        start_screen = self.state.step if self.state.step in self.SCREENS else "welcome"
        if start_screen in {"password", "connecting"}:
            start_screen = "wifi"
        if start_screen in {"welcome", "checks", "wifi"}:
            start_screen = "wifi_splash"
        self.push_screen(start_screen)

    def save_state(self) -> None:
        self.state.save(self.config.paths.state_file)

    def log_exception(self, message: str) -> None:
        LOG.exception(message)

    def clear_command_output(self) -> None:
        self.command_output_lines.clear()
        self.command_running = False
        self.command_started_at = 0.0
        self.refresh_command_output()

    def set_command_running(self, running: bool) -> None:
        self.command_running = running
        if running:
            self.command_started_at = time.monotonic()
        self.refresh_command_output()

    def record_command_output(self, line: str) -> None:
        self.command_output_lines.append(line)
        self.command_output_lines = self.command_output_lines[-MAX_COMMAND_OUTPUT_LINES:]
        self.refresh_command_output()

    def command_output_text(self) -> str:
        lines = self.command_output_lines[-MAX_COMMAND_OUTPUT_LINES:]
        if self.command_running:
            dots = "." * ((int((time.monotonic() - self.command_started_at) * 2) % 3) + 1)
            lines = [*lines, f"Running command{dots}"][-MAX_COMMAND_OUTPUT_LINES:]
        return "\n".join(lines)

    def refresh_command_output(self) -> None:
        text = self.command_output_text()
        for widget in self.query(".command-log"):
            if hasattr(widget, "set_log_text"):
                widget.set_log_text(text, follow=self.command_running)
            else:
                widget.update(text)

    def action_exit_setup(self) -> None:
        LOG.info("Onboarding exited by user")
        self.save_state()
        self.exit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Senseibox onboarding.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="clear onboarding state and start setup again",
    )
    parser.add_argument(
        "--wifi-only",
        action="store_true",
        help="run only the WiFi setup flow",
    )
    args = parser.parse_args()

    config = RuntimeConfig.from_env()
    if args.reset:
        reset_onboarding_state(config)

    app = SenseiboxOnboardingApp(config, wifi_only=args.wifi_only)
    app.run(mouse=False)
    if app.login_after_exit:
        print("\033[2J\033[H", end="", flush=True)
        result = asyncio.run(app.system_service.open_login_session(app.login_after_exit))
        if not result.ok:
            print(result.message)


if __name__ == "__main__":
    main()

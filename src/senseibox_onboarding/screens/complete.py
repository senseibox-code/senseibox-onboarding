from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen


HOSTNAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$|^[a-z0-9]$")
DEFAULT_HOSTNAME = "senseibox"


def _numbered_step(number: int, text: str) -> Static:
    line = Text()
    line.append(f" {number} ", style="black on #d9e1e1 bold")
    line.append("  ")
    line.append(text, style="white")
    return Static(line, classes="instruction")


def _yes_step() -> Static:
    line = Text()
    line.append(" 3 ", style="black on #d9e1e1 bold")
    line.append("  Type ")
    line.append(" yes ", style="black on #d9e1e1")
    line.append(" when asked to connect.", style="white")
    return Static(line, classes="instruction")


def _ssh_command(command: str) -> Static:
    return Static(f"$  {command}", id="ssh_command", classes="code-block", markup=False)


class CompleteScreen(WizardScreen):
    BINDINGS = [
        ("enter", "finish", "Finish"),
        ("u", "update_hostname", "Update hostname"),
    ]

    def compose(self) -> ComposeResult:
        username = self.app.state.linux_username or "your-user"
        hostname = self.app.state.hostname or DEFAULT_HOSTNAME
        ssh_target = f"{username}@{hostname}.local"
        with self.page():
            yield StepHeader(
                "Step 3 of 3: Setup Completed",
                "Your Linux account has been created. Senseibox is ready for SSH and local login.",
            )
            with Vertical(id="hostname_section"):
                yield Static(
                    "Choose a hostname for this Senseibox. You will use it to connect over SSH.",
                    classes="instruction",
                )
                yield Static("Hostname", classes="field-label")
                yield Input(value=hostname, placeholder=DEFAULT_HOSTNAME, id="hostname_input")
                yield Static("", id="hostname_status", classes="status")
                with Horizontal(classes="actions"):
                    yield Button("Save hostname", id="save_hostname")
            with Vertical(id="ssh_section", classes="hidden"):
                yield Static(
                    "To connect to your box via SSH, use your Linux account name and password.",
                    classes="instruction",
                )
                yield _numbered_step(1, "Open a terminal.")
                yield _numbered_step(2, "Run the following command:")
                yield _ssh_command(f"ssh {ssh_target}")
                yield _yes_step()
                yield _numbered_step(
                    4,
                    "Enter the password for the board. This is the password you chose previously.",
                )
                yield Static("")
                yield Static(
                    "Press Enter to start Senseibox services and open your local login session.",
                    id="finish_status",
                    classes="instruction",
                )
                yield Static(
                    f"Press u to update hostname {hostname}.",
                    id="hostname_update_hint",
                    classes="instruction",
                )
        yield HintBar("[Tab] Move   [Enter] Activate   [Esc] Exit")

    def on_mount(self) -> None:
        if self.app.state.hostname:
            self._show_ssh_instructions()
        else:
            self.query_one("#hostname_input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "hostname_input":
            await self._save_hostname()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_hostname":
            await self._save_hostname()

    def action_update_hostname(self) -> None:
        self.query_one("#ssh_section", Vertical).add_class("hidden")
        self.query_one("#hostname_section", Vertical).remove_class("hidden")
        hostname_input = self.query_one("#hostname_input", Input)
        hostname_input.value = self.app.state.hostname or DEFAULT_HOSTNAME
        hostname_input.focus()
        self.query_one(".hints", HintBar).update("[Tab] Move   [Enter] Activate   [Esc] Exit")

    async def _save_hostname(self) -> None:
        status = self.query_one("#hostname_status", Static)
        status.remove_class("error")

        hostname = self._normalize_hostname(self.query_one("#hostname_input", Input).value)
        validation_error = self._validate_hostname(hostname)
        if validation_error:
            status.update(validation_error)
            status.add_class("error")
            return

        status.update(f"Updating hostname to {hostname}...")
        result = await self.app.system_service.configure_hostname(hostname)
        if not result.ok:
            status.update(result.message)
            status.add_class("error")
            return

        self.app.state.hostname = hostname
        self.app.save_state()
        status.update(result.message)
        self._show_ssh_instructions()

    def _show_ssh_instructions(self) -> None:
        username = self.app.state.linux_username or "your-user"
        hostname = self.app.state.hostname or DEFAULT_HOSTNAME
        self.query_one("#ssh_command", Static).update(f"$  ssh {username}@{hostname}.local")
        self.query_one("#hostname_update_hint", Static).update(
            f"Press u to update hostname {hostname}."
        )
        self.query_one("#hostname_section", Vertical).add_class("hidden")
        self.query_one("#ssh_section", Vertical).remove_class("hidden")
        self.query_one(".hints", HintBar).update("[Enter] Finish   [u] Update hostname")

    def _normalize_hostname(self, value: str) -> str:
        hostname = value.strip().lower()
        if hostname.endswith(".local"):
            hostname = hostname.removesuffix(".local")
        return hostname

    def _validate_hostname(self, hostname: str) -> str | None:
        if not hostname:
            return "Enter a hostname."
        if not HOSTNAME_RE.match(hostname):
            return "Use lowercase letters, numbers, or hyphens. Do not start or end with a hyphen."
        return None

    async def action_finish(self) -> None:
        if not self.app.state.hostname:
            await self._save_hostname()
            return

        self.app.state.completed = True
        self.app.state.step = "complete"
        self.app.save_state()
        self.app.state.mark_complete(self.app.config.paths.complete_marker)
        await self.app.system_service.launch_main_services()
        username = self.app.state.linux_username
        if username:
            result = await self.app.system_service.open_login_session(username)
            if not result.ok:
                self.query_one("#finish_status", Static).update(
                    result.message + " Exiting setup instead."
                )
        self.app.exit()

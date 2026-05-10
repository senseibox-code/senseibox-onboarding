from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from senseibox_onboarding.screens.base import CommandLog, HintBar, StepHeader, WizardScreen


USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
RESERVED_USERNAMES = {"root", "daemon", "bin", "sys", "sync", "games", "man", "lp"}


class LinuxAccountScreen(WizardScreen):
    def compose(self) -> ComposeResult:
        with self.page():
            yield StepHeader(
                "Step 2 of 3: Linux Account",
                "Create a new user and password. You will use this account for SSH and local login.",
            )
            yield Static("Username", classes="field-label first")
            yield Input(placeholder="Linux username", id="linux_username")
            yield Static("Password", classes="field-label")
            yield Input(placeholder="Password", password=True, id="linux_password")
            yield Static("Verify password", classes="field-label")
            yield Input(placeholder="Verify password", password=True, id="linux_password_verify")
            yield Static("", id="account_status", classes="status")
            yield Static(f"Log file: {self.app.config.paths.log_file}", classes="log-path")
            yield CommandLog(id="command_log")
            with Horizontal(classes="actions"):
                yield Button("Create user", id="create_account")
                yield Button("Cancel", id="cancel_account")
        yield HintBar("[Tab] Move   [Enter] Activate   [Esc] Exit")

    def on_mount(self) -> None:
        self.query_one("#linux_username", Input).focus()
        self.set_interval(0.2, self._refresh_command_log)
        if self.app.state.linux_username:
            self.run_worker(self._continue_if_account_exists(), name="account-check", exclusive=True)

    async def _continue_if_account_exists(self) -> None:
        username = self.app.state.linux_username
        if not username:
            return
        status = self.query_one("#account_status", Static)
        status.update(f"Checking Linux account {username}...")
        if await self.app.system_service.account_exists(username):
            status.update("Linux account already exists. Continuing...")
            self.app.state.step = "complete"
            self.app.save_state()
            self.app.push_screen("complete")
        else:
            status.update("Create the Linux account to continue.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "linux_username":
            self.query_one("#linux_password", Input).focus()
        elif event.input.id == "linux_password":
            self.query_one("#linux_password_verify", Input).focus()
        else:
            await self._create_account()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_account":
            await self._create_account()
        elif event.button.id == "cancel_account":
            self.app.push_screen("wifi")

    async def _create_account(self) -> None:
        username = self.query_one("#linux_username", Input).value.strip()
        password = self.query_one("#linux_password", Input).value
        verify = self.query_one("#linux_password_verify", Input).value
        status = self.query_one("#account_status", Static)
        status.remove_class("error")

        validation_error = self._validate(username, password, verify)
        if validation_error:
            status.update(validation_error)
            status.add_class("error")
            return

        self.app.clear_command_output()
        status.update("Creating Linux account...")
        result = await self.app.system_service.create_linux_account(username, password)
        self._refresh_command_log()
        if not result.ok:
            status.update(result.message)
            status.add_class("error")
            return

        self.app.state.linux_username = username
        self.app.state.step = "complete"
        self.app.save_state()
        self.app.push_screen("complete")

    def _validate(self, username: str, password: str, verify: str) -> str | None:
        if not USERNAME_RE.match(username):
            return "Use a valid Linux username: lowercase letters, numbers, underscore, or hyphen."
        if username in RESERVED_USERNAMES:
            return "That username is reserved. Choose another username."
        if len(password) < 8:
            return "Use a password with at least 8 characters."
        if password != verify:
            return "The passwords do not match."
        if password.lower() == username.lower():
            return "The password must be different from the username."
        return None

    def _refresh_command_log(self) -> None:
        log = self.query_one("#command_log", CommandLog)
        log.set_log_text(self.app.command_output_text(), follow=self.app.command_running)

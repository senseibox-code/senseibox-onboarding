from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen


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
    return Static(f"$  {command}", classes="code-block", markup=False)


class CompleteScreen(WizardScreen):
    BINDINGS = [("enter", "finish", "Finish")]

    def compose(self) -> ComposeResult:
        username = self.app.state.linux_username or "your-user"
        ssh_target = f"{username}@senseibox.local"
        with self.page():
            yield StepHeader(
                "Step 3 of 3: Setup Completed",
                "Your Linux account has been created. Senseibox is ready for SSH and local login.",
            )
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
        yield HintBar("[Enter] Finish")

    async def action_finish(self) -> None:
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

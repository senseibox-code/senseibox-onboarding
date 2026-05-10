from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen


class ChecksScreen(WizardScreen):
    BINDINGS = [
        ("u", "retry", "Update"),
    ]

    def compose(self) -> ComposeResult:
        with self.page():
            yield StepHeader(
                "Checking Senseibox",
                "Senseibox is making sure the network hardware and services are ready.",
            )
            yield Static("Starting checks...", id="check_status", classes="status")
            yield Static("", id="check_details", classes="body")
        yield HintBar("[u] Update   [Esc] Exit")

    def on_mount(self) -> None:
        self.action_retry()

    def action_retry(self) -> None:
        self.query_one("#check_status", Static).update("Checking network hardware...")
        self.query_one("#check_status", Static).remove_class("error")
        self.query_one("#check_details", Static).update("")
        self.run_worker(self._run_checks(), name="startup-checks", exclusive=True)

    async def _run_checks(self) -> None:
        service = self.app.system_service
        try:
            checks = await service.run_startup_checks()
        except Exception:
            self.app.log_exception("Startup checks failed")
            status = self.query_one("#check_status", Static)
            status.update("Senseibox could not complete its startup checks. Press u to try again.")
            status.add_class("error")
            return

        failed = [check for check in checks if not check.ok]
        status = self.query_one("#check_status", Static)
        details = self.query_one("#check_details", Static)
        if failed:
            primary_failure = failed[0]
            status.update(primary_failure.detail)
            status.add_class("error")
            details.update(
                "\n".join(f"{check.name}: {check.detail}" for check in checks)
                + "\n\nPress u to check again after fixing the issue."
            )
            return
        details.update("\n".join(f"{check.name}: {check.detail}" for check in checks))
        status.update("Everything is ready.")
        self.app.state.step = "wifi"
        self.app.save_state()
        await self.app.push_screen("wifi")

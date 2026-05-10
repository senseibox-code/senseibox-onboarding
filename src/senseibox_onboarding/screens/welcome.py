from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from senseibox_onboarding.screens.base import HintBar, StepHeader, WizardScreen


class WelcomeScreen(WizardScreen):
    BINDINGS = [
        ("enter", "continue_setup", "Continue"),
    ]

    def compose(self) -> ComposeResult:
        with self.page():
            yield StepHeader(
                "Welcome to Senseibox",
                "This short setup will connect Senseibox to your home network and prepare it for first use.",
                title_classes="title brand-title",
            )
            yield Static("You can use the arrow keys, Enter, Esc, and the action keys shown below.")
        yield HintBar("[Enter] Continue   [Esc] Exit")

    def action_continue_setup(self) -> None:
        self.app.push_screen("checks")

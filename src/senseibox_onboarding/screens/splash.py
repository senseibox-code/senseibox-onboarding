from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static


ASCII_LOGO_LINES = """┌───────────┐
│  ███████  │
│  ◤        │
│        ◢  │
│  ███████  │
└───────────┘

Senseibox""".splitlines()
BRAND_MARK_STYLE = "#F4491F"
BORDER_STYLE = "#EBEBEB"
TEXT_STYLE = "#EBEBEB"
BOX_CHARACTERS = frozenset("┌┐└┘─│")
MARK_CHARACTERS = frozenset("█◤◢")


class SplashScreen(Screen[None]):
    CSS = """
    SplashScreen {
        background: black;
        align: center middle;
    }

    #splash_content {
        width: auto;
        height: auto;
    }

    .splash-logo {
        width: 40;
        margin-bottom: 5;
        text-align: center;
    }

    .splash-status {
        width: 40;
        color: #ffffff;
        text-align: center;
    }
    """

    DOTS = ("", ".", "..", "...")

    def __init__(self) -> None:
        super().__init__()
        self._dot_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="splash_content"):
            yield Static(self._logo_text(), classes="splash-logo")
            yield Static(
                self._status_text(),
                id="splash_status",
                classes="splash-status",
                markup=False,
            )

    def on_mount(self) -> None:
        self.set_interval(0.35, self._tick_loading)
        self.run_worker(self._scan(), name="wifi-splash-scan", exclusive=True)

    def _tick_loading(self) -> None:
        self._dot_index = (self._dot_index + 1) % len(self.DOTS)
        self.query_one("#splash_status", Static).update(self._status_text())

    def _status_text(self) -> str:
        dots = self.DOTS[self._dot_index]
        return f"Searching for Wi-Fi connections{dots:<3}"

    def _logo_text(self) -> Text:
        logo = Text()
        for line_index, line in enumerate(ASCII_LOGO_LINES):
            if line_index:
                logo.append("\n")
            if "Senseibox" in line:
                logo.append(line, style=TEXT_STYLE)
                continue
            for character in line:
                if character in BOX_CHARACTERS:
                    logo.append(character, style=BORDER_STYLE)
                elif character in MARK_CHARACTERS:
                    logo.append(character, style=BRAND_MARK_STYLE)
                else:
                    logo.append(character)
        return logo

    async def _scan(self) -> None:
        try:
            self.app.pending_wifi_networks = await self.app.network_service.scan_wifi()
            self.app.pending_wifi_scan_error = None
        except Exception as error:
            self.app.pending_wifi_networks = []
            self.app.pending_wifi_scan_error = (
                str(error) or "Senseibox could not scan right now. Press r to refresh networks."
            )
            self.app.log_exception("Initial WiFi scan failed")
        self.app.state.step = "wifi"
        self.app.save_state()
        self.app.switch_screen("wifi")

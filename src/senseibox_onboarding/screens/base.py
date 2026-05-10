from __future__ import annotations

import textwrap

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Label, Static


class StepHeader(Static):
    def __init__(self, title: str, body: str = "", title_classes: str = "title") -> None:
        super().__init__()
        self.heading = title
        self.body = body
        self.title_classes = title_classes

    def compose(self) -> ComposeResult:
        yield Label(self.heading, classes=self.title_classes)
        if self.body:
            yield Label(self.body, classes="body")
        yield Static("", classes="header-rule")


class HintBar(Static):
    def __init__(self, text: str) -> None:
        super().__init__(text, classes="hints", markup=False)


class CommandLog(Static):
    can_focus = True
    VISIBLE_LINES = 8
    FALLBACK_LINE_WIDTH = 92

    def __init__(self, *, id: str) -> None:
        super().__init__("", id=id, classes="command-log", markup=False)
        self._raw_lines: list[str] = []
        self._lines: list[str] = []
        self._scroll_top = 0
        self._follow_output = True

    def set_log_text(self, text: str, *, follow: bool = False) -> None:
        self._raw_lines = text.splitlines()
        self._lines = self._wrap_lines()
        max_scroll = self._max_scroll
        self._scroll_top = min(self._scroll_top, max_scroll)
        if follow or self._follow_output:
            self._scroll_top = max_scroll
        self._render_visible_lines()

    def on_key(self, event: Key) -> None:
        if event.key in {"up", "k"}:
            self._scroll_by(-1)
            event.stop()
        elif event.key in {"down", "j"}:
            self._scroll_by(1)
            event.stop()
        elif event.key == "pageup":
            self._scroll_by(-self.VISIBLE_LINES)
            event.stop()
        elif event.key == "pagedown":
            self._scroll_by(self.VISIBLE_LINES)
            event.stop()
        elif event.key == "home":
            self._set_scroll_top(0)
            event.stop()
        elif event.key == "end":
            self._set_scroll_top(self._max_scroll)
            event.stop()

    def on_resize(self, event: object) -> None:
        self._lines = self._wrap_lines()
        self._scroll_top = min(self._scroll_top, self._max_scroll)
        self._render_visible_lines()

    @property
    def _max_scroll(self) -> int:
        return max(0, len(self._lines) - self.VISIBLE_LINES)

    def _scroll_by(self, amount: int) -> None:
        self._set_scroll_top(self._scroll_top + amount)

    def _set_scroll_top(self, value: int) -> None:
        self._follow_output = False
        self._scroll_top = max(0, min(value, self._max_scroll))
        if self._scroll_top == self._max_scroll:
            self._follow_output = True
        self._render_visible_lines()

    def _render_visible_lines(self) -> None:
        end = self._scroll_top + self.VISIBLE_LINES
        super().update("\n".join(self._lines[self._scroll_top:end]))

    def _wrap_lines(self) -> list[str]:
        width = self._line_width()
        wrapped: list[str] = []
        for line in self._raw_lines:
            wrapped.extend(
                textwrap.wrap(
                    line,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=False,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                or [""]
            )
        return wrapped

    def _line_width(self) -> int:
        width = self.size.width if self.size.width > 0 else self.FALLBACK_LINE_WIDTH
        return max(20, width - 4)


class WizardScreen(Screen[None]):
    CSS = """
    WizardScreen {
        background: black;
        color: $text;
    }

    .page {
        width: 90%;
        max-width: 96;
        height: 100%;
        margin: 1 4;
    }

    .title {
        color: #00d26a;
        text-style: bold;
        text-align: left;
        margin-top: 1;
        margin-bottom: 1;
    }

    .brand-title {
        color: #00d26a;
    }

    .body {
        color: $text-muted;
        margin-bottom: 1;
    }

    .field-label {
        color: white;
        margin-top: 2;
        margin-bottom: 0;
    }

    .field-label.first {
        margin-top: 0;
    }

    .header-rule {
        height: 1;
        margin-bottom: 1;
        border-top: solid #343434;
    }

    .status {
        margin: 1 0;
        color: white;
    }

    #connect_status {
        color: #ffffff;
    }

    .warning {
        margin: 1 0;
        color: #f2c94c;
    }

    .log-path {
        text-style: italic;
        margin: 1 0 0 0;
        color: #8c8c8c;
    }

    .instruction {
        color: white;
        margin-bottom: 1;
    }

    .code-block {
        width: 82%;
        height: 3;
        margin: 0 0 2 4;
        padding: 1 2;
        background: #1f2628;
        color: white;
        border: none;
    }

    .command-log {
        width: 100%;
        height: 10;
        margin: 0 0 1 0;
        padding: 1 2;
        background: #181818;
        color: #d7d7d7;
        overflow: hidden;
    }

    .command-log:focus {
        background: #101010;
        color: #d7d7d7;
    }

    .error {
        margin: 1 0;
        color: $error;
    }

    .hints {
        dock: bottom;
        height: 2;
        color: white;
        background: black;
        border-top: solid #343434;
        padding: 0 1;
    }

    ListView {
        height: 1fr;
        margin-top: 1;
        background: black;
    }

    .wifi-box {
        width: 100%;
        height: auto;
        margin-top: 1;
        background: black;
    }

    #wifi_header {
        width: 100%;
        margin-top: 0;
        padding: 1 2 0 2;
        background: black;
        color: white;
    }

    #wifi_list {
        width: 100%;
        margin-top: 1;
        background: black;
        scrollbar-color: silver;
        scrollbar-background: black;
        scrollbar-color-hover: silver;
        scrollbar-background-hover: black;
    }

    #wifi_list:focus,
    #wifi_list > .scrollable--content,
    #wifi_list .scrollable--content,
    #wifi_list > .scrollable--viewport,
    #wifi_list .scrollable--viewport {
        background: black;
    }

    ListItem {
        padding: 0 1;
    }

    #wifi_list ListItem {
        background: black;
        color: white;
        padding: 0 2;
    }

    #wifi_list ListItem.selected,
    #wifi_list ListItem.--highlight,
    #wifi_list ListItem.-highlight {
        background: #101010;
        color: white;
    }

    #wifi_list ListItem.selected Label,
    #wifi_list ListItem.--highlight Label,
    #wifi_list ListItem.-highlight Label {
        background: #101010;
        color: white;
    }

    Input {
        margin-top: 1;
        width: 70%;
        height: 3;
        border: none;
        background: #2b2b2b;
        color: white;
        padding: 1 1;
    }

    Input:focus {
        border: none;
        background: #2b2b2b;
        color: white;
    }

    Input > .input--cursor {
        background: #00d26a;
        color: black;
    }

    .actions {
        margin-top: 1;
        height: auto;
    }

    .hidden {
        display: none;
    }

    Button {
        margin-right: 2;
        border: none;
        background: transparent;
        color: white;
        min-width: 10;
        padding: 0 1;
        text-style: none;
    }

    Button:hover,
    Button:focus {
        border: none;
        background: #00d26a;
        color: white;
        text-style: none;
    }

    Button > .button--label {
        background: transparent;
        color: white;
        text-style: none;
    }

    Button:hover > .button--label,
    Button:focus > .button--label {
        background: #00d26a;
        color: white;
        text-style: none;
    }
    """

    def page(self) -> Vertical:
        return Vertical(classes="page")

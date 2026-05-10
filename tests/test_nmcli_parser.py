from __future__ import annotations

import asyncio

import pytest

from senseibox_onboarding.config import RuntimeConfig
from senseibox_onboarding.services.network import (
    NO_WIFI_ADAPTER_MESSAGE,
    NetworkManagerService,
    _split_nmcli_row,
)
from senseibox_onboarding.services.process import CommandResult


def test_split_nmcli_row_handles_escaped_colon() -> None:
    assert _split_nmcli_row(r"My\:Wifi:aa\:bb:80:WPA2:") == [
        "My:Wifi",
        "aa:bb",
        "80",
        "WPA2",
        "",
    ]


class DummyRunner:
    async def run(self, argv, *, timeout_s, input_text=None):
        if argv[:3] == ["nmcli", "-t", "-f"] and argv[-2:] == ["device", "status"]:
            return CommandResult(
                returncode=0,
                stdout="lo:loopback:connected\nenp0s1:ethernet:unmanaged\n",
                stderr="",
            )
        raise AssertionError("WiFi scan command should not run without a WiFi adapter")


def test_scan_wifi_reports_missing_adapter() -> None:
    service = NetworkManagerService(DummyRunner(), RuntimeConfig())

    with pytest.raises(RuntimeError, match="No WiFi adapter") as error:
        asyncio.run(service.scan_wifi())

    assert str(error.value) == NO_WIFI_ADAPTER_MESSAGE

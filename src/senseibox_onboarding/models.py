from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Security(str, Enum):
    OPEN = "open"
    SECURED = "secured"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    bssid: str | None
    signal: int
    security: Security
    in_use: bool = False
    duplicate_count: int = 1

    @property
    def needs_password(self) -> bool:
        return self.security != Security.OPEN

    @property
    def signal_label(self) -> str:
        if self.signal >= 75:
            return "excellent"
        if self.signal >= 55:
            return "good"
        if self.signal >= 35:
            return "fair"
        return "weak"


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    wrong_password: bool = False
    timed_out: bool = False
    needs_rescan: bool = False
    needs_profile_reset: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class AccountResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class HostnameResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class LoginResult:
    ok: bool
    message: str

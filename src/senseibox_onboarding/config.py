from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OnboardingPaths:
    """Filesystem locations used by the appliance onboarding app."""

    state_file: Path = Path("/var/lib/senseibox/onboarding/state.json")
    complete_marker: Path = Path("/var/lib/senseibox/onboarding/complete")
    log_file: Path = Path("/var/log/senseibox/onboarding.log")
    device_config: Path = Path("/etc/senseibox/device.json")


@dataclass(frozen=True)
class RuntimeConfig:
    paths: OnboardingPaths = OnboardingPaths()
    connection_timeout_s: int = 45
    scan_timeout_s: int = 20
    connectivity_timeout_s: int = 8
    weak_signal_threshold: int = 35
    max_connection_failures_before_ap: int = 3
    connectivity_hosts: tuple[str, ...] = (
        "1.1.1.1",
        "8.8.8.8",
    )

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Build config, allowing writable development paths.

        Production images should use the defaults. For local development,
        set SENSEIBOX_ONBOARDING_DATA_DIR to a writable directory.
        """

        data_dir = os.environ.get("SENSEIBOX_ONBOARDING_DATA_DIR")
        if not data_dir:
            if hasattr(os, "geteuid") and os.geteuid() != 0:
                root = Path(".dev-state")
                return cls(
                    paths=OnboardingPaths(
                        state_file=root / "state" / "state.json",
                        complete_marker=root / "state" / "complete",
                        log_file=root / "logs" / "onboarding.log",
                        device_config=root / "config" / "device.json",
                    )
                )
            return cls()

        root = Path(data_dir).expanduser()
        return cls(
            paths=OnboardingPaths(
                state_file=root / "state" / "state.json",
                complete_marker=root / "state" / "complete",
                log_file=root / "logs" / "onboarding.log",
                device_config=root / "config" / "device.json",
            )
        )

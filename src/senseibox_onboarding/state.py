from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


@dataclass
class OnboardingState:
    """Small resumable state file.

    Do not store secrets here. WiFi credentials are handed to NetworkManager
    and password material is handled by the account service only.
    """

    completed: bool = False
    step: str = "welcome"
    linux_username: str | None = None
    hostname: str | None = None
    selected_ssid: str | None = None
    connection_failures: int = 0
    openclaw_setup_requested: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def load(cls, path: Path) -> "OnboardingState":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (json.JSONDecodeError, OSError):
            return cls(step="recovery")
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in raw.items() if key in allowed})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = asdict(self)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, path)

    def mark_complete(self, marker: Path) -> None:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(self.updated_at + "\n", encoding="utf-8")

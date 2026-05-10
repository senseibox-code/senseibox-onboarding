from __future__ import annotations

from senseibox_onboarding.config import RuntimeConfig
from senseibox_onboarding.services.process import CommandRunner


class ConnectivityService:
    def __init__(self, runner: CommandRunner, config: RuntimeConfig) -> None:
        self.runner = runner
        self.config = config

    async def has_internet(self) -> bool:
        for host in self.config.connectivity_hosts:
            result = await self.runner.run(
                ["ping", "-c", "1", "-W", str(self.config.connectivity_timeout_s), host],
                timeout_s=self.config.connectivity_timeout_s + 2,
            )
            if result.returncode == 0:
                return True
        return False

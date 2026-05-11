from __future__ import annotations

import asyncio

from senseibox_onboarding.models import AccountResult, CheckResult, ConnectionResult, LoginResult, Security, WifiNetwork
from senseibox_onboarding.services.system import SystemService


class FakeNetworkManagerService:
    async def has_wifi_device(self) -> bool:
        return True

    async def scan_wifi(self) -> list[WifiNetwork]:
        await asyncio.sleep(0.4)
        return [
            WifiNetwork("BT-89A8ZP", "00:11:22:33:44:55", 86, Security.SECURED),
            WifiNetwork("CommunityFibre10Gb_0BDD4", "00:11:22:33:44:66", 74, Security.SECURED),
            WifiNetwork("CommunityFibre10Gb_7C195", "00:11:22:33:44:77", 58, Security.SECURED),
            WifiNetwork("EE WiFi", "00:11:22:33:44:88", 45, Security.OPEN),
            WifiNetwork("Family room TV", "00:11:22:33:44:99", 34, Security.SECURED),
            WifiNetwork("Matt_PS_5.0Hz", "00:11:22:33:44:aa", 22, Security.SECURED),
        ]

    async def connect_wifi(
        self,
        network: WifiNetwork,
        password: str | None,
        *,
        hidden: bool = False,
    ) -> ConnectionResult:
        await asyncio.sleep(0.8)
        if network.needs_password and password == "wrong":
            return ConnectionResult(
                ok=False,
                wrong_password=True,
                message="That password did not work. Please check it and try again.",
            )
        return ConnectionResult(ok=True, message="Connected to WiFi.")

    async def list_saved_profiles(self) -> list[str]:
        return []

    async def enable_autoconnect(self, connection_name: str) -> None:
        return None

    async def get_local_ip(self) -> str | None:
        await asyncio.sleep(0.1)
        return None

    async def start_ap_fallback(self) -> None:
        return None


class FakeConnectivityService:
    async def has_internet(self) -> bool:
        await asyncio.sleep(0.4)
        return True


class FakeSystemService(SystemService):
    async def run_startup_checks(self) -> list[CheckResult]:
        await asyncio.sleep(0.3)
        return [
            CheckResult("Network tools", True, "Ready"),
            CheckResult("Network service", True, "Ready"),
            CheckResult("WiFi radio", True, "Ready"),
            CheckResult("WiFi hardware", True, "Ready"),
        ]

    async def create_linux_account(self, username: str, password: str) -> AccountResult:
        await asyncio.sleep(0.5)
        if username == "existing":
            return AccountResult(True, "Linux account updated.")
        return AccountResult(True, "Linux account created.")

    async def account_exists(self, username: str) -> bool:
        await asyncio.sleep(0.2)
        return username == "existing"

    async def launch_main_services(self) -> None:
        return None

    async def open_login_session(self, username: str) -> LoginResult:
        await asyncio.sleep(0.2)
        return LoginResult(False, "Fake mode does not open a real login shell.")

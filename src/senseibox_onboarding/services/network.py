from __future__ import annotations

import logging
from collections import Counter

from senseibox_onboarding.config import RuntimeConfig
from senseibox_onboarding.models import ConnectionResult, Security, WifiNetwork
from senseibox_onboarding.services.process import CommandRunner, CommandTimeout

LOG = logging.getLogger(__name__)
NO_WIFI_ADAPTER_MESSAGE = (
    "No WiFi adapter was found. Connect WiFi hardware, then press r to refresh networks."
)


def _split_nmcli_row(row: str) -> list[str]:
    """Split nmcli -t escaped rows.

    nmcli escapes ':' as '\\:' and '\\' as '\\\\'. This avoids brittle parsing
    when an SSID contains punctuation.
    """

    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for char in row:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


class NetworkManagerService:
    def __init__(self, runner: CommandRunner, config: RuntimeConfig) -> None:
        self.runner = runner
        self.config = config

    async def scan_wifi(self) -> list[WifiNetwork]:
        LOG.info("Starting WiFi scan")
        if not await self._has_wifi_device():
            LOG.warning("No WiFi adapter found in NetworkManager device list")
            raise RuntimeError(NO_WIFI_ADAPTER_MESSAGE)

        result = await self.runner.run(
            [
                "nmcli",
                "-t",
                "--escape",
                "yes",
                "-f",
                "SSID,BSSID,SIGNAL,SECURITY,IN-USE",
                "dev",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ],
            timeout_s=self.config.scan_timeout_s,
        )
        if result.returncode != 0:
            LOG.warning("WiFi scan failed: %s", result.stderr.strip())
            raise RuntimeError("Senseibox could not scan for WiFi networks.")

        raw_networks: list[WifiNetwork] = []
        for line in result.stdout.splitlines():
            fields = _split_nmcli_row(line)
            if len(fields) < 5:
                continue
            ssid, bssid, signal_text, security_text, in_use = fields[:5]
            if not ssid:
                continue
            try:
                signal = int(signal_text or "0")
            except ValueError:
                signal = 0
            security = (
                Security.OPEN
                if not security_text or security_text == "--"
                else Security.SECURED
            )
            raw_networks.append(
                WifiNetwork(
                    ssid=ssid,
                    bssid=bssid or None,
                    signal=signal,
                    security=security,
                    in_use=in_use == "*",
                )
            )

        duplicates = Counter(network.ssid for network in raw_networks)
        networks_by_ssid: dict[str, list[WifiNetwork]] = {}
        for network in raw_networks:
            networks_by_ssid.setdefault(network.ssid, []).append(network)

        strongest_by_ssid: dict[str, WifiNetwork] = {}
        for ssid, candidates in networks_by_ssid.items():
            connected_candidates = [network for network in candidates if network.in_use]
            candidate_pool = connected_candidates or candidates
            selected = max(candidate_pool, key=lambda item: item.signal)
            strongest_by_ssid[ssid] = WifiNetwork(
                ssid=selected.ssid,
                bssid=selected.bssid,
                signal=selected.signal,
                security=selected.security,
                in_use=bool(connected_candidates),
                duplicate_count=duplicates[ssid],
            )

        return sorted(
            strongest_by_ssid.values(),
            key=lambda item: (item.in_use, item.signal, item.ssid.lower()),
            reverse=True,
        )

    async def _has_wifi_device(self) -> bool:
        result = await self.runner.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
            timeout_s=5,
        )
        if result.returncode != 0:
            return True
        for line in result.stdout.splitlines():
            fields = _split_nmcli_row(line)
            if len(fields) >= 2 and fields[1] == "wifi":
                return True
        return False

    async def connect_wifi(
        self,
        network: WifiNetwork,
        password: str | None,
        *,
        hidden: bool = False,
    ) -> ConnectionResult:
        LOG.info("Connecting to WiFi SSID=%r signal=%s", network.ssid, network.signal)
        result = await self._connect_wifi_once(network, password, hidden=hidden)
        if result.ok or not result.needs_profile_reset:
            return result

        LOG.info("Recreating saved WiFi profile for SSID=%r", network.ssid)
        if not await self.delete_saved_profiles(network.ssid):
            return ConnectionResult(
                ok=False,
                message="Senseibox found a saved network profile that could not be updated. Choose another network or retry after restarting setup.",
            )
        return await self._connect_wifi_once(network, password, hidden=hidden)

    async def _connect_wifi_once(
        self,
        network: WifiNetwork,
        password: str | None,
        *,
        hidden: bool = False,
    ) -> ConnectionResult:
        argv = ["nmcli", "--wait", str(self.config.connection_timeout_s), "dev", "wifi", "connect", network.ssid]
        if password:
            argv.extend(["password", password])
        if hidden:
            argv.extend(["hidden", "yes"])

        try:
            result = await self.runner.run(argv, timeout_s=self.config.connection_timeout_s + 5)
        except CommandTimeout:
            return ConnectionResult(
                ok=False,
                timed_out=True,
                message="The connection took too long. Check the password or move Senseibox closer to the router.",
            )

        output = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode == 0:
            await self.enable_autoconnect(network.ssid)
            return ConnectionResult(ok=True, message="Connected to WiFi.")
        if "802-11-wireless-security.key-mgmt" in output:
            return ConnectionResult(
                ok=False,
                needs_profile_reset=True,
                message="Senseibox found an old saved network profile and will recreate it.",
            )
        if "secrets were required" in output or "password" in output:
            return ConnectionResult(
                ok=False,
                wrong_password=True,
                message="That password did not work. Please check it and try again.",
            )
        if "not found" in output:
            return ConnectionResult(
                ok=False,
                needs_rescan=True,
                message="That network is no longer visible. Try rescanning.",
            )
        return ConnectionResult(
            ok=False,
            message="Senseibox could not connect to that network. You can try again or choose another network.",
        )

    async def enable_autoconnect(self, connection_name: str) -> None:
        result = await self.runner.run(
            [
                "nmcli",
                "connection",
                "modify",
                connection_name,
                "connection.autoconnect",
                "yes",
            ],
            timeout_s=8,
        )
        if result.returncode != 0:
            LOG.warning("Could not enable WiFi autoconnect for SSID=%r", connection_name)

    async def get_local_ip(self) -> str | None:
        device = await self._active_wifi_device()
        if device:
            result = await self.runner.run(
                ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", device],
                timeout_s=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    fields = _split_nmcli_row(line)
                    if len(fields) >= 2 and fields[0].startswith("IP4.ADDRESS"):
                        return fields[1].split("/", 1)[0]

        result = await self.runner.run(["hostname", "-I"], timeout_s=5)
        if result.returncode != 0:
            return None
        for address in result.stdout.split():
            if "." in address and not address.startswith("127."):
                return address
        return None

    async def _active_wifi_device(self) -> str | None:
        result = await self.runner.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
            timeout_s=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            fields = _split_nmcli_row(line)
            if len(fields) >= 3 and fields[1] == "wifi" and fields[2] == "connected":
                return fields[0]
        return None

    async def list_saved_profiles(self) -> list[str]:
        result = await self.runner.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            timeout_s=8,
        )
        profiles: list[str] = []
        for line in result.stdout.splitlines():
            fields = _split_nmcli_row(line)
            if len(fields) == 2 and fields[1] == "802-11-wireless":
                profiles.append(fields[0])
        return profiles

    async def delete_saved_profiles(self, ssid: str) -> bool:
        result = await self.runner.run(
            ["nmcli", "-t", "--escape", "yes", "-f", "NAME,UUID,TYPE", "connection", "show"],
            timeout_s=8,
        )
        if result.returncode != 0:
            LOG.warning("Could not list saved WiFi profiles before reconnect")
            return False

        deleted_any = False
        for line in result.stdout.splitlines():
            fields = _split_nmcli_row(line)
            if len(fields) < 3:
                continue
            name, uuid, connection_type = fields[:3]
            if name != ssid or connection_type != "802-11-wireless":
                continue
            delete_result = await self.runner.run(
                ["nmcli", "connection", "delete", "uuid", uuid],
                timeout_s=8,
            )
            if delete_result.returncode != 0:
                LOG.warning("Could not delete saved WiFi profile SSID=%r UUID=%r", ssid, uuid)
                return False
            deleted_any = True

        return deleted_any

    async def start_ap_fallback(self) -> None:
        """Placeholder for production fallback.

        A production image should provide a systemd unit or NetworkManager
        profile for setup AP mode. Keep this explicit instead of generating
        ad-hoc hostapd files during onboarding.
        """

        LOG.warning("AP fallback requested")
        await self.runner.run(
            ["systemctl", "start", "senseibox-setup-ap.service"],
            timeout_s=10,
        )

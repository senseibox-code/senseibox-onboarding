from __future__ import annotations

import logging
import os
import shutil

from senseibox_onboarding.models import AccountResult, CheckResult, LoginResult
from senseibox_onboarding.services.process import CommandRunner

LOG = logging.getLogger(__name__)

ACCOUNT_GROUPS = (
    "sudo",
    "dialout",
    "audio",
    "video",
    "users",
    "netdev",
    "bluetooth",
    "docker",
    "render",
    "input",
    "gpiod",
)


class SystemService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    async def run_startup_checks(self) -> list[CheckResult]:
        checks: list[CheckResult] = []

        nmcli = await self.runner.run(["nmcli", "--version"], timeout_s=5)
        checks.append(
            CheckResult(
                name="Network tools",
                ok=nmcli.returncode == 0,
                detail="Ready" if nmcli.returncode == 0 else "Network tools are not installed",
            )
        )
        if nmcli.returncode != 0:
            return checks

        nm = await self.runner.run(["systemctl", "is-active", "NetworkManager"], timeout_s=5)
        checks.append(
            CheckResult(
                name="Network service",
                ok=nm.returncode == 0 and nm.stdout.strip() == "active",
                detail=(
                    "Ready"
                    if nm.returncode == 0 and nm.stdout.strip() == "active"
                    else f"NetworkManager is not running ({nm.stderr.strip() or nm.stdout.strip() or 'inactive'})"
                ),
            )
        )
        if nm.returncode != 0:
            return checks

        radio = await self.runner.run(["nmcli", "radio", "wifi"], timeout_s=5)
        radio_state = radio.stdout.strip().lower()
        checks.append(
            CheckResult(
                name="WiFi radio",
                ok=radio.returncode == 0 and radio_state == "enabled",
                detail=(
                    "Ready"
                    if radio.returncode == 0 and radio_state == "enabled"
                    else "WiFi is disabled"
                ),
            )
        )

        devices = await self.runner.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
            timeout_s=5,
        )
        wifi_lines = [
            line for line in devices.stdout.splitlines() if ":wifi:" in line
        ]
        checks.append(
            CheckResult(
                name="WiFi hardware",
                ok=devices.returncode == 0 and bool(wifi_lines),
                detail="Ready" if wifi_lines else "No WiFi adapter was found",
            )
        )
        return checks

    async def create_linux_account(self, username: str, password: str) -> AccountResult:
        user_existed = await self.account_exists(username)
        if not user_existed:
            created = await self._create_user(username)
            if created.returncode != 0:
                return AccountResult(False, "Senseibox could not create that Linux account.")

        if not await self._set_password(username, password):
            return AccountResult(False, "Senseibox could not set the password for that account.")

        if not await self._add_account_groups(username):
            return AccountResult(False, "Senseibox could not enable administrator access for that account.")

        if not await self._enable_ssh():
            return AccountResult(False, "The account is ready, but Senseibox could not enable SSH.")

        if user_existed:
            return AccountResult(True, "Linux account updated.")
        return AccountResult(True, "Linux account created.")

    async def _create_user(self, username: str):
        adduser = shutil.which("adduser") or (
            "/usr/sbin/adduser" if os.path.exists("/usr/sbin/adduser") else None
        )
        if adduser:
            return await self.runner.run(
                [
                    adduser,
                    "--disabled-password",
                    "--gecos",
                    "",
                    username,
                ],
                timeout_s=30,
            )
        return await self.runner.run(
            ["useradd", "--create-home", "--shell", "/bin/bash", username],
            timeout_s=15,
        )

    async def _set_password(self, username: str, password: str) -> bool:
        password_set = await self.runner.run(
            ["chpasswd"],
            timeout_s=10,
            input_text=f"{username}:{password}",
        )
        return password_set.returncode == 0

    async def _add_account_groups(self, username: str) -> bool:
        existing_groups = [group for group in ACCOUNT_GROUPS if await self._group_exists(group)]
        if "sudo" not in existing_groups:
            LOG.warning("sudo group is missing")
            return False
        if not existing_groups:
            return False

        usermod = shutil.which("usermod") or "/usr/sbin/usermod"
        result = await self.runner.run(
            [usermod, "-aG", ",".join(existing_groups), username],
            timeout_s=10,
        )
        if result.returncode != 0:
            LOG.warning("Could not add user %r to groups %r", username, existing_groups)
            return False
        return True

    async def _group_exists(self, group: str) -> bool:
        result = await self.runner.run(["getent", "group", group], timeout_s=5)
        return result.returncode == 0

    async def _enable_ssh(self) -> bool:
        keygen = await self.runner.run(["ssh-keygen", "-A"], timeout_s=20)
        if keygen.returncode != 0:
            LOG.warning("ssh-keygen -A failed: %s", keygen.stderr.strip())
            return False

        unmask = await self.runner.run(["systemctl", "unmask", "ssh"], timeout_s=10)
        if unmask.returncode != 0:
            LOG.info("systemctl unmask ssh returned non-zero: %s", unmask.stderr.strip())

        enabled = await self.runner.run(["systemctl", "enable", "--now", "ssh"], timeout_s=30)
        if enabled.returncode != 0:
            LOG.warning("systemctl enable --now ssh failed: %s", enabled.stderr.strip())
            return False

        status = await self.runner.run(["systemctl", "status", "ssh", "--no-pager"], timeout_s=10)
        if status.returncode != 0:
            LOG.warning("systemctl status ssh failed: %s", status.stderr.strip())
            return False
        return True

    async def account_exists(self, username: str) -> bool:
        existing = await self.runner.run(["id", "-u", username], timeout_s=5)
        return existing.returncode == 0

    async def launch_main_services(self) -> None:
        await self.runner.run(["systemctl", "start", "senseibox.target"], timeout_s=20)

    async def open_login_session(self, username: str) -> LoginResult:
        """Replace onboarding with the new user's login shell.

        This is intended for root-launched setup sessions, including local tty,
        ADB-style shells, and manual `sudo senseibox-setup` runs. A login shell
        changes to the user's home directory and loads the normal shell profile.
        """

        if hasattr(os, "geteuid") and os.geteuid() != 0:
            return LoginResult(False, "Auto-login requires the onboarding service to run as root.")

        su_path = shutil.which("su")
        if su_path is None:
            return LoginResult(False, "The su program was not found.")

        try:
            os.execv(su_path, [su_path, "--login", username])
        except OSError as exc:
            return LoginResult(False, f"Could not open a login session: {exc}")

        return LoginResult(False, "Could not open a login session.")

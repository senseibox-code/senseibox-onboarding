# Senseibox Onboarding

Terminal-native first boot onboarding for Senseibox appliances. The app guides a user through WiFi setup, Linux account creation, SSH enablement, and completion without exposing Linux internals during normal setup.

## Features

- Textual-based terminal UI with keyboard-first navigation
- WiFi scanning and connection through NetworkManager and `nmcli`
- Hidden network entry and manual WiFi setup mode
- Linux account creation with password confirmation
- SSH enablement after account creation
- Resumable setup state and rotating logs
- systemd service for first boot

## Run Locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m senseibox_onboarding.app
```

For development on machines without NetworkManager WiFi hardware, run with fake service data:

```bash
SENSEIBOX_ONBOARDING_FAKE_NETWORK=1 python -m senseibox_onboarding.app
```

Run the WiFi-only flow during development:

```bash
python -m senseibox_onboarding.app --wifi-only
```

The installed product commands are `senseibox-setup` and `senseibox-wifi-setup`. The app does not expose separate public Python console scripts; the wrappers call the Python module directly inside the installed virtualenv.

## Install As A Service

After checking out the repo on a Linux system, run:

```bash
sudo ./install.sh
```

The installer copies the app into `/opt/senseibox/senseibox-onboarding`, creates the shared no-login `senseibox` service user when needed, builds the virtualenv, installs wrapper commands, installs the systemd service, and starts it. Runtime state is stored in `/var/lib/senseibox/onboarding`, and logs are written under `/var/log/senseibox`.

The tracked service file lives at `systemd/senseibox-onboarding.service`.

Check it:

```bash
systemctl status senseibox-onboarding --no-pager
journalctl -u senseibox-onboarding -f
```

Manual setup commands installed by the service installer:

```bash
sudo senseibox-setup
sudo senseibox-setup --reset
sudo senseibox-wifi-setup
```

The onboarding service is terminal-based and does not expose an HTTP port or HTTP APIs. There is no `/api/version` endpoint for this app.

## Version

The product version is stored in `VERSION` and must match `pyproject.toml`.

## Notes

This project targets Debian-based Senseibox appliance images. It expects NetworkManager, systemd, and the required Linux account-management tools to be available on the target image.

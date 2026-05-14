# Contributing

Thanks for helping improve Senseibox Onboarding.

This app is the first interaction many people have with a Senseibox appliance, so changes should keep the setup flow calm, terminal-native, and recoverable.

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m senseibox_onboarding.app
```

For development on machines without NetworkManager WiFi hardware, use fake network data:

```bash
SENSEIBOX_ONBOARDING_FAKE_NETWORK=1 python -m senseibox_onboarding.app
```

Run only the WiFi setup flow:

```bash
python -m senseibox_onboarding.app --wifi-only
```

## Project Shape

The app is intentionally small and modular:

- `src/senseibox_onboarding/app.py` wires the Textual app, runtime config, and services.
- `src/senseibox_onboarding/screens/` contains onboarding screens and reusable terminal UI components.
- `src/senseibox_onboarding/services/` contains NetworkManager, connectivity, process, and system integration code.
- `src/senseibox_onboarding/state.py` stores resumable onboarding state.
- `systemd/` contains the production service unit.

## Local Checks

Run these before opening a pull request:

```bash
python -m compileall -q src tests
pytest
git diff --check
```

If you touch docs, screenshots, logs, fixtures, or installer output, also scan for private data before committing:

```bash
rg -n "real-usernames|private-hostnames|private-ips|passwords|ssh-key-names" .
```

Replace anything private with generic product examples.

## UX Guidelines

- Keep the interface terminal-native; avoid fake desktop UI patterns.
- Prefer clear text, simple keyboard controls, and recoverable errors.
- Do not expose Linux commands to normal users unless the screen is explicitly showing diagnostic command output.
- Keep `Esc` as a safe exit path.
- Do not log WiFi passwords or account passwords.

## Target Runtime

The target runtime is a Debian-based Senseibox appliance image with systemd, NetworkManager, and Linux account-management tools available. macOS and other desktop systems are useful for development with fake services, but real network and account flows should be tested on Linux.

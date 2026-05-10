# Senseibox Onboarding Architecture

## Product Direction

Senseibox onboarding should feel like a polished embedded Linux appliance wizard, not a desktop app in a terminal. Textual is useful here because it gives us screens, focus handling, async workers, and resilient rendering, but the visual language should remain terminal-native:

- plain step titles
- short explanatory copy
- clean scrollable lists
- obvious keyboard actions
- restrained color
- no fake windows, fake desktop chrome, or decorative panels
- no command names or Linux implementation details in user-facing text

The appliance voice should be calm and practical: "Choose a network", "Checking internet access", "That password did not work", "Press r to refresh networks".

## Recommended Flow

1. Boot splash: "Starting Senseibox..."
2. Welcome: explain setup in one paragraph
3. Device checks: NetworkManager active, WiFi interface present, storage writable
4. WiFi scan: async scan with inline status
5. Network selection: arrow keys choose, Enter confirms, [r] refreshes networks, [h] opens hidden network, Esc exits immediately
6. Password entry: warn if signal is weak, never log secrets
7. Connection progress: join WiFi, classify wrong password, timeout, vanished SSID, generic failure
8. Internet verification: allow continuation if LAN works but internet check fails
9. Linux Account: create a valid Linux username and password for SSH and local login
10. Optional OpenClaw setup: defer if offline
11. Completion: show SSH connection command, mark onboarding complete, and start `senseibox.target`
12. Main services run on future boots

## File Structure

```text
senseibox_onboarding/
  app.py                  # Textual app composition and dependency wiring
  config.py               # timeouts, paths, thresholds
  logging_config.py       # rotating log setup and redaction
  models.py               # typed domain objects
  state.py                # resumable, atomic onboarding state
  screens/
    welcome.py
    checks.py
    wifi.py
    password.py
    connecting.py
    account.py
    complete.py
  services/
    process.py            # async subprocess wrapper
    network.py            # NetworkManager/nmcli adapter
    connectivity.py       # internet checks
    system.py             # Linux account creation and service launch
systemd/
  senseibox-onboarding.service
  senseibox.target
tests/
  test_nmcli_parser.py
```

This keeps Textual screens thin. They ask services to do work and display state; they do not parse shell output, build command strings, or own persistence.

## Textual Practices For Embedded Linux

- Use one screen per step. Avoid one giant conditional `compose`.
- Use `run_worker` or async tasks for scans, connection attempts, and checks.
- Keep widgets simple: `Static`, `Input`, `ListView`, and a bottom hint bar are enough.
- Prefer predictable key bindings over button-heavy layouts.
- Make every screen usable without a mouse.
- Keep CSS minimal. Let the terminal look like a terminal.
- Disable the command palette and nonessential Textual affordances.
- Test in 80x24, 100x30, HDMI console, SSH, and serial-like terminals.
- Avoid animation except tiny textual status changes.
- Never let exceptions bubble to the user. Log internally and show a recovery action.

## Recovery Behaviour

The app stores small, non-secret progress in `/var/lib/senseibox/onboarding/state.json` using atomic writes. If power is lost, the app resumes from the last safe step. Password and WiFi secret input are deliberately not stored.

Recommended recovery rules:

- Resume `welcome`, `checks`, `wifi`, `linux_account`, and `complete`.
- If interrupted during `password` or `connecting`, resume at `wifi`.
- If state is corrupt, start a recovery screen and keep the corrupt file for diagnostics.
- If WiFi fails repeatedly, offer setup AP fallback or a diagnostics path.
- Safe exit should never mark setup complete.
- Only create `/var/lib/senseibox/onboarding/complete` after all required setup succeeds.

## Networking Reliability

NetworkManager remains the right base for Debian appliance WiFi because it owns saved profiles, reconnects, regulatory handling, and common drivers.

Handle these cases explicitly:

- Empty scans: show "No networks found", keep [r] refresh networks available.
- Scan failure: log stderr, show retry.
- Duplicate SSIDs: show the strongest entry and note multiple access points.
- Weak signal: warn before password entry.
- Hidden SSID: separate manual entry path.
- Wrong password: classify from nmcli output and return to password entry.
- Timeout: let the user retry without restarting onboarding.
- Saved profiles: future enhancement can show "Previously used" above scan results.
- Internet failure after WiFi success: distinguish LAN connection from internet access.
- AP fallback: use a pre-baked NetworkManager profile or systemd unit, not ad-hoc config generation inside the UI.

Important production note: passing WiFi passwords to `nmcli` as argv may briefly expose them to privileged process inspection. For a production image, prefer NetworkManager D-Bus or a root-owned helper that receives the password over stdin and never logs argv. The sample keeps `nmcli` because that matches the current prototype and keeps dependencies light.

## Logging Strategy

- Log to `/var/log/senseibox/onboarding.log`.
- Rotate logs locally, keep them small.
- Mirror critical failures to journald via systemd.
- Redact password-like messages defensively.
- Log event names and safe metadata: SSID, signal, step, result class.
- Never log WiFi passwords, generated account passwords, tokens, or OpenClaw secrets.
- Add a future diagnostics export command that bundles logs, OS version, NetworkManager status, and hardware info.

## Systemd Integration

Use a dedicated onboarding unit on tty1:

- `ConditionPathExists=!/var/lib/senseibox/onboarding/complete`
- `StandardInput=tty`, `StandardOutput=tty`
- `TTYPath=/dev/tty1`
- restart on failure
- start after NetworkManager
- mark complete only from the app

After completion, start `senseibox.target`, which groups the normal appliance services. Future recovery/reset mode can remove the complete marker and restart the onboarding service.

## Security And PSTI Readiness

- Force unique password creation during setup; do not ship default credentials.
- Do not log secrets.
- Avoid hardcoded credentials.
- Use root-owned config files with restrictive permissions.
- Separate the UI user from privileged operations where possible.
- Consider a minimal privileged helper for account creation, password setting, WiFi, and service actions.
- Record software version, build version, and update channel in device config.
- Add a documented reset path that clears onboarding state safely.
- Make SSH disabled by default unless the user enables it and sets a password/key.

## Testing Strategy

Unit tests:

- nmcli parser with escaped characters and duplicate SSIDs
- state load/save/corrupt-file recovery
- connection result classification
- Linux username/password validation
- log redaction

Service tests:

- fake `CommandRunner` returning known nmcli outputs
- timeout paths
- no-network scan path
- wrong password path

UI tests:

- Textual pilot tests for key flows
- 80x24 snapshot checks
- focus order checks
- Esc exits immediately and saves resumable progress

Hardware tests:

- boot to tty1
- connect to WPA2/WPA3 router
- wrong password recovery
- router disappears during connection
- weak signal
- no internet after LAN connection
- power loss at every setup step

## Textual Vs Simpler Terminal UIs

Textual is a good fit if Senseibox needs async scans, reusable screens, focus management, responsive terminal rendering, and a future diagnostics screen. The cost is a larger dependency and more framework surface area.

Whiptail/dialog/simple-term-menu are lighter and easier to reason about, but they make async updates, polished recovery states, and multi-step stateful flows clumsy. They also tend to feel like admin utilities.

For Senseibox, Textual is reasonable as long as the app uses a restrained terminal-native design and avoids pretending to be a GUI.

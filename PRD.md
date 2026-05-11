# Senseibox Onboarding PRD

## Overview

Senseibox is a small always-on Linux appliance intended for home and local-network use. On first boot, users must be guided through the minimum setup required to make the device reachable and secure without needing to understand Linux administration.

The onboarding application runs in a terminal environment on the device itself. It should feel like a finished appliance setup flow, not a developer utility and not a desktop-style GUI recreated inside a terminal.

## Product Goal

Create a calm, reliable, terminal-native onboarding experience that helps a user:

- confirm the device is connected to the local network
- connect to WiFi when needed
- create a Linux account for SSH and local login
- understand how to connect to Senseibox after setup
- complete setup without seeing Linux commands, stack traces, or implementation details

The experience should feel closer to a router, set-top box, or embedded Linux installer than a general-purpose computer setup script.

## Target Users

Primary users:

- Home users setting up Senseibox for the first time
- Developers testing Senseibox locally or in a virtual machine
- Operators recovering network access on an already configured device

Secondary users:

- Engineers maintaining the onboarding app
- Support staff diagnosing setup failures
- Future companion apps or services that may trigger onboarding-related flows

## User Experience Principles

- Embrace the terminal environment instead of hiding it.
- Keep the flow step-by-step and keyboard-first.
- Use short, direct language.
- Make progress and recovery paths obvious.
- Avoid fake windows, fake desktop panels, heavy borders, decorative animation, or mouse-dependent interactions.
- Use restrained color: green for screen titles and success indicators, white for primary text, grey for secondary text.
- Never expose raw stack traces or internal command failures as the main user experience.
- Keep advanced details available in logs, not in the primary copy.

## Required Flow

### Step 1: Network Setup

The app should determine whether Senseibox already has a working network connection.

If a WiFi adapter is available:

- show a splash screen while scanning for WiFi networks
- display available networks in a terminal-native list
- allow arrow-key selection
- allow refresh, hidden network entry, and immediate exit
- request a password for secured networks
- show connection progress and command output where useful for diagnostics
- verify internet access after connecting

If no WiFi adapter is available:

- change the splash message to indicate that the wired network is being checked
- if wired or virtual Ethernet has internet access, show a success state in Step 1
- allow the user to continue to Linux account setup
- if no network is available, show a recoverable message and keep retry available

Standalone WiFi setup should remain WiFi-specific. If launched only to change WiFi, it should not open Linux account setup.

### Step 2: Linux Account

The user creates or updates a Linux account used for:

- SSH access
- local terminal login
- system administration tasks where appropriate

The username must be valid for Linux. The password must be confirmed before account creation. The flow should handle existing users by updating the password and continuing.

The app should enable the required system services for SSH access after the account is ready.

### Step 3: Setup Completed

The final screen should confirm that setup is complete and explain how to connect over SSH:

1. Open a terminal.
2. Run the SSH command using the Linux account name.
3. Confirm the host connection when prompted.
4. Enter the password created during setup.

The screen should then allow Senseibox services to start and, where possible, open a local login session for the created account.

## Functional Requirements

### Network Detection

- Detect whether NetworkManager is available.
- Detect whether a WiFi adapter exists.
- Detect whether the device is already connected through Ethernet, virtual Ethernet, or another non-WiFi network path.
- Detect internet access after network connection.
- Show the local IP address when available.

### WiFi Setup

- Scan with NetworkManager.
- Handle empty scans.
- Handle missing WiFi hardware.
- Handle hidden SSIDs.
- Handle duplicate SSIDs by showing the strongest useful entry.
- Show signal strength, quality percentage, security type, and connected status.
- Prevent selecting an already connected network as if it were a new setup action.
- Enable autoconnect for successful WiFi profiles.
- Classify common failures such as wrong password, timeout, vanished SSID, and stale saved profile.

### Linux Account Setup

- Validate usernames before attempting system changes.
- Reject reserved system usernames.
- Require password confirmation.
- Do not log account passwords.
- Add the created user to the expected device groups.
- Ensure SSH host keys exist.
- Enable SSH after the account is ready.
- Support updating an existing valid user.

### Persistence And Recovery

- Store onboarding state in a product-owned data directory.
- Store only non-secret progress.
- Use atomic state writes.
- Resume safely after power loss.
- Do not mark setup complete until required setup has succeeded.
- If interrupted during password entry or connection, resume at a safe network step.

### Logging And Diagnostics

- Write logs to a product-owned log path.
- Keep logs useful for engineering support.
- Redact secrets before logging.
- Show troubleshooting log paths only when useful, especially after failures.
- Keep command output visible only where it helps users understand progress or diagnose failures.

## Non-Functional Requirements

### Reliability

- The UI must remain responsive during scans and connection attempts.
- Failures must be recoverable from the UI.
- The app must not crash to a raw terminal traceback.
- The app should tolerate NetworkManager errors and missing hardware.

### Performance

- Keep startup fast.
- Keep memory use modest for embedded hardware.
- Avoid unnecessary animations.
- Avoid polling loops that create CPU load.

### Security

- Do not ship usable default credentials.
- Do not hardcode user passwords or WiFi credentials.
- Do not log secrets.
- Avoid storing secrets in plaintext.
- Keep privileged operations explicit and minimal.
- Prepare for a future privileged helper boundary if the UI no longer runs with elevated permissions.

### Maintainability

- Keep UI, system services, network services, process execution, state, and configuration separated.
- Keep Textual screens focused on rendering and user interaction.
- Keep system calls behind service classes.
- Keep wording consistent and product-oriented.
- Add tests for parser logic, state transitions, validation, and failure handling.

## System Integration Requirements

- Install under `/opt/senseibox/senseibox-onboarding`.
- Run under the shared `senseibox:senseibox` service account where appropriate.
- Provide systemd integration for first boot.
- Disable first-boot onboarding after successful completion.
- Provide standalone commands for setup and WiFi recovery:
  - `sudo senseibox-setup`
  - `sudo senseibox-wifi-setup`
- Support reset or recovery mode in a future release.

## Acceptance Criteria

The onboarding flow is considered ready when:

- A device with WiFi can scan, connect, verify internet, and continue.
- A device with Ethernet but no WiFi adapter can continue after showing wired network success.
- A device with no network path shows a clear recoverable message.
- Wrong WiFi passwords are handled without restarting the app.
- Existing Linux users are handled without duplicate-user failure.
- The completion screen shows correct SSH guidance.
- Secrets do not appear in logs, command output, tests, docs, or commits.
- The app remains usable from a keyboard-only terminal.
- The app can be installed and managed through systemd.

## Non-Goals

- Browser-based onboarding.
- Mobile companion onboarding.
- A desktop-style terminal UI.
- Touchscreen-first interactions.
- Captive portal setup.
- Bluetooth setup.
- OpenClaw account linking.
- OTA update management.

These may be considered future product work, but they are outside the scope of the current onboarding CLI.

## Future Opportunities

- Captive portal or setup access point mode.
- Bluetooth onboarding fallback.
- QR code display for pairing or SSH instructions.
- Remote onboarding through SSH.
- Local web dashboard handoff after first boot.
- Diagnostics export bundle.
- Device pairing with OpenClaw services.
- Update channel selection and OTA readiness checks.

# VoLtex

VoLtex is a Linux desktop launcher for Vortex.

It opens Vortex in a native GTK WebKit window, handles `vortex://` play links, and launches the installed Windows Vortex client through Wine.

## Features

* Native Linux webview launcher
* `vortex://` link handling
* Wine-based Vortex client launching
* Persistent web session storage
* Optional keyring-backed login persistence
* Linux app menu and desktop shortcut installer
* Local logs with token and cookie redaction

## Installation

```bash
git clone https://github.com/FrameT-bit/VoLtex
cd VoLtex
./install
```

Or use the GUI installer:

```bash
./install-gui
```

After installation, launch **VoLtex** from your app menu or desktop shortcut.

The installer copies VoLtex to:

```text
~/.local/opt/voltex
```

After installing, the original cloned folder can be moved or deleted.

VoLtex does not install system packages automatically by default. If a dependency is missing, the installer will show the correct command for your Linux distribution.

To allow automatic dependency installation, run:

```bash
./install --install-system-deps
```

## Running Without Installing

```bash
./run-voltex
```

Useful commands:

```bash
./run-voltex --doctor
./run-voltex --print-config
./run-voltex --clear-session
```

## Updates

VoLtex checks GitHub for new versions. No need to re-download zip files.

```bash
# Check for updates (stable branch)
./run-voltex --check-update

# Install the latest stable update
./run-voltex --update

# Track the testing branch (pre-releases)
./run-voltex --check-update --update-branch testing
./run-voltex --update --update-branch testing
```

Updates are applied atomically — the previous version is kept as a backup
(`~/.local/share/voltex/app.old`) and can be restored if needed.

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases. Safe for everyday use. |
| `testing` | Pre-release builds. New features land here first. May have rough edges. |

To switch from `main` to `testing`:

```bash
./run-voltex --update --update-branch testing
```

To go back to stable:

```bash
./run-voltex --update --update-branch main
```

## Vortex Player Requirement

VoLtex can be installed before the Windows Vortex player, but games will only launch after `Vortex.exe` is installed in your Wine prefix.

By default, VoLtex looks for Vortex at:

```text
~/.wine/drive_c/Program Files/Vortex/Vortex.exe
```

If the player is missing, VoLtex will show an error instead of failing silently.

## Configuration

VoLtex can be configured with environment variables.

Common options:

```text
VOLTEX_SITE_URL
VOLTEX_WINE_BINARY
VOLTEX_WINEPREFIX
VOLTEX_EXE
VOLTEX_LAUNCH_MODE
VOLTEX_REMEMBER_LOGIN
VOLTEX_PERSISTENT_SESSION
```

Example:

```bash
VOLTEX_WINEPREFIX="$HOME/.wine-vortex" ./run-voltex
```

## Logs

Logs are stored in:

```text
~/.local/state/voltex
```

Useful files:

```text
launcher.log
voltex.log
game.log
```

Sensitive values such as cookies, tokens, passwords, and authorization headers are redacted from logs.

## Error Reporting

When VoLtex crashes, a dialog appears with two options:

- **Close** — dismiss the dialog
- **Report Issue** — opens the GitHub Issues page

Crash logs are stored in `~/.local/state/voltex/launcher.log`.
No data is ever sent automatically.

## Troubleshooting

Run:

```bash
./run-voltex --doctor
```

If you are running VoLtex in a headless or Xvfb environment, Wine virtual desktop mode may be required:

```bash
VOLTEX_LAUNCH_MODE=wine-virtual-desktop VOLTEX_WINE_DESKTOP=Vortex,1280x720 ./run-voltex
```

To manually test Wine without the default D3D12 override:

```bash
VOLTEX_WINE_ENV="WINEDLLOVERRIDES=" ./run-voltex
```

## Security

* The local bridge only binds to `127.0.0.1`
* Each run uses a random bridge secret
* Bridge requests require authentication
* Logs redact sensitive values
* Session data is stored using GTK WebKit storage
* Optional login persistence uses the system keyring when available

## Planned

* Friendlier first-run diagnostics
* AppImage packaging
* In-window status notifications

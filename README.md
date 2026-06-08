# VoLtex

VoLtex is a Linux desktop launcher for Vortex. It opens the real Vortex site in a native GTK WebKit window, intercepts `vortex://` play links, and launches the installed Windows Vortex client through Wine.

## Status

Working:

- native webview launcher;
- GTK-level `vortex://` interception;
- host Wine launch through `wine start /wait /unix`;
- persistent web session storage;
- keyring-backed token persistence when readable session tokens are exposed to the web page;
- Linux desktop/menu shortcut installer;
- `x-scheme-handler/vortex` registration;
- local bridge and game logs with token/cookie redaction.

Still planned:

- friendlier first-run diagnostics;
- AppImage packaging;
- in-window status notifications.

## Quick Install

```bash
git clone https://github.com/FrameT-bit/VoLtex voltex
cd voltex
./install
```

After install, launch VoLtex from the app menu or the desktop shortcut.

The installer copies the app into:

```text
~/.local/opt/voltex
```

Desktop entries point to that stable install path, so the original cloned/downloaded folder can be moved or deleted after installation.

The installer does not install system packages by default. If dependencies are missing, it prints the correct distro command and exits. Users who explicitly want automatic package installation can run:

```bash
./install --install-system-deps
```

VoLtex can be installed before the Windows Vortex player. Play will only work after `Vortex.exe` exists in the configured Wine prefix. VoLtex searches common Wine install paths automatically and reports a visible error if the player is missing.

## Run Without Installing

```bash
./run-voltex
```

Useful checks:

```bash
./run-voltex --print-config
./run-voltex --doctor
./run-voltex --clear-session
.venv/bin/python -m unittest discover -s tests
```

## Runtime Paths

VoLtex follows XDG user directories:

```text
~/.config/voltex
~/.local/share/voltex
~/.local/share/voltex/webview
~/.cache/voltex
~/.local/state/voltex
```

Runtime directories are created with `0700` permissions.

## Configuration

Environment variables:

```text
VOLTEX_SITE_URL
VOLTEX_WINE_BINARY
VOLTEX_WINEPREFIX
VOLTEX_EXE
VOLTEX_LAUNCH_MODE
VOLTEX_WINE_DESKTOP
VOLTEX_REMEMBER_LOGIN
VOLTEX_PERSISTENT_SESSION
VOLTEX_WINE_ENV
VOLTEX_CONFIG_DIR
VOLTEX_DATA_DIR
VOLTEX_CACHE_DIR
VOLTEX_STATE_DIR
VOLTEX_WEBVIEW_STORAGE
VOLTEX_LOG_FILE
VOLTEX_GAME_LOG_FILE
VOLTEX_GDK_BACKEND
```

Default Vortex path:

```text
~/.wine/drive_c/Program Files/Vortex/Vortex.exe
```

Default launch mode:

```text
wine start /wait /unix Vortex.exe vortex://...
```

Default Wine compatibility env:

```text
WINEDLLOVERRIDES=d3d12=d
```

Useful logs:

```text
~/.local/state/voltex/launcher.log
~/.local/state/voltex/voltex.log
~/.local/state/voltex/game.log
```

If you want to test Wine's D3D12 path manually:

```bash
VOLTEX_WINE_ENV="WINEDLLOVERRIDES=" ./run-voltex
```

Headless/Xvfb environments can trigger a Windows monitor detection panic in Vortex's `winit` stack. Use Wine virtual desktop mode there:

```bash
VOLTEX_LAUNCH_MODE=wine-virtual-desktop VOLTEX_WINE_DESKTOP=Vortex,1280x720 ./run-voltex
```

## Security Model

- The Flask bridge binds to `127.0.0.1` on a random port.
- Each run creates a random bridge secret.
- Bridge API calls require `X-Voltex-Secret`.
- Logs redact cookies, tokens, passwords, and authorization values.
- Session tokens readable from JavaScript are stored in the system keyring when login persistence is enabled.
- Browser session persistence uses GTK WebKit's own storage under `~/.local/share/voltex/webview`.

Important limitation: injected JavaScript cannot read `HttpOnly` cookies. If Vortex stores auth only in `HttpOnly` cookies, VoLtex relies on WebKit's browser session storage rather than copying those cookies into keyring.

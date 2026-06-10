# VoLtex Install Notes

## User Install

Run:

```bash
./install
```

Do not run the installer with `sudo`. Run it as the normal desktop user. The installer does not install system packages by default.

The installer:

- copies VoLtex to `~/.local/share/voltex/app`;
- detects Fedora, Ubuntu/Debian, Arch/Manjaro, openSUSE, and yum-based systems;
- prints dependency commands and reference links if automatic install cannot complete;
- creates `.venv` with `--system-site-packages`;
- installs Python dependencies from `requirements.txt`;
- installs the icon to `~/.local/share/icons/hicolor/scalable/apps/voltex.svg`;
- writes `~/.local/share/applications/voltex.desktop`;
- writes `~/.local/share/applications/voltex-reset-session.desktop`;
- creates `~/Desktop/VoLtex.desktop` when the Desktop folder exists;
- registers `x-scheme-handler/vortex` to VoLtex.

If the downloaded files lost executable permissions, run the same installer through the shell:

```bash
bash install
```

To explicitly allow the installer to request admin privileges and install missing system packages, run:

```bash
./install --install-system-deps
```

## Install Order

It is fine to install VoLtex before installing the Windows Vortex player. The wrapper opens the website either way. Launching a game requires `Vortex.exe` to exist in the configured Wine prefix.

Default prefix:

```text
~/.wine
```

Default expected player path:

```text
~/.wine/drive_c/Program Files/Vortex/Vortex.exe
```

VoLtex also searches common Wine locations such as:

```text
~/.wine/drive_c/users/<user>/AppData/Local/Programs/Vortex/Vortex.exe
~/.wine/drive_c/users/<user>/AppData/Local/Vortex/Vortex.exe
```

If the player is somewhere else, launch VoLtex with:

```bash
VOLTEX_EXE="/path/to/Vortex.exe" ./run-voltex
```

## Wayland

VoLtex defaults GTK to XWayland with `GDK_BACKEND=x11` because WebKitGTK can crash on some Wayland compositor/driver combinations. To test native Wayland manually:

```bash
VOLTEX_GDK_BACKEND=wayland ./run-voltex
```

## Logs

Tester logs are written to:

```text
~/.local/state/voltex/launcher.log
~/.local/state/voltex/voltex.log
~/.local/state/voltex/game.log
```

Use `launcher.log` for app startup errors, `voltex.log` for bridge/play events, and `game.log` for Wine/Vortex output.

## Renderer Fallback

VoLtex disables Wine's D3D12 path by default:

```text
WINEDLLOVERRIDES=d3d12=d
```

This avoids known Vortex/Bevy/wgpu crashes in Wine's D3D12 path. To test D3D12 manually:

```bash
VOLTEX_WINE_ENV="WINEDLLOVERRIDES=" ./run-voltex
```

## Headless Or Xvfb

When running under Xvfb or another headless display, Vortex may panic in Windows monitor detection. Use Wine virtual desktop mode:

```bash
VOLTEX_LAUNCH_MODE=wine-virtual-desktop VOLTEX_WINE_DESKTOP=Vortex,1280x720 ./run-voltex
```

For direct server testing without the webview:

```bash
xvfb-run -a -s "-screen 0 1280x720x24 +extension GLX +render -noreset" \
  env WINEPREFIX="$HOME/.wine-voltex-server" WINEDLLOVERRIDES="d3d12=d" \
  wine explorer /desktop=Vortex,1280x720 "$HOME/Vortex/Vortex.exe"
```

## System Dependencies

Fedora:

```bash
sudo dnf install python3-gobject webkit2gtk4.1 wine
```

Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1 wine
```

## Uninstall

Remove desktop integration but keep session data:

```bash
./uninstall.sh
```

Remove desktop integration and local VoLtex data:

```bash
./uninstall.sh --purge
```

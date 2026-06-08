#!/usr/bin/env bash
set -euo pipefail

APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/voltex.svg"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
INSTALL_DIR="${VOLTEX_INSTALL_DIR:-$HOME/.local/opt/voltex}"

rm -f "$APPLICATIONS_DIR/voltex.desktop"
rm -f "$APPLICATIONS_DIR/voltex-reset-session.desktop"
rm -f "$ICON_FILE"
rm -f "$DESKTOP_DIR/VoLtex.desktop"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$INSTALL_DIR"
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/voltex"
  rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/voltex"
  rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/voltex"
  rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/voltex"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

printf 'VoLtex desktop integration removed.\n'
if [[ "${1:-}" != "--purge" ]]; then
  printf 'Saved session data was kept. Run with --purge to remove local app data.\n'
else
  printf 'VoLtex app files and local app data were removed.\n'
fi

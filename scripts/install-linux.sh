#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
APP_NAME="VoLtex"
DESKTOP_ID="voltex.desktop"
RESET_DESKTOP_ID="voltex-reset-session.desktop"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
INSTALL_DIR="${VOLTEX_INSTALL_DIR:-$DATA_HOME/voltex/app}"
LEGACY_INSTALL_DIR="$HOME/.local/opt/voltex"
APPLICATIONS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
STATE_DIR="$STATE_HOME/voltex"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
INSTALL_SYSTEM_DEPS=0

info() {
  printf '%s\n' "$*"
}

warn() {
  printf 'Warning: %s\n' "$*" >&2
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./install [options]

Options:
  --install-system-deps   Ask for sudo/pkexec and install missing system packages.
  --help                  Show this help.

Default behavior checks dependencies, prints distro-specific install commands if
anything is missing, and exits without installing system packages.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-system-deps)
        INSTALL_SYSTEM_DEPS=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

refuse_root_install() {
  if [[ "$(id -u)" -eq 0 ]]; then
    cat >&2 <<'EOF'
Error: Do not run the VoLtex installer with sudo.

Run it as your normal desktop user:

  ./install

The installer will ask for sudo/pkexec only when system packages are missing.
Running the whole installer as root would install shortcuts and session files into
root's home instead of the user's desktop profile.
EOF
    exit 1
  fi
}

normalize_install_dir() {
  local parent
  parent="$(dirname "$INSTALL_DIR")"
  mkdir -p "$parent"
  INSTALL_DIR="$(cd "$parent" && pwd -P)/$(basename "$INSTALL_DIR")"
}

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$@"
  else
    return 127
  fi
}

python_has_webkit() {
  command -v python3 >/dev/null 2>&1 && python3 -c '
import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2
' >/dev/null 2>&1 </dev/null
}

dependencies_available() {
  command -v python3 >/dev/null 2>&1 &&
    python3 -c 'import venv' >/dev/null 2>&1 </dev/null &&
    python3 -m pip --version >/dev/null 2>&1 </dev/null &&
    command -v wine >/dev/null 2>&1 &&
    command -v xdg-mime >/dev/null 2>&1 &&
    python_has_webkit
}

print_dependency_help() {
  cat >&2 <<'EOF'

VoLtex needs these system dependencies:

- Python 3 with venv and pip
- GTK Python bindings
- GTK WebKit bindings for Python
- Wine
- xdg-utils
- desktop-file-utils
- hicolor icon theme

Install commands by distro family:

Fedora:
  sudo dnf install python3 python3-pip python3-gobject webkit2gtk4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme

Ubuntu/Debian:
  sudo apt install python3 python3-venv python3-pip python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme
  If gir1.2-webkit2-4.1 is unavailable, try gir1.2-webkit2-4.0.

Arch/Manjaro:
  sudo pacman -S python python-pip python-gobject webkit2gtk-4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme
  If webkit2gtk-4.1 is unavailable, try webkit2gtk.

openSUSE:
  sudo zypper install python3 python3-pip python3-gobject-Gdk typelib-1_0-Gtk-3_0 typelib-1_0-WebKit2-4_1 wine xdg-utils desktop-file-utils hicolor-icon-theme

Reference links:
  Wine: https://www.winehq.org/
  pywebview Linux dependencies: https://pywebview.flowrl.com/guide/installation.html#dependencies
  Python venv: https://docs.python.org/3/library/venv.html

EOF
}

detect_os_like() {
  if [[ -r /etc/os-release ]]; then
    . /etc/os-release
    printf '%s %s\n' "${ID:-}" "${ID_LIKE:-}"
  fi
}

install_system_dependencies() {
  if [[ "${VOLTEX_SKIP_SYSTEM_DEPS:-0}" == "1" ]]; then
    warn "Skipping system dependency checks because VOLTEX_SKIP_SYSTEM_DEPS=1."
    return
  fi

  if dependencies_available; then
    return
  fi

  if [[ "$INSTALL_SYSTEM_DEPS" != "1" ]]; then
    print_dependency_help
    fail "Missing system dependencies. Install them, then rerun ./install. To let VoLtex install them, rerun ./install --install-system-deps."
  fi

  info "Installing missing system dependencies..."
  local os_like
  os_like="$(detect_os_like)"

  if command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y python3 python3-pip python3-gobject webkit2gtk4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme || {
      print_dependency_help
      fail "Automatic dependency install failed."
    }
  elif command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update || {
      print_dependency_help
      fail "Could not refresh apt metadata."
    }
    local webkit_pkg="gir1.2-webkit2-4.1"
    if ! apt-cache show "$webkit_pkg" >/dev/null 2>&1; then
      webkit_pkg="gir1.2-webkit2-4.0"
    fi
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip python3-gi gir1.2-gtk-3.0 "$webkit_pkg" wine xdg-utils desktop-file-utils hicolor-icon-theme || {
      print_dependency_help
      fail "Automatic dependency install failed."
    }
  elif command -v pacman >/dev/null 2>&1; then
    run_as_root pacman -S --needed --noconfirm python python-pip python-gobject webkit2gtk-4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme || {
      print_dependency_help
      fail "Automatic dependency install failed."
    }
  elif command -v zypper >/dev/null 2>&1; then
    run_as_root zypper install -y python3 python3-pip python3-gobject-Gdk typelib-1_0-Gtk-3_0 typelib-1_0-WebKit2-4_1 wine xdg-utils desktop-file-utils hicolor-icon-theme || {
      print_dependency_help
      fail "Automatic dependency install failed."
    }
  elif command -v yum >/dev/null 2>&1; then
    run_as_root yum install -y python3 python3-pip python3-gobject webkit2gtk4.1 wine xdg-utils desktop-file-utils hicolor-icon-theme || {
      print_dependency_help
      fail "Automatic dependency install failed."
    }
  else
    warn "Could not detect a supported package manager. Detected: $os_like"
    print_dependency_help
    fail "Install dependencies manually and rerun this installer."
  fi

  if ! dependencies_available; then
    print_dependency_help
    fail "Dependencies are still missing after automatic install."
  fi
}

copy_app() {
  local source_real install_real install_parent tmp_dir
  source_real="$(cd "$SOURCE_DIR" && pwd -P)"
  install_parent="$(dirname "$INSTALL_DIR")"
  mkdir -p "$install_parent"
  install_real="$(cd "$install_parent" && pwd -P)/$(basename "$INSTALL_DIR")"

  if [[ "$source_real" == "$install_real" ]]; then
    return
  fi

  case "$install_real" in
    "/"|"$HOME"|"$HOME/.local"|"$DATA_HOME"|"$DATA_HOME/voltex"|"$HOME/.local/opt")
      fail "Refusing unsafe install directory: $install_real"
      ;;
  esac

  info "Copying VoLtex to $install_real..."
  tmp_dir="$install_real.tmp.$$"
  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"
  tar -C "$source_real" \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./.pytest_cache' \
    --exclude='./__pycache__' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='voltex-working-*.zip' \
    -cf - . | tar -C "$tmp_dir" -xf -
  rm -rf "$install_real"
  mv "$tmp_dir" "$install_real"
}

set_app_entrypoint_permissions() {
  chmod 755 "$INSTALL_DIR/run-voltex" 2>/dev/null || true
  chmod 755 "$INSTALL_DIR/install" "$INSTALL_DIR/install.sh" "$INSTALL_DIR/uninstall.sh" 2>/dev/null || true
  chmod 755 "$INSTALL_DIR/scripts/install-linux.sh" "$INSTALL_DIR/scripts/uninstall-linux.sh" 2>/dev/null || true
  chmod 755 "$INSTALL_DIR/scripts/backup-working-state.sh" 2>/dev/null || true
}

normalize_app_permissions() {
  if [[ ! -d "$INSTALL_DIR" ]]; then
    return
  fi

  find "$INSTALL_DIR" -path "$INSTALL_DIR/.venv" -prune -o -type d -exec chmod 755 {} +
  find "$INSTALL_DIR" -path "$INSTALL_DIR/.venv" -prune -o -type f -exec chmod 644 {} +
  set_app_entrypoint_permissions
}

remove_legacy_default_install() {
  if [[ -n "${VOLTEX_INSTALL_DIR+x}" ]]; then
    return
  fi
  if [[ "$INSTALL_DIR" == "$LEGACY_INSTALL_DIR" || ! -d "$LEGACY_INSTALL_DIR" ]]; then
    return
  fi

  rm -rf "$LEGACY_INSTALL_DIR"
}

write_desktop_file() {
  local template="$1"
  local target="$2"
  sed "s|@APP_DIR@|$INSTALL_DIR|g" "$template" >"$target"
  chmod 644 "$target"
}

install_python_environment() {
  local python="$INSTALL_DIR/.venv/bin/python"

  if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    info "Creating Python environment..."
    python3 -m venv --system-site-packages "$INSTALL_DIR/.venv" </dev/null
  fi

  if ! grep -q '^include-system-site-packages = true$' "$INSTALL_DIR/.venv/pyvenv.cfg"; then
    warn "Updating venv to use system GTK Python bindings."
    python3 -m venv --system-site-packages "$INSTALL_DIR/.venv" </dev/null
  fi

  if ! "$python" -m pip --version >/dev/null 2>&1 </dev/null; then
    info "Bootstrapping pip in Python environment..."
    "$python" -m ensurepip --upgrade </dev/null || {
      print_dependency_help
      fail "Could not bootstrap pip inside the VoLtex Python environment."
    }
  fi

  if [[ "${VOLTEX_SKIP_PIP_INSTALL:-0}" == "1" ]]; then
    warn "Skipping Python dependency install because VOLTEX_SKIP_PIP_INSTALL=1."
    return
  fi

  info "Installing Python dependencies..."
  "$python" -m pip install -r "$INSTALL_DIR/requirements.txt" </dev/null || {
    print_dependency_help
    fail "Python dependency install failed."
  }

  validate_python_environment "$python"
}

validate_python_environment() {
  local python="$1"
  local missing

  if ! missing="$("$python" -c 'import importlib.util; missing = [name for name in ("flask", "webview", "keyring") if importlib.util.find_spec(name) is None]; print(", ".join(missing)); raise SystemExit(1 if missing else 0)' 2>/dev/null)"; then
    fail "Python dependency validation failed. Missing modules: ${missing:-unknown}. Rerun ./install or ./install --install-system-deps."
  fi
}

install_desktop_integration() {
  mkdir -p "$STATE_DIR" "$CONFIG_HOME" "$APPLICATIONS_DIR" "$ICON_DIR" "$DESKTOP_DIR"
  chmod 700 "$STATE_DIR" 2>/dev/null || true

  set_app_entrypoint_permissions

  cp "$INSTALL_DIR/assets/icons/voltex.svg" "$ICON_DIR/voltex.svg"
  write_desktop_file "$INSTALL_DIR/packaging/linux/voltex.desktop.in" "$APPLICATIONS_DIR/$DESKTOP_ID"
  write_desktop_file "$INSTALL_DIR/packaging/linux/voltex-reset-session.desktop.in" "$APPLICATIONS_DIR/$RESET_DESKTOP_ID"
  write_desktop_file "$INSTALL_DIR/packaging/linux/voltex.desktop.in" "$DESKTOP_DIR/$APP_NAME.desktop"
  chmod +x "$DESKTOP_DIR/$APP_NAME.desktop"

  if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_DIR/$APP_NAME.desktop" metadata::trusted true 2>/dev/null || true
  fi
  if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default "$DESKTOP_ID" x-scheme-handler/vortex || true
  fi
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

install_cli_alias() {
  local bin_dir="$HOME/.local/bin"
  local target="$bin_dir/voltex"

  mkdir -p "$bin_dir"

  if [[ -L "$target" ]] || [[ -e "$target" ]]; then
    rm -f "$target"
  fi

  ln -s "$INSTALL_DIR/run-voltex" "$target"

  if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
    warn "$bin_dir is not in your PATH."
    warn "Add this to your shell profile to use 'voltex' from any terminal:"
    warn ""
    warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    warn ""
  fi
}

install_auto_update() {
  local config_dir="$CONFIG_HOME/voltex"
  mkdir -p "$config_dir"
  echo "auto_update=true" > "$config_dir/config"
}

install_crash_reports() {
  local config_dir="$CONFIG_HOME/voltex"
  mkdir -p "$config_dir"
  echo "crash_reports=true" >> "$config_dir/config"
}

parse_args "$@"
refuse_root_install
normalize_install_dir
install_system_dependencies
copy_app
normalize_app_permissions
remove_legacy_default_install
install_python_environment
install_desktop_integration

if [[ "${VOLTEX_ENABLE_CLI:-1}" == "1" ]]; then
  install_cli_alias
fi

if [[ "${VOLTEX_ENABLE_AUTO_UPDATE:-1}" == "1" ]]; then
  install_auto_update
fi

if [[ "${VOLTEX_ENABLE_CRASH_REPORTS:-0}" == "1" ]]; then
  install_crash_reports
fi

info "$APP_NAME installed."
info "App files: $INSTALL_DIR"
info "Launcher: $APPLICATIONS_DIR/$DESKTOP_ID"
info "Desktop shortcut: $DESKTOP_DIR/$APP_NAME.desktop"
info "Protocol handler: x-scheme-handler/vortex"

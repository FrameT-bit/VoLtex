from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _read_local_version() -> str:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _check_dependencies() -> None:
    missing: list[str] = []
    for name in ("flask", "webview", "keyring"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)

    if not missing:
        return

    print(
        "VoLtex dependencies are missing from the Python environment.\n"
        f"Missing modules: {', '.join(missing)}\n"
        "\n"
        "Run the installer first:\n"
        "  ./install\n"
        "\n"
        "If the installer is not executable (common after extracting a zip):\n"
        "  bash install\n"
        "\n"
        "The installer creates the Python environment and installs everything needed.",
        file=sys.stderr,
    )
    sys.exit(1)


_check_dependencies()

from .auth_manager import AuthManager
from .config import VoltexConfig
from .diagnostics import format_diagnostics, run_diagnostics
from .game_launcher import GameLauncher
from .server import BridgeServer
from .updater import check_update, apply_update
from .webview_manager import WebviewManager


############################################################
# CLI                                                      #
############################################################

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voltex", description="VoLtex launcher bridge for Vortex")
    parser.add_argument("uri", nargs="?", help="optional vortex:// URI to launch directly")
    parser.add_argument("--doctor", action="store_true", help="print local launch diagnostics and exit")
    parser.add_argument("--print-config", action="store_true", help="print resolved runtime paths and exit")
    parser.add_argument("--clear-session", action="store_true", help="delete saved webview and keyring session")
    parser.add_argument("--check-update", action="store_true", help="check GitHub for newer version and exit")
    parser.add_argument("--update", action="store_true", help="download and apply latest update from GitHub")
    parser.add_argument(
        "--update-branch",
        default="main",
        help="branch to track for updates (default: main; use 'testing' for pre-releases)",
    )
    return parser


def print_config(config: VoltexConfig) -> None:
    print(f"site_url={config.site_url}")
    print(f"wine_binary={config.wine_binary}")
    print(f"wine_env={config.wine_env}")
    print(f"wine_prefix={config.wine_prefix}")
    print(f"vortex_exe={config.vortex_exe}")
    print(f"launch_mode={config.launch_mode}")
    print(f"wine_desktop={config.wine_desktop}")
    print(f"remember_login={config.remember_login}")
    print(f"persistent_session={config.persistent_session}")
    print(f"config_dir={config.config_dir}")
    print(f"data_dir={config.data_dir}")
    print(f"cache_dir={config.cache_dir}")
    print(f"state_dir={config.state_dir}")
    print(f"webview_storage_path={config.webview_storage_path}")
    print(f"log_file={config.log_file}")
    print(f"game_log_file={config.game_log_file}")


def clear_saved_session(config: VoltexConfig) -> None:
    auth = AuthManager(config)
    auth.forget_saved_token()
    shutil.rmtree(config.webview_storage_path, ignore_errors=True)
    config.webview_storage_path.mkdir(parents=True, exist_ok=True)
    try:
        config.webview_storage_path.chmod(0o700)
    except OSError:
        pass
    print("VoLtex saved session cleared.")


############################################################
# MAIN                                                     #
############################################################

def run() -> int:
    args = build_parser().parse_args()
    config = VoltexConfig.from_env()
    config.ensure_runtime_dirs()

    if args.print_config:
        print_config(config)
        return 0

    if args.clear_session:
        clear_saved_session(config)
        return 0

    if args.doctor:
        print(format_diagnostics(run_diagnostics(config)))
        return 0

    ############################################################
    # UPDATE COMMANDS                                          #
    ############################################################
    if args.check_update or args.update:
        version = _read_local_version()
        status = check_update(version, args.update_branch)

        if args.check_update:
            print(f"VoLtex {status.current}  |  branch: {status.branch}")
            print(f"Latest:  {status.latest}")
            if status.update_available:
                print(f"\nUpdate available! Run: voltex --update --update-branch {status.branch}")
            else:
                print("You are up to date.")
            return 0 if not status.update_available else 1

        if args.update:
            if not status.update_available:
                print(f"VoLtex {status.current} is already the latest version on {status.branch}.")
                return 0

            print(f"Updating VoLtex {status.current} → {status.latest} ({status.branch}) ...")
            app_dir = Path(__file__).resolve().parent.parent
            if apply_update(app_dir, args.update_branch):
                print("Restart VoLtex to use the new version.")
                return 0
            return 1

    auth = AuthManager(config)
    launcher = GameLauncher(config)

    if args.uri:
        launcher.launch(args.uri)
        return 0

    bridge = BridgeServer(config.flask_host, auth, launcher, config.log_file)
    info = bridge.start()

    print(f"VoLtex bridge: {info.base_url}")
    print("Opening Vortex webview...")

    try:
        WebviewManager(config, info).start()
    finally:
        auth.clear()
        bridge.stop()

    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    sys.exit(run())

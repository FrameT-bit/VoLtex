from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _xdg_dir(env_name: str, fallback: Path, app_name: str = "voltex") -> Path:
    root = Path(os.getenv(env_name, str(fallback)))
    return root / app_name


def _default_config_dir() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config")


def _default_data_dir() -> Path:
    return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")


def _default_cache_dir() -> Path:
    return _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache")


def _default_state_dir() -> Path:
    return _xdg_dir("XDG_STATE_HOME", Path.home() / ".local" / "state")


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o700)
    except OSError:
        return


@dataclass(frozen=True)
class VoltexConfig:
    site_url: str = "https://playvortex.io"
    flask_host: str = "127.0.0.1"
    wine_binary: str = "wine"
    wine_prefix: Path = field(default_factory=lambda: Path.home() / ".wine")
    vortex_exe: Path = field(
        default_factory=lambda: Path.home()
        / ".wine"
        / "drive_c"
        / "Program Files"
        / "Vortex"
        / "Vortex.exe"
    )
    remember_login: bool = True
    persistent_session: bool = True
    launch_mode: str = "wine-start-wait"
    wine_desktop: str = "Vortex,1280x720"
    service_name: str = "voltex"
    config_dir: Path = field(default_factory=_default_config_dir)
    data_dir: Path = field(default_factory=_default_data_dir)
    cache_dir: Path = field(default_factory=_default_cache_dir)
    state_dir: Path = field(default_factory=_default_state_dir)
    webview_storage_path: Path = field(default_factory=lambda: _default_data_dir() / "webview")
    log_file: Path = field(default_factory=lambda: _default_state_dir() / "voltex.log")
    game_log_file: Path = field(default_factory=lambda: _default_state_dir() / "game.log")

    @classmethod
    def from_env(cls) -> "VoltexConfig":
        config_dir = Path(os.getenv("VOLTEX_CONFIG_DIR", str(_default_config_dir())))
        data_dir = Path(os.getenv("VOLTEX_DATA_DIR", str(_default_data_dir())))
        cache_dir = Path(os.getenv("VOLTEX_CACHE_DIR", str(_default_cache_dir())))
        state_dir = Path(os.getenv("VOLTEX_STATE_DIR", str(_default_state_dir())))
        return cls(
            site_url=os.getenv("VOLTEX_SITE_URL", cls.site_url),
            flask_host=os.getenv("VOLTEX_FLASK_HOST", cls.flask_host),
            wine_binary=os.getenv("VOLTEX_WINE_BINARY", cls.wine_binary),
            wine_prefix=Path(os.getenv("VOLTEX_WINEPREFIX", str(Path.home() / ".wine"))),
            vortex_exe=Path(
                os.getenv(
                    "VOLTEX_EXE",
                    str(
                        Path.home()
                        / ".wine"
                        / "drive_c"
                        / "Program Files"
                        / "Vortex"
                        / "Vortex.exe"
                    ),
                )
            ),
            remember_login=_bool_env("VOLTEX_REMEMBER_LOGIN", True),
            persistent_session=_bool_env("VOLTEX_PERSISTENT_SESSION", True),
            launch_mode=os.getenv("VOLTEX_LAUNCH_MODE", cls.launch_mode),
            wine_desktop=os.getenv("VOLTEX_WINE_DESKTOP", cls.wine_desktop),
            service_name=os.getenv("VOLTEX_KEYRING_SERVICE", cls.service_name),
            config_dir=config_dir,
            data_dir=data_dir,
            cache_dir=cache_dir,
            state_dir=state_dir,
            webview_storage_path=Path(
                os.getenv("VOLTEX_WEBVIEW_STORAGE", str(data_dir / "webview"))
            ),
            log_file=Path(
                os.getenv(
                    "VOLTEX_LOG_FILE",
                    str(state_dir / "voltex.log"),
                )
            ),
            game_log_file=Path(
                os.getenv(
                    "VOLTEX_GAME_LOG_FILE",
                    str(state_dir / "game.log"),
                )
            ),
        )

    def ensure_runtime_dirs(self) -> None:
        for path in {
            self.config_dir,
            self.data_dir,
            self.cache_dir,
            self.state_dir,
            self.webview_storage_path,
            self.log_file.parent,
            self.game_log_file.parent,
        }:
            path.mkdir(parents=True, exist_ok=True)
            _chmod_private(path)

    @property
    def wine_env(self) -> dict[str, str]:
        env = {
            "WINEPREFIX": str(self.wine_prefix),
            "WINEDLLOVERRIDES": "d3d12=d",
        }
        raw = os.getenv("VOLTEX_WINE_ENV", "")
        for item in raw.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip()
            if key:
                env[key] = value.strip()
        return env

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voltex.config import VoltexConfig


class ConfigTest(unittest.TestCase):
    def test_persistent_session_defaults_on(self):
        config = VoltexConfig()

        self.assertTrue(config.remember_login)
        self.assertTrue(config.persistent_session)

    def test_xdg_paths_are_used_from_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_DATA_HOME": str(Path(tmp) / "data"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
                "XDG_STATE_HOME": str(Path(tmp) / "state"),
            }
            with patch.dict(os.environ, env, clear=False):
                config = VoltexConfig.from_env()

            self.assertEqual(config.config_dir, Path(tmp) / "config" / "voltex")
            self.assertEqual(config.data_dir, Path(tmp) / "data" / "voltex")
            self.assertEqual(config.cache_dir, Path(tmp) / "cache" / "voltex")
            self.assertEqual(config.state_dir, Path(tmp) / "state" / "voltex")
            self.assertEqual(config.webview_storage_path, Path(tmp) / "data" / "voltex" / "webview")
            self.assertEqual(config.log_file, Path(tmp) / "state" / "voltex" / "voltex.log")
            self.assertEqual(config.game_log_file, Path(tmp) / "state" / "voltex" / "game.log")

    def test_wine_desktop_can_be_configured_from_environment(self):
        with patch.dict(os.environ, {"VOLTEX_WINE_DESKTOP": "VoLtex,1920x1080"}):
            config = VoltexConfig.from_env()

        self.assertEqual(config.wine_desktop, "VoLtex,1920x1080")

    def test_runtime_dirs_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = VoltexConfig(
                config_dir=Path(tmp) / "config",
                data_dir=Path(tmp) / "data",
                cache_dir=Path(tmp) / "cache",
                state_dir=Path(tmp) / "state",
                webview_storage_path=Path(tmp) / "data" / "webview",
                log_file=Path(tmp) / "state" / "voltex.log",
                game_log_file=Path(tmp) / "state" / "game.log",
            )

            config.ensure_runtime_dirs()

            self.assertEqual((Path(tmp) / "data").stat().st_mode & 0o777, 0o700)
            self.assertEqual((Path(tmp) / "data" / "webview").stat().st_mode & 0o777, 0o700)

    def test_wine_env_disables_d3d12_by_default(self):
        config = VoltexConfig(wine_prefix=Path("/tmp/prefix"))

        self.assertEqual(config.wine_env["WINEPREFIX"], "/tmp/prefix")
        self.assertEqual(config.wine_env["WINEDLLOVERRIDES"], "d3d12=d")

    def test_wine_env_can_override_defaults(self):
        with patch.dict(os.environ, {"VOLTEX_WINE_ENV": "WINEDLLOVERRIDES=,WGPU_BACKEND=vulkan"}):
            config = VoltexConfig(wine_prefix=Path("/tmp/prefix"))
            wine_env = config.wine_env

        self.assertEqual(wine_env["WINEDLLOVERRIDES"], "")
        self.assertEqual(wine_env["WGPU_BACKEND"], "vulkan")


if __name__ == "__main__":
    unittest.main()

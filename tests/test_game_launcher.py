import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from voltex.config import VoltexConfig
from voltex.game_launcher import (
    GameLauncher,
    VortexPlayerNotFound,
    find_vortex_executable,
    redact_command,
    redact_log_text,
)


class FakeProcess:
    pid = 4242
    returncode = 0

    def __init__(self) -> None:
        self.stdout = io.StringIO("received vortex://play?game=3&token=secret-token\n")

    def wait(self) -> int:
        return self.returncode


class GameLauncherTest(unittest.TestCase):
    def test_builds_wine_start_wait_command_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Vortex.exe"
            exe.write_text("", encoding="utf-8")
            config = VoltexConfig(vortex_exe=exe, wine_prefix=Path(tmp))
            launcher = GameLauncher(config)

            command = launcher.build_command("vortex://play?game=3&token=abc")

            self.assertEqual(command[:4], ["wine", "start", "/wait", "/unix"])
            self.assertEqual(command[4], str(exe))
            self.assertEqual(command[5], "vortex://play?game=3&token=abc")

    def test_rejects_non_vortex_uri(self):
        config = VoltexConfig()
        launcher = GameLauncher(config)

        with self.assertRaises(ValueError):
            launcher.build_command("https://playvortex.io")

    def test_builds_legacy_wine_start_command_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Vortex.exe"
            exe.write_text("", encoding="utf-8")
            config = VoltexConfig(vortex_exe=exe, wine_prefix=Path(tmp), launch_mode="wine-start")
            launcher = GameLauncher(config)

            command = launcher.build_command("vortex://play?game=3&token=abc")

            self.assertEqual(command[:3], ["wine", "start", "/unix"])

    def test_builds_virtual_desktop_command_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Vortex.exe"
            exe.write_text("", encoding="utf-8")
            config = VoltexConfig(
                vortex_exe=exe,
                wine_prefix=Path(tmp),
                launch_mode="wine-virtual-desktop",
                wine_desktop="Vortex,1280x720",
            )
            launcher = GameLauncher(config)

            command = launcher.build_command("vortex://play?game=3&token=abc")

            self.assertEqual(command[:3], ["wine", "explorer", "/desktop=Vortex,1280x720"])
            self.assertEqual(command[3], str(exe))
            self.assertEqual(command[4], "vortex://play?game=3&token=abc")

    def test_discovers_local_appdata_vortex_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            exe = (
                prefix
                / "drive_c"
                / "users"
                / "tester"
                / "AppData"
                / "Local"
                / "Programs"
                / "Vortex"
                / "Vortex.exe"
            )
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            config = VoltexConfig(wine_prefix=prefix, vortex_exe=prefix / "missing.exe")

            self.assertEqual(find_vortex_executable(config), str(exe))

    def test_launch_reports_missing_player(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = VoltexConfig(wine_prefix=Path(tmp), vortex_exe=Path(tmp) / "missing.exe")
            launcher = GameLauncher(config)

            with self.assertRaises(VortexPlayerNotFound):
                launcher.launch("vortex://play?game=3&token=abc")

    def test_redacts_sensitive_log_text(self):
        self.assertEqual(
            redact_log_text("vortex://play?game=3&token=abc password=secret"),
            "vortex://play?game=3&token=[redacted] password=[redacted]",
        )
        self.assertEqual(
            redact_command(["wine", "vortex://play?game=3&token=abc"]),
            ["wine", "vortex://play?game=3&token=[redacted]"],
        )

    def test_launch_streams_process_output_to_game_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            exe = prefix / "drive_c" / "Program Files" / "Vortex" / "Vortex.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            config = VoltexConfig(
                wine_prefix=prefix,
                vortex_exe=exe,
                game_log_file=prefix / "state" / "game.log",
            )
            launcher = GameLauncher(config)

            with patch("voltex.game_launcher.subprocess.Popen", return_value=FakeProcess()) as popen:
                result = launcher.launch("vortex://play?game=3&token=abc")

            time.sleep(0.1)
            self.assertEqual(result.log_file, config.game_log_file)
            self.assertEqual(popen.call_args.kwargs["stderr"], -2)
            self.assertIn("token=[redacted]", config.game_log_file.read_text(encoding="utf-8"))
            self.assertNotIn("secret-token", config.game_log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

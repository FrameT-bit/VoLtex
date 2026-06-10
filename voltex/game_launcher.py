from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import VoltexConfig
from .uri import VortexUri, parse_vortex_uri


class VortexPlayerNotFound(FileNotFoundError):
    def __init__(self, expected_path: str) -> None:
        super().__init__(
            "Vortex player was not found in the Wine prefix. "
            f"Expected: {expected_path}. "
            "Install the Windows Vortex player in Wine, then try Play again. "
            "If it is installed in another location, set VOLTEX_EXE to that Vortex.exe path."
        )


@dataclass(frozen=True)
class LaunchResult:
    pid: int
    command: list[str]
    log_file: Path


ProcessCallback = Callable[[subprocess.Popen[str]], None]


############################################################
# LOG REDACTION                                            #
############################################################

def redact_log_text(text: str) -> str:
    return re.sub(
        r"(?i)\b(token|session_token|password)=([^&\s]+)",
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )


def redact_command(command: list[str]) -> list[str]:
    return [redact_log_text(item) for item in command]


############################################################
# VORTEX EXECUTABLE DISCOVERY                              #
############################################################

def find_vortex_executable(config: VoltexConfig) -> str | None:
    if config.vortex_exe.exists():
        return str(config.vortex_exe)

    drive_c = config.wine_prefix / "drive_c"
    candidates = [
        drive_c / "Program Files" / "Vortex" / "Vortex.exe",
        drive_c / "Program Files (x86)" / "Vortex" / "Vortex.exe",
    ]

    users_dir = drive_c / "users"
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            candidates.extend(
                [
                    user_dir / "AppData" / "Local" / "Programs" / "Vortex" / "Vortex.exe",
                    user_dir / "AppData" / "Local" / "Vortex" / "Vortex.exe",
                ]
            )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    if drive_c.exists():
        for candidate in drive_c.rglob("Vortex.exe"):
            if candidate.is_file():
                return str(candidate)

    return None


############################################################
# GAME LAUNCHER                                            #
############################################################

class GameLauncher:
    def __init__(self, config: VoltexConfig) -> None:
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def build_command(self, uri: str | VortexUri, vortex_exe: str | None = None) -> list[str]:
        raw_uri = uri.raw if isinstance(uri, VortexUri) else uri
        parse_vortex_uri(raw_uri)
        exe = vortex_exe or str(self._config.vortex_exe)

        if self._config.launch_mode == "wine-direct":
            return [self._config.wine_binary, exe, raw_uri]

        if self._config.launch_mode == "wine-virtual-desktop":
            return [
                self._config.wine_binary,
                "explorer",
                f"/desktop={self._config.wine_desktop}",
                exe,
                raw_uri,
            ]

        command = [self._config.wine_binary, "start"]
        if self._config.launch_mode == "wine-start-wait":
            command.append("/wait")
        command.extend(["/unix", exe, raw_uri])
        return command

    def launch(self, uri: str, on_exit: ProcessCallback | None = None) -> LaunchResult:
        vortex_exe = find_vortex_executable(self._config)
        if vortex_exe is None:
            raise VortexPlayerNotFound(str(self._config.vortex_exe))

        command = self.build_command(uri, vortex_exe=vortex_exe)
        env = os.environ.copy()
        env.update(self._config.wine_env)

        process = subprocess.Popen(
            command,
            env=env,
            bufsize=1,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._start_log_thread(process, command)

        with self._lock:
            self._process = process

        if on_exit is not None:
            threading.Thread(target=self._watch, args=(process, on_exit), daemon=True).start()

        return LaunchResult(pid=process.pid, command=command, log_file=self._config.game_log_file)

    def current_process(self) -> subprocess.Popen[str] | None:
        with self._lock:
            return self._process

    def _watch(self, process: subprocess.Popen[str], on_exit: ProcessCallback) -> None:
        process.wait()
        self._append_game_log(f"[{_timestamp()}] exit status: {process.returncode}\n")
        on_exit(process)
        with self._lock:
            if self._process is process:
                self._process = None

    def _start_log_thread(self, process: subprocess.Popen[str], command: list[str]) -> None:
        thread = threading.Thread(target=self._write_process_log, args=(process, command), daemon=True)
        thread.start()

    def _write_process_log(self, process: subprocess.Popen[str], command: list[str]) -> None:
        header = (
            f"\n[{_timestamp()}] launching Vortex player\n"
            f"command: {redact_command(command)}\n"
        )
        self._append_game_log(header)

        if process.stdout is None:
            return

        try:
            for line in process.stdout:
                self._append_game_log(redact_log_text(line))
        finally:
            process.stdout.close()

    def _append_game_log(self, text: str) -> None:
        self._config.game_log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._config.game_log_file.parent.chmod(0o700)
        except OSError:
            pass
        with self._config.game_log_file.open("a", encoding="utf-8") as handle:
            handle.write(text)
        try:
            self._config.game_log_file.chmod(0o600)
        except OSError:
            pass


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

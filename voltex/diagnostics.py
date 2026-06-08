from __future__ import annotations

import shutil
from dataclasses import dataclass

from .config import VoltexConfig
from .game_launcher import find_vortex_executable


@dataclass(frozen=True)
class Diagnostic:
    name: str
    ok: bool
    detail: str


def run_diagnostics(config: VoltexConfig) -> list[Diagnostic]:
    vortex_exe = find_vortex_executable(config)
    return [
        Diagnostic("Wine binary", shutil.which(config.wine_binary) is not None, config.wine_binary),
        Diagnostic("Wine prefix", config.wine_prefix.exists(), str(config.wine_prefix)),
        Diagnostic(
            "Vortex executable",
            vortex_exe is not None,
            vortex_exe or f"not found; expected {config.vortex_exe}",
        ),
    ]


def format_diagnostics(items: list[Diagnostic]) -> str:
    lines: list[str] = []
    for item in items:
        status = "PASS" if item.ok else "FAIL"
        lines.append(f"[{status}] {item.name}: {item.detail}")
    return "\n".join(lines)

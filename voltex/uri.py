from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class VortexUri:
    raw: str
    game_id: int
    token: str


def parse_vortex_uri(raw: str) -> VortexUri:
    parsed = urlparse(raw)
    if parsed.scheme != "vortex":
        raise ValueError("URI scheme must be vortex")

    query = parse_qs(parsed.query)
    game_values = query.get("game", [])
    token_values = query.get("token", [])

    if not game_values:
        raise ValueError("Missing game query parameter")
    if not token_values or not token_values[0]:
        raise ValueError("Missing token query parameter")

    try:
        game_id = int(game_values[0])
    except ValueError as exc:
        raise ValueError("Game query parameter must be an integer") from exc

    return VortexUri(raw=raw, game_id=game_id, token=token_values[0])


def is_vortex_uri(raw: str | None) -> bool:
    if not raw:
        return False
    return urlparse(raw).scheme == "vortex"

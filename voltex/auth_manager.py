from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any

from .config import VoltexConfig


@dataclass(frozen=True)
class TokenSnapshot:
    session_token: str | None = None
    source: str = "memory"

    @property
    def authenticated(self) -> bool:
        return bool(self.session_token)


class AuthManager:
    def __init__(self, config: VoltexConfig) -> None:
        self._config = config
        self._session_token: str | None = None

    def snapshot(self) -> TokenSnapshot:
        if self._session_token:
            return TokenSnapshot(session_token=self._session_token)

        if not self._config.remember_login:
            return TokenSnapshot()

        token = self._load_keyring_token()
        if token:
            self._session_token = token
            return TokenSnapshot(session_token=token, source="keyring")

        return TokenSnapshot()

    def clear(self) -> None:
        self._session_token = None

    def forget_saved_token(self) -> bool:
        self._session_token = None
        try:
            import keyring
        except ImportError:
            return False

        try:
            keyring.delete_password(self._config.service_name, "session_token")
        except Exception:
            return False
        return True

    def ingest_cookie_header(self, cookie_header: str, persist: bool = False) -> TokenSnapshot:
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get("session_token")
        if morsel is None:
            return self.snapshot()

        return self.set_session_token(morsel.value, persist=persist)

    def ingest_payload(self, payload: dict[str, Any]) -> TokenSnapshot:
        token = payload.get("session_token") or payload.get("token")
        persist = bool(payload.get("persist"))
        cookie_header = payload.get("cookie")

        if isinstance(token, str) and token:
            return self.set_session_token(token, persist=persist)
        if isinstance(cookie_header, str) and cookie_header:
            return self.ingest_cookie_header(cookie_header, persist=persist)

        return self.snapshot()

    def set_session_token(self, token: str, persist: bool = False) -> TokenSnapshot:
        token = token.strip()
        if not token:
            return self.snapshot()

        self._session_token = token
        if persist or self._config.remember_login:
            self._save_keyring_token(token)
            return TokenSnapshot(session_token=token, source="keyring")

        return TokenSnapshot(session_token=token)

    def _load_keyring_token(self) -> str | None:
        try:
            import keyring
        except ImportError:
            return None

        try:
            return keyring.get_password(self._config.service_name, "session_token")
        except Exception:
            return None

    def _save_keyring_token(self, token: str) -> None:
        try:
            import keyring
        except ImportError:
            return

        try:
            keyring.set_password(self._config.service_name, "session_token", token)
        except Exception:
            return

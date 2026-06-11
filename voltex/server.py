from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Flask, jsonify, request
from werkzeug.serving import BaseWSGIServer, make_server

from .auth_manager import AuthManager
from .game_launcher import GameLauncher, GameAlreadyRunning, VortexPlayerNotFound, redact_command


SENSITIVE_FIELDS = {"authorization", "cookie", "password", "session_token", "token"}


############################################################
# LOG REDACTION                                            #
############################################################

def redact_sensitive(value: Any, field_name: str | None = None) -> Any:
    if field_name is not None and field_name.lower() in SENSITIVE_FIELDS:
        return "[redacted]"
    if isinstance(value, dict):
        return {key: redact_sensitive(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return _redact_url_query(value)
    return value


def _redact_url_query(value: str) -> str:
    split = urlsplit(value)
    if not split.query:
        return value

    pairs = parse_qsl(split.query, keep_blank_values=True)
    redacted_pairs = [
        (key, "[redacted]" if key.lower() in SENSITIVE_FIELDS else item)
        for key, item in pairs
    ]
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(redacted_pairs), split.fragment))


@dataclass(frozen=True)
class BridgeInfo:
    host: str
    port: int
    secret: str

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


############################################################
# EVENT LOG                                                #
############################################################

class EventLog:
    def __init__(self, log_file: Path | None = None) -> None:
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._log_file = log_file

    def push(self, event: str, **data: Any) -> None:
        entry = {"ts": time.time(), "event": event, **redact_sensitive(data)}
        with self._lock:
            self._events.append(entry)
            self._events = self._events[-50:]
            if self._log_file is not None:
                self._log_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self._log_file.parent.chmod(0o700)
                except OSError:
                    pass
                with self._log_file.open("a", encoding="utf-8") as handle:
                    handle.write(f"{entry}\n")
                try:
                    self._log_file.chmod(0o600)
                except OSError:
                    pass

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


############################################################
# FLASK APPLICATION                                        #
############################################################

def create_app(
    auth: AuthManager,
    launcher: GameLauncher,
    event_log: EventLog,
    secret: str,
) -> Flask:
    app = Flask(__name__)

    def allowed() -> bool:
        return request.headers.get("X-Voltex-Secret") == secret

    def secure_json(payload: dict[str, Any], status: int = 200):
        response = jsonify(payload)
        response.status_code = status
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Voltex-Secret"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.before_request
    def handle_options():
        if request.method == "OPTIONS":
            return secure_json({"ok": True})
        return None

    @app.get("/health")
    def health():
        return secure_json({"ok": True})

    @app.get("/api/auth/status")
    def auth_status():
        if not allowed():
            return secure_json({"error": "unauthorized"}, 401)
        snapshot = auth.snapshot()
        return secure_json({"authenticated": snapshot.authenticated, "source": snapshot.source})

    @app.post("/api/auth/token")
    def auth_token():
        if not allowed():
            return secure_json({"error": "unauthorized"}, 401)
        payload = request.get_json(silent=True) or {}
        snapshot = auth.ingest_payload(payload)
        return secure_json({"authenticated": snapshot.authenticated, "source": snapshot.source})

    @app.post("/api/launch")
    def launch():
        if not allowed():
            return secure_json({"error": "unauthorized"}, 401)

        payload = request.get_json(silent=True) or {}
        uri = payload.get("uri")
        if not isinstance(uri, str):
            return secure_json({"error": "missing uri"}, 400)

        try:
            result = launcher.launch(uri, on_exit=lambda proc: event_log.push("game_exit", code=proc.returncode))
        except GameAlreadyRunning:
            return secure_json({"error": "A game is already running", "kind": "already_running"}, 409)
        except VortexPlayerNotFound as exc:
            event_log.push("launch_error", kind="missing_player", detail=str(exc))
            return secure_json({"error": str(exc), "kind": "missing_player"}, 500)
        except Exception as exc:
            event_log.push("launch_error", detail=str(exc))
            return secure_json({"error": str(exc)}, 500)

        event_log.push("game_launch", pid=result.pid, log_file=str(result.log_file))
        return secure_json(
            {"pid": result.pid, "command": redact_command(result.command), "log_file": str(result.log_file)}
        )

    @app.post("/api/debug")
    def debug():
        if not allowed():
            return secure_json({"error": "unauthorized"}, 401)
        payload = request.get_json(silent=True) or {}
        event = payload.get("event", "client_debug")
        if not isinstance(event, str):
            event = "client_debug"
        event_log.push(event, payload=payload)
        return secure_json({"ok": True})

    @app.get("/api/events")
    def events():
        if not allowed():
            return secure_json({"error": "unauthorized"}, 401)
        return secure_json({"events": event_log.list()})

    return app


############################################################
# BRIDGE SERVER                                            #
############################################################

class BridgeServer:
    def __init__(
        self,
        host: str,
        auth: AuthManager,
        launcher: GameLauncher,
        log_file: Path | None = None,
    ) -> None:
        self.event_log = EventLog(log_file)
        self.info = BridgeInfo(host=host, port=0, secret=secrets.token_urlsafe(32))
        self._app = create_app(auth, launcher, self.event_log, self.info.secret)
        self._server: BaseWSGIServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> BridgeInfo:
        self._server = make_server(self.info.host, 0, self._app, threaded=True)
        self.info = BridgeInfo(
            host=self.info.host,
            port=int(self._server.server_port),
            secret=self.info.secret,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.event_log.push("bridge_start", base_url=self.info.base_url)
        return self.info

    def stop(self) -> None:
        self.event_log.push("bridge_stop")
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=2)

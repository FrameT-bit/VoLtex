import unittest
from pathlib import Path

from voltex.auth_manager import AuthManager
from voltex.config import VoltexConfig
from voltex.server import EventLog, create_app


class FakeLauncher:
    def launch(self, uri, on_exit=None):
        class Result:
            pid = 123
            command = ["wine", "start", "/unix", "Vortex.exe", uri]
            log_file = Path("/tmp/voltex-game.log")

        return Result()


class MissingPlayerLauncher:
    def launch(self, uri, on_exit=None):
        from voltex.game_launcher import VortexPlayerNotFound

        raise VortexPlayerNotFound("/tmp/missing/Vortex.exe")


class ServerTest(unittest.TestCase):
    def test_requires_secret_for_auth_status(self):
        app = create_app(AuthManager(VoltexConfig()), FakeLauncher(), EventLog(), "secret")
        client = app.test_client()

        response = client.get("/api/auth/status")

        self.assertEqual(response.status_code, 401)

    def test_launch_accepts_secret(self):
        app = create_app(AuthManager(VoltexConfig()), FakeLauncher(), EventLog(), "secret")
        client = app.test_client()

        response = client.post(
            "/api/launch",
            json={"uri": "vortex://play?game=1&token=abc"},
            headers={"X-Voltex-Secret": "secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["pid"], 123)
        self.assertEqual(response.get_json()["log_file"], "/tmp/voltex-game.log")
        self.assertEqual(
            response.get_json()["command"][-1],
            "vortex://play?game=1&token=[redacted]",
        )

    def test_event_log_redacts_tokens(self):
        event_log = EventLog()

        event_log.push(
            "client_debug",
            payload={
                "uri": "vortex://play?game=1&token=abc",
                "cookie": "session_token=abc",
            },
        )

        event = event_log.list()[0]
        self.assertEqual(event["payload"]["uri"], "vortex://play?game=1&token=%5Bredacted%5D")
        self.assertEqual(event["payload"]["cookie"], "[redacted]")

    def test_launch_reports_missing_player_kind(self):
        app = create_app(AuthManager(VoltexConfig()), MissingPlayerLauncher(), EventLog(), "secret")
        client = app.test_client()

        response = client.post(
            "/api/launch",
            json={"uri": "vortex://play?game=1&token=abc"},
            headers={"X-Voltex-Secret": "secret"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["kind"], "missing_player")


if __name__ == "__main__":
    unittest.main()

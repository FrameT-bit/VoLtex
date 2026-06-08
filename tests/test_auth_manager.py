import unittest

from voltex.auth_manager import AuthManager
from voltex.config import VoltexConfig


class AuthManagerTest(unittest.TestCase):
    def test_ingests_session_cookie(self):
        auth = AuthManager(VoltexConfig(remember_login=False))
        snapshot = auth.ingest_cookie_header("theme=dark; session_token=abc123")

        self.assertTrue(snapshot.authenticated)
        self.assertEqual(snapshot.session_token, "abc123")

    def test_payload_token_wins(self):
        auth = AuthManager(VoltexConfig(remember_login=False))
        snapshot = auth.ingest_payload({"token": "from_payload", "cookie": "session_token=from_cookie"})

        self.assertEqual(snapshot.session_token, "from_payload")


if __name__ == "__main__":
    unittest.main()

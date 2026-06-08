import unittest

from voltex.config import VoltexConfig
from voltex.server import BridgeInfo
from voltex.webview_manager import WebviewManager


class WebviewManagerTest(unittest.TestCase):
    def test_script_contains_bridge_details(self):
        bridge = BridgeInfo(host="127.0.0.1", port=4321, secret="test-secret")
        script = WebviewManager(VoltexConfig(), bridge).build_script()

        self.assertIn("http://127.0.0.1:4321", script)
        self.assertIn("test-secret", script)
        self.assertIn("/api/launch", script)
        self.assertIn("rememberLogin = true", script)
        self.assertIn("/api/events", script)
        self.assertIn("voltex-notice", script)
        self.assertIn("launch_error", script)


if __name__ == "__main__":
    unittest.main()

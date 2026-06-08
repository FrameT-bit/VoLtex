import unittest

from voltex.uri import is_vortex_uri, parse_vortex_uri


class VortexUriTest(unittest.TestCase):
    def test_parse_valid_uri(self):
        uri = parse_vortex_uri("vortex://play?game=4&token=abc123")

        self.assertEqual(uri.game_id, 4)
        self.assertEqual(uri.token, "abc123")

    def test_rejects_missing_token(self):
        with self.assertRaises(ValueError):
            parse_vortex_uri("vortex://play?game=4")

    def test_identifies_vortex_scheme(self):
        self.assertTrue(is_vortex_uri("vortex://play?game=4&token=abc123"))
        self.assertFalse(is_vortex_uri("https://playvortex.io"))


if __name__ == "__main__":
    unittest.main()

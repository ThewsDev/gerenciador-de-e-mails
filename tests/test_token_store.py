import unittest

from src.services.token_store import TokenStore


class TokenStoreTests(unittest.TestCase):
    def test_token_is_available_in_memory(self):
        store = TokenStore()
        store.set_access_token("access-token")
        self.assertEqual(store.get_access_token(), "access-token")
        self.assertTrue(store.has_token())

    def test_clear_discards_token(self):
        store = TokenStore()
        store.set_access_token("access-token")
        store.clear()
        self.assertIsNone(store.get_access_token())
        self.assertFalse(store.has_token())

    def test_empty_token_is_rejected(self):
        store = TokenStore()
        with self.assertRaises(ValueError):
            store.set_access_token("")


if __name__ == "__main__":
    unittest.main()

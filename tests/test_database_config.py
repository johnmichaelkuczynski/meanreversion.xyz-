import unittest
from unittest.mock import patch

from database_config import database_url


class DatabaseConfigTests(unittest.TestCase):
    def test_neon_overrides_default_database(self):
        self.assertEqual(database_url({
            "NEON_DATABASE_URL": "postgresql://custom/test",
            "DATABASE_URL": "postgresql://default/test",
        }), "postgresql://custom/test")

    def test_standard_database_remains_supported(self):
        self.assertEqual(database_url({"DATABASE_URL": "postgresql://default/test"}),
                         "postgresql://default/test")

    def test_empty_neon_uses_standard_database(self):
        self.assertEqual(database_url({
            "NEON_DATABASE_URL": "  ", "DATABASE_URL": "postgresql://default/test",
        }), "postgresql://default/test")

    def test_missing_credentials_do_not_crash_configuration(self):
        self.assertEqual(database_url({}), "")

    def test_visitor_connection_uses_same_database(self):
        import visitor_counter
        with patch.dict("os.environ", {
            "NEON_DATABASE_URL": "postgresql://custom/test",
            "DATABASE_URL": "postgresql://default/test",
        }), patch.object(visitor_counter.psycopg2, "connect") as connect:
            visitor_counter._connect()
            connect.assert_called_once_with("postgresql://custom/test", connect_timeout=4)

    def test_schwab_token_storage_uses_app_specific_neon_database(self):
        import schwab_token_store
        with patch.object(schwab_token_store, "database_url",
                          return_value="postgresql://app-specific/test"), \
                patch.object(schwab_token_store.psycopg2, "connect") as connect, \
                patch.object(schwab_token_store, "_ensure_schema"):
            with schwab_token_store._connection():
                pass
            connect.assert_called_once()
            self.assertEqual(
                connect.call_args.args[0],
                "postgresql://app-specific/test",
            )

import unittest

from mail.db_compat import _adapt_postgres_sql


class TestAdaptPostgresSqlCollateNocase(unittest.TestCase):
    def test_collate_nocase_rewritten_to_lower(self) -> None:
        sql = "SELECT id, name FROM global_suppliers ORDER BY name COLLATE NOCASE, id"
        adapted = _adapt_postgres_sql(sql)
        self.assertNotIn("NOCASE", adapted.upper())
        self.assertIn("LOWER(name)", adapted)

    def test_collate_nocase_with_qualified_column(self) -> None:
        sql = "SELECT u.id FROM users u ORDER BY u.display_name COLLATE NOCASE, u.id"
        adapted = _adapt_postgres_sql(sql)
        self.assertIn("LOWER(u.display_name)", adapted)

    def test_multiple_collate_nocase_in_one_query(self) -> None:
        sql = "SELECT kind, value FROM t ORDER BY kind, value COLLATE NOCASE, id"
        adapted = _adapt_postgres_sql(sql)
        self.assertNotIn("NOCASE", adapted.upper())
        self.assertIn("LOWER(value)", adapted)

    def test_placeholder_conversion_still_works_alongside(self) -> None:
        sql = "SELECT id FROM t WHERE workspace_id=? ORDER BY name COLLATE NOCASE"
        adapted = _adapt_postgres_sql(sql)
        self.assertIn("LOWER(name)", adapted)
        self.assertIn("%s", adapted)


if __name__ == "__main__":
    unittest.main()

import unittest

from supplier_discovery_v2.query_planner import QueryPlanner, load_positions, normalize_text


class QueryPlannerTests(unittest.TestCase):
    def test_cable_spec_normalization_and_bounded_queries(self):
        self.assertEqual(normalize_text("кабель ВВГ нг 3х2,5"), "кабель ВВГнг 3x2.5")
        position = load_positions(key="кабель ВВГ нг 3х2,5", quantity="100", region="Москва")[0]
        variants = QueryPlanner(3).plan(position)
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].query, "кабель ВВГнг 3x2.5")
        self.assertIn("Москва", variants[-1].query)

    def test_request_json_shape_is_supported(self):
        position = load_positions(key="насос", quantity="4")[0]
        self.assertEqual(position.quantity, 4.0)
        self.assertEqual(position.position_key, "position-1")


if __name__ == "__main__":
    unittest.main()

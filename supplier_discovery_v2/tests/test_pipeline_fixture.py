import tempfile
import unittest
from pathlib import Path

from supplier_discovery_v2.pipeline import plan_only, run_pipeline
from supplier_discovery_v2.query_planner import load_positions


class PipelineFixtureTests(unittest.TestCase):
    def test_plan_and_dry_run_make_no_network_request(self):
        positions = load_positions(key="кабель ВВГнг 3х2.5", quantity="100")
        plan = plan_only(positions, 3)
        self.assertEqual(plan["network_requests"], 0)
        with tempfile.TemporaryDirectory() as directory:
            report = run_pipeline(positions, "dry-run", Path(directory) / "out", Path(directory) / "db" / "pilot.sqlite3")
            self.assertEqual(report["mode"], "dry-run")
            self.assertEqual(report["writes_to_current_system"], 0)
            self.assertTrue((Path(directory) / "out" / "latest_report.json").exists())


if __name__ == "__main__":
    unittest.main()

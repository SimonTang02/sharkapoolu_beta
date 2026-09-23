import sqlite3
import tempfile
import unittest
from pathlib import Path

from job_bot.scoring_experiment import evaluate


class ScoringExperimentTests(unittest.TestCase):
    def test_evaluate_is_read_only_and_reports_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "jobs.sqlite3"
            conn = sqlite3.connect(database)
            conn.execute(
                """
                CREATE TABLE jobs (
                  id INTEGER, source_name TEXT, company TEXT, title TEXT,
                  url TEXT, location TEXT, description TEXT, external_id TEXT,
                  platform TEXT, role_kind TEXT, fit_score INTEGER, is_active INTEGER
                )
                """
            )
            conn.execute(
                "INSERT INTO jobs VALUES (1,'Fixture','Example','RTL Intern','https://example.com','','RTL design','','','internship',10,1)"
            )
            conn.commit()
            conn.close()
            config = {
                "scoring": {
                    "algorithm": "foundation_v2",
                    "foundation_secondary_bonus": 0,
                    "max_secondary_foundations": 0,
                    "foundation_groups": [
                        {"name": "digital", "base_score": 70, "keywords": ["RTL"], "min_body_hits": 1}
                    ],
                    "modifiers": [],
                }
            }
            rows = evaluate(config, database)
            self.assertEqual(rows[0]["experimental_score"], 70)
            self.assertEqual(rows[0]["delta"], 60)
            conn = sqlite3.connect(database)
            self.assertEqual(conn.execute("SELECT fit_score FROM jobs").fetchone()[0], 10)
            conn.close()


if __name__ == "__main__":
    unittest.main()

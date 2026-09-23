import sqlite3
import unittest
from pathlib import Path

from application_bot.dispatcher import application_rows, build_plans


class DispatcherTests(unittest.TestCase):
    def test_builds_configured_workday_plan(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE jobs (id INTEGER, company TEXT, title TEXT, platform TEXT, url TEXT);
            CREATE TABLE applications (id INTEGER, job_id INTEGER, status TEXT);
            INSERT INTO jobs VALUES (
              1, 'NVIDIA', 'ASIC Intern', 'workday',
              'https://nvidia.wd5.myworkdayjobs.com/site/job/1'
            );
            INSERT INTO applications VALUES (7, 1, 'queued');
            """
        )
        rows = application_rows(conn, [7], None)
        config = {
            "portals": {"adapters": [{
                "id": "workday", "platforms": ["workday"],
                "host_suffixes": ["myworkdayjobs.com"],
                "script": "application_bot/cli.py", "subcommand": "workday-preview",
                "env_option": "--env-file", "supports_draft": True,
            }]}
        }
        plans = build_plans(config, rows, Path("config.json"), Path("passport.env"))
        self.assertEqual(plans[0].adapter, "workday")
        self.assertIsNone(plans[0].company_profile)
        self.assertEqual(plans[0].state, "ready")
        self.assertTrue(plans[0].supports_draft)
        self.assertEqual(plans[0].timeout_seconds, 180)

    def test_adapter_timeout_is_part_of_plan(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE jobs (id INTEGER, company TEXT, title TEXT, platform TEXT, url TEXT);
            CREATE TABLE applications (id INTEGER, job_id INTEGER, status TEXT);
            INSERT INTO jobs VALUES (
              1, 'NVIDIA', 'ASIC Intern', 'workday',
              'https://nvidia.wd5.myworkdayjobs.com/site/job/1'
            );
            INSERT INTO applications VALUES (7, 1, 'queued');
            """
        )
        rows = application_rows(conn, [7], None)
        config = {
            "portals": {"adapters": [{
                "id": "workday", "platforms": ["workday"],
                "host_suffixes": ["myworkdayjobs.com"],
                "script": "application_bot/cli.py", "timeout_seconds": 420,
            }]}
        }
        plans = build_plans(config, rows, Path("config.json"), Path("passport.env"))
        self.assertEqual(plans[0].timeout_seconds, 420)


if __name__ == "__main__":
    unittest.main()

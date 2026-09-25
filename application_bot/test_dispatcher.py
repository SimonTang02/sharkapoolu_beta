import sqlite3
import unittest
from datetime import date
from pathlib import Path

from application_bot.application_limits import check_application_limit
from application_bot.dispatcher import application_rows, build_plans


class DispatcherTests(unittest.TestCase):
    def test_hard_application_limit_prevents_adapter_execution(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE jobs(id INTEGER, company TEXT, title TEXT, platform TEXT,
              url TEXT, recruitment_category TEXT);
            CREATE TABLE applications(id INTEGER, job_id INTEGER, status TEXT,
              submitted_at TEXT, updated_at TEXT, created_at TEXT);
            CREATE TABLE application_limits(id INTEGER, company TEXT, category TEXT,
              window_start TEXT, window_end TEXT, max_applications INTEGER,
              enforcement TEXT, source_url TEXT);
            INSERT INTO jobs VALUES
              (1,'Example Company','ASIC Intern','workday','https://example.myworkdayjobs.com/1','2027_campus'),
              (2,'Example Company','RTL Intern','workday','https://example.myworkdayjobs.com/2','2027_campus');
            INSERT INTO applications VALUES
              (1,1,'submitted','2026-09-20',NULL,NULL),
              (2,2,'queued',NULL,NULL,NULL);
            INSERT INTO application_limits VALUES
              (1,'Example Company','2027_campus','2026-09-01','2027-08-31',1,'hard',NULL);
            """
        )
        rows = application_rows(conn, [2], None)
        check = check_application_limit(conn, 2, today=date(2026, 9, 25))
        config = {"portals": {"adapters": [{
            "id": "workday", "platforms": ["workday"],
            "host_suffixes": ["myworkdayjobs.com"],
            "script": "application_bot/cli.py", "subcommand": "workday-preview",
        }]}}
        plans = build_plans(config, rows, Path("config.json"), Path("passport.env"), {2: check})
        self.assertEqual(plans[0].state, "application_limit_reached")
        self.assertIsNone(plans[0].command)
        conn.close()

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

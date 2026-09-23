import copy
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zoneinfo import ZoneInfo

from job_bot.bot import load_config
from job_bot.weekly_report import (
    DEFAULT_CONFIG,
    build_report,
    funnel_group,
    parse_timestamp,
    week_window,
)


class WeeklyReportTests(unittest.TestCase):
    def test_week_window_uses_monday_in_configured_timezone(self) -> None:
        timezone = ZoneInfo("Asia/Shanghai")
        start, end = week_window(
            dt.datetime(2026, 9, 2, 12, tzinfo=dt.timezone.utc), timezone
        )
        self.assertEqual(start.isoformat(), "2026-08-31T00:00:00+08:00")
        self.assertEqual(end.isoformat(), "2026-09-07T00:00:00+08:00")

    def test_timestamp_parser_treats_legacy_naive_values_as_utc(self) -> None:
        parsed = parse_timestamp("2026-09-01 12:00:00")
        self.assertEqual(parsed.tzinfo, dt.timezone.utc)

    def test_funnel_groups(self) -> None:
        self.assertEqual(funnel_group("submitted"), "submitted")
        self.assertEqual(funnel_group("draft_saved"), "review_ready")
        self.assertEqual(funnel_group("captcha_required"), "blocked")
        self.assertEqual(funnel_group("new_status"), "other")

    def test_build_report_rebuilds_period_files_from_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "jobs.sqlite3"
            conn = sqlite3.connect(database)
            conn.executescript(
                """
                CREATE TABLE jobs (
                  id INTEGER PRIMARY KEY, company TEXT, title TEXT,
                  location TEXT, url TEXT, role_kind TEXT, description TEXT,
                  fit_score INTEGER, source_name TEXT, first_seen TEXT,
                  last_seen TEXT, updated_at TEXT, is_active INTEGER,
                  inactive_since TEXT
                );
                CREATE TABLE applications (
                  id INTEGER PRIMARY KEY, job_id INTEGER, status TEXT,
                  submitted_at TEXT, updated_at TEXT
                );
                CREATE TABLE scan_runs (
                  id INTEGER PRIMARY KEY, source_name TEXT, started_at TEXT,
                  finished_at TEXT, status TEXT, jobs_seen INTEGER,
                  jobs_new INTEGER, error TEXT
                );
                """
            )
            jobs = [
                (
                    1, "Fixture CN", "RTL Design New College Grad 2027",
                    "Shanghai, China", "https://example.com/cn", "full_time",
                    "SystemVerilog ASIC", 90, "Fixture Source",
                    "2026-09-01T01:00:00+00:00", "2026-09-01T01:00:00+00:00", 1,
                ),
                (
                    2, "Fixture US", "ASIC Design Intern Summer 2027",
                    "Austin, Texas, United States", "https://example.com/us",
                    "internship", "RTL Verilog master students", 90,
                    "Fixture Source", "2026-09-01T02:00:00+00:00",
                    "2026-09-01T02:00:00+00:00", 1,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO jobs (
                  id,company,title,location,url,role_kind,description,fit_score,
                  source_name,first_seen,updated_at,is_active
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                jobs,
            )
            conn.execute(
                """
                INSERT INTO jobs (
                  id,company,title,location,url,role_kind,description,fit_score,
                  source_name,first_seen,updated_at,is_active,inactive_since
                ) VALUES (3,'Old Internship','RTL Intern','Shenzhen',
                  'https://example.com/old','internship','RTL',80,
                  'Fixture Source','2026-08-20T00:00:00+00:00',
                  '2026-09-01T04:00:00+00:00',0,'2026-09-01T04:00:00+00:00')
                """
            )
            conn.execute(
                "INSERT INTO applications VALUES (1,1,'submitted',?,?)",
                ("2026-09-01T03:00:00+00:00", "2026-09-01T03:00:00+00:00"),
            )
            conn.execute(
                "INSERT INTO scan_runs VALUES (1,'Fixture Source',?,?,?,2,2,NULL)",
                (
                    "2026-09-01T00:00:00+00:00",
                    "2026-09-01T00:01:00+00:00",
                    "ok",
                ),
            )
            conn.commit()
            conn.close()

            config = copy.deepcopy(load_config(DEFAULT_CONFIG))
            config["sources"] = [{"name": "Fixture Source", "enabled": True}]
            config["reporting"]["weekly"].update(
                {"include_session_audit": False, "write_latest_pointer": False}
            )
            md_path, json_path, payload = build_report(
                config=config,
                database=database,
                output_dir=root / "out",
                now=dt.datetime(2026, 9, 2, 12, tzinfo=dt.timezone.utc),
            )

            self.assertEqual(md_path.name, "weekly_2026-W36.md")
            self.assertEqual(payload["jobs"]["new_this_week"], 2)
            self.assertEqual(payload["jobs"]["detected_inactive_this_week"], 1)
            self.assertEqual(
                payload["jobs"]["inactive_this_week"][0]["title"], "RTL Intern"
            )
            self.assertEqual(payload["applications"]["funnel"]["submitted"], 1)
            self.assertEqual(len(payload["strategy"]["new_cn_hk_campus"]), 1)
            self.assertEqual(len(payload["strategy"]["new_us_summer"]), 1)
            self.assertIn("SQLite 完整重建", md_path.read_text(encoding="utf-8"))
            self.assertIn("本周检测为下线的岗位", md_path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(json_path.read_text())["period"], "2026-W36")


if __name__ == "__main__":
    unittest.main()

import sqlite3
import unittest
from datetime import date

from application_bot.application_limits import check_application_limit


class ApplicationLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE jobs(id INTEGER PRIMARY KEY, company TEXT, recruitment_category TEXT);
            CREATE TABLE applications(id INTEGER PRIMARY KEY, job_id INTEGER, status TEXT,
              submitted_at TEXT, updated_at TEXT, created_at TEXT);
            CREATE TABLE application_limits(id INTEGER PRIMARY KEY, company TEXT, category TEXT,
              window_start TEXT, window_end TEXT, max_applications INTEGER,
              enforcement TEXT, source_url TEXT);
            INSERT INTO application_limits VALUES
              (1,'Employer','2027_campus','2026-09-01','2027-08-31',2,'hard','https://example.com/rule');
            INSERT INTO jobs VALUES (1,'Employer','2027_campus'), (2,'Employer','2027_campus'),
              (3,'Employer','2027_campus'), (4,'Employer','social'), (5,'Employer',NULL);
            INSERT INTO applications VALUES
              (1,1,'submitted','2026-09-15',NULL,NULL),
              (2,2,'submitted','2026-09-16',NULL,NULL),
              (3,3,'queued',NULL,NULL,NULL),
              (4,4,'queued',NULL,NULL,NULL),
              (5,5,'queued',NULL,NULL,NULL);
            """
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_reached_cap_blocks_only_matching_category(self) -> None:
        day = date(2026, 9, 25)
        blocked = check_application_limit(self.conn, 3, today=day)
        self.assertEqual((blocked.state, blocked.submitted_count, blocked.remaining),
                         ("application_limit_reached", 2, 0))
        self.assertEqual(check_application_limit(self.conn, 4, today=day).state, "ready")
        self.assertEqual(check_application_limit(self.conn, 5, today=day).state,
                         "category_review_required")

    def test_outside_window_and_advisory_do_not_hard_block(self) -> None:
        self.assertEqual(check_application_limit(
            self.conn, 3, today=date(2028, 1, 1)).state, "ready")
        self.conn.execute("UPDATE application_limits SET enforcement='advisory'")
        self.assertEqual(check_application_limit(
            self.conn, 3, today=date(2026, 9, 25)).state, "limit_advisory")


if __name__ == "__main__":
    unittest.main()

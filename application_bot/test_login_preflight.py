import sqlite3
import unittest

from application_bot.login_preflight import build_login_targets, campaign_rows


class LoginPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE jobs (
              id INTEGER, company TEXT, title TEXT, platform TEXT, url TEXT,
              external_id TEXT
            );
            CREATE TABLE applications (id INTEGER, job_id INTEGER, status TEXT);
            CREATE TABLE application_campaign_jobs (
              campaign_id INTEGER, rank INTEGER, application_id INTEGER, job_id INTEGER
            );
            INSERT INTO jobs VALUES
              (1, 'NVIDIA', 'ASIC Intern', 'workday',
               'https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x', 'JR1'),
              (2, 'NVIDIA', 'Architecture Intern', 'workday',
               'https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/y', 'JR2'),
              (3, 'AMD', 'Design Verification Intern', 'icims',
               'https://careers.amd.com/jobs/123', '123');
            INSERT INTO applications VALUES (11, 1, 'queued'), (12, 2, 'queued'), (13, 3, 'queued');
            INSERT INTO application_campaign_jobs VALUES
              (4, 1, 11, 1), (4, 2, 12, 2), (4, 3, 13, 3);
            """
        )

    def test_one_target_per_company_and_rank_order(self) -> None:
        config = {"portals": {"adapters": [
            {"id": "amd_icims", "priority": 100, "company_patterns": ["^AMD$"],
             "host_suffixes": ["careers.amd.com"]},
            {"id": "workday", "priority": 80, "platforms": ["workday"],
             "host_suffixes": ["myworkdayjobs.com"]},
        ]}}
        targets = build_login_targets(config, campaign_rows(self.conn, [4]))
        self.assertEqual([item.company for item in targets], ["NVIDIA", "AMD"])
        self.assertEqual(targets[0].application_id, 11)
        self.assertTrue(targets[0].login_check_url.endswith("/NVIDIAExternalCareerSite/userHome"))
        self.assertEqual(targets[1].login_check_url, "https://campus-amd.icims.com/jobs/123/login")


if __name__ == "__main__":
    unittest.main()

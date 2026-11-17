import json
import sqlite3
import unittest
from pathlib import Path

from application_bot.login_preflight import build_login_targets, campaign_rows


PORTALS_CONFIG = Path(__file__).resolve().parents[1] / "job_bot" / "config" / "portals.json"

LEVER_URL = "https://jobs.eu.lever.co/cirrus/639a7c66"
GREENHOUSE_URL = "https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005"
ASHBY_URL = "https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d"


def application_row(company: str, title: str, platform: str, url: str,
                    external_id: str, application_id: int) -> dict:
    return {
        "company": company, "title": title, "platform": platform, "url": url,
        "external_id": external_id, "application_id": application_id,
    }


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


class ConfiguredStandardAtsPreflightTests(unittest.TestCase):
    """The preflight target comes from ``portals.json``, not from the row URL."""

    def setUp(self) -> None:
        self.config = json.loads(PORTALS_CONFIG.read_text(encoding="utf-8"))

    def targets(self, rows):
        return build_login_targets(self.config, rows)

    def test_standard_ats_targets_the_application_page(self) -> None:
        rows = [
            application_row("Cirrus Logic", "Design Intern", "lever", LEVER_URL, "639a7c66", 14),
            application_row("Astera Labs", "Silicon Intern", "greenhouse", GREENHOUSE_URL, "4731399005", 16),
            application_row("Etched", "ASIC Intern", "ashby", ASHBY_URL, "5f1f5739", 17),
        ]
        by_company = {item.company: item for item in self.targets(rows)}
        # Lever appends its application route; Ashby does the same for /application.
        self.assertEqual(by_company["Cirrus Logic"].login_check_url, f"{LEVER_URL}/apply")
        self.assertEqual(by_company["Etched"].login_check_url, f"{ASHBY_URL}/application")
        # Greenhouse renders the form on the job page, which is already the target.
        self.assertEqual(by_company["Astera Labs"].login_check_url, GREENHOUSE_URL)
        for item in by_company.values():
            self.assertEqual(item.representative_url, next(
                row["url"] for row in rows if row["company"] == item.company
            ))

    def test_application_route_is_not_appended_twice(self) -> None:
        rows = [
            application_row("Cirrus Logic", "Design Intern", "lever",
                            f"{LEVER_URL}/apply", "639a7c66", 14),
            application_row("Etched", "ASIC Intern", "ashby",
                            f"{ASHBY_URL}/application/", "5f1f5739", 17),
        ]
        by_company = {item.company: item for item in self.targets(rows)}
        self.assertEqual(by_company["Cirrus Logic"].login_check_url, f"{LEVER_URL}/apply")
        self.assertEqual(by_company["Etched"].login_check_url, f"{ASHBY_URL}/application")

    def test_duplicate_company_generates_one_target_at_first_rank(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
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
              (1, 'Cirrus Logic', 'Design Intern', 'lever',
               'https://jobs.eu.lever.co/cirrus/639a7c66', '639a7c66'),
              (2, 'Cirrus Logic', 'DV Intern', 'lever',
               'https://jobs.eu.lever.co/cirrus/11112222', '11112222');
            INSERT INTO applications VALUES (14, 1, 'queued'), (15, 2, 'queued');
            INSERT INTO application_campaign_jobs VALUES (7, 1, 14, 1), (7, 2, 15, 2);
            """
        )
        targets = build_login_targets(self.config, campaign_rows(conn, [7]))
        conn.close()
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].company, "Cirrus Logic")
        self.assertEqual(targets[0].application_id, 14)
        self.assertEqual(targets[0].login_check_url, f"{LEVER_URL}/apply")
        self.assertEqual(targets[0].label, "jobbot-login-company-cirrus-logic")

    def test_workday_and_icims_targets_are_unchanged(self) -> None:
        rows = [
            application_row(
                "NVIDIA", "ASIC Intern", "workday",
                "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x",
                "JR1", 11,
            ),
            application_row(
                "AMD", "Design Verification Intern", "icims",
                "https://careers.amd.com/jobs/123", "123", 13,
            ),
        ]
        urls = [item.login_check_url for item in self.targets(rows)]
        self.assertEqual(urls, [
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/userHome",
            "https://campus-amd.icims.com/jobs/123/login",
        ])
        non_campus = self.targets([
            application_row(
                "AMD", "Senior Design Engineer", "icims",
                "https://careers.amd.com/jobs/456", "456", 18,
            ),
        ])
        self.assertEqual(
            [item.login_check_url for item in non_campus],
            ["https://global-external-amd.icims.com/jobs/456/login"],
        )

    def test_configured_apply_path_matches_the_dispatch_adapter(self) -> None:
        from application_bot import ashby, greenhouse, lever
        from application_bot.portal_registry import application_url, resolve_adapter

        for company, platform, url, module, expected in (
            ("Cirrus Logic", "lever", LEVER_URL, lever, f"{LEVER_URL}/apply"),
            ("Astera Labs", "greenhouse", GREENHOUSE_URL, greenhouse, GREENHOUSE_URL),
            ("Etched", "ashby", ASHBY_URL, ashby, f"{ASHBY_URL}/application"),
        ):
            adapter = resolve_adapter(
                self.config, company=company, platform=platform, url=url
            )
            self.assertEqual(application_url(adapter, url), expected, company)
            self.assertEqual(module.apply_url(url), expected, company)


if __name__ == "__main__":
    unittest.main()

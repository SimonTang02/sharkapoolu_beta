import json
import sqlite3
import unittest
from pathlib import Path

from application_bot.session_audit import build_probes, classify_session


PORTALS_CONFIG = Path(__file__).resolve().parents[1] / "job_bot" / "config" / "portals.json"


class SessionAuditTests(unittest.TestCase):
    def connection(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE jobs (
              id INTEGER, company TEXT, url TEXT, platform TEXT, external_id TEXT
            );
            CREATE TABLE applications (
              id INTEGER, job_id INTEGER, draft_url TEXT, status TEXT
            );
            """
        )
        return conn

    def test_two_regions_share_one_workday_tenant_probe(self) -> None:
        config = {
            "portals": {"adapters": [{
                "id": "workday", "platforms": ["workday"],
                "host_suffixes": ["myworkdayjobs.com"],
                "session_probe": {
                    "kind": "source_template",
                    "template": "{host}/en-US/{site}/userHome",
                    "scope": "{host}/{site}",
                },
            }]},
            "sources": [
                {"name": "NV CN", "type": "workday", "company": "NVIDIA", "host": "https://nvidia.wd5.myworkdayjobs.com", "site": "External"},
                {"name": "NV US", "type": "workday", "company": "NVIDIA", "host": "https://nvidia.wd5.myworkdayjobs.com", "site": "External"},
            ],
        }
        probes = build_probes(config, self.connection())
        self.assertEqual(len(probes), 1)
        self.assertEqual(len(probes[0].sources), 2)
        self.assertTrue(probes[0].url.endswith("/userHome"))

    def test_login_wins_over_editable_controls(self) -> None:
        state, _ = classify_session(
            adapter="workday", url="https://tenant/login", title="Sign In",
            body="Returning candidate", http_status=200,
            password_visible=True, visible_controls=4,
        )
        self.assertEqual(state, "authentication_required")

    def test_candidate_home_is_authenticated(self) -> None:
        state, _ = classify_session(
            adapter="workday", url="https://tenant/site/userHome",
            title="Candidate Home", body="My Applications", http_status=200,
            password_visible=False, visible_controls=0,
        )
        self.assertEqual(state, "authenticated")

    def test_standard_ats_application_page_is_accessible(self) -> None:
        for adapter in ("lever", "greenhouse", "ashby"):
            state, _ = classify_session(
                adapter=adapter,
                url="https://job-boards.greenhouse.io/example/jobs/123456",
                title="Job Application",
                body="First Name Last Name Email Phone Resume/CV",
                http_status=200,
                password_visible=False,
                visible_controls=8,
            )
            self.assertEqual(state, "application_accessible", adapter)

    def test_handshake_pennkey_duo_and_student_page(self) -> None:
        for url, body, expected in [
            ("https://upenn.joinhandshake.com/login", "Log-In Using Your PennKey.", "authentication_required"),
            ("https://weblogin.pennkey.upenn.edu/idp/", "PennKey", "authentication_required"),
            ("https://api-example.duosecurity.com/prompt/", "Duo", "challenge_required"),
            ("https://upenn.joinhandshake.com/job-search", "Jobs Search Saved Resume optimizer", "authenticated"),
        ]:
            state, _ = classify_session(adapter="handshake", url=url, title="",
                                        body=body, http_status=200,
                                        password_visible=False, visible_controls=2)
            self.assertEqual(state, expected)

    def test_standard_ats_probe_uses_the_application_page(self) -> None:
        config = json.loads(PORTALS_CONFIG.read_text(encoding="utf-8"))
        config["sources"] = [
            {"name": "Cirrus", "type": "lever", "company": "Cirrus Logic",
             "url": "https://jobs.eu.lever.co/cirrus/639a7c66"},
            {"name": "Astera", "type": "greenhouse", "company": "Astera Labs",
             "url": "https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005"},
            {"name": "Etched", "type": "ashby", "company": "Etched",
             "url": "https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d"},
        ]
        conn = self.connection()
        conn.executescript(
            """
            INSERT INTO jobs VALUES
              (1, 'Cirrus Logic', 'https://jobs.eu.lever.co/cirrus/639a7c66', 'lever', '639a7c66'),
              (2, 'Astera Labs',
               'https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005',
               'greenhouse', '4731399005'),
              (3, 'Etched',
               'https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d',
               'ashby', '5f1f5739');
            INSERT INTO applications VALUES
              (1, 1, NULL, 'queued'), (2, 2, NULL, 'queued'), (3, 3, NULL, 'queued');
            """
        )
        probes = {probe.adapter: probe for probe in build_probes(config, conn)}
        self.assertEqual(
            probes["lever"].url, "https://jobs.eu.lever.co/cirrus/639a7c66/apply"
        )
        self.assertEqual(
            probes["greenhouse"].url,
            "https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005",
        )
        self.assertEqual(
            probes["ashby"].url,
            "https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d/application",
        )

    def test_saved_application_page_is_probed_without_a_second_route(self) -> None:
        config = json.loads(PORTALS_CONFIG.read_text(encoding="utf-8"))
        config["sources"] = [
            {"name": "Cirrus", "type": "lever", "company": "Cirrus Logic",
             "url": "https://jobs.eu.lever.co/cirrus/639a7c66"},
        ]
        conn = self.connection()
        conn.executescript(
            """
            INSERT INTO jobs VALUES
              (1, 'Cirrus Logic', 'https://jobs.eu.lever.co/cirrus/639a7c66', 'lever', '639a7c66');
            INSERT INTO applications VALUES
              (1, 1, 'https://jobs.eu.lever.co/cirrus/639a7c66/apply', 'draft_saved');
            """
        )
        probes = build_probes(config, conn)
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0].url, "https://jobs.eu.lever.co/cirrus/639a7c66/apply")


if __name__ == "__main__":
    unittest.main()

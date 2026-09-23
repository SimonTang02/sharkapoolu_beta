import sqlite3
import unittest

from application_bot.session_audit import build_probes, classify_session


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


if __name__ == "__main__":
    unittest.main()

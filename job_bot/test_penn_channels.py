import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from job_bot.penn_channels import classify, extract_references, matching_host, run, safe_url


class PennChannelTests(unittest.TestCase):
    def test_credentials_and_sso_parameters_never_enter_report_urls(self):
        self.assertEqual(safe_url("https://example.com/path?token=secret#password"), "https://example.com/path")
        self.assertEqual(safe_url("https://weblogin.pennkey.upenn.edu/idp/session-id?SAML=secret"), "https://weblogin.pennkey.upenn.edu/")
        self.assertEqual(safe_url("https://user:secret@example.com/x"), "")
        self.assertEqual(safe_url("javascript:alert(1)"), "")
        self.assertFalse(matching_host("https://upenn.edu.evil.test/", ["upenn.edu"]))

    def test_login_and_challenge_are_not_successful_empty_results(self):
        c = {"hosts": ["myworkday.com"], "kind": "campus_job"}
        self.assertEqual(classify(c, {"url": "https://weblogin.pennkey.upenn.edu/"}), "login_required")
        self.assertEqual(classify(c, {"url": "https://api-test.duosecurity.com/"}), "verification_required")
        self.assertEqual(classify(c, {"url": "https://www.myworkday.com/", "password": True}), "login_required")

    def test_upcoming_events_are_not_enterprise_jobs(self):
        c = {"id": "engineering", "kind": "event", "link_pattern": r"/events/\d{4}/\d{2}/\d{2}/[^/]+"}
        state = {"links": [
            {"title": "Past career day", "url": "https://careerservices.upenn.edu/events/2026/09/16/fair/"},
            {"title": "Virtual engineering fair", "url": "https://careerservices.upenn.edu/events/2026/09/24/fair/?tracking=1"},
            {"title": "Virtual engineering fair", "url": "https://careerservices.upenn.edu/events/2026/09/24/fair/?tracking=2"},
        ]}
        rows = extract_references(c, state, dt.date(2026, 9, 17))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "event")

    def test_research_is_only_a_lead_and_contacts_are_not_collected(self):
        c = {"id": "curf", "kind": "research_lead", "link_pattern": r"^https://curf\.upenn\.edu/rd/"}
        state = {"links": [{"title": "Hardware research", "url": "https://curf.upenn.edu/rd/hardware"},
                           {"title": "Account", "url": "https://curf.upenn.edu/profile/student"}]}
        rows = extract_references(c, state, dt.date.today())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "research_lead")
        self.assertNotIn("paid", rows[0])
        self.assertEqual(extract_references({"id": "mypenn", "kind": "network"}, state, dt.date.today()), [])

    def test_gated_board_links_are_not_guessed_into_jobs(self):
        state = {"links": [{"title": "A possible job", "url": "https://student.interstride.com/jobs/1"}]}
        self.assertEqual(extract_references({"id": "interstride", "kind": "external_job"}, state, dt.date.today()), [])

    def test_general_workday_staff_jobs_are_not_student_jobs(self):
        channel = {"id": "workday", "kind": "campus_job"}
        state = {"job_links": [{"title": "Office manager", "url": "https://www.myworkday.com/jobs/1"}]}
        self.assertEqual(extract_references(channel, state, dt.date.today()), [])
        state["student_recruiting"] = True
        self.assertEqual(extract_references(channel, state, dt.date.today())[0]["kind"], "campus_job")

    def test_existing_login_tab_is_never_renavigated_or_duplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "penn_channels"
            out.mkdir()
            (out / "tabs.json").write_text(json.dumps({"interstride": {"target_id": "owned-tab"}}))
            browser, context, page = MagicMock(), MagicMock(), MagicMock()
            browser.contexts = [context]
            context.pages = [page]
            page.evaluate.return_value = {"url": "https://student.interstride.com/", "login": True, "links": []}
            api = MagicMock()
            api.return_value.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
            config = {"penn_channels": {"channels": [{"id": "interstride", "name": "Interstride", "kind": "external_job",
                       "entry_url": "https://student.interstride.com/", "hosts": ["interstride.com"]}]}}
            with patch("job_bot.penn_channels.JOBBOT_OUTPUT", Path(temp)), \
                 patch("job_bot.penn_channels._playwright_api", api), \
                 patch("job_bot.penn_channels.configured_cdp_connect_url", return_value="ws://local"), \
                 patch("job_bot.penn_channels.target_id", return_value="owned-tab"):
                result = run(config, open_pages=True)
            self.assertEqual(result["channels"][0]["status"], "login_required")
            page.goto.assert_not_called()
            page.close.assert_not_called()
            context.new_page.assert_not_called()


if __name__ == "__main__":
    unittest.main()

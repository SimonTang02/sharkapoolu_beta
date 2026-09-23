from __future__ import annotations

import sqlite3
import unittest

from application_bot.tab_registry import (
    ensure_browser_tab_schema,
    job_fingerprint,
    register_application_page,
    resolve_application_page,
)


class FakeSession:
    def __init__(self, target_id: str):
        self.target_id = target_id

    def send(self, method: str):
        return {"targetInfo": {"targetId": self.target_id}}

    def detach(self) -> None:
        pass


class FakePage:
    def __init__(self, context, url: str, target_id: str):
        self.context = context
        self.url = url
        self.target_id = target_id
        self.window_name = ""

    def is_closed(self) -> bool:
        return False

    def evaluate(self, script: str, value=None):
        if "window.name =" in script:
            self.window_name = value
            return None
        if script == "window.name":
            return self.window_name
        raise AssertionError(script)

    def title(self) -> str:
        return "Application"


class FakeContext:
    def __init__(self):
        self.pages = []

    def add(self, url: str, target_id: str) -> FakePage:
        page = FakePage(self, url, target_id)
        self.pages.append(page)
        return page

    def new_page(self) -> FakePage:
        return self.add("about:blank", f"target-{len(self.pages) + 1}")

    def new_cdp_session(self, page: FakePage) -> FakeSession:
        return FakeSession(page.target_id)


class TabRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE applications(id INTEGER PRIMARY KEY)")
        self.conn.executemany("INSERT INTO applications(id) VALUES (?)", [(1,), (2,)])
        ensure_browser_tab_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_workday_detail_and_apply_urls_share_job_fingerprint(self) -> None:
        detail = (
            "https://nvidia.wd5.myworkdayjobs.com/en-US/site/job/China-Shanghai/"
            "Hardware_JR2024110"
        )
        apply = (
            "https://nvidia.wd5.myworkdayjobs.com/en-US/site/job/China%2C-Shanghai/"
            "Hardware_JR2024110/apply/autofillWithResume"
        )
        self.assertEqual(job_fingerprint(detail), job_fingerprint(apply))

    def test_eightfold_detail_and_apply_urls_share_job_fingerprint(self) -> None:
        detail = "https://careers.qualcomm.com/careers/job/446717251740"
        apply = "https://careers.qualcomm.com/careers/apply?pid=446717251740"
        self.assertEqual(job_fingerprint(detail), job_fingerprint(apply))

    def test_registered_target_id_wins_over_other_matching_tabs(self) -> None:
        expected = "https://example.test/jobs/123456"
        context = FakeContext()
        registered = context.add(expected + "/apply", "target-registered")
        context.add(expected, "target-newer")
        initial = resolve_application_page(
            context,
            self.conn,
            application_id=1,
            expected_url=expected,
            browser_mode="windows_cdp",
        )
        self.assertIs(initial.page, context.pages[-1])
        chosen = type(initial)(registered, False, "manual", registered.target_id, "jobbot-application-1")
        register_application_page(
            self.conn,
            chosen,
            application_id=1,
            expected_url=expected,
            browser_mode="windows_cdp",
        )
        resumed = resolve_application_page(
            context,
            self.conn,
            application_id=1,
            expected_url=expected,
            browser_mode="windows_cdp",
        )
        self.assertIs(resumed.page, registered)
        self.assertEqual(resumed.method, "stored_target_id")

    def test_new_page_receives_application_window_label(self) -> None:
        context = FakeContext()
        resolution = resolve_application_page(
            context,
            self.conn,
            application_id=2,
            expected_url="https://example.test/jobs/999999",
            browser_mode="windows_cdp",
        )
        self.assertTrue(resolution.created)
        self.assertEqual(resolution.page.window_name, "jobbot-application-2")


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from application_bot.ats_form import (
    classify_application_body,
    contact_values,
    fill_mapped_fields,
    full_name,
    is_submit_control,
    load_context,
    local_phone,
    missing_required_contacts,
)


class FakeNode:
    def __init__(self, value="", visible=True, attributes=None, text="", files=None):
        self.value = value
        self.visible = visible
        self.attributes = attributes or {}
        self.text = text
        self.files = files

    def is_visible(self):
        return self.visible

    def fill(self, value):
        self.value = value

    def set_input_files(self, path, timeout=None):
        self.files = path

    def get_attribute(self, name):
        return self.attributes.get(name, "")

    def inner_text(self):
        return self.text


class FakeLocator:
    def __init__(self, nodes):
        self.nodes = list(nodes)

    @property
    def first(self):
        return self.nodes[0] if self.nodes else FakeNode(visible=False)

    def count(self):
        return len(self.nodes)

    def nth(self, index):
        return self.nodes[index]


class FakePage:
    """Minimal Playwright double that records fills/uploads and no clicks."""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.filled = {}
        self.uploads = []
        self.clicks = []

    def locator(self, selector):
        return FakeLocator(self.mapping.get(selector, []))

    def get_by_label(self, pattern, exact=False):
        return FakeLocator([])

    def wait_for_timeout(self, milliseconds):
        return None


class ClassifyTests(unittest.TestCase):
    def test_existing_success_receipt_is_reported_read_only(self) -> None:
        state, _ = classify_application_body(
            "Thank you for applying to Example Company", form_present=False
        )
        self.assertEqual(state, "submitted")

    def test_challenge_is_a_human_checkpoint(self) -> None:
        for body in ("Please complete the reCAPTCHA", "Enter verification code"):
            state, _ = classify_application_body(body, form_present=True)
            self.assertEqual(state, "challenge_required")

    def test_passive_captcha_disclosure_does_not_block_editable_form(self) -> None:
        state, _ = classify_application_body(
            "Application form protected by hCaptcha", form_present=True
        )
        self.assertEqual(state, "browser_form_started")

    def test_authentication_boundary(self) -> None:
        state, _ = classify_application_body("Sign in to continue", form_present=False)
        self.assertEqual(state, "authentication_required")

    def test_open_form_wins_over_login_links(self) -> None:
        state, _ = classify_application_body(
            "Sign in Create account Apply for this job", form_present=True
        )
        self.assertEqual(state, "browser_form_started")

    def test_unknown_page_is_manual(self) -> None:
        state, _ = classify_application_body("uneven page", form_present=False)
        self.assertEqual(state, "manual_required")


class SubmitGuardTests(unittest.TestCase):
    def test_submit_labels_are_recognized(self) -> None:
        for label in (
            "Submit application",
            "Submit Application",
            "Submit",
            "Apply now",
            "提交申请",
        ):
            self.assertTrue(is_submit_control(label), label)

    def test_ordinary_field_labels_are_not_submit_controls(self) -> None:
        for label in ("First Name", "Email", "Phone", "LinkedIn URL", "Resume/CV"):
            self.assertFalse(is_submit_control(label), label)


class ContactValueTests(unittest.TestCase):
    def test_full_name_skips_missing_parts(self) -> None:
        self.assertEqual(full_name({"first_name": "Ada", "last_name": "Lovelace"}), "Ada Lovelace")
        self.assertEqual(full_name({"first_name": "Ada", "last_name": ""}), "Ada")

    def test_local_phone_strips_hk_country_code(self) -> None:
        self.assertEqual(local_phone("+852 0000 0000"), "00000000")
        self.assertEqual(local_phone("00000000"), "00000000")

    def test_missing_contact_fields_stay_empty_and_unresolved(self) -> None:
        profile = {"fields": {"first_name": "Ada", "email": "ada@example.test"}}
        values = contact_values(profile)
        self.assertEqual(values["phone"], "")
        self.assertEqual(values["last_name"], "")
        self.assertEqual(missing_required_contacts(profile), ["last_name", "phone"])

    def test_complete_contacts_resolve(self) -> None:
        profile = {
            "fields": {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.test",
                "phone": "+852 0000 0000",
            }
        }
        self.assertEqual(missing_required_contacts(profile), [])


class FillMappedFieldsTests(unittest.TestCase):
    def test_only_non_empty_values_are_filled(self) -> None:
        page = FakePage(
            {
                "#first_name": [FakeNode()],
                "#email": [FakeNode()],
                "#phone": [FakeNode()],
            }
        )
        filled = fill_mapped_fields(
            page,
            (("#first_name", "first_name"), ("#email", "email"), ("#phone", "phone")),
            {"first_name": "Ada", "email": "ada@example.test", "phone": ""},
        )
        self.assertEqual(filled, ["first_name", "email"])
        self.assertEqual(page.mapping["#phone"][0].value, "")


class LoadContextTests(unittest.TestCase):
    def connection(self, profile_path: Path):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE jobs (id INTEGER, company TEXT, title TEXT, platform TEXT,
              url TEXT, location TEXT);
            CREATE TABLE applications (id INTEGER, job_id INTEGER, profile_path TEXT,
              tailored_resume_path TEXT);
            INSERT INTO jobs VALUES
              (1,'Etched','DFT Intern','ashby',
               'https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d','San Jose');
            """
        )
        conn.execute(
            "INSERT INTO applications VALUES (1,1,?,'/tmp/resume.pdf')",
            (str(profile_path),),
        )
        return conn

    def test_allow_submit_profile_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile.json"
            profile_path.write_text(
                json.dumps({"fields": {}, "safety": {"allow_submit": True}}),
                encoding="utf-8",
            )
            conn = self.connection(profile_path)
            with self.assertRaises(SystemExit):
                load_context(
                    conn, 1, platform="ashby", adapter_id="ashby", config={"portals": {}}
                )

    def test_wrong_platform_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile.json"
            profile_path.write_text(json.dumps({"fields": {}}), encoding="utf-8")
            conn = self.connection(profile_path)
            with self.assertRaises(SystemExit):
                load_context(
                    conn, 1, platform="lever", adapter_id="lever", config={"portals": {}}
                )


if __name__ == "__main__":
    unittest.main()

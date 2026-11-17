import json
import unittest

from application_bot.ats_form import is_submit_control
from application_bot.lever import (
    FIELD_MAP,
    SUBMIT_CONTROL_SELECTORS,
    apply_url,
    classify_body,
    current_company,
    fill_form,
    parse_card_definitions,
    resolve_field_values,
)
from application_bot.test_ats_form import FakeNode, FakePage

PROFILE = {
    "fields": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.test",
        "phone": "+852 0000 0000",
        "city": "Hong Kong",
        "linkedin_url": "https://example.test/in/ada",
        "github_url": "https://example.test/ada",
    },
    "work_experience": [
        {"company": "Previous Employer", "end_year": 2026},
        {"company": "Current Employer", "end_year": None},
    ],
}


def page_for_form() -> FakePage:
    cards = json.dumps(
        {
            "text": "Referral Source",
            "fields": [
                {
                    "text": "Were you referred by a current employee?",
                    "type": "multiple-choice",
                    "required": False,
                }
            ],
        }
    )
    return FakePage(
        {
            "input[name='name']": [FakeNode()],
            "input[name='email']": [FakeNode()],
            "input[name='phone']": [FakeNode()],
            "input[name='location']": [FakeNode()],
            "input[name='org']": [FakeNode()],
            "input[name='urls[LinkedIn]']": [FakeNode()],
            "input[name='urls[GitHub]']": [FakeNode()],
            "input[name='resume']": [FakeNode()],
            "[data-qa='additional-cards'] input[type=hidden]": [
                FakeNode(attributes={"value": cards})
            ],
        }
    )


class LeverUrlTests(unittest.TestCase):
    def test_apply_url_appends_once(self) -> None:
        base = "https://jobs.eu.lever.co/cirrus/639a7c66-76c4-4c22-9b9f-43af17595103"
        self.assertEqual(apply_url(base), base + "/apply")
        self.assertEqual(apply_url(base + "/apply"), base + "/apply")
        self.assertEqual(apply_url(base + "/"), base + "/apply")


class LeverFieldTests(unittest.TestCase):
    def test_current_company_uses_only_a_current_role(self) -> None:
        self.assertEqual(current_company(PROFILE), "Current Employer")
        self.assertEqual(current_company({"work_experience": [{"company": "X", "end_year": 2020}]}), "")

    def test_resolved_values_are_profile_backed(self) -> None:
        values = resolve_field_values(PROFILE)
        self.assertEqual(values["full_name"], "Ada Lovelace")
        self.assertEqual(values["email"], "ada@example.test")
        self.assertEqual(values["current_company"], "Current Employer")

    def test_missing_current_company_stays_empty(self) -> None:
        values = resolve_field_values({"fields": {"first_name": "Ada", "last_name": "L"}})
        self.assertEqual(values["current_company"], "")


class LeverCardTests(unittest.TestCase):
    def test_card_definitions_are_read_without_values(self) -> None:
        raw = json.dumps(
            {
                "text": "Office Location",
                "fields": [
                    {"text": "Which office?", "type": "checkbox", "required": True},
                    {"text": "", "type": "text"},
                ],
            }
        )
        questions = parse_card_definitions([raw, "not-json", "null"])
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["card"], "Office Location")
        self.assertEqual(questions[0]["question"], "Which office?")
        self.assertTrue(questions[0]["required"])


class LeverFillTests(unittest.TestCase):
    def test_fill_form_uploads_resume_and_never_submits(self) -> None:
        page = page_for_form()
        report = fill_form(page, _context())
        self.assertIn("resume", report["filled_fields"])
        self.assertIn("full_name", report["filled_fields"])
        self.assertIn("current_company", report["filled_fields"])
        self.assertEqual(report["unanswered_questions"], ["Were you referred by a current employee?"])
        self.assertFalse(report["submit_clicked"])
        self.assertEqual(page.mapping["input[name='email']"][0].value, "ada@example.test")


class LeverSafetyTests(unittest.TestCase):
    def test_submit_controls_are_never_fill_targets(self) -> None:
        mapped = {selector for selector, _ in FIELD_MAP}
        self.assertTrue(mapped.isdisjoint(SUBMIT_CONTROL_SELECTORS))
        self.assertTrue(is_submit_control("#btn-submit"))
        self.assertTrue(is_submit_control("button[data-qa='btn-submit']"))

    def test_captcha_disclosure_keeps_form_editable(self) -> None:
        state, _ = classify_body("protected by hCaptcha", form_present=True)
        self.assertEqual(state, "browser_form_started")


def _context():
    from pathlib import Path

    from application_bot.ats_form import ApplicationContext

    return ApplicationContext(
        row={"id": 1},
        profile=PROFILE,
        company_profile={"id": "cirrus_lever", "rules": {"resume_upload": True}},
        resume_path=Path(__file__),
    )


if __name__ == "__main__":
    unittest.main()

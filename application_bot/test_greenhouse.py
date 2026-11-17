import unittest
from pathlib import Path

from application_bot.ats_form import ApplicationContext, is_submit_control
from application_bot.greenhouse import (
    FIELD_MAP,
    MANUAL_SECTIONS,
    SUBMIT_CONTROL_SELECTORS,
    apply_url,
    classify_body,
    fill_form,
    resolve_field_values,
)
from application_bot.test_ats_form import FakeNode, FakePage

PROFILE = {
    "fields": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "preferred_name": "Ada",
        "email": "ada@example.test",
        "phone": "+852 0000 0000",
    }
}


def page_for_form() -> FakePage:
    return FakePage(
        {
            "#first_name": [FakeNode()],
            "#last_name": [FakeNode()],
            "#preferred_name": [FakeNode()],
            "#email": [FakeNode()],
            "#phone": [FakeNode()],
            "#resume": [FakeNode()],
            "[id^='question_']": [
                FakeNode(attributes={"id": "question_1", "aria-label": "Legal First Name *"}),
                FakeNode(attributes={"id": "question_2", "aria-label": "Would you require visa sponsorship? *"}),
            ],
            ", ".join(MANUAL_SECTIONS): [
                FakeNode(text="Country *"),
                FakeNode(text="School *"),
            ],
        }
    )


class GreenhouseUrlTests(unittest.TestCase):
    def test_application_form_stays_on_the_job_page(self) -> None:
        url = "https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005"
        self.assertEqual(apply_url(url), url)
        self.assertEqual(apply_url(""), "")


class GreenhouseFieldTests(unittest.TestCase):
    def test_resolved_values_are_profile_backed(self) -> None:
        values = resolve_field_values(PROFILE)
        self.assertEqual(values["first_name"], "Ada")
        self.assertEqual(values["preferred_name"], "Ada")
        self.assertEqual(values["phone"], "+852 0000 0000")


class GreenhouseFillTests(unittest.TestCase):
    def test_fill_form_uploads_resume_and_never_submits(self) -> None:
        page = page_for_form()
        report = fill_form(page, _context())
        self.assertEqual(
            report["filled_fields"],
            ["first_name", "last_name", "preferred_name", "email", "phone", "resume"],
        )
        self.assertEqual(
            report["unanswered_questions"],
            ["Legal First Name *", "Would you require visa sponsorship? *"],
        )
        self.assertEqual(report["manual_sections"], ["Country *", "School *"])
        self.assertFalse(report["submit_clicked"])


class GreenhouseSafetyTests(unittest.TestCase):
    def test_submit_controls_are_never_fill_targets(self) -> None:
        mapped = {selector for selector, _ in FIELD_MAP}
        self.assertTrue(mapped.isdisjoint(SUBMIT_CONTROL_SELECTORS))
        self.assertTrue(is_submit_control("Submit application"))

    def test_captcha_disclosure_keeps_form_editable(self) -> None:
        state, _ = classify_body("This site is protected by reCAPTCHA", form_present=True)
        self.assertEqual(state, "browser_form_started")


def _context():
    return ApplicationContext(
        row={"id": 2},
        profile=PROFILE,
        company_profile={"id": "astera_greenhouse"},
        resume_path=Path(__file__),
    )


if __name__ == "__main__":
    unittest.main()

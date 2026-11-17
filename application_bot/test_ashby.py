import re
import unittest
from pathlib import Path

from application_bot.ashby import (
    FIELD_MAP,
    QUESTION_SELECTOR,
    SUBMIT_CONTROL_SELECTORS,
    apply_url,
    classify_body,
    fill_form,
    form_present,
    resolve_field_values,
)
from application_bot.ats_form import ApplicationContext, is_submit_control
from application_bot.test_ats_form import FakeNode, FakeLocator, FakePage

PROFILE = {
    "fields": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.test",
        "phone": "+852 0000 0000",
        "city": "San Jose",
        "linkedin_url": "https://example.test/in/ada",
        "github_url": "https://example.test/ada",
    }
}


class LabelPage(FakePage):
    """Fake page that also resolves fields by accessible label."""

    def __init__(self, mapping, labels):
        super().__init__(mapping)
        self.labels = labels

    def get_by_label(self, pattern, exact=False):
        text = pattern.pattern if isinstance(pattern, re.Pattern) else str(pattern)
        return FakeLocator(self.labels.get(text, []))


def page_for_form(with_labels=False) -> FakePage:
    mapping = {
        "#_systemfield_name": [FakeNode()],
        "#_systemfield_email": [FakeNode()],
        "#_systemfield_location": [FakeNode()],
        "input[name='_systemfield_resume'], #_systemfield_resume": [FakeNode()],
        QUESTION_SELECTOR: [
            FakeNode(attributes={"id": "custom-1", "aria-label": "Why do you want to join?"}),
        ],
    }
    labels = {
        r"phone": [FakeNode()],
        r"linkedin": [FakeNode()],
        r"github": [FakeNode()],
    }
    if with_labels:
        return LabelPage(mapping, labels)
    return FakePage(mapping)


class AshbyUrlTests(unittest.TestCase):
    def test_apply_url_targets_the_application_route(self) -> None:
        base = "https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d"
        self.assertEqual(apply_url(base), base + "/application")
        self.assertEqual(apply_url(base + "/application"), base + "/application")
        self.assertEqual(apply_url(base + "/"), base + "/application")


class AshbyFieldTests(unittest.TestCase):
    def test_resolved_values_are_profile_backed(self) -> None:
        values = resolve_field_values(PROFILE)
        self.assertEqual(values["full_name"], "Ada Lovelace")
        self.assertEqual(values["city"], "San Jose")


class AshbyFillTests(unittest.TestCase):
    def test_system_attributes_fill_first(self) -> None:
        page = page_for_form()
        report = fill_form(page, _context())
        self.assertIn("full_name", report["filled_fields"])
        self.assertIn("email", report["filled_fields"])
        self.assertIn("city", report["filled_fields"])
        self.assertIn("resume", report["filled_fields"])
        self.assertEqual(report["unanswered_questions"], ["Why do you want to join?"])
        self.assertFalse(report["submit_clicked"])

    def test_label_fallback_fills_remaining_contact_fields(self) -> None:
        page = page_for_form(with_labels=True)
        report = fill_form(page, _context())
        self.assertIn("phone", report["filled_fields"])
        self.assertIn("linkedin_url", report["filled_fields"])
        self.assertIn("github_url", report["filled_fields"])

    def test_form_detection_uses_system_attribute(self) -> None:
        self.assertTrue(form_present(page_for_form()))
        self.assertFalse(form_present(FakePage()))


class AshbySafetyTests(unittest.TestCase):
    def test_submit_controls_are_never_fill_targets(self) -> None:
        mapped = {selector for selector, _ in FIELD_MAP}
        self.assertTrue(mapped.isdisjoint(SUBMIT_CONTROL_SELECTORS))
        self.assertTrue(is_submit_control("Submit Application"))

    def test_recaptcha_disclosure_keeps_form_editable(self) -> None:
        state, _ = classify_body("This form is protected by reCAPTCHA", form_present=True)
        self.assertEqual(state, "browser_form_started")


def _context():
    return ApplicationContext(
        row={"id": 3},
        profile=PROFILE,
        company_profile={"id": "etched_ashby"},
        resume_path=Path(__file__),
    )


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from pathlib import Path

from application_bot.ats_form import ApplicationContext, is_submit_control
from application_bot.test_ats_form import FakeLocator, FakeNode, FakePage
from application_bot.xiaomi import (
    ENTRY_CONTROL_SELECTORS,
    FIELD_MAP,
    LABEL_MAP,
    QUESTION_SELECTOR,
    RESUME_SELECTORS,
    SUBMIT_CONTROL_SELECTORS,
    apply_url,
    classify_body,
    fill_form,
    form_present,
    is_final_submit_label,
    resolve_field_values,
    submit_controls,
)

PROFILE = {
    "fields": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.test",
        "phone": "+852 0000 0000",
        "city": "Shenzhen",
        "linkedin_url": "https://example.test/in/ada",
        "github_url": "https://example.test/ada",
    }
}

SIGNED_OUT_BODY = (
    "职位 小米招聘 投递须知 登录 芯片设计工程师 深圳校招正式硬件研发类"
    "2027届校园招聘计划 职位描述 投递"
)


class LabelPage(FakePage):
    """Fake page that also resolves fields by accessible label."""

    def __init__(self, mapping, labels):
        super().__init__(mapping)
        self.labels = labels

    def get_by_label(self, pattern, exact=False):
        text = pattern.pattern if isinstance(pattern, re.Pattern) else str(pattern)
        return FakeLocator(self.labels.get(text, []))


def page_for_form() -> FakePage:
    return FakePage(
        {
            "input[name='realName']": [FakeNode()],
            "input[type='email']": [FakeNode()],
            "input[type='tel']": [FakeNode()],
            "input[name='currentCity']": [FakeNode()],
            "input[type='file']": [FakeNode()],
            QUESTION_SELECTOR: [
                FakeNode(attributes={"id": "q1", "aria-label": "你从哪里得知本次招聘？"}),
            ],
            "button": [FakeNode(text="投递"), FakeNode(text="提交申请")],
            "button:has-text('提交')": [FakeNode(visible=True)],
        }
    )


def page_with_labels() -> LabelPage:
    labels = {
        pattern.pattern: [FakeNode()]
        for pattern, key in LABEL_MAP
        if key in ("linkedin_url", "github_url")
    }
    return LabelPage(page_for_form().mapping, labels)


class XiaomiUrlTests(unittest.TestCase):
    def test_detail_segment_is_added_for_every_position_prefix(self) -> None:
        for prefix in ("campus", "internship", "toptalent"):
            with self.subTest(prefix=prefix):
                base = f"https://xiaomi.jobs.f.mioffice.cn/{prefix}/position/7671129001520384319"
                self.assertEqual(apply_url(base), base + "/detail")

    def test_existing_detail_segment_is_not_duplicated(self) -> None:
        url = "https://xiaomi.jobs.f.mioffice.cn/campus/position/7671129001520384319/detail"
        self.assertEqual(apply_url(url), url)
        self.assertEqual(apply_url(url + "/"), url)

    def test_query_and_fragment_are_preserved(self) -> None:
        self.assertEqual(
            apply_url(
                "https://xiaomi.jobs.f.mioffice.cn/campus/position/42?from=list#top"
            ),
            "https://xiaomi.jobs.f.mioffice.cn/campus/position/42/detail?from=list#top",
        )

    def test_empty_url_stays_empty(self) -> None:
        self.assertEqual(apply_url(""), "")
        self.assertEqual(apply_url("   "), "")


class XiaomiFormDetectionTests(unittest.TestCase):
    def test_application_form_candidate_is_detected(self) -> None:
        self.assertTrue(form_present(page_for_form()))

    def test_empty_page_has_no_form(self) -> None:
        self.assertFalse(form_present(FakePage()))

    def test_login_page_is_not_an_application_form(self) -> None:
        page = FakePage(
            {
                "input[name='password']": [FakeNode()],
                "input[type='password']": [FakeNode()],
            }
        )
        self.assertFalse(form_present(page))


class XiaomiFieldTests(unittest.TestCase):
    def test_resolved_values_are_profile_backed(self) -> None:
        values = resolve_field_values(PROFILE)
        self.assertEqual(values["full_name"], "Ada Lovelace")
        self.assertEqual(values["email"], "ada@example.test")
        self.assertEqual(values["city"], "Shenzhen")

    def test_missing_values_stay_empty(self) -> None:
        values = resolve_field_values({"fields": {"first_name": "Ada"}})
        self.assertEqual(values["email"], "")
        self.assertEqual(values["github_url"], "")
        self.assertEqual(values["full_name"], "Ada")


class XiaomiFillTests(unittest.TestCase):
    def test_candidate_selectors_fill_and_resume_uploads(self) -> None:
        page = page_for_form()
        report = fill_form(page, _context())
        self.assertIn("full_name", report["filled_fields"])
        self.assertIn("email", report["filled_fields"])
        self.assertIn("phone", report["filled_fields"])
        self.assertIn("city", report["filled_fields"])
        self.assertIn("resume", report["filled_fields"])
        self.assertEqual(page.mapping["input[name='realName']"][0].value, "Ada Lovelace")
        self.assertEqual(page.mapping["input[type='email']"][0].value, "ada@example.test")
        self.assertEqual(page.mapping["input[type='file']"][0].files, str(Path(__file__)))
        self.assertEqual(report["unanswered_questions"], ["你从哪里得知本次招聘？"])
        self.assertFalse(report["submit_clicked"])
        self.assertEqual(page.clicks, [])

    def test_label_fallback_fills_remaining_profile_fields(self) -> None:
        report = fill_form(page_with_labels(), _context())
        self.assertIn("linkedin_url", report["filled_fields"])
        self.assertIn("github_url", report["filled_fields"])

    def test_label_fallback_skips_missing_profile_values(self) -> None:
        page = page_with_labels()
        report = fill_form(page, _context_with_profile({"fields": {"first_name": "Ada"}}))
        self.assertNotIn("linkedin_url", report["filled_fields"])
        self.assertNotIn("github_url", report["filled_fields"])


class XiaomiSubmitGuardTests(unittest.TestCase):
    def test_final_submit_labels_are_recognized(self) -> None:
        for label in ("提交", "提交申请", "确认投递", "Submit application"):
            self.assertTrue(is_final_submit_label(label), label)
        # The shared pattern needs an 申请/简历 suffix, so the adapter adds the
        # bare-Chinese-label case locally while still delegating the rest.
        for label in ("提交申请", "确认申请", "Submit application"):
            self.assertTrue(is_submit_control(label), label)

    def test_entry_control_label_is_not_a_final_submit(self) -> None:
        self.assertFalse(is_final_submit_label("投递"))
        self.assertFalse(is_submit_control("投递"))

    def test_submit_and_entry_selectors_are_never_field_targets(self) -> None:
        selectors = {selector for selector, _ in FIELD_MAP}
        keys = {key for _, key in FIELD_MAP}
        self.assertEqual(
            keys,
            {"full_name", "email", "phone", "city", "linkedin_url", "github_url"},
        )
        for selector in ENTRY_CONTROL_SELECTORS + SUBMIT_CONTROL_SELECTORS:
            self.assertNotIn(selector, selectors)
        self.assertTrue(set(ENTRY_CONTROL_SELECTORS).isdisjoint(SUBMIT_CONTROL_SELECTORS))

    def test_submit_controls_are_inventoried_but_never_clicked(self) -> None:
        page = page_for_form()
        found = submit_controls(page)
        self.assertIn("button:has-text('提交')", found)
        self.assertIn("提交申请", found)
        self.assertNotIn("投递", found)
        report = fill_form(page, _context())
        self.assertEqual(report["submit_controls"], found)
        self.assertFalse(report["submit_clicked"])
        self.assertEqual(page.clicks, [])

    def test_entry_only_page_reports_no_submit_control(self) -> None:
        page = FakePage(
            {
                "button.atsx-btn.apply-block-applyBtn": [FakeNode(text="投递")],
                "button": [FakeNode(text="投递")],
            }
        )
        self.assertEqual(submit_controls(page), [])


class XiaomiClassificationTests(unittest.TestCase):
    def test_signed_out_detail_page_requires_authentication(self) -> None:
        state, _ = classify_body(SIGNED_OUT_BODY, form_present=False)
        self.assertEqual(state, "authentication_required")

    def test_open_form_wins_over_the_login_link(self) -> None:
        state, _ = classify_body(SIGNED_OUT_BODY, form_present=True)
        self.assertEqual(state, "browser_form_started")

    def test_challenge_is_a_human_checkpoint(self) -> None:
        state, _ = classify_body("请完成验证码后继续", form_present=True)
        self.assertEqual(state, "challenge_required")

    def test_existing_receipt_is_reported_read_only(self) -> None:
        state, _ = classify_body("感谢您的申请", form_present=False)
        self.assertEqual(state, "submitted")

    def test_page_without_form_or_login_is_manual(self) -> None:
        state, _ = classify_body("芯片设计工程师 职位描述 职位要求", form_present=False)
        self.assertEqual(state, "manual_required")


def _context():
    return ApplicationContext(
        row={"id": 1},
        profile=PROFILE,
        company_profile={"id": "xiaomi_campus"},
        resume_path=Path(__file__),
    )


def _context_with_profile(profile):
    return ApplicationContext(
        row={"id": 1},
        profile=profile,
        company_profile={"id": "xiaomi_campus"},
        resume_path=Path(__file__),
    )


if __name__ == "__main__":
    unittest.main()

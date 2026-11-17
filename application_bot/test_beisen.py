import unittest
from pathlib import Path

from application_bot.ats_form import ApplicationContext, is_submit_control
from application_bot.beisen import (
    CLICK_STRATEGIES,
    DELIVER_BUTTON_SELECTOR,
    FIELD_MAP,
    QUESTION_SELECTOR,
    SUBMIT_CONTROL_SELECTORS,
    apply_url,
    choose_click_strategy,
    classify_body,
    click_deliver_button,
    fill_form,
    form_present,
    is_final_submit_label,
    job_id_from_url,
    resolve_field_values,
)
from application_bot.test_ats_form import FakeNode, FakePage

PROFILE = {
    "fields": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.test",
        "phone": "+852 0000 0000",
        "city": "Beijing",
        "linkedin_url": "https://example.test/in/ada",
    }
}


def page_for_form(body_text="") -> FakePage:
    mapping = {
        "input[name='name'], input[placeholder*='姓名']": [FakeNode()],
        "input[name='email'], input[type='email']": [FakeNode()],
        "input[name='phone'], input[placeholder*='手机'], input[placeholder*='电话']": [FakeNode()],
        "input[type='file']": [FakeNode()],
        QUESTION_SELECTOR: [
            FakeNode(attributes={"id": "custom-1", "aria-label": "请选择意向城市"}),
        ],
    }
    if body_text:
        mapping["body"] = [FakeNode(text=body_text)]
    return FakePage(mapping)


class BeisenUrlTests(unittest.TestCase):
    def test_zhiye_detail_derives_form_url(self) -> None:
        detail = "https://mthreads.zhiye.com/campus/detail?jobId=311175514"
        self.assertEqual(
            apply_url(detail),
            "https://mthreads.zhiye.com/form?fromPage=job&jobAdId=311175514",
        )

    def test_existing_form_url_is_preserved(self) -> None:
        form = "https://mthreads.zhiye.com/form?fromPage=job&jobAdId=311175514"
        self.assertEqual(apply_url(form), form)

    def test_url_without_job_id_is_returned_unchanged(self) -> None:
        url = "https://mthreads.zhiye.com/campus/jobs"
        self.assertEqual(apply_url(url), url)

    def test_job_id_extraction_supports_beisen_variants(self) -> None:
        self.assertEqual(
            job_id_from_url("https://x.zhiye.com/campus/detail?jobId=42"), "42"
        )
        self.assertEqual(
            job_id_from_url("https://x.zhiye.com/form?jobAdId=99"), "99"
        )
        self.assertEqual(
            job_id_from_url("https://wecruit.hotjob.cn/x/pb/social.html?postId=abc"), "abc"
        )


class BeisenFieldTests(unittest.TestCase):
    def test_resolved_values_are_profile_backed(self) -> None:
        values = resolve_field_values(PROFILE)
        self.assertEqual(values["full_name"], "Ada Lovelace")
        self.assertEqual(values["email"], "ada@example.test")
        self.assertEqual(values["city"], "Beijing")


class BeisenFormDetectionTests(unittest.TestCase):
    def test_file_input_marks_form_present(self) -> None:
        self.assertTrue(form_present(page_for_form()))

    def test_body_marker_marks_form_present_without_file_input(self) -> None:
        page = FakePage({"body": [FakeNode(text="你正在投递职位: 芯片设计工程师")]})
        self.assertTrue(form_present(page))

    def test_empty_page_has_no_form(self) -> None:
        self.assertFalse(form_present(FakePage()))


class BeisenFillTests(unittest.TestCase):
    def test_fill_form_uploads_resume_and_never_submits(self) -> None:
        page = page_for_form()
        report = fill_form(page, _context())
        self.assertIn("full_name", report["filled_fields"])
        self.assertIn("email", report["filled_fields"])
        self.assertIn("resume", report["filled_fields"])
        self.assertEqual(report["unanswered_questions"], ["请选择意向城市"])
        self.assertFalse(report["submit_clicked"])
        self.assertEqual(
            page.mapping["input[name='email'], input[type='email']"][0].value,
            "ada@example.test",
        )


class BeisenClickStrategyTests(unittest.TestCase):
    def test_click_strategy_order_prefers_js_dispatch_over_trusted_cdp(self) -> None:
        strategies = choose_click_strategy()
        self.assertEqual(strategies, list(CLICK_STRATEGIES))
        self.assertNotIn("trusted_cdp", strategies)
        self.assertEqual(strategies[0], "untrusted_dispatch")

    def test_click_deliver_button_reports_no_submit_clicked(self) -> None:
        page = FakePage()
        report = click_deliver_button(page)
        self.assertFalse(report["clicked"])
        self.assertFalse(report["submit_clicked"])
        self.assertTrue(report["strategies"])


class BeisenSafetyTests(unittest.TestCase):
    def test_submit_controls_are_never_fill_targets(self) -> None:
        mapped = {selector for selector, _ in FIELD_MAP}
        self.assertTrue(mapped.isdisjoint(SUBMIT_CONTROL_SELECTORS))
        self.assertTrue(is_submit_control("提交申请"))
        self.assertTrue(is_final_submit_label("确认投递"))
        self.assertTrue(is_final_submit_label("提交"))

    def test_deliver_button_is_not_a_submit_control(self) -> None:
        self.assertFalse(is_submit_control("立即投递"))
        self.assertFalse(is_submit_control(DELIVER_BUTTON_SELECTOR))

    def test_captcha_disclosure_keeps_form_editable(self) -> None:
        state, _ = classify_body("请完成验证码", form_present=True)
        self.assertEqual(state, "challenge_required")
        state, _ = classify_body("申请表单", form_present=True)
        self.assertEqual(state, "browser_form_started")


def _context():
    return ApplicationContext(
        row={"id": 7},
        profile=PROFILE,
        company_profile={"id": "mthreads_beisen"},
        resume_path=Path(__file__),
    )


if __name__ == "__main__":
    unittest.main()

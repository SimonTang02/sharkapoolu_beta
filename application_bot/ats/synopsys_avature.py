"""Bounded, caller-owned page preparation for one verified Synopsys flow.

This module owns no browser, navigation, credentials, database or CLI runner.
An authorized caller supplies an already-open page and a private profile.
No button is clicked, including Continue: account creation and intermediate
POSTs are not safe substitutes for a review checkpoint. Public Register has
password fields and is therefore refused. Compliance/Review was not learned
from an authenticated template and remains a manual boundary.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from application_bot.ats_form import (
    contact_values,
    fill_selector,
    inventory_questions,
    upload_resume,
)


JOB_ID = "18478"
JOB_HEADING = "Serdes IP Design Engineer---18478"
HOST = "synopsys.avature.net"
STEP_LABELS = ("Select your resume", "Personal info", "Compliance")
HEADING_SELECTOR = ".banner__text__title"
STEP_SELECTOR = ".list--steps > .list__item"
FORM_SELECTOR = "form.tpt_wizard"
RESUME_FORM_SELECTOR = "#manualRegisterMethodsForm"
RESUME_SELECTOR = f'{RESUME_FORM_SELECTOR} input[type="file"]'
AUTH_SELECTOR = 'input[type="password"], form.form--login, input[name="username"]'
CHALLENGE_SELECTOR = (
    '[id*="captcha" i], [class*="captcha" i], '
    'iframe[src*="captcha" i], input[autocomplete="one-time-code"], '
    'input[name="verificationCode"], input[name="securityCode"]'
)

# Numeric Avature IDs are matched as attributes, not invalid CSS such as #162.
# Each input must also retain its observed label and input type.
FIELD_SPECS = (
    ("162", "first_name", "First name", "text"),
    ("163", "last_name", "Last name", "text"),
    ("164", "email", "Email", "email"),
    ("165", "phone", "Mobile phone number", "tel"),
    ("9149", "github_url", "Github Profile Link", "text"),
    ("251", "address_line_1", "Address", "text"),
    ("168", "city", "City", "text"),
    ("5305", "postal_code", "Postal Code", "text"),
)
KNOWN_QUESTIONS = frozenset(
    (
        "Current Employer", "Current Position Title", "Country",
        "State/Province/Region", "How did you discover this opportunity?",
        "Are you legally authorized to work in the country you are applying to?",
        "Have you previously worked for Synopsys or Ansys?",
        "Company", "Position title", "Start date", "End date", "Degree name",
        "University", "Language", "Written Level", "Spoken Level", "Skills",
    )
)
QUESTION_SELECTOR = (
    f'{FORM_SELECTOR} input:not([type="hidden"]):not([type="password"]), '
    f"{FORM_SELECTOR} select, {FORM_SELECTOR} textarea"
)


def _normalise(text: str) -> str:
    return " ".join(text.split()).strip().rstrip(" *")


def _report(status: str, reason: str, stage: str | None = None) -> dict[str, Any]:
    # Values, DOM text, URLs with query data, document paths and exceptions are
    # intentionally excluded. All emitted strings are controlled metadata.
    return {
        "adapter": "synopsys_avature", "employer_req_id": JOB_ID,
        "status": status, "reason": reason, "stage": stage,
        "filled_fields": [], "preserved_fields": [], "pending_fields": [],
        "pending_questions": [], "unknown_question_count": 0,
        "resume_uploaded": False, "review_ready": False,
        "submit_clicked": False, "continue_clicked": False,
        "account_created": False,
    }


def _route(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        if (
            parts.scheme != "https" or parts.hostname != HOST
            or parts.port not in (None, 443) or parts.username or parts.password
            or parts.fragment
        ):
            return None
        if parse_qs(parts.query, keep_blank_values=True).get("jobId") != [JOB_ID]:
            return None
        route = parts.path.removeprefix("/careers/")
        return route if route in ("Login", "ApplicationMethods", "Register") else None
    except (TypeError, ValueError):
        return None


def _form_is_local(page: Any, selector: str) -> bool:
    forms = page.locator(selector)
    if forms.count() != 1:
        return False
    action = forms.first.get_attribute("action")
    # The public forms post back to their current route with no action attr.
    # Do not infer the meaning of a newly introduced explicit action.
    return not action and (forms.first.get_attribute("method") or "").lower() == "post"


def inspect_page(page: Any) -> dict[str, Any]:
    """Read only req/heading/stage structure; never read a contact value."""
    try:
        route = _route(page.url)
        if route is None:
            return _report("manual_required", "unverified_route")
        headings = page.locator(HEADING_SELECTOR)
        if (
            headings.count() != 1
            or _normalise(headings.first.inner_text(timeout=2_000)) != JOB_HEADING
        ):
            return _report("manual_required", "job_heading_mismatch")
        hidden = page.locator('input[type="hidden"][name="jobId"]')
        if hidden.count() > 1 or (
            hidden.count() == 1 and hidden.first.get_attribute("value") != JOB_ID
        ):
            return _report("manual_required", "job_id_mismatch")
        multi = page.locator('input[type="hidden"][name="jobIds"]')
        if multi.count() > 1 or (
            multi.count() == 1 and multi.first.get_attribute("value") not in (None, "", JOB_ID)
        ):
            return _report("manual_required", "multiple_job_target_unverified")
        if route == "Login" or page.locator(AUTH_SELECTOR).count():
            return _report("authentication_required", "auth_or_password_boundary")
        if page.locator(CHALLENGE_SELECTOR).count():
            return _report("manual_required", "captcha_or_verification_boundary")
        steps = page.locator(STEP_SELECTOR)
        if steps.count() != 3:
            return _report("manual_required", "unverified_step_structure")
        current: list[int] = []
        for index, label in enumerate(STEP_LABELS):
            node = steps.nth(index)
            text = " ".join(node.inner_text(timeout=2_000).split())
            if not text.startswith(label) or not re.search(
                rf"\b{index + 1}\s*/\s*3\b", text
            ):
                return _report("manual_required", "unverified_step_structure")
            if "list__item--current" in (node.get_attribute("class") or "").split():
                current.append(index)
        if len(current) != 1:
            return _report("manual_required", "ambiguous_current_step")
        stage = ("resume", "personal", "questions")[current[0]]
        if stage == "questions":
            return _report("manual_required", "compliance_review_template_unverified", stage)
        if route != ("ApplicationMethods" if stage == "resume" else "Register"):
            return _report("manual_required", "route_step_mismatch", stage)
        selector = RESUME_FORM_SELECTOR if stage == "resume" else FORM_SELECTOR
        if not _form_is_local(page, selector):
            return _report("manual_required", "unverified_form_target", stage)
        if stage == "personal" and hidden.count() != 1:
            return _report("manual_required", "missing_form_job_id", stage)
        return _report("preparation_available", "identified_editable_step", stage)
    except Exception:
        return _report("manual_required", "page_inspection_failed")


def _questions(page: Any, report: dict[str, Any]) -> None:
    labels = {_normalise(x) for x in inventory_questions(page, QUESTION_SELECTOR)}
    contact_labels = {_normalise(spec[2]) for spec in FIELD_SPECS}
    report["pending_questions"] = sorted(labels & KNOWN_QUESTIONS)
    # Unknown labels can contain user data; emit a count, not arbitrary text.
    report["unknown_question_count"] = len(labels - KNOWN_QUESTIONS - contact_labels)


def _personal_targets(page: Any) -> list[tuple[str, str, bool]] | None:
    targets: list[tuple[str, str, bool]] = []
    for index, (identifier, key, label, input_type) in enumerate(FIELD_SPECS):
        selector = f'{FORM_SELECTOR} input[name="{identifier}"]'
        nodes = page.locator(selector)
        if nodes.count() == 0 and index >= 4:
            continue
        labels = page.locator(f'{FORM_SELECTOR} label[for="{identifier}"]')
        if nodes.count() != 1 or labels.count() != 1:
            return None
        node = nodes.first
        if (
            node.get_attribute("id") != identifier
            or node.get_attribute("type") != input_type
            or _normalise(labels.first.inner_text(timeout=2_000)) != label
            or not node.is_visible() or not node.is_editable()
        ):
            return None
        empty = node.evaluate("el => typeof el.value === 'string' && el.value.trim().length === 0")
        if not isinstance(empty, bool):
            return None
        targets.append((selector, key, empty))
    return targets


def prepare_page(
    page: Any,
    profile: dict[str, Any],
    *,
    resume_path: Path | None = None,
    resume_reviewed: bool = False,
    allow_submit: bool = False,
) -> dict[str, Any]:
    """Prepare only the current verified step; caller advances manually.

    A reviewed resume can only be uploaded to one explicitly labelled file
    input inside the learned resume form. No unlabeled fallback is attempted.
    All declaration/consent/country/education/custom answers remain manual.
    """
    if (
        allow_submit is not False or not isinstance(profile, dict)
        or not isinstance(profile.get("safety"), dict)
        or profile["safety"].get("allow_submit") is not False
    ):
        return _report("manual_required", "explicit_no_submit_policy_required")
    fields = profile.get("fields", {})
    if not isinstance(fields, dict) or any(
        fields.get(key) is not None and not isinstance(fields.get(key), str)
        for _, key, _, _ in FIELD_SPECS
    ):
        return _report("manual_required", "invalid_profile_fields")
    report = inspect_page(page)
    if report["status"] != "preparation_available":
        return report
    try:
        if report["stage"] == "resume":
            inputs = page.locator(RESUME_SELECTOR)
            if inputs.count() != 1:
                return _report("manual_required", "resume_input_template_unverified", "resume")
            labels = inventory_questions(page, RESUME_SELECTOR)
            if len(labels) != 1 or _normalise(labels[0]) not in (
                "Resume", "Resume/CV", "CV", "Select your resume", "Upload CV file"
            ):
                return _report("manual_required", "resume_label_template_unverified", "resume")
            selected = inputs.first.evaluate("el => Boolean(el.files && el.files.length)")
            if selected is not False:
                return _report("manual_required", "existing_resume_selection_preserved", "resume")
            if (
                resume_reviewed is not True or not isinstance(resume_path, Path)
                or resume_path.suffix.lower() != ".pdf" or not resume_path.is_file()
            ):
                return _report("manual_required", "reviewed_pdf_required", "resume")
            current = inspect_page(page)
            if current["status"] != "preparation_available" or current["stage"] != "resume":
                return _report("manual_required", "page_changed_before_upload", "resume")
            report["resume_uploaded"] = upload_resume(page, resume_path, RESUME_SELECTOR)
            if not report["resume_uploaded"]:
                return _report("manual_required", "resume_upload_failed", "resume")
        else:
            targets = _personal_targets(page)
            if targets is None:
                return _report("manual_required", "personal_fields_template_unverified", "personal")
            _questions(page, report)
            values = contact_values(profile)
            for selector, key, empty in targets:
                if not empty:
                    report["preserved_fields"].append(key)
                    continue
                if not values.get(key):
                    report["pending_fields"].append(key)
                    continue
                current = inspect_page(page)
                if current["status"] != "preparation_available" or current["stage"] != "personal":
                    report.update(status="manual_required", reason="page_changed_during_preparation")
                    return report
                fresh = _personal_targets(page)
                if fresh is None or (selector, key, True) not in fresh:
                    report.update(status="manual_required", reason="fields_changed_during_preparation")
                    return report
                if fill_selector(page, selector, values[key]):
                    report["filled_fields"].append(key)
                else:
                    report["pending_fields"].append(key)
        current = inspect_page(page)
        if current["status"] != "preparation_available" or current["stage"] != report["stage"]:
            report.update(status="manual_required", reason="page_changed_after_preparation")
        else:
            report.update(status="manual_required", reason="current_step_prepared_advance_manually")
        return report
    except Exception:
        report.update(status="manual_required", reason="preparation_action_failed")
        return report

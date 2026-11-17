#!/usr/bin/env python3
"""Fill known Xiaomi application fields and stop before the final Submit.

Xiaomi's招聘 portal renders the job detail at
``xiaomi.jobs.f.mioffice.cn/{campus,internship,toptalent}/position/<id>/detail``.
The detail page exposes one stable entry control,
``button.atsx-btn.apply-block-applyBtn`` ("投递"), which opens the application
flow. The application form itself has not been observed yet because the
portal was inspected while signed out, so every form selector below is a
candidate with an accessible-label fallback rather than a confirmed fact.

The adapter only fills fields backed by the maintained private profile and
uploads the reviewed resume, then stops. It never clicks the entry control or
any final submission control, and it classifies a signed-out page as
``authentication_required`` instead of guessing field names.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application_bot.ats_form import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_ENV,
    ApplicationContext,
    classify_application_body,
    contact_values,
    fill_label,
    fill_selector,
    inventory_questions,
    is_submit_control,
    run_adapter,
    upload_resume,
)


# Job-detail prefixes observed on the Xiaomi portal. The adapter keeps the
# prefix it was given and only supplies the missing /detail segment.
POSITION_PREFIXES = (
    "/campus/position/",
    "/internship/position/",
    "/toptalent/position/",
)

# The entry control on the job-detail page. It opens the application flow; it is
# not a final submission control and the adapter never clicks it. It is named
# here so tests can assert it is neither a field target nor a submit control.
ENTRY_CONTROL_SELECTORS = (
    "button.atsx-btn.apply-block-applyBtn",
    "button.apply-block-applyBtn",
)

# Final submission candidates. The adapter never clicks these; it only reports
# how many were found so the human reviewer sees the refusal explicitly. None of
# these has been verified in a live authenticated session.
SUBMIT_CONTROL_SELECTORS = (
    "button.atsx-btn.apply-block-submitBtn",
    "button[class*='submitBtn']",
    "button:has-text('提交')",
    "button:has-text('确认投递')",
    "button:has-text('Submit application')",
)

# Xiaomi is a Chinese portal, so a bare "提交" can label the final control
# without the 申请/简历 suffix the shared ATS pattern requires.
SUBMIT_LABEL_PATTERN = re.compile(r"提交|确认投递|確認投遞", re.I)

# Candidate selectors for the editable application form. They are deliberately
# specific to the application flow so a signed-out page or a login form is not
# mistaken for an open application. The two empty-src host bridge frames
# (#__ToutiaoJSBridgeIframe__ and #__ToutiaoJSBridgeIframe_SetResult__) are not
# the application form and are intentionally ignored.
FORM_SELECTORS = (
    "form.atsx-form",
    "form[class*='atsx-form']",
    ".atsx-form",
    "form[class*='apply']",
    "input[name='realName']",
    "input[name='real_name']",
    "input[name='name']",
    "input[placeholder='请输入姓名']",
)

# Candidate field selectors, grouped by logical profile value. The first
# matching candidate wins; anything still empty falls back to LABEL_MAP.
FIELD_MAP = (
    ("input[name='realName']", "full_name"),
    ("input[name='real_name']", "full_name"),
    ("input[name='name']", "full_name"),
    ("input[name='userName']", "full_name"),
    ("input[name='email']", "email"),
    ("input[type='email']", "email"),
    ("input[name='phone']", "phone"),
    ("input[name='mobile']", "phone"),
    ("input[type='tel']", "phone"),
    ("input[name='city']", "city"),
    ("input[name='currentCity']", "city"),
    ("input[name='location']", "city"),
    ("input[name='linkedin']", "linkedin_url"),
    ("input[name='linkedinUrl']", "linkedin_url"),
    ("input[name='github']", "github_url"),
    ("input[name='githubUrl']", "github_url"),
)

# Accessible-label fallbacks for fields without a confirmed attribute. The
# patterns cover the Chinese labels the portal is expected to use plus the
# English equivalents.
LABEL_MAP = (
    (re.compile(r"姓名|真实姓名|full\s*name|^name$", re.I), "full_name"),
    (re.compile(r"邮箱|电子邮箱|e-?mail", re.I), "email"),
    (re.compile(r"手机|电话|phone|mobile|tel", re.I), "phone"),
    (re.compile(r"城市|所在城市|现居|location|city", re.I), "city"),
    (re.compile(r"linkedin", re.I), "linkedin_url"),
    (re.compile(r"github", re.I), "github_url"),
)

# Resume upload candidates, most specific first. The generic filter is the last
# resort for a form whose upload input has no descriptive attribute.
RESUME_SELECTORS = (
    "input[type='file'][name*='resume']",
    "input[type='file'][name*='Resume']",
    "input[type='file'][accept*='pdf']",
    "input[type='file']",
)

# Question inventory: editable text controls other than the resume upload and
# non-text controls. Nodes without an accessible label are skipped, so the
# already-filled contact fields normally do not appear here.
QUESTION_SELECTOR = (
    "input:not([type='file']):not([type='hidden']):not([type='submit'])"
    ":not([type='checkbox']):not([type='radio']), textarea"
)


def apply_url(url: str) -> str:
    """Return the canonical job-detail URL for any Xiaomi position URL.

    The campus, internship, and top-talent prefixes are preserved; a missing
    ``/detail`` segment is appended once and an existing one is left untouched.
    """
    base = str(url or "").strip()
    if not base:
        return ""
    split = urlsplit(base)
    path = split.path.rstrip("/")
    if not path.endswith("/detail"):
        path = f"{path}/detail"
    return urlunsplit((split.scheme, split.netloc, path, split.query, split.fragment))


def resolve_field_values(profile: dict[str, Any]) -> dict[str, str]:
    """Return only the profile-backed identity values the adapter may fill."""
    return contact_values(profile)


def classify_body(body: str, form_present: bool = False) -> tuple[str, str]:
    return classify_application_body(body, form_present=form_present)


def form_present(page: Any) -> bool:
    for selector in FORM_SELECTORS:
        try:
            if page.locator(selector).count():
                return True
        except Exception:
            continue
    return False


def is_final_submit_label(label: str) -> bool:
    """True when an accessible name identifies a final submission control."""
    text = " ".join(str(label or "").split())
    return is_submit_control(text) or bool(SUBMIT_LABEL_PATTERN.search(text))


def submit_controls(page: Any) -> list[str]:
    """Inventory the final-submit candidates present, without clicking them."""
    found: list[str] = []
    for selector in SUBMIT_CONTROL_SELECTORS:
        try:
            present = bool(page.locator(selector).count())
        except Exception:
            present = False
        if present and selector not in found:
            found.append(selector)
    try:
        buttons = page.locator("button")
        for index in range(buttons.count()):
            try:
                label = " ".join(str(buttons.nth(index).inner_text() or "").split())
            except Exception:
                continue
            if label and is_final_submit_label(label) and label not in found:
                found.append(label)
    except Exception:
        pass
    return found


def _fill_first(page: Any, selectors: tuple[str, ...], value: str) -> bool:
    for selector in selectors:
        if fill_selector(page, selector, value):
            return True
    return False


def _upload_first(page: Any, path: Path, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        if upload_resume(page, path, selector):
            return True
    return False


def fill_form(page: Any, context: ApplicationContext) -> dict[str, Any]:
    values = resolve_field_values(context.profile)
    filled: list[str] = []

    # Candidate selectors first, grouped so a logical field is filled once.
    grouped: dict[str, tuple[str, ...]] = {}
    for selector, key in FIELD_MAP:
        grouped[key] = grouped.get(key, ()) + (selector,)
    for key, selectors in grouped.items():
        if _fill_first(page, selectors, values.get(key, "")):
            filled.append(key)

    # Accessible-label fallbacks for anything still empty.
    for pattern, key in LABEL_MAP:
        if key in filled or not values.get(key):
            continue
        if fill_label(page, pattern, values[key]):
            filled.append(key)

    resume_uploaded = _upload_first(page, context.resume_path, RESUME_SELECTORS)
    if resume_uploaded:
        filled.append("resume")

    questions = inventory_questions(page, QUESTION_SELECTOR)
    submits = submit_controls(page)
    note = (
        "Xiaomi application prepared without submit. Profile-backed identity fields "
        f"({', '.join(filled) or 'none'}) were filled; "
        + ("the tailored resume was uploaded. " if resume_uploaded else "the resume was NOT uploaded. ")
        + f"{len(questions)} additional form question(s) remain for human review; "
        "no legal, visa or demographic answer was selected. "
        + f"{len(submits)} potential final-submit control(s) were identified and refused."
    )
    return {
        "filled_fields": filled,
        "unanswered_questions": questions,
        "submit_controls": submits,
        "submit_clicked": False,
        "note": note,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application-id", type=int, required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    args = parser.parse_args()
    run_adapter(
        platform="xiaomi",
        adapter="xiaomi",
        config_path=Path(args.config),
        env_path=Path(args.env),
        application_id=args.application_id,
        apply_url=apply_url,
        form_present=form_present,
        fill_form=fill_form,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fill known Ashby application fields and stop before the final Submit.

Ashby renders a client-side application form at
``jobs.ashbyhq.com/<board>/<job-uuid>/application``. The form is submitted by a
single ``Submit Application`` control and the page loads reCAPTCHA, so this
adapter stops at the editable form and never clicks that button.

Ashby's form is SPA-rendered, so the adapter resolves fields by their stable
``_systemfield_*`` attributes first and falls back to accessible-label lookup.
Only profile-backed identity fields are filled and the reviewed resume is
uploaded; custom and legal questions are inventoried for the human reviewer.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
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
    run_adapter,
    upload_resume,
)


# The adapter never clicks these controls; they are named so the refusal is
# explicit and asserted by tests.
SUBMIT_CONTROL_SELECTORS = (
    ".ashby-application-form-submit-button",
    "button:has-text('Submit Application')",
)

# Ashby's documented system-field attributes.
FIELD_MAP = (
    ("#_systemfield_name", "full_name"),
    ("input[name='_systemfield_name']", "full_name"),
    ("#_systemfield_email", "email"),
    ("input[name='_systemfield_email']", "email"),
    ("#_systemfield_location", "city"),
    ("input[name='_systemfield_location']", "city"),
)

# Accessible-label fallbacks for fields without a stable system attribute.
LABEL_MAP = (
    (re.compile(r"^name$", re.I), "full_name"),
    (re.compile(r"full\s*name", re.I), "full_name"),
    (re.compile(r"e-?mail", re.I), "email"),
    (re.compile(r"phone", re.I), "phone"),
    (re.compile(r"location", re.I), "city"),
    (re.compile(r"linkedin", re.I), "linkedin_url"),
    (re.compile(r"github", re.I), "github_url"),
)

FORM_SELECTORS = (
    "#_systemfield_name",
    "input[name='_systemfield_name']",
)

QUESTION_SELECTOR = (
    "input:not([id^='_systemfield']):not([type='file']):not([type='hidden'])"
    ":not([type='checkbox']):not([type='radio']):not([type='submit']), "
    "textarea:not([id^='_systemfield'])"
)


def apply_url(url: str) -> str:
    base = str(url or "").strip().rstrip("/")
    if base.endswith("/application"):
        return base
    return f"{base}/application"


def resolve_field_values(profile: dict[str, Any]) -> dict[str, str]:
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


def _fill_first(page: Any, selectors: tuple[str, ...], value: str) -> bool:
    for selector in selectors:
        if fill_selector(page, selector, value):
            return True
    return False


def fill_form(page: Any, context: ApplicationContext) -> dict[str, Any]:
    values = resolve_field_values(context.profile)
    filled: list[str] = []

    # Stable system attributes first.
    grouped: dict[str, tuple[str, ...]] = {}
    for selector, key in FIELD_MAP:
        grouped.setdefault(key, ())
        grouped[key] = grouped[key] + (selector,)
    for key, selectors in grouped.items():
        if _fill_first(page, selectors, values.get(key, "")):
            filled.append(key)

    # Accessible-label fallbacks for anything still empty.
    for pattern, key in LABEL_MAP:
        if key in filled or not values.get(key):
            continue
        if fill_label(page, pattern, values[key]):
            filled.append(key)

    resume_uploaded = upload_resume(
        page, context.resume_path,
        "input[name='_systemfield_resume'], #_systemfield_resume",
    )
    if resume_uploaded:
        filled.append("resume")

    questions = inventory_questions(page, QUESTION_SELECTOR)
    note = (
        "Ashby application prepared without submit. Profile-backed identity fields "
        f"({', '.join(filled) or 'none'}) were filled; "
        + ("the tailored resume was uploaded. " if resume_uploaded else "the resume was NOT uploaded. ")
        + f"{len(questions)} additional form question(s) remain for human review; no legal, "
        "visa or demographic answer was selected. Ashby also loads reCAPTCHA before submit."
    )
    return {
        "filled_fields": filled,
        "unanswered_questions": questions,
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
        platform="ashby",
        adapter="ashby",
        config_path=Path(args.config),
        env_path=Path(args.env),
        application_id=args.application_id,
        apply_url=apply_url,
        form_present=form_present,
        fill_form=fill_form,
    )


if __name__ == "__main__":
    main()

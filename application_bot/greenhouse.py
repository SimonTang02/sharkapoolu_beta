#!/usr/bin/env python3
"""Fill known Greenhouse application fields and stop before the final Submit.

Greenhouse hosts a server-rendered application form on the job page itself
(``job-boards.greenhouse.io/<board>/jobs/<id>``). The form is submitted by the
single ``Submit application`` button and is protected by reCAPTCHA, so this
adapter stops at the editable form and never clicks that button.

Only profile-backed identity fields are filled and the reviewed resume is
uploaded. Education react-select fields, country, and the board's custom
questions (including legal/visa prompts) are inventoried for the human reviewer
and never answered automatically.
"""

from __future__ import annotations

import argparse
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
    fill_mapped_fields,
    inventory_headings,
    inventory_questions,
    run_adapter,
    upload_resume,
)


# The adapter never clicks a submit control. The selector is retained so the
# refusal is explicit and asserted by tests.
SUBMIT_CONTROL_SELECTORS = ("form#application-form button[type='submit']",)

FIELD_MAP = (
    ("#first_name", "first_name"),
    ("#last_name", "last_name"),
    ("#preferred_name", "preferred_name"),
    ("#email", "email"),
    ("#phone", "phone"),
)

FORM_SELECTORS = (
    "form#application-form",
    "#first_name",
    "#resume",
)

# Greenhouse renders these required comboboxes/labels but they are not backed
# by a single confirmed profile value, so the human reviewer resolves them.
MANUAL_SECTIONS = (
    "label[for='country']",
    "label[for^='school--']",
    "label[for^='degree--']",
    "label[for^='discipline--']",
    "label[for^='start-year--']",
    "label[for^='end-year--']",
)


def apply_url(url: str) -> str:
    """Greenhouse's application form lives on the job page itself."""
    return str(url or "").strip()


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


def fill_form(page: Any, context: ApplicationContext) -> dict[str, Any]:
    values = resolve_field_values(context.profile)
    filled = fill_mapped_fields(page, FIELD_MAP, values)
    resume_uploaded = upload_resume(page, context.resume_path, "#resume")
    if resume_uploaded:
        filled.append("resume")

    questions = inventory_questions(page, "[id^='question_']")
    manual_sections = inventory_headings(page, ", ".join(MANUAL_SECTIONS))
    note = (
        "Greenhouse application prepared without submit. Profile-backed identity fields "
        f"({', '.join(filled) or 'none'}) were filled; "
        + ("the tailored resume was uploaded. " if resume_uploaded else "the resume was NOT uploaded. ")
        + f"{len(questions)} custom question(s) and {len(manual_sections)} required "
        "education/country control(s) remain for human review; no legal, visa or "
        "demographic answer was selected."
    )
    return {
        "filled_fields": filled,
        "unanswered_questions": questions,
        "manual_sections": manual_sections,
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
        platform="greenhouse",
        adapter="greenhouse",
        config_path=Path(args.config),
        env_path=Path(args.env),
        application_id=args.application_id,
        apply_url=apply_url,
        form_present=form_present,
        fill_form=fill_form,
    )


if __name__ == "__main__":
    main()

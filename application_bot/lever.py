#!/usr/bin/env python3
"""Fill known Lever application fields and stop before the final Submit.

Lever hosts a single-page application at ``<job hostedUrl>/apply``. The form is
submitted in one action that is protected by hCaptcha, so this adapter stops at
the editable form and never clicks ``#btn-submit`` or ``#hcaptchaSubmitBtn``.

Only profile-backed identity fields are filled and the reviewed resume is
uploaded. Lever's custom ``cards[...]`` questions (referral source, office
location, visa/export-control and data-processing acknowledgements) are legal
or candidate facts; they are inventoried for the human reviewer and never
answered automatically.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


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
    run_adapter,
    upload_resume,
)


# The adapter never clicks these controls. They are named here so the refusal
# is explicit and asserted by tests.
SUBMIT_CONTROL_SELECTORS = ("#btn-submit", "#hcaptchaSubmitBtn", "button[data-qa='btn-submit']")

# Selectors are the stable Lever field names observed on jobs.lever.co and
# jobs.eu.lever.co application pages.
FIELD_MAP = (
    ("input[name='name']", "full_name"),
    ("input[name='email']", "email"),
    ("input[name='phone']", "phone"),
    ("input[name='location']", "city"),
    ("input[name='org']", "current_company"),
    ("input[name='urls[LinkedIn]']", "linkedin_url"),
    ("input[name='urls[GitHub]']", "github_url"),
)

FORM_SELECTORS = (
    "form.application-form",
    "input[name='name']",
    "input[name='email']",
    "#resume-upload-input",
)

# Required Lever fields with no profile-backed answer must be reported rather
# than guessed. Lever always requires a current company for the applicant.
UNRESOLVED_REQUIRED = ("current_company",)


def apply_url(url: str) -> str:
    base = str(url or "").strip().rstrip("/")
    return base if base.endswith("/apply") else f"{base}/apply"


def current_company(profile: dict[str, Any]) -> str:
    """Return the employer of a currently-held role, if the profile states one."""
    for record in profile.get("work_experience") or []:
        if not isinstance(record, dict):
            continue
        if not record.get("end_year") and str(record.get("company") or "").strip():
            return str(record["company"]).strip()
    return ""


def resolve_field_values(profile: dict[str, Any]) -> dict[str, str]:
    values = contact_values(profile)
    values["current_company"] = current_company(profile)
    return values


def classify_body(body: str, form_present: bool = False) -> tuple[str, str]:
    return classify_application_body(body, form_present=form_present)


def parse_card_definitions(raw_values: Iterable[str]) -> list[dict[str, Any]]:
    """Parse Lever's embedded hidden card-definition JSON (read-only).

    Lever stores each additional card's schema in a hidden input whose value is
    a JSON object. Reading it produces a precise question inventory without
    touching any candidate answer.
    """
    questions: list[dict[str, Any]] = []
    for raw in raw_values:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        card = str(data.get("text") or "").strip()
        for entry in data.get("fields") or []:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            if not text:
                continue
            questions.append(
                {
                    "card": card,
                    "question": text,
                    "type": str(entry.get("type") or "").strip(),
                    "required": bool(entry.get("required")),
                }
            )
    return questions


def card_questions(page: Any) -> list[dict[str, Any]]:
    nodes = page.locator("[data-qa='additional-cards'] input[type=hidden]")
    raw_values: list[str] = []
    for index in range(nodes.count()):
        try:
            raw_values.append(nodes.nth(index).get_attribute("value") or "")
        except Exception:
            continue
    return parse_card_definitions(raw_values)


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
    resume_uploaded = upload_resume(page, context.resume_path, "input[name='resume']")
    if resume_uploaded:
        filled.append("resume")

    questions = card_questions(page)
    unresolved = [key for key in UNRESOLVED_REQUIRED if not values.get(key)]
    question_texts = [item["question"] for item in questions]
    note = (
        "Lever application prepared without submit. Profile-backed contact fields "
        f"({', '.join(filled) or 'none'}) were filled; "
        + ("the tailored resume was uploaded. " if resume_uploaded else "the resume was NOT uploaded. ")
        + f"{len(question_texts)} custom card question(s) and the EEO section remain for human review; "
        "no legal, visa, export-control or demographic answer was selected."
    )
    if unresolved:
        note += f" Unresolved required fields: {', '.join(unresolved)}."
    return {
        "filled_fields": filled,
        "unanswered_questions": question_texts,
        "unresolved_required_fields": unresolved,
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
        platform="lever",
        adapter="lever",
        config_path=Path(args.config),
        env_path=Path(args.env),
        application_id=args.application_id,
        apply_url=apply_url,
        form_present=form_present,
        fill_form=fill_form,
    )


if __name__ == "__main__":
    main()

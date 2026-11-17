#!/usr/bin/env python3
"""Shared no-submit mechanics for standard ATS application adapters.

Lever, Greenhouse, and Ashby all expose a public, single-page application form
that is submitted in one action. The safety boundary is identical for all
three: open the application, upload the reviewed resume, fill only fields that
are backed by the private profile, inventory the remaining questions, and stop
before the final Submit control.

Per-ATS adapters own their selectors, URL rules, and classifiers. This module
owns the parts that must not diverge: the tab/session handling, the artifact and
status bookkeeping, the submit-control refusal, and the shared field helpers.
No function here clicks a final submission control.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application_bot.artifacts import save_fill_test_artifact  # noqa: E402
from application_bot.portal_registry import resolve_company_profile  # noqa: E402
from application_bot.tab_registry import (  # noqa: E402
    page_matches_application,
    register_application_page,
    resolve_application_page,
)
from job_bot.application_bot import add_event, resolve_browser_connection  # noqa: E402
from job_bot.applications.nvidia_workday import _playwright_api  # noqa: E402
from job_bot.bot import connect_db, load_config, load_env_file, utc_now  # noqa: E402
from private_paths import APPLICATION_OUTPUT, CREDENTIALS_FILE  # noqa: E402


DEFAULT_CONFIG = ROOT / "job_bot/config.china_hk_ic_foreign.json"
DEFAULT_ENV = CREDENTIALS_FILE

# These adapters never submit an application. The pattern is used to recognize
# a final submission control so it can be refused/inventoried; it is never used
# to click one.
SUBMIT_CONTROL_PATTERN = re.compile(
    r"(?:^|\b)(?:submit(?:\s+(?:application|my\s+application))?|"
    r"apply(?:\s+(?:now|for\s+this\s+job))?|send\s+application)(?:\b|$)|"
    r"提交(?:申请|申請|履歷|简历)|确认申请|確認申請",
    re.I,
)

SUBMITTED_MARKERS = (
    "thank you for applying",
    "thanks for applying",
    "application received",
    "we have received your application",
    "your application has been submitted",
    "感谢您的申请",
    "感謝您的申請",
)

CHALLENGE_MARKERS = (
    "captcha",
    "hcaptcha",
    "recaptcha",
    "verification code",
    "security code",
    "验证码",
    "驗證碼",
)

# CAPTCHA vendors often put their name in every editable form's footer or
# JavaScript disclosure. Only an instruction to solve a challenge should stop
# field preparation while the form itself is visible.
ACTIVE_CHALLENGE_PATTERN = re.compile(
    r"(?:complete|solve|verify|enter|check|finish|请完成|請完成|请输入|請輸入)"
    r".{0,55}(?:captcha|verification code|security code|验证码|驗證碼)|"
    r"(?:captcha|验证码|驗證碼).{0,40}(?:required|failed|expired|必填|失效)",
    re.I,
)

AUTH_MARKERS = (
    "sign in",
    "signed out",
    "log in",
    "login",
    "returning user",
    "create an account",
    "create account",
    "password",
    "登入",
    "登录",
    "密碼",
    "密码",
)

CONSENT_MARKERS = (
    "privacy policy",
    "terms and conditions",
    "i agree to",
    "consent to",
    "隱私政策",
    "隐私政策",
)

REQUIRED_CONTACT_FIELDS = ("first_name", "last_name", "email", "phone")


def is_submit_control(label: str) -> bool:
    """True when an accessible name identifies a final submission control."""
    return bool(SUBMIT_CONTROL_PATTERN.search(" ".join(str(label or "").split())))


def full_name(fields: dict[str, Any]) -> str:
    parts = [
        str(fields.get("first_name") or "").strip(),
        str(fields.get("last_name") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def local_phone(phone: str) -> str:
    """Return the national number when a +852 country code is already selected."""
    compact = "".join(character for character in str(phone or "") if character.isdigit())
    return compact[3:] if compact.startswith("852") else compact


def contact_values(profile: dict[str, Any]) -> dict[str, str]:
    """Profile-backed identity values shared by every standard ATS form.

    Only fields that the maintained application profile explicitly provides are
    returned. Missing values stay empty so the human reviewer resolves them.
    """
    fields = profile.get("fields", {}) or {}
    values = {
        key: str(fields.get(key) or "").strip()
        for key in (
            "first_name",
            "last_name",
            "preferred_name",
            "email",
            "phone",
            "linkedin_url",
            "github_url",
            "city",
            "country",
            "postal_code",
            "address_line_1",
        )
    }
    values["full_name"] = full_name(fields)
    return values


def missing_required_contacts(profile: dict[str, Any]) -> list[str]:
    values = contact_values(profile)
    return [key for key in REQUIRED_CONTACT_FIELDS if not values.get(key)]


def body_text(page: Any, timeout_ms: int = 8_000) -> str:
    return " ".join(page.locator("body").inner_text(timeout=timeout_ms).lower().split())


def classify_application_body(body: str, *, form_present: bool) -> tuple[str, str]:
    """Classify an ATS page from its rendered text and form detection.

    Read-only: a recognized success receipt is reported, never created.
    """
    text = " ".join(str(body or "").casefold().split())
    if any(marker in text for marker in SUBMITTED_MARKERS):
        return "submitted", "An existing application success receipt was detected; nothing was submitted."
    if ACTIVE_CHALLENGE_PATTERN.search(text):
        return "challenge_required", "A CAPTCHA or account-verification challenge is visible; this is a human checkpoint."
    if form_present:
        return "browser_form_started", "An editable application form is open; the final Submit control was not clicked."
    if any(marker in text for marker in CHALLENGE_MARKERS):
        return "challenge_required", "A CAPTCHA or account-verification challenge is visible; this is a human checkpoint."
    if any(marker in text for marker in AUTH_MARKERS):
        return "authentication_required", "The ATS is at a sign-in or account-creation boundary."
    if any(marker in text for marker in CONSENT_MARKERS):
        return "policy_consent_required", "The ATS reached a policy/consent step; no consent was accepted."
    return "manual_required", "No editable application form or authentication boundary was detected."


def fill_selector(page: Any, selector: str, value: str) -> bool:
    if not value:
        return False
    locator = page.locator(selector)
    if not locator.count():
        return False
    target = locator.first
    try:
        if not target.is_visible():
            return False
    except Exception:
        return False
    target.fill(value)
    return True


def fill_label(
    page: Any,
    pattern: str | re.Pattern[str],
    value: str,
    *,
    exact: bool = False,
) -> bool:
    if not value:
        return False
    try:
        locator = page.get_by_label(pattern, exact=exact)
        if not locator.count():
            return False
        target = locator.first
        if not target.is_visible():
            return False
        target.fill(value)
        return True
    except Exception:
        return False


def fill_mapped_fields(
    page: Any,
    field_map: Sequence[tuple[str, str]],
    values: dict[str, str],
) -> list[str]:
    """Fill CSS-selector fields from logical values; return the keys filled."""
    filled: list[str] = []
    for selector, key in field_map:
        if fill_selector(page, selector, values.get(key, "")):
            filled.append(key)
    return filled


def upload_resume(page: Any, path: Path, selector: str = "input[type=file]") -> bool:
    if not path or not Path(path).is_file():
        return False
    inputs = page.locator(selector)
    if not inputs.count():
        return False
    inputs.first.set_input_files(str(path), timeout=10_000)
    return True


def inventory_questions(page: Any, selector: str) -> list[str]:
    """Return unique, trimmed accessible labels without reading field values."""
    labels: list[str] = []
    nodes = page.locator(selector)
    for index in range(nodes.count()):
        node = nodes.nth(index)
        label = ""
        try:
            label = node.get_attribute("aria-label") or ""
        except Exception:
            label = ""
        if not label:
            try:
                identifier = node.get_attribute("id")
                if identifier:
                    associated = page.locator(f'label[for="{identifier}"]')
                    if associated.count():
                        label = associated.first.inner_text()
            except Exception:
                continue
        label = " ".join(str(label).split())
        if label and label not in labels:
            labels.append(label)
    return labels


def inventory_headings(page: Any, selector: str, *, limit: int = 200) -> list[str]:
    """Return unique, trimmed heading texts for question inventory only."""
    texts: list[str] = []
    nodes = page.locator(selector)
    for index in range(nodes.count()):
        try:
            text = " ".join(str(nodes.nth(index).inner_text() or "").split())
        except Exception:
            continue
        if text and text not in texts:
            texts.append(text[:limit])
    return texts


@dataclass(frozen=True)
class ApplicationContext:
    row: Any
    profile: dict[str, Any]
    company_profile: dict[str, Any]
    resume_path: Path


def load_context(
    conn: Any,
    application_id: int,
    *,
    platform: str,
    adapter_id: str,
    config: dict[str, Any],
) -> ApplicationContext:
    row = conn.execute(
        """
        SELECT applications.id, applications.profile_path,
               applications.tailored_resume_path, jobs.url, jobs.platform,
               jobs.company, jobs.title, jobs.location
        FROM applications JOIN jobs ON jobs.id=applications.job_id
        WHERE applications.id=?
        """,
        (application_id,),
    ).fetchone()
    if not row or str(row["platform"] or "").casefold() != platform.casefold():
        raise SystemExit(f"Application is not a {platform} campaign role")
    profile_path = row["profile_path"]
    if not profile_path or not Path(str(profile_path)).is_file():
        raise SystemExit("The isolated application profile is missing")
    profile = json.loads(Path(str(profile_path)).read_text(encoding="utf-8"))
    if profile.get("safety", {}).get("allow_submit"):
        raise SystemExit("Safety violation: allow_submit must remain false")
    company_profile = resolve_company_profile(
        config, company=str(row["company"] or ""), adapter_id=adapter_id
    )
    return ApplicationContext(
        row=row,
        profile=profile,
        company_profile=company_profile,
        resume_path=Path(str(row["tailored_resume_path"] or "")),
    )


def update_application(
    conn: Any,
    application_id: int,
    *,
    status: str,
    note: str,
    draft_url: str,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        UPDATE applications SET status=?, notes=?, last_error=NULL,
            draft_url=?, updated_at=? WHERE id=?
        """,
        (status, note, draft_url, utc_now(), application_id),
    )
    conn.execute(
        """
        UPDATE application_campaign_jobs SET status=?, last_error=?
        WHERE application_id=?
        """,
        (status, note, application_id),
    )
    add_event(conn, application_id, event_type, details or {})
    conn.commit()


def run_adapter(
    *,
    platform: str,
    adapter: str,
    config_path: Path,
    env_path: Path,
    application_id: int,
    apply_url: Callable[[str], str],
    form_present: Callable[[Any], bool],
    fill_form: Callable[[Any, ApplicationContext], dict[str, Any]],
) -> None:
    """Open one ATS application, fill profile-backed fields, and stop.

    ``fill_form`` must return a JSON-serializable report. It must never click a
    final submission control; the shared runner only navigates to the
    canonical application URL and uploads/fills fields.
    """
    config = load_config(Path(config_path))
    conn = connect_db(config)
    try:
        context = load_context(
            conn, application_id, platform=platform, adapter_id=adapter, config=config
        )
        load_env_file(Path(env_path))
        _, cdp_url = resolve_browser_connection(config)
        target_url = apply_url(str(context.row["url"] or ""))
        if not target_url:
            raise SystemExit(f"Application {application_id} has no job URL")

        sync_playwright = _playwright_api()
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=30_000)
            browser_context = browser.contexts[0]
            resolution = resolve_application_page(
                browser_context,
                conn,
                application_id=int(context.row["id"]),
                expected_url=target_url,
                browser_mode="windows_cdp",
            )
            page = resolution.page
            if resolution.created or not page_matches_application(page.url, target_url):
                page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
            register_application_page(
                conn,
                resolution,
                application_id=int(context.row["id"]),
                expected_url=target_url,
                browser_mode="windows_cdp",
            )
            try:
                page.wait_for_timeout(1_500)
            except Exception:
                pass

            present = False
            for _ in range(15):
                present = bool(form_present(page))
                if present:
                    break
                try:
                    page.wait_for_timeout(1_000)
                except Exception:
                    break
            status, note = classify_application_body(body_text(page), form_present=present)
            report: dict[str, Any] = {}
            if status == "browser_form_started":
                report = dict(fill_form(page, context) or {})
                try:
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                present = bool(form_present(page))
                status, note = classify_application_body(
                    body_text(page), form_present=present
                )
                if report.get("note"):
                    note = str(report["note"])

            stage = "confirmation" if status == "submitted" else "editable_form"
            artifact = save_fill_test_artifact(
                page,
                APPLICATION_OUTPUT / "applications" / str(context.row["id"]),
                adapter=adapter,
                stage=stage,
                status=status,
                metadata={
                    "tab_resolution": resolution.method,
                    "company_profile": context.company_profile.get("id"),
                    "submit_clicked": False,
                    **report,
                },
            )
            register_application_page(
                conn,
                resolution,
                application_id=int(context.row["id"]),
                expected_url=target_url,
                browser_mode="windows_cdp",
            )
            update_application(
                conn,
                int(context.row["id"]),
                status=status,
                note=note,
                draft_url=page.url,
                event_type=f"{adapter}_progress",
                details={"status": status, "url": page.url, **report},
            )
            filled = report.get("filled_fields") or []
            print(
                f"{adapter} application {context.row['id']}: {status}; "
                f"filled={len(filled)}; screenshot={artifact['screenshot_path']}"
            )
    finally:
        conn.close()

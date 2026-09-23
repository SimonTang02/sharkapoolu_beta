#!/usr/bin/env python3
"""Advance Eightfold application entries to their authentication boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application_bot.artifacts import save_fill_test_artifact  # noqa: E402
from application_bot.tab_registry import (  # noqa: E402
    page_matches_application,
    register_application_page,
    resolve_application_page,
)
from job_bot.application_bot import add_event, resolve_browser_connection  # noqa: E402
from job_bot.applications.nvidia_workday import _playwright_api  # noqa: E402
from job_bot.bot import connect_db, load_config, load_env_file, utc_now  # noqa: E402
from private_paths import CREDENTIALS_FILE  # noqa: E402


DEFAULT_CONFIG = ROOT / "job_bot/config.china_hk_ic_foreign.json"
DEFAULT_ENV = CREDENTIALS_FILE


def _body_text(page) -> str:
    return " ".join(page.locator("body").inner_text(timeout=8_000).lower().split())


def _fill_if_present(page, selector: str, value: str) -> bool:
    field = page.locator(selector)
    if not field.count() or not value:
        return False
    field.first.fill(value)
    return True


def _local_phone(phone: str) -> str:
    """Return a local HK number when Eightfold already selected +852."""
    compact = "".join(character for character in phone if character.isdigit())
    return compact[3:] if compact.startswith("852") else compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-id", type=int, required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    args = parser.parse_args()
    config = load_config(Path(args.config))
    conn = connect_db(config)
    row = conn.execute(
        """
        SELECT applications.id, applications.profile_path,
               applications.tailored_resume_path, jobs.url, jobs.platform
        FROM applications JOIN jobs ON jobs.id=applications.job_id
        WHERE applications.id=?
        """,
        (args.application_id,),
    ).fetchone()
    if not row or row["platform"] != "eightfold":
        raise SystemExit("Application is not an Eightfold campaign role")
    profile = json.loads(Path(row["profile_path"]).read_text(encoding="utf-8"))
    if profile.get("safety", {}).get("allow_submit"):
        raise SystemExit("Safety violation: allow_submit must remain false")
    email = str(profile.get("fields", {}).get("email", "")).strip()
    if not email:
        raise SystemExit("The isolated profile has no email")

    load_env_file(Path(args.env))
    _, cdp_url = resolve_browser_connection(config)
    sync_playwright = _playwright_api()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=30_000)
        context = browser.contexts[0]
        resolution = resolve_application_page(
            context,
            conn,
            application_id=row["id"],
            expected_url=row["url"],
            browser_mode="windows_cdp",
        )
        page = resolution.page
        if resolution.created or not page_matches_application(page.url, row["url"]):
            page.goto(row["url"], wait_until="domcontentloaded", timeout=45_000)
        register_application_page(
            conn,
            resolution,
            application_id=row["id"],
            expected_url=row["url"],
            browser_mode="windows_cdp",
        )
        parts = urlsplit(row["url"])
        if "/careers/job/" in parts.path and "/careers/apply" not in urlsplit(page.url).path:
            pid = parts.path.rstrip("/").split("/")[-1]
            page.goto(
                f"{parts.scheme}://{parts.netloc}/careers/apply?pid={pid}",
                wait_until="domcontentloaded",
                timeout=45_000,
            )
        page.wait_for_timeout(1_500)
        body = _body_text(page)

        # Current Eightfold tenants may begin with resume bootstrapping instead
        # of email authentication. Uploading here only creates a candidate
        # profile draft; it is not the job application's final Submit action.
        files = page.locator("input[type=file]")
        if (
            files.count()
            and Path(row["tailored_resume_path"]).is_file()
            and any(term in body for term in ("profile bootstrapping", "上传您的简历", "upload your resume"))
            and not page.locator("[data-test-id='firstname']").count()
        ):
            files.first.set_input_files(row["tailored_resume_path"], timeout=10_000)
            page.wait_for_timeout(8_000)
            body = _body_text(page)

        first_name = str(profile.get("fields", {}).get("first_name", "")).strip()
        last_name = str(profile.get("fields", {}).get("last_name", "")).strip()
        phone = str(profile.get("fields", {}).get("phone", "")).strip()
        profile_form = page.locator("[data-test-id='firstname']")
        if profile_form.count():
            _fill_if_present(page, "[data-test-id='firstname']", first_name)
            _fill_if_present(page, "[data-test-id='lastname']", last_name)
            phone_fields = page.locator(
                "input[placeholder='电话号码'], input[placeholder*='Phone']"
            )
            if phone_fields.count() and phone:
                phone_fields.first.fill(_local_phone(phone))
            # This tightly guarded Submit creates/updates the Eightfold
            # candidate profile only. Never click a Submit after this screen.
            profile_submit = page.get_by_role("button", name="提交", exact=True)
            if not profile_submit.count():
                profile_submit = page.get_by_role("button", name="Submit", exact=True)
            if (
                profile_submit.count()
                and "profile bootstrapping" in body
                and any(term in body for term in ("创建您的个人资料", "create your profile"))
            ):
                profile_submit.first.click(timeout=5_000)
                page.wait_for_timeout(6_000)
                body = _body_text(page)

        email_field = page.locator("input[name='email']")
        if email_field.count():
            email_field.fill(email)
            continues = page.get_by_role("button", name="继续", exact=True)
            if not continues.count():
                continues = page.get_by_role("button", name="Continue", exact=True)
            if continues.count():
                continues.first.click(timeout=5_000)
                page.wait_for_timeout(3_000)
            body = _body_text(page)
            files = page.locator("input[type=file]")
            if files.count() and Path(row["tailored_resume_path"]).is_file():
                files.first.set_input_files(row["tailored_resume_path"], timeout=10_000)
                page.wait_for_timeout(2_000)
                body = _body_text(page)

        if any(term in body for term in ("创建新帐户", "创建帐户", "create account")):
            status = "account_creation_required"
            note = "Eightfold candidate profile is prepared; account creation/verification remains."
        elif any(
            term in body
            for term in (
                "password",
                "verification code",
                "check your email",
                "输入以下代码",
                "查看电子邮件",
                "验证码",
                "密码",
            )
        ):
            status = "authentication_required"
            note = "Eightfold candidate profile is prepared; password or verification remains."
        elif any(term in body for term in ("privacy", "consent", "terms")):
            status = "policy_consent_required"
            note = "Eightfold reached an unapproved policy/consent step; no consent was accepted."
        elif profile_form.count():
            status = "profile_bootstrap_required"
            note = "Eightfold resume was parsed and corrected, but candidate profile creation did not advance."
        elif any(term in body for term in ("job application", "申请职位", "apply for")):
            status = "browser_form_started"
            note = "Eightfold candidate profile is ready and the job application form is open; final submit was not clicked."
        else:
            status = "manual_required"
            note = "Eightfold state changed but no safe editable job form or authentication boundary was detected."

        artifact = save_fill_test_artifact(
            page,
            ROOT / "job_bot" / "out" / "applications" / str(row["id"]),
            adapter="eightfold",
            stage="application_entry",
            status=status,
            metadata={"tab_resolution": resolution.method},
        )
        register_application_page(
            conn,
            resolution,
            application_id=row["id"],
            expected_url=row["url"],
            browser_mode="windows_cdp",
        )
        conn.execute(
            "UPDATE applications SET status=?, notes=?, draft_url=?, updated_at=? WHERE id=?",
            (status, note, page.url, utc_now(), row["id"]),
        )
        conn.execute(
            "UPDATE application_campaign_jobs SET status=?, last_error=? WHERE application_id=?",
            (status, note, row["id"]),
        )
        add_event(conn, row["id"], "eightfold_progress", {"status": status, "url": page.url})
        conn.commit()
        print(
            f"Eightfold application {row['id']}: {status}; "
            f"screenshot={artifact['screenshot_path']}"
        )


if __name__ == "__main__":
    main()

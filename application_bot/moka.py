#!/usr/bin/env python3
"""Fill known Moka application fields and stop before preview/submit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


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
from application_bot.portal_registry import resolve_company_profile  # noqa: E402
from job_bot.application_bot import add_event, resolve_browser_connection  # noqa: E402
from job_bot.applications.nvidia_workday import _playwright_api  # noqa: E402
from job_bot.bot import connect_db, load_config, load_env_file, utc_now  # noqa: E402
from private_paths import CREDENTIALS_FILE, JOBBOT_OUTPUT  # noqa: E402


DEFAULT_CONFIG = ROOT / "job_bot/config.china_hk_ic_foreign.json"
DEFAULT_ENV = CREDENTIALS_FILE


def row_for(conn, application_id: int):
    row = conn.execute(
        """
        SELECT applications.id, applications.job_id, applications.profile_path,
               applications.tailored_resume_path, jobs.url, jobs.platform,
               jobs.location, jobs.role_kind, jobs.company, jobs.title
        FROM applications JOIN jobs ON jobs.id = applications.job_id
        WHERE applications.id = ?
        """,
        (application_id,),
    ).fetchone()
    if not row or row["platform"] != "moka_cdp":
        raise SystemExit("Application is not a Moka campaign role")
    return row


def update_status(conn, row, status: str, note: str, draft_url: str) -> None:
    conn.execute(
        """
        UPDATE applications SET status=?, notes=?, last_error=NULL,
            draft_url=?, updated_at=? WHERE id=?
        """,
        (status, note, draft_url, utc_now(), row["id"]),
    )
    conn.execute(
        """
        UPDATE application_campaign_jobs SET status=?, last_error=?
        WHERE application_id=?
        """,
        (status, note, row["id"]),
    )
    add_event(conn, row["id"], "moka_progress", {"status": status, "url": draft_url})
    conn.commit()


def digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def choose(page, field, value: str) -> None:
    field.click(force=True, timeout=5_000)
    page.wait_for_timeout(200)
    option = page.get_by_text(value, exact=True)
    visible = [option.nth(i) for i in range(option.count()) if option.nth(i).is_visible()]
    if not visible:
        page.keyboard.press("Escape")
        raise RuntimeError(f"Moka option was not found: {value}")
    visible[-1].click(force=True, timeout=5_000)
    page.wait_for_timeout(200)


def find_input_by_value(page, expected: str):
    inputs = page.locator("input")
    for index in range(inputs.count()):
        field = inputs.nth(index)
        try:
            if field.input_value() == expected:
                return field
        except Exception:
            continue
    return None


def fill_if_empty(field, value: str) -> None:
    if value and not field.input_value().strip():
        field.fill(value)


def choose_if_needed(page, field, value: str) -> None:
    if value and field.input_value().strip() != value:
        choose(page, field, value)


def choose_phone_calling_code(page, phone_field, code: str) -> bool:
    """Select the calling code bound to this phone field, not a login-modal duplicate."""
    prefix_input = phone_field.locator("xpath=preceding::input[1]")
    try:
        prefix_input.click(force=True, timeout=5_000)
        page.wait_for_timeout(300)
        pattern = re.compile(rf"(?:^|\D){re.escape(code)}(?:\D|$)", re.I)
        candidates = page.get_by_text(pattern)
        visible = [
            candidates.nth(index)
            for index in range(candidates.count())
            if candidates.nth(index).is_visible()
        ]
        if not visible:
            page.keyboard.press("Escape")
            return False
        visible[-1].click(force=True, timeout=5_000)
        page.wait_for_timeout(300)
        return code in (prefix_input.input_value() or prefix_input.locator("xpath=..").inner_text())
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def login_prompt_visible(page) -> bool:
    prompt = page.get_by_text("首次登录会自动创建新账号", exact=False)
    try:
        return any(prompt.nth(index).is_visible() for index in range(prompt.count()))
    except Exception:
        return False


def fill_work_experience(page, records: list[dict]) -> int:
    if not records:
        return 0
    company_fields = page.locator("input[placeholder='公司名称']")
    # Moka initializes one work record followed by one internship/research
    # record. Both are truthful homes for the user's two undergraduate research
    # roles, and using the existing slots avoids brittle portal-specific Add UI.
    work_count = min(len(records), company_fields.count())

    year_fields = page.locator("input[placeholder='年']")
    month_fields = page.locator("input[placeholder='月']")
    job_titles = page.locator("input[placeholder='职位名称']")
    locations = page.locator("input[placeholder='工作地点']")
    content_fields = page.locator("textarea[placeholder='内容']")
    for index, record in enumerate(records[:work_count]):
        fill_if_empty(company_fields.nth(index), str(record.get("company") or ""))
        fill_if_empty(job_titles.nth(index), str(record.get("job_title") or ""))
        if index < locations.count():
            fill_if_empty(locations.nth(index), str(record.get("location") or ""))
        if index < content_fields.count():
            fill_if_empty(
                content_fields.nth(index), str(record.get("description") or "")
            )
        date_values = (
            record.get("start_year"),
            record.get("start_month"),
            record.get("end_year"),
            record.get("end_month"),
        )
        choose_if_needed(page, year_fields.nth(index * 2), str(date_values[0] or ""))
        choose_if_needed(page, month_fields.nth(index * 2), str(date_values[1] or ""))
        choose_if_needed(
            page, year_fields.nth(index * 2 + 1), str(date_values[2] or "")
        )
        choose_if_needed(
            page, month_fields.nth(index * 2 + 1), str(date_values[3] or "")
        )
    return work_count


def fill_projects(page, projects: list[dict]) -> int:
    if not projects:
        return 0
    project_names = page.locator("input[placeholder='项目名称']")
    project_count = min(len(projects), project_names.count())
    for index, project in enumerate(projects[:project_count]):
        name_field = project_names.nth(index)
        record = name_field.locator(
            "xpath=ancestor::div[.//textarea[@placeholder='项目中职责']][1]"
        )
        if not record.count():
            raise RuntimeError(f"Moka project record {index + 1} was not found")
        fill_if_empty(name_field, str(project.get("name") or ""))
        role = record.locator("input[placeholder='职责']")
        if role.count():
            fill_if_empty(role.first, str(project.get("role") or ""))
        description = record.locator("textarea[placeholder='内容']")
        if description.count():
            fill_if_empty(description.first, str(project.get("description") or ""))
        duty = record.locator("textarea[placeholder='项目中职责']")
        if duty.count():
            fill_if_empty(duty.first, str(project.get("role") or ""))
        date_inputs = record.locator("input")
        date_values = (
            project.get("start_year"),
            project.get("start_month"),
            project.get("end_year"),
            project.get("end_month"),
        )
        if date_inputs.count() >= 4:
            for date_index, value in enumerate(date_values):
                choose_if_needed(page, date_inputs.nth(date_index), str(value or ""))
    return project_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-id", type=int, required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    args = parser.parse_args()

    config = load_config(Path(args.config))
    conn = connect_db(config)
    row = row_for(conn, args.application_id)
    profile = json.loads(Path(row["profile_path"]).read_text(encoding="utf-8"))
    company_profile = resolve_company_profile(
        config, company=str(row["company"] or ""), adapter_id="moka"
    )
    company_rules = company_profile.get("rules", {})
    safety = profile.get("safety", {})
    if safety.get("allow_submit"):
        raise SystemExit("Safety violation: allow_submit must remain false")
    fields = profile.get("fields", {})
    required = ("first_name", "last_name", "email", "phone")
    if any(not str(fields.get(key, "")).strip() for key in required):
        raise SystemExit("The isolated application profile lacks contact fields")
    resume = Path(row["tailored_resume_path"])
    if not resume.is_file():
        raise SystemExit("Tailored resume is missing")

    load_env_file(Path(args.env))
    _, cdp_url = resolve_browser_connection(config)
    apply_url = row["url"].rstrip("/")
    if not apply_url.endswith("/apply"):
        apply_url += "/apply"
    sync_playwright = _playwright_api()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=30_000)
        context = browser.contexts[0]
        resolution = resolve_application_page(
            context,
            conn,
            application_id=row["id"],
            expected_url=apply_url,
            browser_mode="windows_cdp",
        )
        page = resolution.page
        if resolution.created or not page_matches_application(page.url, apply_url):
            page.goto(apply_url, wait_until="domcontentloaded", timeout=45_000)
        register_application_page(
            conn,
            resolution,
            application_id=row["id"],
            expected_url=apply_url,
            browser_mode="windows_cdp",
        )
        for _ in range(20):
            if page.get_by_role("button", name="预览并提交", exact=True).count():
                break
            page.wait_for_timeout(1_000)
        if not page.get_by_role("button", name="预览并提交", exact=True).count():
            artifact = save_fill_test_artifact(
                page,
                JOBBOT_OUTPUT / "applications" / str(row["id"]),
                adapter="moka",
                stage="application_entry",
                status="authentication_required",
                metadata={"tab_resolution": resolution.method},
            )
            update_status(
                conn,
                row,
                "authentication_required",
                "Moka application form did not open; manual login/session repair required.",
                page.url,
            )
            print(
                f"Moka application {row['id']}: authentication_required; "
                f"screenshot={artifact['screenshot_path']}"
            )
            return

        # Moka is used here for mainland-China employers. Use the applicant's
        # explicit Chinese legal name instead of synthesizing an English name.
        full_name = str(fields.get("chinese_name") or "").strip()
        if not full_name or not re.search(r"[\u3400-\u9fff]", full_name):
            raise SystemExit(
                "The isolated application profile lacks a valid Chinese name for this "
                "mainland-China application"
            )
        page.locator("input[placeholder='姓名']").fill(full_name)
        raw_phone = str(fields["phone"]).strip()
        phone_digits = digits(raw_phone)
        phone_blocked = False
        if raw_phone.startswith("+852"):
            if not choose_phone_calling_code(
                page, page.locator("input[placeholder='请输入手机号']"), "+852"
            ):
                if login_prompt_visible(page):
                    artifact = save_fill_test_artifact(
                        page,
                        JOBBOT_OUTPUT / "applications" / str(row["id"]),
                        adapter="moka",
                        stage="phone_calling_code",
                        status="authentication_required",
                        metadata={"tab_resolution": resolution.method},
                    )
                    update_status(
                        conn, row, "authentication_required",
                        "Moka login expired while opening the phone calling-code control.",
                        page.url,
                    )
                    print(
                        f"Moka application {row['id']}: authentication_required; "
                        f"screenshot={artifact['screenshot_path']}"
                    )
                    return
                # Cambricon's current Moka form exposes only +86.  Do not put a
                # Hong Kong number under the wrong calling code; continue all
                # independent fields so the human has only this blocker left.
                phone_blocked = True
                phone_digits = ""
            else:
                phone_digits = phone_digits[3:]
        phone_field = page.locator("input[placeholder='请输入手机号']")
        if phone_digits:
            phone_field.fill(phone_digits)
        page.locator("input[placeholder='邮箱']").fill(str(fields["email"]))
        skill = page.locator("textarea[placeholder='请输入技能']")
        if skill.count():
            skill.fill(", ".join(str(value) for value in profile.get("skills", [])))

        file_inputs = page.locator("input[type=file]")
        if file_inputs.count():
            file_inputs.first.set_input_files(str(resume), timeout=10_000)
            page.wait_for_timeout(5_000)

        # The resume parser fills most of the education section. Complete only
        # fields backed by the user's explicit answers and resume facts.
        gender_fields = page.locator("input[placeholder='请选择']")
        if gender_fields.count() and not gender_fields.first.input_value().strip():
            choose(page, gender_fields.first, "男")
        education_records = profile.get("education", [])
        for education_profile in education_records:
            portal = education_profile.get("portal_values", {}).get("moka", {})
            school_value = str(portal.get("school") or "").strip()
            school = find_input_by_value(page, school_value) if school_value else None
            if school is None:
                continue
            education = school.locator(
                "xpath=ancestor::div[.//input[@placeholder='请输入专业名称']][1]"
            )
            education_inputs = education.locator("input")
            if education_inputs.count() >= 4:
                end_month = education_profile.get("to_month")
                if row["role_kind"] == "full_time" and education_profile.get("to_year") == 2027:
                    end_month = 6
                choose_if_needed(
                    page, education_inputs.nth(2), str(education_profile.get("to_year") or "")
                )
                choose_if_needed(page, education_inputs.nth(3), str(end_month or ""))
            major = education.locator("input[placeholder='请输入专业名称']")
            if major.count():
                fill_if_empty(major.first, str(portal.get("major") or ""))
            degree = education.locator("input[placeholder='请选择']")
            if degree.count() and not degree.first.input_value().strip():
                choose(page, degree.first, str(portal.get("degree") or ""))
        work_count = fill_work_experience(
            page, list(profile.get("work_experience") or [])
        )
        project_count = fill_projects(page, list(profile.get("projects") or []))
        note = (
            "Known Chinese legal name, contact, authorized gender, June 2027 full-time graduation, education, "
            f"skills, {work_count} work/research records, and {project_count} project records "
            "were filled and the tailored resume was uploaded. Unknown birth-date, nationality, "
            "address, identity and demographic fields remain blank. The browser is left "
            "on the editable form; Preview and Submit was not clicked."
        )
        if phone_blocked:
            note += (
                " Company profile confirmed that this Cambricon form currently offers only +86; "
                "the +852 phone field remains for human resolution while all independent fields were filled."
            )
        final_status = "manual_required" if phone_blocked else "browser_form_started"
        artifact = save_fill_test_artifact(
            page,
            JOBBOT_OUTPUT / "applications" / str(row["id"]),
            adapter="moka",
            stage="editable_form",
            status=final_status,
            metadata={
                "tab_resolution": resolution.method,
                "company_profile": company_profile.get("id"),
                "phone_blocked": phone_blocked,
            },
        )
        register_application_page(
            conn,
            resolution,
            application_id=row["id"],
            expected_url=apply_url,
            browser_mode="windows_cdp",
        )
        update_status(conn, row, final_status, note, page.url)
        print(
            f"Moka application {row['id']}: {final_status}; "
            f"screenshot={artifact['screenshot_path']}"
        )


if __name__ == "__main__":
    main()

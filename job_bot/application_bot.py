#!/usr/bin/env python3
"""Queue and prepare applications with mandatory human approval."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_bot.applications.nvidia_workday import _playwright_api, run_preview  # noqa: E402
from job_bot.browser_connection import check_cdp_health  # noqa: E402
from job_bot.bot import connect_db, load_config, load_env_file, utc_now  # noqa: E402
from application_bot.profile_policy import apply_explicit_authorization  # noqa: E402
from application_bot.portal_registry import resolve_company_profile  # noqa: E402
from cv.application_keywords import select_keywords, apply_keyword_selection  # noqa: E402
from private_paths import (  # noqa: E402
    APPLICATION_PROFILE,
    BROWSER_PROFILE_DIR,
    BROWSER_STATE_DIR,
    CREDENTIALS_FILE,
    CURRENT_RESUME_PDF,
    CURRENT_RESUME_TEX,
    JOBBOT_OUTPUT,
)


DEFAULT_CONFIG = ROOT / "job_bot" / "config.china_hk_ic_foreign.json"
DEFAULT_PROFILE = APPLICATION_PROFILE


def resolve_browser_connection(
    config: dict,
    *,
    mode_override: str | None = None,
    cdp_url_override: str | None = None,
) -> tuple[str, str]:
    browser_config = config.get("application_browser", {})
    mode = mode_override or browser_config.get("mode", "local_persistent")
    if cdp_url_override and not mode_override:
        mode = "windows_cdp"
    if mode == "local_persistent":
        if cdp_url_override:
            raise SystemExit("--cdp-url cannot be combined with --browser-mode local_persistent")
        return mode, ""
    if mode != "windows_cdp":
        raise SystemExit(
            "application_browser.mode must be local_persistent or windows_cdp"
        )

    cdp_config = browser_config.get("windows_cdp", {})
    url_env = cdp_config.get("url_env", "CHROME_CDP_URL")
    cdp_url = (
        (cdp_url_override or "").strip()
        or os.environ.get(url_env, "").strip()
        or str(cdp_config.get("url", "")).strip()
    )
    if not cdp_url:
        raise SystemExit(
            f"windows_cdp is selected but no endpoint is configured; set {url_env} "
            "or application_browser.windows_cdp.url"
        )
    if not cdp_url.startswith(("http://", "https://", "ws://", "wss://")):
        raise SystemExit("The Chrome CDP endpoint must be an HTTP(S) or WebSocket URL")
    return mode, cdp_url


def add_event(conn, application_id: int, event_type: str, details: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO application_events(application_id, event_type, details_json) VALUES (?, ?, ?)",
        (application_id, event_type, json.dumps(details or {}, ensure_ascii=False)),
    )


def cmd_queue(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    conn = connect_db(config)
    if args.job_id:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (args.job_id,)).fetchone()
    else:
        job = conn.execute("SELECT * FROM jobs WHERE url = ?", (args.job_url,)).fetchone()
    if not job:
        raise SystemExit("Job not found in the local database; scan it before queueing")
    existing = conn.execute(
        "SELECT id, status FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
        (job["id"],),
    ).fetchone()
    if existing and existing["status"] not in {"failed", "cancelled"}:
        print(f"Application already exists: id={existing['id']} status={existing['status']}")
        return
    now = utc_now()
    application_id = conn.execute(
        """
        INSERT INTO applications(
          job_id, status, tailored_resume_path, profile_path, notes, created_at, updated_at
        ) VALUES (?, 'queued', ?, ?, ?, ?, ?)
        """,
        (job["id"], args.resume, args.profile, args.notes, now, now),
    ).lastrowid
    add_event(conn, application_id, "queued", {"job_url": job["url"]})
    conn.commit()
    print(f"Queued application id={application_id}: {job['title']} — {job['company']}")


def cmd_list(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    conn = connect_db(config)
    rows = conn.execute(
        """
        SELECT applications.id, applications.status, jobs.title, jobs.company, jobs.url,
               applications.updated_at
        FROM applications JOIN jobs ON jobs.id = applications.job_id
        ORDER BY applications.id DESC
        """
    ).fetchall()
    if not rows:
        print("No queued applications")
        return
    for row in rows:
        print(f"{row['id']:4d} | {row['status']:20s} | {row['title']} | {row['company']} | {row['url']}")


def load_profile(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"Application profile not found: {path}. Copy job_bot/application_profile.template.json "
            "to private_data/profiles/application_profile.json and fill it locally."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def hydrate_known_resume_contacts(profile: dict, resume_tex: str) -> dict:
    """Fill only empty contact fields that are explicitly present in the resume."""
    fields = profile.setdefault("fields", {})
    name_match = re.search(r"\\name\{([^}]+)\}", resume_tex)
    if name_match:
        formal, _, preferred = name_match.group(1).partition(",")
        name_parts = formal.strip().split()
        known = {
            "first_name": name_parts[0] if name_parts else "",
            "last_name": " ".join(name_parts[1:]).title() if len(name_parts) > 1 else "",
            "preferred_name": preferred.strip(),
        }
        for key, value in known.items():
            if value and not fields.get(key):
                fields[key] = value
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", resume_tex)
    if email_match and not fields.get("email"):
        fields["email"] = email_match.group(0)
    us_phone = re.search(r"US:\s*([+\d][\d ()-]+)", resume_tex)
    hk_phone = re.search(r"HK:\s*([+\d][\d ()-]+)", resume_tex)
    phone_match = us_phone or hk_phone
    if phone_match and not fields.get("phone"):
        fields["phone"] = phone_match.group(1).strip()
    linkedin = re.search(r"\\href\{(https?://(?:www\.)?linkedin\.com/[^}]+)\}", resume_tex)
    if linkedin and not fields.get("linkedin_url"):
        fields["linkedin_url"] = linkedin.group(1)
    return profile


def cmd_prepare_profile(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    conn = connect_db(config)
    row = conn.execute(
        "SELECT applications.id, jobs.title, jobs.description FROM applications "
        "JOIN jobs ON jobs.id = applications.job_id WHERE applications.id = ?", (args.application_id,)
    ).fetchone()
    if not row:
        raise SystemExit(f"Application not found: {args.application_id}")
    base_path = Path(args.base_profile)
    if not base_path.is_absolute():
        base_path = ROOT / base_path
    profile = hydrate_known_resume_contacts(
        load_profile(base_path),
        CURRENT_RESUME_TEX.read_text(encoding="utf-8"),
    )
    profile = apply_keyword_selection(profile, select_keywords(row["title"] or "", row["description"] or ""))
    resume_path = Path(args.resume).resolve()
    cover_path = Path(args.cover_letter).resolve()
    if not resume_path.is_file() or not cover_path.is_file():
        raise SystemExit("Both tailored resume and cover-letter files must exist")
    profile.setdefault("documents", {})["resume_path"] = str(resume_path)
    profile["documents"]["cover_letter_path"] = str(cover_path)
    safety = profile.setdefault("safety", {})
    safety["allow_submit"] = False
    safety["allow_sensitive_answers"] = False
    output_dir = ROOT / "job_bot" / "out" / "applications" / str(args.application_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_path = output_dir / "profile.json"
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    profile_path.chmod(0o600)
    now = utc_now()
    conn.execute(
        """
        UPDATE applications
        SET tailored_resume_path = ?, cover_letter_path = ?, profile_path = ?, updated_at = ?
        WHERE id = ?
        """,
        (str(resume_path), str(cover_path), str(profile_path), now, args.application_id),
    )
    add_event(
        conn,
        args.application_id,
        "materials_prepared",
        {"resume_path": str(resume_path), "cover_letter_path": str(cover_path)},
    )
    conn.commit()
    print(f"Prepared isolated materials/profile for application {args.application_id}")


def cmd_authorize_profile(args: argparse.Namespace) -> None:
    profile_path = Path(args.profile)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = load_profile(profile_path)
    apply_explicit_authorization(
        profile,
        gender=args.gender,
        work_authorized=args.work_authorized == "yes",
        sponsorship_required=args.sponsorship == "yes",
        scopes=["mainland_china", "hong_kong"],
        amd_privacy_accepted=args.amd_privacy_accepted,
    )
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    profile_path.chmod(0o600)
    print("Stored explicit application answers; final submission remains disabled")


def cmd_workday_preview(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    browser_mode, cdp_url = resolve_browser_connection(
        config,
        mode_override=args.browser_mode,
        cdp_url_override=args.cdp_url,
    )
    if config.get("application_browser", {}).get("auto_submit", False):
        raise SystemExit(
            "application_browser.auto_submit must remain false; final submission is not implemented"
        )
    if browser_mode == "windows_cdp":
        health = check_cdp_health(cdp_url)
        cdp_url = health.connect_url
        print(f"Dedicated Chrome ready: {health.browser}")
    conn = connect_db(config)
    row = conn.execute(
        """
        SELECT applications.*, jobs.title, jobs.company, jobs.url, jobs.location, jobs.description
        FROM applications JOIN jobs ON jobs.id = applications.job_id
        WHERE applications.id = ?
        """,
        (args.application_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Application not found: {args.application_id}")
    hostname = (urllib.parse.urlsplit(row["url"] or "").hostname or "").lower()
    if not hostname.endswith("myworkdayjobs.com"):
        raise SystemExit("workday-preview only supports Workday job URLs")
    company_slug = re.sub(r"[^A-Za-z0-9]+", "_", row["company"] or "workday").strip("_").upper()
    tenant_slug = re.sub(r"[^A-Za-z0-9]+", "_", hostname).strip("_").lower()

    profile_path = Path(args.profile or row["profile_path"] or DEFAULT_PROFILE)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = load_profile(profile_path)
    profile = apply_keyword_selection(profile, select_keywords(row["title"] or "", row["description"] or ""))
    company_profile = resolve_company_profile(
        config, company=str(row["company"] or ""), adapter_id="workday"
    )
    output_dir = JOBBOT_OUTPUT / "applications" / str(args.application_id)
    browser_profile_dir = BROWSER_PROFILE_DIR / "workday" / tenant_slug
    storage_env = f"COMPANY_{company_slug}_STORAGE_STATE"
    raw_browser_state = os.environ.get(storage_env, "").strip()
    browser_state_path = (
        Path(raw_browser_state)
        if raw_browser_state
        else BROWSER_STATE_DIR / "workday" / f"{tenant_slug}.json"
    )
    if not browser_state_path.is_absolute():
        browser_state_path = ROOT / browser_state_path
    now = utc_now()
    try:
        report = run_preview(
            job_url=row["url"],
            job_location=str(row["location"] or ""),
            cookie_header=(
                os.environ.get(f"COMPANY_{company_slug}_COOKIE", "")
                or os.environ.get(f"COMPANY_{company_slug}_SESSION", "")
            ),
            profile=profile,
            project_root=ROOT,
            browser_profile_dir=browser_profile_dir,
            browser_state_path=browser_state_path,
            output_dir=output_dir,
            headless=args.headless,
            start_application=args.start_application,
            apply_mode=args.apply_mode,
            advance_one_step=args.advance_one_step,
            advance_to_review=args.advance_to_review,
            save_draft=args.save_draft,
            interactive=args.interactive,
            cdp_url=cdp_url if browser_mode == "windows_cdp" else "",
            cookie_origin=f"{urllib.parse.urlsplit(row['url']).scheme}://{hostname}",
            login_username=os.environ.get(f"COMPANY_{company_slug}_USERNAME", ""),
            login_password=os.environ.get(f"COMPANY_{company_slug}_PASSWORD", ""),
            application_id=args.application_id,
            registry_conn=conn,
            company_rules=company_profile.get("rules", {}),
        )
        if report.get("authentication_required"):
            status = "authentication_required"
        elif report.get("manual_intervention"):
            status = "manual_action_required"
        elif report.get("validation_blocked"):
            status = "validation_blocked"
        elif report["server_draft_saved"]:
            status = "draft_saved"
        elif report["application_started"]:
            status = "awaiting_review"
        else:
            status = "previewed"
        conn.execute(
            """
            UPDATE applications
            SET status = ?, profile_path = ?, browser_state_path = ?, draft_url = ?,
                field_report_json = ?, last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                str(profile_path),
                str(browser_state_path) if report.get("browser_state_saved") else None,
                report["final_url"],
                json.dumps(report, ensure_ascii=False),
                now,
                args.application_id,
            ),
        )
        add_event(conn, args.application_id, status, report)
        conn.commit()
        print(f"Workday application {args.application_id} ({row['company']}): {status}")
        print(f"Preview: {report['screenshot_path']}")
        print(f"Field report: {output_dir / 'field_report.json'}")
        print("Final submission was not performed.")
    except Exception as exc:
        conn.execute(
            "UPDATE applications SET status = 'failed', last_error = ?, updated_at = ? WHERE id = ?",
            (str(exc), now, args.application_id),
        )
        add_event(conn, args.application_id, "failed", {"error": str(exc)})
        conn.commit()
        raise


def cmd_nvidia_preview(args: argparse.Namespace) -> None:
    """Backward-compatible NVIDIA-only entry point."""
    config = load_config(Path(args.config))
    conn = connect_db(config)
    row = conn.execute(
        """
        SELECT jobs.company, jobs.url
        FROM applications JOIN jobs ON jobs.id = applications.job_id
        WHERE applications.id = ?
        """,
        (args.application_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Application not found: {args.application_id}")
    if "nvidia" not in (row["company"] or "").lower() and "nvidia" not in (row["url"] or "").lower():
        raise SystemExit("nvidia-preview only supports NVIDIA Workday jobs; use workday-preview")
    cmd_workday_preview(args)


def cmd_browser_health(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    mode, cdp_url = resolve_browser_connection(
        config,
        mode_override=args.browser_mode,
        cdp_url_override=args.cdp_url,
    )
    if mode != "windows_cdp":
        raise SystemExit(
            "Select application_browser.mode=windows_cdp or pass "
            "--browser-mode windows_cdp"
        )
    health = check_cdp_health(cdp_url)
    print(f"Dedicated Chrome CDP is healthy: {health.browser}")


def cmd_browser_smoke(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    mode, cdp_url = resolve_browser_connection(
        config,
        mode_override=args.browser_mode,
        cdp_url_override=args.cdp_url,
    )
    if mode != "windows_cdp":
        raise SystemExit("The browser smoke test requires windows_cdp mode")
    health = check_cdp_health(cdp_url)
    sync_playwright = _playwright_api()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(
            health.connect_url,
            timeout=30_000,
        )
        if not browser.contexts:
            raise RuntimeError("Connected Chrome exposed no usable browser context")
        page = browser.contexts[0].new_page()
        try:
            response = page.goto(
                args.url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if response is not None and response.status >= 400:
                raise RuntimeError(f"Smoke-test page returned HTTP {response.status}")
            title = page.title()
        finally:
            page.close()
        # Do not call browser.close(): this is an externally managed Windows Chrome.
    after = check_cdp_health(cdp_url)
    print(
        f"Dedicated Chrome smoke test passed: {after.browser}; "
        f"opened and closed one automation tab ({title or args.url})"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Human-approved job application preparation")
    sub = parser.add_subparsers(required=True)

    queue = sub.add_parser("queue", help="Queue a job from the local jobs database")
    target = queue.add_mutually_exclusive_group(required=True)
    target.add_argument("--job-id", type=int)
    target.add_argument("--job-url")
    queue.add_argument("--config", default=str(DEFAULT_CONFIG))
    queue.add_argument("--profile", default=str(DEFAULT_PROFILE))
    queue.add_argument("--resume", default=str(CURRENT_RESUME_PDF))
    queue.add_argument("--notes", default="")
    queue.set_defaults(func=cmd_queue)

    list_parser = sub.add_parser("list", help="List the local application queue")
    list_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    list_parser.set_defaults(func=cmd_list)

    prepare = sub.add_parser(
        "prepare-profile",
        help="Bind reviewed resume/cover-letter PDFs to an isolated application profile",
    )
    prepare.add_argument("--application-id", type=int, required=True)
    prepare.add_argument("--resume", required=True)
    prepare.add_argument("--cover-letter", required=True)
    prepare.add_argument("--base-profile", default=str(DEFAULT_PROFILE))
    prepare.add_argument("--config", default=str(DEFAULT_CONFIG))
    prepare.set_defaults(func=cmd_prepare_profile)

    authorize = sub.add_parser(
        "authorize-profile",
        help="Store explicit sensitive answers with a China/Hong Kong scope",
    )
    authorize.add_argument("--profile", default=str(DEFAULT_PROFILE))
    authorize.add_argument("--gender", choices=("male", "female", "decline"), required=True)
    authorize.add_argument("--work-authorized", choices=("yes", "no"), required=True)
    authorize.add_argument("--sponsorship", choices=("yes", "no"), required=True)
    authorize.add_argument("--amd-privacy-accepted", action="store_true")
    authorize.set_defaults(func=cmd_authorize_profile)

    def add_workday_preview(name: str, help_text: str, handler: object) -> None:
        preview = sub.add_parser(name, help=help_text)
        preview.add_argument("--application-id", type=int, required=True)
        preview.add_argument("--config", default=str(DEFAULT_CONFIG))
        preview.add_argument("--env-file", default=str(CREDENTIALS_FILE))
        preview.add_argument("--profile")
        preview.add_argument("--headless", action="store_true")
        preview.add_argument("--start-application", action="store_true")
        preview.add_argument("--apply-mode", choices=("resume", "manual", "last"), default="resume")
        preview.add_argument("--advance-one-step", action="store_true")
        preview.add_argument("--advance-to-review", action="store_true")
        preview.add_argument("--save-draft", action="store_true")
        preview.add_argument("--interactive", action="store_true")
        preview.add_argument(
            "--cdp-url",
            help="Temporarily override the dedicated Chrome CDP endpoint",
        )
        preview.add_argument(
            "--browser-mode",
            choices=("local_persistent", "windows_cdp"),
            help="Temporarily override application_browser.mode from the config",
        )
        preview.set_defaults(func=handler)

    add_workday_preview(
        "workday-preview",
        "Open and prepare any supported Workday application",
        cmd_workday_preview,
    )
    add_workday_preview(
        "nvidia-preview",
        "Backward-compatible NVIDIA Workday application command",
        cmd_nvidia_preview,
    )

    health = sub.add_parser(
        "browser-health",
        help="Check the configured dedicated Windows Chrome CDP endpoint",
    )
    health.add_argument("--config", default=str(DEFAULT_CONFIG))
    health.add_argument("--env-file", default=str(CREDENTIALS_FILE))
    health.add_argument("--cdp-url")
    health.add_argument(
        "--browser-mode",
        choices=("local_persistent", "windows_cdp"),
    )
    health.set_defaults(func=cmd_browser_health)

    smoke = sub.add_parser(
        "browser-smoke",
        help="Open and close one automation-owned tab in dedicated Windows Chrome",
    )
    smoke.add_argument("--config", default=str(DEFAULT_CONFIG))
    smoke.add_argument("--env-file", default=str(CREDENTIALS_FILE))
    smoke.add_argument("--cdp-url")
    smoke.add_argument(
        "--browser-mode",
        choices=("local_persistent", "windows_cdp"),
    )
    smoke.add_argument("--url", default="https://example.com")
    smoke.set_defaults(func=cmd_browser_smoke)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    env_file = getattr(args, "env_file", None)
    if env_file:
        load_env_file(Path(env_file))
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read-only audit of application portals open in the dedicated Chrome.

This module deliberately does not click, fill, upload, accept policies, or
submit.  Its output is a compact readiness report used to decide which portal
adapter may safely proceed to a human-reviewed draft.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = PROJECT_ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.application_bot import resolve_browser_connection  # noqa: E402
from job_bot.bot import load_config, load_env_file  # noqa: E402
from job_bot.browser_connection import check_cdp_health  # noqa: E402
from application_bot.portal_registry import resolve_adapter_by_url  # noqa: E402
from private_paths import APPLICATION_OUTPUT, CREDENTIALS_FILE  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "job_bot" / "config.china_hk_ic_foreign.json"
DEFAULT_ENV = CREDENTIALS_FILE
DEFAULT_OUT = APPLICATION_OUTPUT


@dataclass(frozen=True)
class PortalAudit:
    platform: str
    title: str
    url: str
    state: str
    reason: str
    visible_inputs: int
    visible_file_inputs: int
    simplify_present: bool
    safe_next_action: str


def platform_for_url(url: str, config: dict) -> str | None:
    adapter = resolve_adapter_by_url(config, url)
    return adapter.id if adapter else None


def classify_portal(
    *,
    platform: str,
    url: str,
    title: str,
    text: str,
    visible_inputs: int,
    visible_file_inputs: int,
) -> tuple[str, str, str]:
    """Classify without treating a final action as a draft action."""
    normalized = " ".join(text.lower().split())
    title_l = title.lower()
    url_l = url.lower()

    if "hcaptcha" in normalized or "protected by hcaptcha" in normalized:
        return (
            "captcha_or_consent_required",
            "The portal requires human consent and/or hCaptcha before the form.",
            "Human review: accept the named policy if desired and complete hCaptcha.",
        )
    if platform == "mediatek" and (
        "提交申请" in text or "your application will be submitted" in normalized
    ):
        return (
            "final_submit_only",
            "The next control is the final application submission, not Save Draft.",
            "Do not continue automatically; require an explicit final-submit decision.",
        )
    if (
        "sign in" in title_l
        or title_l.startswith("login")
        or "create account" in title_l
        or "/login" in url_l
        or "/authorize" in url_l
        or "returning user login" in normalized
        or "登录" in normalized[:1200]
        or "登錄" in normalized[:1200]
    ):
        return (
            "authentication_required",
            "The application session is not at an authenticated editable form.",
            "Log in manually in the dedicated Chrome; stop for MFA/CAPTCHA.",
        )
    if platform == "mediatek" and (
        "完善您的简历" in text
        or "请填写至少1段教育背景" in text
        or "请输入以下信息" in text
    ):
        return (
            "profile_incomplete",
            "The account profile is incomplete and includes sensitive required fields.",
            "Fill only explicitly authorized factual and sensitive profile fields.",
        )
    if any(word in title_l for word in ("principal", "senior", "staff", "director")):
        return (
            "role_mismatch",
            "The open role is senior-level and outside the configured early-career queue.",
            "Do not fill; select a scored internship or new-graduate role instead.",
        )
    if platform == "simplify" and "/search" in url_l:
        return (
            "discovery_helper",
            "Simplify is open as a search/autofill helper, not an employer application form.",
            "Use the extension only after a supported employer form is open.",
        )
    if platform in {"analog_devices", "huawei"} and any(
        marker in url_l for marker in ("/careers.html", "job-list")
    ):
        return (
            "listing_or_redirect",
            "This is a careers search/landing page, not an application form.",
            "Choose a high-fit early-career role before attempting autofill.",
        )
    if visible_inputs or visible_file_inputs:
        return (
            "form_detected",
            "An editable form is visible and can be considered by a portal adapter.",
            "Run a no-submit preview, fill known fields, and stop at Review.",
        )
    if any(word in normalized for word in ("apply", "申请", "應徵", "职位", "職位")):
        return (
            "listing_or_redirect",
            "A job/listing page is available but no editable application form is visible.",
            "Open the application entry once, then rerun the audit.",
        )
    return (
        "unsupported_or_landing",
        "No authenticated editable application form was detected.",
        "Keep this source for job discovery; do not attempt blind autofill.",
    )


def audit_page(page, platform: str) -> PortalAudit:
    try:
        title = page.title().strip()
    except Exception:
        title = ""
    text_parts: list[str] = []
    visible_inputs = 0
    visible_file_inputs = 0
    for frame in page.frames:
        try:
            text_parts.append(frame.locator("body").inner_text(timeout=2_000)[:40_000])
        except Exception:
            pass
        try:
            inputs = frame.locator(
                "input:not([type=hidden]):not([type=file]), textarea, select"
            )
            visible_inputs += sum(
                inputs.nth(i).is_visible() for i in range(inputs.count())
            )
        except Exception:
            pass
        try:
            files = frame.locator("input[type=file]")
            visible_file_inputs += sum(
                files.nth(i).is_visible() for i in range(files.count())
            )
        except Exception:
            pass
    text = "\n".join(text_parts)[:80_000]
    try:
        simplify_present = any(
            frame.url.startswith("chrome-extension://") for frame in page.frames
        ) or page.locator('[class*="simplify" i], [id*="simplify" i]').count() > 0
    except Exception:
        simplify_present = False
    state, reason, next_action = classify_portal(
        platform=platform,
        url=page.url,
        title=title,
        text=text,
        visible_inputs=visible_inputs,
        visible_file_inputs=visible_file_inputs,
    )
    return PortalAudit(
        platform=platform,
        title=title,
        url=page.url,
        state=state,
        reason=reason,
        visible_inputs=visible_inputs,
        visible_file_inputs=visible_file_inputs,
        simplify_present=simplify_present,
        safe_next_action=next_action,
    )


def render_markdown(records: list[PortalAudit], generated_at: str) -> str:
    lines = [
        "# Application platform audit",
        "",
        f"Generated: {generated_at}",
        "",
        "Read-only audit. No form was filled and no application was submitted.",
        "",
        "| Platform | State | Inputs | Simplify | Safe next action |",
        "|---|---|---:|:---:|---|",
    ]
    for item in records:
        lines.append(
            f"| {item.platform} | {item.state} | "
            f"{item.visible_inputs}/{item.visible_file_inputs} files | "
            f"{'yes' if item.simplify_present else 'no'} | {item.safe_next_action} |"
        )
    lines.append("")
    lines.append("## Details")
    lines.append("")
    for item in records:
        lines.extend(
            [
                f"### {item.platform}",
                "",
                f"- Page: {item.title or '(untitled)'}",
                f"- URL: {item.url}",
                f"- Finding: {item.reason}",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    load_env_file(Path(args.env_file))
    config = load_config(Path(args.config))
    mode, endpoint = resolve_browser_connection(config)
    if mode != "windows_cdp":
        raise SystemExit("platform-audit requires the dedicated Windows CDP browser")
    health = check_cdp_health(endpoint)

    from playwright.sync_api import sync_playwright

    records: list[PortalAudit] = []
    seen: set[str] = set()
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(health.connect_url)
        for context in browser.contexts:
            for page in reversed(context.pages):
                platform = platform_for_url(page.url, config)
                if not platform or platform in seen:
                    continue
                seen.add(platform)
                records.append(audit_page(page, platform))
                if len(records) >= args.limit:
                    break
            if len(records) >= args.limit:
                break
    finally:
        playwright.stop()

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"platform_audit_{stamp}.json"
    md_path = out_dir / f"platform_audit_{stamp}.md"
    json_path.write_text(
        json.dumps(
            {"generated_at": generated_at, "browser": health.browser, "portals": [asdict(r) for r in records]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(records, generated_at) + "\n", encoding="utf-8")
    print(md_path)
    print(json_path)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate the human review/action queue for a no-submit campaign."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_bot.bot import connect_db, load_config  # noqa: E402


DEFAULT_CONFIG = ROOT / "job_bot/config.china_hk_ic_foreign.json"
from private_paths import APPLICATION_OUTPUT

DEFAULT_OUT = APPLICATION_OUTPUT


ACTION = {
    "qr_login_policy_required": (
        "Scan the Hotjob WeChat QR code and decide whether to accept the displayed privacy policy; "
        "this single action can unlock all 40 Horizon/UNISOC roles."
    ),
    "authentication_required": (
        "Complete the named portal sign-in/account step in the dedicated Chrome. Workday tenants, "
        "Apple, and Moore Threads use separate sessions."
    ),
    "browser_form_started": (
        "Review the open form. Moka still requires birth date and nationality; Infineon requires "
        "country of residence and preferred start date. Do not press the final submit button yet."
    ),
    "profile_ready_final_only": (
        "Review the MediaTek global profile. The site has no per-role draft: the next job action is "
        "final submission, so tailored PDFs remain in the local review bundles."
    ),
    "captcha_required": "Complete each AMD hCaptcha; email and AMD privacy consent are already filled.",
    "policy_consent_required": (
        "Review and explicitly authorize or decline the TI policy/consent screen before automation continues."
    ),
    "account_creation_required": (
        "Create a Qualcomm candidate account or sign in with Google; the authorized email is already entered."
    ),
    "external_redirect_unresolved": (
        "Open the employer's real destination manually. JobsDB only recorded an external-site visit and did "
        "not send an application."
    ),
    "job_detail_unresolved": (
        "Repair the current Alibaba position-detail URL mapping; the stored links now open the general job list."
    ),
    "profile_repair_required": (
        "Repair or recreate the Shixiseng online resume; its current completion link resolves to /resume/undefined."
    ),
    "portal_unreachable": "Repair the Kunlunxin Zhiye detail route, which currently opens a blank page.",
    "draft_saved": "Review the saved NVIDIA server draft; no final submission has occurred.",
}

PRIORITY = {
    "qr_login_policy_required": 1,
    "authentication_required": 2,
    "browser_form_started": 3,
    "profile_ready_final_only": 4,
    "captcha_required": 5,
    "policy_consent_required": 6,
    "account_creation_required": 7,
    "draft_saved": 8,
    "external_redirect_unresolved": 9,
    "job_detail_unresolved": 10,
    "profile_repair_required": 11,
    "portal_unreachable": 12,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", type=int, default=2)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    conn = connect_db(load_config(Path(args.config)))
    rows = conn.execute(
        """
        SELECT acj.rank, acj.status, acj.application_id, jobs.company,
               jobs.title, jobs.location, applications.draft_url
        FROM application_campaign_jobs acj
        JOIN jobs ON jobs.id=acj.job_id
        LEFT JOIN applications ON applications.id=acj.application_id
        WHERE acj.campaign_id=? ORDER BY acj.rank
        """,
        (args.campaign_id,),
    ).fetchall()
    groups = defaultdict(list)
    for row in rows:
        groups[row["status"]].append(row)
    lines = [
        f"# Campaign {args.campaign_id} review actions",
        "",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        f"Total roles: {len(rows)}. Final submissions: 0.",
        "",
        "Every role has tailored resume and cover-letter PDFs. Browser/server progress is listed below.",
        "",
    ]
    for status in sorted(groups, key=lambda value: PRIORITY.get(value, 99)):
        items = groups[status]
        lines.extend(
            [
                f"## {status} ({len(items)})",
                "",
                ACTION.get(status, "Review this state manually."),
                "",
                "| Rank | App | Company | Role | Location |",
                "|---:|---:|---|---|---|",
            ]
        )
        for row in items:
            lines.append(
                f"| {row['rank']} | {row['application_id']} | {row['company']} | "
                f"{row['title']} | {row['location']} |"
            )
        lines.append("")
    output = DEFAULT_OUT / f"campaign_{args.campaign_id:03d}_review_actions_{datetime.now():%Y%m%d_%H%M%S}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

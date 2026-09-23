# Job Bot

This folder contains the Synology-ready job collector, scorer, database, and
daily-report generator. The stable application-preparation entry point is now
`application_bot/cli.py`; the implementation remains here temporarily for
backward compatibility.

Penn campus work, research, events and other career platforms have a separate
[channel reader and login queue](source_lists/upenn_channels.md). Run
`make workflow WORKFLOW=penn_channels_refresh`, or
`python3 job_bot/penn_channels.py --open-login-pages` to retain missing login
pages. Daily/weekly reporting includes a link to their separate status report.

The intended flow is:

1. Collect job postings from approved sources.
2. Store postings in a local database.
3. Score each role against the resume profile.
4. Generate tailored resume notes and cover-letter bullets.
5. Require human approval before any application is submitted.

Automatic submission should stay disabled until each platform account, permission model, and application rule is explicitly approved.

## Semi-automatic Workday applications

The Workday adapter can queue a stored job, open it in an isolated
Chromium profile, seed the local NVIDIA session cookie, fill explicitly mapped
contact fields, upload a resume, and produce a screenshot plus field report.
It never clicks the final Submit control.

Application preparation has two separate browser channels, selected only by
`application_browser.mode` in the JSON config:

- `local_persistent`: the original flow, which launches the isolated Chromium
  profile inside WSL.
- `windows_cdp`: attaches to the dedicated Windows `JobApplyChrome` profile
  through the WSL-only portproxy endpoint (currently port `9223`). It creates
  and later closes only its own tab, leaves Windows Chrome running, reuses that
  profile's authenticated session, and does not inject the legacy Cookie header
  or export the Windows browser state into WSL.

Example configuration:

```json
"application_browser": {
  "mode": "windows_cdp",
  "windows_cdp": {
    "url_env": "CHROME_CDP_URL",
    "url": ""
  }
}
```

Switch `mode` back to `local_persistent` to use the original flow. The endpoint
can be kept in `passport.env` as `CHROME_CDP_URL`; it is read only while
`windows_cdp` is selected. `--browser-mode` and `--cdp-url` are temporary CLI
overrides. If WSL NAT addresses change, update the portproxy/firewall rule and
the endpoint without changing the browser mode.

Start the dedicated Chrome from Windows PowerShell:

```powershell
& .\job_bot\scripts\windows\start-job-chrome.ps1
Invoke-RestMethod http://127.0.0.1:9222/json/version
```

For NAT-mode WSL, configure the separate `9223 -> 9222` path from an
Administrator PowerShell after substituting the current addresses:

```powershell
& .\job_bot\scripts\windows\configure-wsl-cdp-portproxy.ps1 `
  -WslGatewayAddress <wsl-gateway-ip> `
  -WslAddress <wsl-ip>
```

The Chrome process still listens only on Windows `127.0.0.1:9222`; port `9223`
is bound only to the WSL virtual gateway, and the firewall rule admits only the
current WSL address. Do not bind Chrome to `0.0.0.0`, use the ordinary Chrome
profile, or add `--remote-allow-origins=*`.

Check the configured connection from WSL, then perform the safe integration
test that opens and closes only one automation-owned `example.com` tab:

```bash
./job_bot/scripts/check-chrome-cdp.sh
./job_bot/scripts/check-chrome-cdp.sh --smoke
```

Run a generic Workday dry-run preview using the browser mode selected in the config:

```bash
python3 application_bot/cli.py workday-preview --application-id 1
```

`nvidia-preview` remains a backward-compatible alias. Each Workday tenant may
require a separate sign-in, and all tenant-specific questions remain subject to
human review.

There is deliberately no explicit-submit command: the adapter blocks the final
Submit action and requires `application_browser.auto_submit=false` plus
`application_profile.local.json` safety `allow_submit=false`. CAPTCHA, MFA,
sign-in verification, and unanswered screening questions produce a manual-action
status; in Windows CDP mode the automation tab is left open for manual handling.

Install the optional browser runtime inside the project:

```bash
python3 -m pip install --target .python_packages \
  -r job_bot/requirements-browser.txt
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
  PYTHONPATH=.python_packages python3 -m playwright install chromium --no-shell
```

Copy `application_profile.template.json` to the ignored
`application_profile.local.json`, then fill only answers that are true and
stable. Legal authorization, sponsorship, demographic, and declaration
answers are never inferred.

Queue a job already stored in SQLite and preview it:

```bash
python3 job_bot/application_bot.py queue --job-url 'NVIDIA_WORKDAY_URL'
python3 job_bot/application_bot.py list
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
  python3 job_bot/application_bot.py nvidia-preview \
  --application-id 1 --start-application --interactive
```

Local profile/state paths, screenshots, field inventories, and application
events are saved for resuming. NVIDIA Workday may preserve data after a
Save/Continue step; this server-side action is disabled unless both
`safety.allow_server_draft=true` in the local profile and `--save-draft` are
provided. Even then, final submission remains disabled.

To resume an existing NVIDIA draft, fill structured `education` and `skills`
entries from the local profile, and advance through My Experience to the
Application Questions checkpoint:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers \
  python3 job_bot/application_bot.py nvidia-preview \
  --application-id 1 --start-application --save-draft \
  --advance-to-review --headless
```

Hierarchical Workday prompts can be represented as a list, for example
`["University", "Example University"]`. The workflow stops when a
required legal, immigration, declaration, or other unanswered question is
encountered. It never infers those answers or clicks final Submit.

The local application profile, browser profile, and storage-state files contain
personal or authentication data. They are Git-ignored; keep their file modes at
`600` and their directories at `700` when copying the project to Synology.

## What It Does Now

- Monitors configured job sources.
- Stores jobs in local SQLite.
- Deduplicates by job URL.
- Scores each job against hardware/digital-design keywords.
- Generates a daily digest.
- Writes the digest to `private_data/outputs/job_bot/` by default.
- Can send the digest through SMTP when `dry_run` is set to `false`.

Supported source types:

- `greenhouse`: company Greenhouse job boards.
- `lever`: company Lever job boards.
- `rss`: RSS/Atom feeds.
- `html`: simple careers pages; extracts links and filters by regex.
- `icims`: public iCIMS result cards with pagination, title, location, and summary.
- `attrax`: public Attrax vacancy tiles with official option filters and pagination.
- `workday`: Workday public careers search endpoints; numbered multi-location
  summaries are expanded through the public job-detail endpoint.
- `mediatek`: MediaTek's public structured job endpoint with full pagination.
- `xiaomi`: Xiaomi's public structured search API, including official
  publication dates and social/campus/internship type mapping.
- `moka_cdp`: Moka job cards collected in the dedicated Windows Chrome for
  portals such as Cambricon, Biren, and DJI.
- `jobsdb_hk`: JobsDB HK structured cards, optionally collected through the
  authenticated dedicated Windows Chrome with `fetch_via_cdp=true`.
- `zhipin`: BOSS Zhipin adapter; disabled by default in the shared config because login/captcha friction is expected.
- `shixiseng`: Shixiseng internship cards through the dedicated Chrome; normal
  title and description metadata are read from each public detail page.
- `cuhk_careers`: CUHK CPDC / CU Careers structured search adapter using an exported browser session.
- `handshake`: Penn's student job portal through the existing PennKey Chrome
  login, with bounded read-only searches. This is a browser integration, not
  the institution-only EDU API. See [Penn setup and validation status](source_lists/upenn_handshake.md).

Each stored posting has a `role_kind`:

- `internship`
- `full_time`
- `unknown`

The label is inferred from the title/description/location unless a source forces a role type.

## Quick Start

From the project root:

```bash
python3 job_bot/bot.py init --config job_bot/config.example.json
python3 job_bot/bot.py digest --config job_bot/config.example.json --print
```

To scan real sources, copy `config.example.json` to `config.local.json`, replace the example source entries, and run:

```bash
python3 job_bot/bot.py run --config job_bot/config.local.json
```

For an observable retry of one or more sources, repeat `--source` with the
exact configured name. The scanner prints a line before and after every source:

```bash
python3 job_bot/bot.py scan --config job_bot/config.local.json \
  --source "NVIDIA Greater China Hardware" \
  --source "Cambricon Campus Careers"
```

`config.local.json` should not be committed if it contains private email or source details.

For the China/Hong Kong IC-design target list, start from:

```bash
python3 job_bot/bot.py init --config job_bot/config.china_hk_ic_foreign.json
python3 job_bot/bot.py run --config job_bot/config.china_hk_ic_foreign.json --env-file private_data/credentials/passport.env
```

The source rationale is documented in `job_bot/source_lists/china_hk_ic_foreign_companies.md`.

Useful config fields for source tuning:

- `role_kinds`: keep only internship/full-time/unknown postings from that source.
- `include_patterns`: all regex groups must match somewhere in title/location/description/url. Use one group for geography and one for IC-role keywords.
- `exclude_patterns`: drop noisy roles.
- `title_include_patterns`: require at least one high-precision regex match in the job title.
- `title_exclude_patterns`: reject a job when its title matches any listed regex.
- Digest-level `include_title_patterns`: require a relevant title signal for
  lower-scoring jobs; `title_match_bypass_score` keeps strongly matched generic
  titles whose descriptions contain enough verified evidence.
- `enabled: false`: keep a source in the list but skip it during scans.
- `timeout_seconds`: override the default per-request timeout.

Credentials/session support:

- Do not commit account passwords, cookies, or tokens.
- Put local secrets in the ignored `private_data/credentials/passport.env` file or Synology Task Scheduler environment variables.
- Every company/platform can use optional `*_USERNAME`, `*_PASSWORD`, `*_COOKIE`, and `*_STORAGE_STATE` variables. Add only populated variables; missing variables are treated as empty. Username/password slots are reserved for future interactive login adapters and are not consumed by current collectors.
- `*_COOKIE` must contain the Cookie **request** header for exactly one matching domain. The bot rejects common `Set-Cookie` attributes and obvious Google/LinkedIn cross-domain mistakes.
- `*_STORAGE_STATE` is a path to a Playwright storage-state JSON file. Browser-assisted adapters should prefer it for OAuth, SSO, multi-domain, localStorage, CAPTCHA, or 2FA flows such as Apply with LinkedIn; plain HTTP collectors only report its availability and do not load it.
- If a board requires login, prefer a short-lived browser-state/cookie export over storing raw passwords.
- Start from the compact `job_bot/env.template`, which keeps blank fields only for the most frequently used companies/platforms; fill only local values you actually use.
- Migrate or compact an existing file without printing secret values with `python3 job_bot/migrate_passport.py --env-file private_data/credentials/passport.env`. It preserves populated values, retains the curated blank fields, removes other empty placeholders, and converts legacy `*_SESSION` names; legacy names remain readable as a fallback.
- Pass it explicitly with `--env-file private_data/credentials/passport.env`; existing process environment variables take precedence.
- The CUHK source calls the portal's structured `/job/search` API and never needs the CUHK account password.
- When the exported CUHK session expires, refresh only `PLATFORM_CUHK_CAREERS_COOKIE`; the failed scan is included in the digest.
- Company sources automatically use `COMPANY_<NORMALIZED_COMPANY>_COOKIE` and the matching username/password/storage-state names. For example, `Arm` maps to `COMPANY_ARM_COOKIE` and `Huawei / HiSilicon` maps to `COMPANY_HUAWEI_HISILICON_COOKIE`.
- Current platform adapters use `PLATFORM_JOBSDB_HK_COOKIE`, `PLATFORM_BOSS_ZHIPIN_COOKIE`, `PLATFORM_SHIXISENG_COOKIE`, and `PLATFORM_CUHK_CAREERS_COOKIE`.
- The same naming rule supports LinkedIn, Handshake, Indeed, Glassdoor, Simplify, Wellfound, ZipRecruiter, RippleMatch, Liepin, 51job, Zhaopin, Maimai, CTgoodjobs, and cpjobs. A credential variable does not imply that a collector is implemented yet.
- Leave optional credentials empty when public fetching works. A cookie is attached only when its value is non-empty.
- Failed crawls are recorded in `scan_runs` and included in the digest when `digest.include_scan_errors=true`.

Audit session coverage without exposing any secret values:

```bash
python3 job_bot/bot.py auth-status \
  --config job_bot/config.china_hk_ic_foreign.json \
  --env-file private_data/credentials/passport.env
```

Useful digest fields:

- `include_scan_errors`: include failed sources in the daily email.
- `max_items`: cap the email length while keeping all jobs in SQLite.
- `min_score`: hide low-scoring jobs from the email.
- `deduplicate_similar`: collapse duplicate company/title/location requisitions in the email.
- `exclude_title_patterns`: hide senior or otherwise unsuitable titles from the email without deleting them from SQLite.

The regular digest includes newly discovered active jobs and is divided into
internship and full-time sections. When a source exposes an official publication
date, the 24-hour filter uses it; otherwise it falls back to first discovery.
Use `--since` with the preceding baseline/report timestamp to suppress jobs that
were already covered:

```bash
python3 job_bot/bot.py digest \
  --config job_bot/config.china_hk_ic_foreign.json \
  --env-file private_data/credentials/passport.env \
  --hours 24 --since '2026-08-28T00:26:23+08:00' --edition 2
```

To create a numbered baseline containing the
entire currently active inventory after filtering and deduplication:

```bash
python3 job_bot/bot.py digest \
  --config job_bot/config.china_hk_ic_foreign.json \
  --env-file private_data/credentials/passport.env \
  --all-active --edition 1
```

The China/Hong Kong profile uses two-level Foundation scoring. A Foundation
first identifies what a role fundamentally is; resume evidence, early-career
signals, seniority, and non-design/software modifiers then adjust the score.
Digital RTL design and CPU/computer architecture are the preferred directions;
verification and EDA are strong adjacent paths, while PD/DFT and analog remain
searchable at lower bases. After changing the policy, refresh stored scores with:

```bash
python3 job_bot/bot.py rescore --config job_bot/config.china_hk_ic_foreign.json
```

Render the active Foundation definitions, complete keyword lists, modifiers,
decision bands, and current top matches:

```bash
python3 job_bot/scoring_report.py
```

### 2027 two-track application strategy

The application shortlist is now split from the ordinary daily digest:

1. Mainland China/Hong Kong full-time roles must be a 2027/new-graduate role
   or come from an official campus portal.
2. United States internships must target Summer 2027 (or be an explicitly
   rolling Apple master's hardware internship), allow master's students, and
   pass term/degree/export-control checks.

The US collector set includes dedicated NVIDIA, AMD, Qualcomm, Apple, ADI,
Broadcom, Marvell, Cadence, TI, Etched, and SpaceX sources in addition to the
existing global Intel/Lattice/Samsung/Skyworks/Cirrus/MaxLinear sources. Scan a
single newly added source with repeatable `--source` arguments, then render the
current shortlist:

```bash
python3 job_bot/bot.py scan \
  --config job_bot/config.china_hk_ic_foreign.json \
  --env-file private_data/credentials/passport.env \
  --source "NVIDIA United States 2027 Hardware Internships"
python3 job_bot/strategy_report.py
```

### One-command daily pipeline

The preferred daily entry point now checks the dedicated Windows Chrome,
starts it automatically from WSL when possible, scans ordinary HTTP sources in
parallel, keeps shared-CDP sources serial, rescoring stored jobs, and writes both
the two-track delta report and a compact human-intervention report:

```bash
python3 job_bot/daily_pipeline.py \
  --config job_bot/config.china_hk_ic_foreign.json \
  --env-file private_data/credentials/passport.env
```

The baseline is stored in
`private_data/outputs/job_bot/daily_pipeline_state.json`, so later runs only
report jobs first discovered since the preceding run. Use `--since` to override
it. If Chrome or its WSL portproxy is unavailable, the pipeline continues with
the public HTTP sources and lists skipped browser sources in the intervention
report instead of blocking the whole run. Portproxy/firewall repair remains an
explicit administrator action.

Transient 408/429/5xx, timeout, reset, and SSL-EOF failures receive a bounded
exponential-backoff retry. Requests for the same employer are serialized even
when different employers run concurrently, preventing parallel regional
searches from rate-limiting each other. Authentication failures and parser/layout
changes are not retried blindly; they are routed to the intervention report.

Only login expiry, MFA/CAPTCHA, genuinely ambiguous eligibility answers, portal
layout changes, and final submission should require human review.

Use the truthful degree dates appropriate to each track: the full-time variant
can state June 2027, while an internship variant must show a real enrollment
date that covers the entire internship. The strategy report never submits an
application.

## Local Test

A small fixture RSS feed is included for testing the full path without external network:

```bash
python3 job_bot/bot.py scan --config job_bot/test_fixtures/config.fixture.json
python3 job_bot/bot.py digest --config job_bot/test_fixtures/config.fixture.json --print
```

## Email

Keep `email.dry_run` as `true` while testing. The bot will write a digest text file instead of sending email.

To enable SMTP email:

```json
"email": {
  "dry_run": false,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "starttls": true,
  "username_env": "SMTP_USERNAME",
  "password_env": "SMTP_PASSWORD",
  "from": "your_email@example.com",
  "to": [],
  "to_env": "JOBBOT_EMAIL_TO"
}
```

Then set environment variables on the Synology task:

```bash
export SMTP_USERNAME="your_email@example.com"
export SMTP_PASSWORD="your_app_password"
python3 /volume1/path/to/26fall_intern/job_bot/bot.py run --config /volume1/path/to/26fall_intern/job_bot/config.local.json
```

Use an app password or SMTP token, not your primary email password.

## Platform Notes

Start with low-risk sources:

- Company career pages with public postings.
- LinkedIn/Handshake/Simplify/Greenhouse/Lever links manually exported or saved.
- Email alerts forwarded into a structured inbox.

Potential database/platform integrations:

- Local SQLite for private testing.
- Airtable for a visual tracker after plugin connection.
- Google Drive for resume artifact storage after plugin connection.

## Synology Plan

Once this is copied to the Synology server, use Task Scheduler:

- User-defined script.
- Run daily, e.g. 8:30 AM.
- Command: `python3 /volume1/path/to/26fall_intern/job_bot/bot.py run --config /volume1/path/to/26fall_intern/job_bot/config.local.json`
- Keep `dry_run=true` for the first few days and inspect `private_data/outputs/job_bot/`.

Later deployment options:

- Synology Task Scheduler for simple daily runs.
- Docker container for reproducible Python/runtime setup.
- SQLite backup to Synology Drive.

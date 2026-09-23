# Penn channels beyond Handshake

Attempted and checked September 17, 2026, New York (September 18 UTC).
Configuration: `job_bot/config/penn_channels.json`. Reader and access report:
`job_bot/penn_channels.py`. These channels are separate from the existing
Handshake job source and enterprise-job scoring.

| Channel | Verified state | Collection scope |
|---|---|---|
| Workday@Penn Student Employment | PennKey re-authentication required; retained page | Student job listing reader awaits login and mapping verification; no jobs ingested |
| Engineering recruiting events | 3 upcoming references collected | Visible dated event links; past events omitted |
| Engineering Career Development Hub | PennKey access succeeded; 5 resource links collected | Career resources, not job postings |
| Interstride | Email login page retained | Authenticated job collector not verified |
| CareerShift | Login/sign-up page retained | Authenticated job collector not verified |
| GoinGlobal | Current official login page retained | Penn legacy `default.aspx` link did not load; institutional access not verified |
| MyPenn | Existing PennKey session entered the site | Networking entry/status only; no alumni profile harvesting or outreach |
| CURF Research Directory | PennKey access succeeded; 10 visible research links collected | Current directory page only; primarily undergraduate leads, not verified paid/master's positions |

Disabled channels are skipped and their login pages are not reopened. Existing
tabs are preserved. Keep account-specific login results in the ignored output
report rather than this shared source guide.

## Commands

```bash
# Read/recheck all channels and refresh implemented resource readers
make workflow WORKFLOW=penn_channels_refresh

# Open missing entry/login pages, reusing each retained target when it exists
python3 job_bot/penn_channels.py --open-login-pages
```

Daily processing refreshes this report when Chrome is available. W38 and later
weekly reports link to it. References remain separate from enterprise job counts,
scoring, and the graduate/internship strategy. In particular, Work-Study and
Non-Work-Study eligibility must be checked individually, and research-directory
membership does not establish pay, current vacancy or master's eligibility.

## Browser and handoff

The ignored `private_data/outputs/job_bot/penn_channels/tabs.json` contains
retained CDP target IDs. Preserve these pages while the user logs in.
Repeated `--open-login-pages` does not navigate or duplicate an existing target.
Implemented readers refresh in disposable tabs during normal runs; existing user
pages are only read. If the user closes a target, the open-pages command can
recreate its entry page. PennKey/MFA/registration/consent remain manual.

Results: `private_data/outputs/job_bot/penn_channels/latest.md` and `latest.json`.
The report records per-channel state and typed references, not credentials,
cookies, profile bodies, or SSO query strings. Pending boards must be inspected
after login before enabling full job ingestion. Do not describe configured
entry points as implemented APIs or complete job collectors.

Official references are stored alongside each channel in configuration:
[Penn student jobs](https://srfs.upenn.edu/student-employment/job-search),
[Engineering career development](https://academics.engineering.upenn.edu/student-career-development/),
[Interstride Penn](https://www.interstride.com/upenn/),
[CareerShift Penn](https://upenn.careershift.com/),
[Penn GoinGlobal](https://careerservices.upenn.edu/resources/goinglobal/),
[current GoinGlobal login](https://online.goinglobal.com/user/login),
[MyPenn](https://mypenn.upenn.edu/),
[CURF directory](https://curf.upenn.edu/undergraduate-research/research-directory).

## Weekly campus income section

`make weekly` regenerates a dedicated campus employment section near the top of
the weekly report. `campus_employment_report.py` reads `campus_job` references
from the latest channel snapshot and reviewed leads from
`penn_channels.campus_employment.leads` in the configuration. It does not apply
the enterprise IC relevance score. Public pages are manually verified snapshots,
not refreshed by the database-only weekly command; retain their check dates.

Optional numeric fields: `hourly_usd: [min, max]`, `weekly_hours: [min, max]`.
Include `pay_basis`, `hours_basis`, `status`, `checked_at`, `eligibility`, and
`next_step` so readers can distinguish current offers, historical quotes and
unknowns. Monthly hours use 52/12 weeks; gross pay uses unrounded weekly hours.
Missing values stay unknown. Research leads do not automatically become paid
jobs. The separate budget table is hypothetical. PSA's public page still labels
its rates August 2025; verify current vacancies and terms in Workday.

Official supporting pages: [Penn Recreation](https://recreation.upenn.edu/sports/2021/8/26/structured-sports-employment-opportunities.aspx),
[Penn Student Agencies](https://psa.universitylife.upenn.edu/join/),
[ISSS on-campus employment](https://global.upenn.edu/isss/oncampus/),
[ISSS SSN process](https://global.upenn.edu/isss/ssn/).

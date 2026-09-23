# Penn official career access

## Official entry points

- [Penn Career Services: Handshake](https://careerservices.upenn.edu/resources/handshake/)
- [PennKey login](https://upenn.joinhandshake.com/login)
- [Student jobs](https://upenn.joinhandshake.com/job-search)
- [Penn recruiting events](https://careerservices.upenn.edu/events/)

The configured source is **UPenn Handshake Hardware and IC Careers**. Penn is
the access institution, not the employer. Actual employer/location are taken
from posting details when available; missing facts remain unknown. Events are
reference links only, not job postings in SQLite.

## Student browser integration versus EDU API

The `handshake` adapter reads student pages in the existing Windows
JobApplyChrome session. It is **not an official API client**. It does not use
PennKey passwords, export cookies, call undocumented internal endpoints, or
submit applications. PennKey, Duo/MFA, first-login onboarding and challenges
must be completed by the user.

Handshake also offers an [official EDU API](https://support.joinhandshake.com/hc/en-us/articles/31061076506391-Getting-Started-with-EDU-API).
Its setup requires a developer account issued by Handshake Support, an approved
subscription and an enabled API key. A Penn student login is not that API
authorization. No institutional API access has been assumed or activated.

## Run

1. In JobApplyChrome, open the PennKey login link above and complete login.
2. Run `make workflow WORKFLOW=penn_refresh` from the project root.
3. Review the source's scan status and regenerated weekly report.

To collect only this source without rebuilding all reports:

```bash
python3 job_bot/bot.py scan --config job_bot/config.china_hk_ic_foreign.json \
  --source "UPenn Handshake Hardware and IC Careers"
```

It is also included in the normal daily/browser refresh and session audit.
It reads hardware, ASIC and RTL keyword searches via the verified `query` URL
parameter, waiting for the requested query and stable cards after asynchronous
loading. The total budget is shared across queries, with configurable page/job
limits, normalizes Handshake posting IDs, and uses existing filtering/scoring.
No institution or geography is fabricated from the Penn entry point. Existing
strategy rules still decide whether a job fits US Summer 2027 or China/HK.

`sync_active=false` is mandatory: bounded personalized search results are not
a complete inventory and cannot prove a missing job has closed. Login expiry,
browser challenges, unknown markup and broken pagination produce an error
rather than a successful empty scan. No other person's/browser agent's tabs
are navigated: the adapter uses `new_scan_page` and honors an explicitly owned
`JOBBOT_SCAN_TARGET_ID`.

## Validation

Unit tests cover routing, URL identity, missing facts, authentication boundaries,
asynchronous search stabilization, session audit, and scanner/config/workflow
behavior. A logged-out request must report `Handshake login required` rather
than a successful empty scan. Private run evidence belongs in
`private_data/outputs/job_bot/handshake_validation/` (`result.json` and
`completed_refresh.log`). This remains bounded student-website retrieval, not
institutional EDU API access or full coverage.

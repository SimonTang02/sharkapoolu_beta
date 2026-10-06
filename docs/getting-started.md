# Setup ownership and readiness

For everyday feature switches after setup, use the annotated
[`easy_settings.json` guide](beginner-settings.md). Its `jobbot-settings` entry
point compiles the current base config without changing existing advanced
configuration or browser progress; personal facts still need separate setup.

This guide describes what a fresh clone actually initializes, what needs
candidate input, and where an agent or developer can help. An agent is optional:
a technically experienced user can do the same configuration work. Candidate
confirmation and portal challenges cannot be replaced by inferred answers.

## What bootstrap completes

Read [AGENTS.md](../AGENTS.md) and [AGENT_HANDOFF.md](../AGENT_HANDOFF.md), then
follow [installation](installation.md). Bootstrap creates a virtual environment,
installs code, creates missing blank profile/evidence/keyword/credential files,
validates structure, and runs synthetic tests. It preserves existing files.
Blank required facts produce warnings; no-errors does not mean ready to apply.

Bootstrap does not create a populated resume, select suitable sources, tune
career preferences, initialize production job history, grant institutional
access, log in to employers, or configure SSH sharing, SMTP or a scheduler.
The optional browser install does not choose or authenticate a browser profile.
The shipped runtime currently selects Windows CDP; Linux-only users must
deliberately choose `local_persistent` in their private override.

## Who configures what

| Area | Existing input or tool | Agent/developer assistance | Candidate or operator must supply |
| --- | --- | --- | --- |
| Private storage and machine role | `JOBBOT_PRIVATE_DIR`, `private_paths.py`, `jobbot-private paths` | Select paths, permissions, backups and local/SSH role | Storage destination and authorized machines |
| Identity, education and dates | `profiles/application_profile.json` | Organize provided facts; check duplicates and formats | Legal identity, contacts, degree/GPA and confirmed graduation dates |
| Skills and evidence | `cv/profile/evidence_profile.json`, `application_keywords.json` | Map verified work to evidence groups, source IDs and keywords | Actual experience, source documents and explicit limits |
| Work permission, sponsorship and consent | Profile authorization and exact private answers | Preserve unresolved answers; check portal wording and location scope | Region-specific facts and each required policy decision |
| Career preferences and sources | Private `job_bot.local.json` overlays for `sources`, `scoring`, `strategy` | Translate preferences into consumed settings; disable unsuitable sources; preview a small run | Roles, regions, cycle, availability and exclusions |
| New regions, years or professions | Existing three strategy tracks and hardware classifiers | Adapt code and tests if existing tracks cannot express the preference | Desired scope and review of qualification rules |
| Institutional channels | Source definitions and session preflight | Configure a supported source or implement a new adapter | Legitimate account/access, login and MFA |
| Browser preparation | Browser extra, private `application_browser.mode`, `CHROME_CDP_URL` | Set up a dedicated profile, restricted CDP transport and routing | Login, CAPTCHA, MFA, recovery and policy choices |
| LaTeX materials | Private `cv/source/current.tex`, shared `cv/latex/`, `cvbot` | Convert verified content to the expected layout, configure TeX, fix rendering | Approved claims, language, source material and final PDF review |
| Manual HTML kit | `applybot manual-kit`, reviewed manifest and role `Application_Data.json` | Assemble factual answers, official URLs, PDF review hashes and attachments; render a new kit | Reviewed targets, approved PDFs and actual supporting documents |
| Portal-specific preparation | Queue, batch, login-preflight and supported dispatcher | Learn the first real form; configure exact options or implement missing behavior | Unknown mandatory answers, limits and per-company consent |
| Shared database | `jobbot-db configure`, `prepare-host`, `check` | Verify roles, deduplicate histories, prepare backups and SSH routing | Authorized host, existing SSH access and online availability |
| Reports and SMTP | Workflow preview, weekly report, private `email` settings | Configure timezone/recipients and inspect dry-run output | Private credentials and explicit send authorization |
| Recurring runs | Existing CLI plus OS scheduler | Create and verify scheduler/environment setup when requested | Desired timing and delivery authorization |
| Continuation and submission records | Private handoff, manifest, progress export, `mark_submitted.py` | Match ranks/URLs, query the authoritative DB, record confirmed outcomes | Active job, actual receipt or explicit success confirmation |

## Important implementation limits

`career_preferences` records intent. Arbitrary extra preference keys are not
automatically consumed by every command. The strategy report currently builds
three named queues: China/Hong Kong campus, US new graduate, and US summer
internship. It uses hardware-oriented patterns and recruiting-year logic.
Adding another JSON track or geography label alone does not add its collector
or report branch. Trace the consumer before claiming coverage.

The authorization validator has first-class scopes for mainland China, Hong
Kong and the United States. Other regions require preserved, explicitly
confirmed private answers and portal-specific review; adding a country to an
address field does not establish its work authorization.

The legacy full-time bundle entry points request a fixed graduation date
override in `cv/bot/bot.py` and `application_bot/batch_campaign.py`. Before using
them for a different candidate or date, an agent or developer must adapt this
behavior to the confirmed private evidence profile and test the rendered date.
A structurally valid profile alone does not fix this legacy override. Do not
run material generation over an approved bundle.

The standard HTML generator consumes an already assembled manifest and each
role's `Application_Data.json`. It is not yet a one-command conversion from
`batch_campaign.py` output. It verifies declared passed PDF review and hashes,
but cannot perform that visual review or establish factual accuracy. Transcript
official/unofficial labels and employer requirements still need review. Public
example values never establish candidate eligibility.

Database sharing routes SQL to one online host. It does not sync private files,
browser sessions or unsaved forms; there is no offline write/merge system.
Use [the shared-database guide](shared-database.md) for migration and updates.

## A bounded first run

1. Choose one stable private root; create and validate blank files. Record facts
   and unresolved questions before enabling application work.
2. Create a private runtime override from `examples/job_bot.local.json`. Its
   include path assumes the in-repository private layout; adjust that include
   and `database.path` for an external root. Validate the composed file.
3. Choose suitable sources and a supported strategy scope. Preview a small
   HTTP-only workflow; check actual results and failures before expanding it.
4. Initialize the intended database and run the reviewed workflow. In shared
   mode, confirm that the host owns the only authoritative history first.
5. Prepare a reviewed private resume and evidence profile. Learn one employer's
   current form before preparing a batch. Keep final-submit guards false.
6. Choose manual HTML delivery or supported agent-assisted form preparation.
   Review the actual portal and submit personally; then record the confirmed
   submission.

Commands accepting `--config` must receive the same private override. The
Makefile's daily/weekly defaults do not automatically load arbitrary private
settings. For example, after reviewing source selection:

```bash
jobbot-config --config private_data/config/job_bot.local.json
python3 job_bot/run_modules.py --config private_data/config/job_bot.local.json \
  --workflow http_refresh --dry-run
```

## Start a new agent conversation

A fresh clone describes tools and configuration contracts. It cannot recover
private application history or browser-local progress from public templates.
For an existing installation, read current canonical private files and the
latest private continuation record after the repository contracts.

Each newly rendered manual kit includes its own `AGENT_HANDOFF.md`: bundle
directory, original target count, manifest fingerprint, progress-key prefix and
receipt rules. Its dashboard links that file and offers a copyable continuation
prompt. An agent can use those pointers without old chat history, but must
obtain the active job/export/receipt before treating progress as known. It must
not replay old cleanup or material-generation steps.

Existing delivered bundles are not modified to add this feature. Keep their
entry file address and localStorage keys, and use their existing private
handoff. Only official receipt evidence or explicit success confirmation
authorizes a new `submitted` record; progress exports do not automatically
synchronize the database.

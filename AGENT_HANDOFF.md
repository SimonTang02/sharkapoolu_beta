# Sharkapoolu agent handoff

This is the short entry point for a new conversation. Read `AGENTS.md`, identify
what the user wants, then open only the relevant references below. English is the
development upstream; the Chinese edition is maintained separately. Public docs
contain operating contracts, not a candidate's application history.

## Start here

From the project root, inspect `git status --short --branch`, `git remote -v`,
`python3 --version`, and `python3 -m job_bot.private_config paths`. Determine the
platform, private root, active config, database role, current campaign and existing
changes. Read the latest private task handoff and actual receipts before acting.
Do not reset Git, reinitialize profiles, replace databases or replay old tab cleanup.

| Task | Read |
| --- | --- |
| First installation / nontechnical users | [getting started](docs/getting-started.md), [beginner guide](docs/foolproof_guide.md), [platforms](docs/platforms.md) |
| Original PDF/TXT/LaTeX and candidate facts | [onboarding](docs/candidate-onboarding.md), [examples](examples/README.md) |
| Mode, modules, regions, review rounds | [beginner settings](docs/beginner-settings.md) and private `config/easy_settings.json` |
| Sources, scoring, eligibility, workflows | [configuration](docs/configuration.md), [job bot](job_bot/README.md) |
| Resume/letter tailoring and PDF review | [CV bot](cv/bot/README.md), [CV workspace](cv/README.md) |
| Forms, batches, login, tabs, manual HTML | [application bot](application_bot/README.md) |
| Manual jobs/application records | [manual database](docs/manual-database.md) |
| SSH shared database, backup and recovery | [shared database](docs/shared-database.md) |
| Public changes and releases | `AGENTS.md`, [release guide](docs/GITHUB_RELEASE.md) |

## Installation and private state

Recommended desktop setup is Windows + WSL2 + VS Code. Linux, macOS and native
Windows differences are in the platform guide. An agent alone does not install
Git, Python, browser or TeX dependencies automatically.

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
jobbot-private check
make config-check
```

Add `--with-browser` for browser tasks and `--with-resume` for PDF text parsing.
PDF compilation separately needs a TeX distribution, `latexmk`, a supported engine
and fonts. Inspect existing files before bootstrap; never use `init --force` on
real data. Empty-template checks are not candidate eligibility or readiness.

Use only `private_paths.py` to resolve private paths. Set `JOBBOT_PRIVATE_DIR`
before initialization and retain it in later commands when using an external root.

- `profiles/application_profile.json`: factual form answers, explicit permissions,
  documents and career/length preferences.
- `cv/profile/evidence_profile.json`, `fact_ledger.json`, `application_keywords.json`:
  evidence, confirmed statement references and supported keywords.
- `config/job_bot.local.json`, `easy_settings.json`, `database_connection.json`:
  explicit runtime overlay, beginner settings and local/SSH database mode.
- `cv/source`, `cv/variants`, `database`, `browser`, `outputs`: private originals,
  generated material, DB, sessions and audit artifacts. Keep them out of Git.

Commands supporting `--config` must receive the intended private overlay. Merely
saving a setting does not make every old entry point consume it. Validate composed
config and preview workflows before running. The default domain is hardware;
a new candidate must review sources, scoring, eligibility and recruiting dates.
Scores are relevance, not eligibility. Never infer authorization or consent from
school, location, nationality, keywords or default booleans.

## Resume generation: current behavior

Project-level tailoring uses optional `evidence_profile.resume_content` and a
confirmed ledger. Single-job and batch generation share `write_bundle`.
`fact_ids` must resolve to current `user_confirmed` textual statements with source
hashes and dated confirmation. Missing, unresolved or superseded facts stop the
structured build. An agent/person must still check the meaning, personal/team
contribution and completion state; record validation is not proof of truth.

The planner ranks projects by title/JD relevance, deduplicates facts and selects
content within the resolved page budget. Resume and cover letter use the same
selected statements. Without `resume_content`, old sources remain limited drafts
marked `legacy_source_requires_fact_migration`; they do not gain project tailoring.

Length comes from `career_preferences.resume_language_policy`: default two pages;
company exceptions require explicit pages, HTTPS evidence, kind/scope and check
date. Do not pad sparse evidence or invent results. Candidate policy and actual
PDF pagination are separate checks. Use the fictional structured examples only
for learning; never promote example facts into a real candidate profile.

```bash
cvbot --job-description PRIVATE_JD --company COMPANY --role ROLE \
  --profile PRIVATE_EVIDENCE --fact-ledger PRIVATE_LEDGER \
  --application-profile PRIVATE_APPLICATION --resume-source PRIVATE_TEX \
  --generate-bundle --bundle-dir NEW_PRIVATE_DIRECTORY
cvbot verify-bundle PRIVATE_BUNDLE/manifest.json
```

Batch/default ledger: `private_data/cv/profile/fact_ledger.json`. New bundles reject
existing directories. The manifest binds source, supplied profile/ledger/JD files,
templates/generator/bibliography and output hashes. Pass external fonts/images as
`input_paths` when using the Python API. Requery database JDs separately.
Fingerprint verification means fresh files, not approval. Operator review and
manual-kit export recheck adjacent versioned manifests; do not strip provenance.

Check identity, dates, text extraction, page count, overflow, missing glyphs and
**every rendered page**. Install the PDF extra for automatic text identity checks;
without it identity remains unknown. Content, rendered-page and candidate reviews
start pending. Headings, dates and untouched education/other sections still need
factual review. Changing facts, sources, templates or PDFs requires affected
reviews again. Preserve historical submitted attachments.

## Jobs, forms and progress

Preview scans with `make workflow-plan WORKFLOW=http_refresh`; pass the same
private config to execution. Record failed sources separately; partial scans must
not deactivate unseen jobs. Do not send configured email without authorization.

Use a dedicated local browser profile or restricted Windows CDP connection.
Login/MFA/CAPTCHA stay manual. Recheck session and portal support; a browser health
check does not prove login or adapter readiness. Preserve populated forms,
registered applications and tenant login anchors; never export cookies/storage.

`applybot dispatch` plans by default; `--execute` prepares supported forms up to
review. Keep adapter `auto_submit` / `allow_submit` flags false; final submission
follows the current user authorization and repository contract. Uploads, drafts
and review pages are not successful submissions. Record `submitted` only from an
official receipt or explicit user confirmation, using the existing registration
workflow and duplicate/limit checks.

`applybot manual-kit` packages reviewed PDFs into a **new** private directory,
preserving original targets/order and a stable progress key. Browser progress is
origin/profile-specific; read an exported progress file or actual receipts, never
reset it or infer batch progress from total database submissions.

## Shared DB and closing a session

Use `job_bot.shared_database.connect` / `jobbot-db`, not raw SQLite on a stale
client file. Verify connection mode, host, project and canonical database path.
Missing/failed SSH is not permission to fall back to a local production DB. Back
up active SQLite with Backup API, not by copying live DB/WAL files. Detailed
configuration, transaction and restore procedures live in the shared-DB guide.

Before a public commit/push, run `make release-check`, `make history-audit`,
`make private-check` when available, and `git diff --check`; inspect the exact
staged files. Never stage private outputs, PDFs, credentials, browser state or DBs.
Finish with a short private handoff: actual changes/checks, current campaign and
receipts, unresolved facts, exact artifact paths and next action. Replace stale
summaries with current evidence; retain old history in an archive, not the startup
reading path.

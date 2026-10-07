# Sharkapoolu

An agent-driven toolkit for job discovery, tailored resumes, and application tracking.

New users and coding agents: start with the complete
[operating and handoff guide](AGENT_HANDOFF.md) and
[setup ownership and readiness guide](docs/getting-started.md), then the
[commented public templates](examples/README.md), including a fictional
Mike Malon / NYU Computer Science resume and the shared-database settings.

Sharkapoolu is a local-first toolkit for job discovery, ranking, resume
tailoring, and review-assisted application preparation. It was built around
hardware and digital-design recruiting, but its source and scoring layers are
configurable. Candidate data stays outside the public Git history, and every
final application submission remains a human action.

## Key features

- **Resume onboarding and manual records.** Import an original PDF, text or
  LaTeX resume into a private review packet with an editable draft and Agent
  instructions for answers, evidenced keywords and scoring. UTF-8 CSV supports
  manually maintained jobs and confirmed application history with transactional
  import. Start with [candidate onboarding](docs/candidate-onboarding.md) and
  the [Windows + WSL2 + VS Code platform guide](docs/platforms.md).
- **Beginner controls in one file.** A Chinese annotated settings file selects
  modules, regions, HTTP or isolated-browser collection, CDP preparation,
  review rounds, time budgets and retries. `jobbot-settings` checks and previews
  changes before explicit execution. See [the beginner guide](docs/beginner-settings.md).
- **Two application workflows.** Manual delivery provides an offline HTML
  dashboard, per-job copyable answers, reviewed PDF and supporting-document
  links, receipt notes, and browser-local progress export. Agent-assisted
  preparation provides queues, explicit batches, ATS routing, and supported
  form filling up to human review. Both workflows leave final submission to
  the candidate; queueing, uploading, or reaching Review is not a submission.
- **Preference-based discovery and review.** Collect and normalize jobs from
  HTTP feeds, career APIs, and authorized browser sessions. Configure source
  selection, role keywords, score weights and the implemented region/degree/
  recruiting-cycle filters. Eligibility and work permission still require
  evidence and candidate confirmation. Adding new regions, years or job
  families may require adapting the current hardware-focused strategy code.
- **One application history across machines.** SQLite stores postings and
  application events. Optional authenticated SSH lets clients operate one
  host's private database without a database listener. Machines must be online;
  browser sessions, PDFs and progress exports are not automatically synced.
  See [the sharing contract](docs/shared-database.md).
- **Evidence-grounded materials.** `cvbot` selects supported evidence and
  keywords from a private profile, produces tailoring notes, and can render
  LaTeX resume and cover-letter PDF bundles with a configured TeX toolchain.
  Rendered PDFs need review; the generator does not create new qualifications.
- **Personal customization with private storage.** Identity, evidence,
  keywords, credentials, sessions, receipts and generated materials stay in a
  candidate-owned private tree. Public templates use blank or fictional data;
  configuration and privacy audits report structure without printing values.
- **Dedicated browser session and tab management.** Supported paths use a
  separate Chromium profile or restricted Windows Chrome CDP. Session audits,
  login preflight and audited tab cleanup preserve active application forms
  and authentication anchors. MFA, CAPTCHA and policy choices stay manual;
  persistent profiles do not guarantee that a login remains valid.
- **Reports and optional notifications.** Generate daily, weekly and strategy
  review reports. SMTP delivery requires explicit private configuration and
  authorization; dry-run is the default. Recurring execution requires a
  separately configured scheduler.
- **New-conversation handoffs.** Every newly rendered manual kit includes a
  campaign handoff, manifest fingerprint and copyable continuation prompt.
  A new agent can discover the files and operating rules without old chat
  history; actual progress still comes from current private records, the
  user's export and receipts.

## Quick start

Python 3.10 or newer is required.

```bash
git clone git@github.com:SimonTang02/sharkapoolu_beta.git
cd sharkapoolu_beta
./scripts/bootstrap.sh
source .venv/bin/activate
```

The bootstrap script creates `.venv`, installs the package, creates ignored
private configuration files from safe examples, validates them, and runs the
test suite. A passing blank-template check is not application readiness.
Fill the generated files under `private_data/`, then validate again:

```bash
jobbot-private check
jobbot-config --config job_bot/config.china_hk_ic_foreign.json
```

For browser-assisted collection and form preparation:

```bash
./scripts/bootstrap.sh --with-browser
sudo .venv/bin/python -m playwright install-deps chromium  # Linux only, if needed
```

See [installation](docs/installation.md) for Windows CDP, TeX, encrypted data,
and update instructions. See [who configures what](docs/getting-started.md)
before collecting or applying: bootstrap does not populate candidate facts,
choose sources, create a LaTeX CV, log in to portals, or assemble a manual kit.

## Repository layout

```text
application_bot/   Browser session checks and review-assisted form adapters
cv/                Resume evidence, keyword, and document-generation code
docs/              Installation, architecture, configuration, and interfaces
examples/          Redacted templates copied into the private data tree
job_bot/           Discovery, normalization, scoring, database, and reports
schemas/           JSON Schemas for candidate-maintained private files
scripts/           Bootstrap, privacy audit, and release utilities
private_data/      Ignored identity, credentials, sessions, databases, and output
```

## Common commands

| Command | Purpose |
| --- | --- |
| `make private-init` | Create missing private templates without overwriting files |
| `make private-check` | Check private structure, cross-file consistency, and permissions |
| `make config-check` | Resolve includes and validate the effective public config |
| `make daily` | Collect, rescore, and write daily and weekly reports |
| `make weekly` | Rebuild the weekly report from SQLite |
| `make session-audit` | Check configured login sessions without exposing credentials |
| `applybot manual-kit --manifest <private-manifest> --output <new-private-directory> --progress-key <stable-prefix>` | Render a reviewed offline manual kit with a new-conversation handoff |
| `make workflow-plan WORKFLOW=http_refresh` | Preview a named modular workflow |
| `make workflow WORKFLOW=http_refresh` | Run a named modular workflow |
| `make test` | Run unit tests |
| `make release-check` | Audit publishable files, test, and validate config |

The installed command-line entry points are `jobbot`, `applybot`, `cvbot`,
`jobbot-config`, `jobbot-private`, and `jobbot-db`.

## Configuration model

Versioned configuration under `job_bot/config/` defines runtime behavior,
sources, scoring, strategy, workflows, portal adapters, and field mappings.
Ignored files under `private_data/` hold identity, evidence, keywords,
credentials, browser state, application artifacts, and databases. Set
`JOBBOT_PRIVATE_DIR` to relocate the entire private tree to an encrypted disk or
private synced directory. A wheel installation defaults to the platform data
directory instead of writing inside `site-packages`.

Start with [configuration.md](docs/configuration.md). The repository-level
[AGENTS.md](AGENTS.md) gives coding agents the complete operating contract,
including safety rules, command selection, and extension points.

## Safety and privacy

- Never commit `private_data/`, resumes, cookies, tokens, screenshots, or local
  databases.
- Legal authorization, sponsorship, demographic, and declaration answers must
  come from explicit candidate input.
- Automation may prepare and save a draft only when its separate safety gate is
  enabled. It must never click the final Submit control.
- Run `make public-audit` before publishing. Use `make history-audit` when an
  older Git history may have contained personal files.

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability or suspected
data exposure. Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

# Repository operating contract

This file applies to the whole repository. It is the working contract for
coding agents and contributors. Read it before changing code, configuration,
tests, browser behavior, or release files. More detail is available in
[`docs/architecture.md`](docs/architecture.md),
[`docs/interfaces.md`](docs/interfaces.md),
[`docs/installation.md`](docs/installation.md), and
[`SECURITY.md`](SECURITY.md).

## Mission and boundaries

Sharkapoolu is a local-first toolkit for:

1. collecting and normalizing job postings;
2. scoring and prioritizing roles with configurable policy;
3. producing daily and weekly reports from a local SQLite database;
4. preparing evidence-grounded resume and cover-letter material; and
5. assisting with application forms up to a human review checkpoint.

The public repository contains reusable code, redacted examples, schemas, and
shared policy. Candidate identity, credentials, browser state, application
answers, resumes, databases, screenshots, and generated reports are private
runtime data. Final application submission is a human action and is outside the
automation boundary.

## Safety invariants

These rules are requirements, not preferences:

- Keep every real candidate value out of public code, examples, fixtures,
  documentation, logs, errors, Git history, and delegation prompts. Use
  synthetic values such as `Example Company` in tests.
- Store private material only below the root resolved by `private_paths.py`.
  Do not construct an alternate private path inside feature modules.
- Never print, copy, export, or record passwords, cookies, tokens, browser
  storage, password-manager values, or full private profile fields.
- Resume and application claims must be supported by the evidence profile.
  Do not infer proficiency, duration, GPA, identity, personality ratings, or
  other candidate facts from a job description.
- Legal authorization, sponsorship, immigration, demographic, consent,
  declaration, compensation, and location-scoped answers require explicit
  candidate input. Preserve `null` or an unresolved state when confirmation is
  absent or conflicting.
- `application_browser.auto_submit`,
  `field_mappings.safety.allow_submit`, and
  `application_profile.safety.allow_submit` must remain `false`. No adapter may
  activate a final Submit control.
- Server-side draft saving requires both an explicit local safety flag and an
  explicit command option. A draft authorization does not authorize final
  submission or another campaign.
- CAPTCHA, MFA, Windows Hello, account recovery, policy review, and ambiguous
  required questions remain manual checkpoints. Do not bypass or automate
  them.
- Use a dedicated browser profile for browser automation. Never expose a CDP
  debugging endpoint to the LAN, reuse the everyday personal browser profile,
  or export its authentication state.
- Browser tab cleanup must preserve populated forms, registered application
  tabs, and authenticated tenant anchors. Capture the configured audit artifact
  before an allowed close.
- Network collectors must use bounded timeouts, pagination, concurrency, and
  retries. Do not evade access controls or treat anti-bot failures as empty
  successful snapshots.
- Only mark missing jobs inactive when `sync_active` is justified by a complete
  successful source snapshot and the lifecycle guard accepts it.
- Durable outputs belong below the private root. Public tests must use
  deterministic synthetic fixtures and must not require network access or real
  accounts.
- Do not push, publish, deploy, submit applications, send email, or alter
  external accounts unless the current task explicitly authorizes that action.

If a requested change conflicts with an invariant, keep the invariant and
explain the conflict. A feature request is not implicit permission to expose
private data or weaken a submission guard.

## Repository map

| Path | Responsibility |
| --- | --- |
| `job_bot/` | Source collection, normalization, SQLite storage, scoring, strategy, reporting, workflow runner, and compatibility application code |
| `job_bot/sources/` | Reusable public/API, HTML/feed, campus, and third-party source adapters |
| `job_bot/applications/` | Shared or compatibility ATS application mechanics |
| `job_bot/config/` | Canonical composed public configuration |
| `job_bot/source_lists/` | Public source rationale and setup notes |
| `application_bot/` | Session checks, portal routing, tab management, artifacts, and review-assisted form adapters |
| `cv/` | Evidence-backed keyword selection, CV/cover-letter bundle logic, and shared LaTeX resources |
| `examples/` | Redacted templates copied into the ignored private tree |
| `schemas/` | JSON Schemas for candidate-maintained private JSON files |
| `scripts/` | Bootstrap, privacy/release audits, snapshot export, and local support scripts |
| `docs/` | Architecture, interfaces, installation, privacy, and release guidance |
| `private_paths.py` | The sole canonical map from code to candidate-owned storage |
| `private_data/` | Ignored local data; only `private_data/README.md` may be tracked |
| `Makefile` | Stable development, workflow, CV, audit, and release commands |
| `pyproject.toml` | Package metadata, Python requirement, optional dependencies, and CLI entry points |

Compatibility entry points may remain while callers migrate. Do not remove an
older command or wrapper without checking its tests, README examples, workflow
definitions, and downstream imports.

## Public configuration

`job_bot/config/jobbot.json` is the canonical public composition root. It
includes the following files in order:

| File | Owns |
| --- | --- |
| `runtime.json` | Database path; scan concurrency, retry, and lifecycle guard; browser transport; tab policy; digest filters; reporting timezone; email delivery settings |
| `workflows.json` | Named module sequences, source selectors, failure policy, worker overrides, and experiment-manifest behavior |
| `sources.json` | Source endpoints/identifiers, adapter type, company, categories, pagination, role kinds, filters, active-sync policy, and enablement |
| `scoring.json` | Broad retrieval relevance: scoring algorithm, bands, foundations, evidence modifiers, and keyword groups |
| `strategy.json` | Narrow campaign eligibility and priority: tracks, geography, graduation/degree/seniority gates, thresholds, patterns, and ranking modifiers |
| `portals.json` | ATS recognition, session audit probes, company portal profiles, adapter routing, timeouts, environment-file options, and draft capability |
| `penn_channels.json` | Public campus-channel definitions and campus-employment reporting rules |
| `field_mappings.json` | Logical form-field mappings, document mappings, regional answer policy, and no-submit safety policy |

`job_bot/config.china_hk_ic_foreign.json` is the compatibility wrapper around
the canonical composition. `job_bot/config.example.json` and
`job_bot/config.example.toml` demonstrate smaller standalone configurations;
they are examples rather than the authoritative production shape.
`job_bot/env.template` contains names and empty placeholders only.

Public configuration may include public endpoints, board identifiers, regular
expressions, ranking policy, generic environment-variable names, and safe
defaults. It must not contain candidate contact details, private institutional
URLs, credentials, browser exports, application answers, or machine-specific
absolute paths.

Configuration composition is deterministic:

1. Resolve `includes` relative to the file that declares them.
2. Merge includes in listed order.
3. Merge mappings recursively; later scalars and lists replace earlier ones.
4. Apply the including file as the final overlay.
5. Apply `patches` afterward.

Use a patch when changing one named list item. A patch must match exactly one
item. Use `$append`, `$remove`, or `$replace` for intentional list changes.
Never duplicate the full source or scoring file to tune one value. Validate
every public or private overlay with:

```bash
jobbot-config --config path/to/config.json
```

Scoring and strategy serve different decisions. Scoring asks whether a posting
is broadly relevant and writes `jobs.fit_score`. Strategy applies candidate and
campaign eligibility before queue priority. A scoring keyword must not silently
bypass a strategy exclusion.

## Private configuration and data

Set `JOBBOT_PRIVATE_DIR` before the first private-data command to relocate the
entire private tree to encrypted or separately backed-up storage. Otherwise the
default is `private_data/` inside the clone. All code must import paths from
`private_paths.py`; add new canonical constants there when introducing a new
private artifact class.

The maintained private inputs are:

| Path below the private root | Purpose | Public contract |
| --- | --- | --- |
| `credentials/passport.env` | Optional credentials, session headers, storage-state paths, CDP URL, and mail environment values | Start from `job_bot/env.template`; consume values without printing them; file mode must be `600` |
| `profiles/application_profile.json` | Identity fields, documents, education, experience, projects, skills, custom answers, explicit authorization, career preferences, and safety gates | Template: `examples/application_profile.json`; schema: `schemas/application-profile.schema.json` |
| `cv/profile/evidence_profile.json` | Verified identity linkage, graduation facts, summaries, GPA map, and claim evidence groups | Template: `examples/evidence_profile.json`; schema: `schemas/evidence-profile.schema.json` |
| `cv/profile/application_keywords.json` | Evidence-scoped technical and collaboration labels plus role presets and provenance | Template: `examples/application_keywords.json`; schema: `schemas/application-keywords.schema.json` |
| `config/job_bot.local.json` | Machine paths, source enablement, browser selection, report routing, and other non-secret local overrides | Start from `examples/job_bot.local.json`; keep secrets in `passport.env` |

Other private state includes:

- `database/`: SQLite job, scan, application, and tab state;
- `browser/state/` and `browser/profiles/`: authenticated browser material;
- `outputs/job_bot/` and `outputs/application_bot/`: reports and artifacts;
- `cv/source/`, `cv/build/`, `cv/variants/`, and `cv/reports/`: source and
  generated candidate documents.

Create missing templates without replacing existing files and validate them:

```bash
make private-init
make private-check
jobbot-private paths
```

Do not use `jobbot-private init --force` unless the task explicitly requires
replacing local candidate files and a backup exists. Directory permissions
should be `700`; credential and maintained profile files should be `600`.
Validation and diagnostics may report paths, key names, counts, and status, but
not candidate values.

## Fresh-clone installation

On a new Linux or WSL machine, install Git, Python 3.10 or newer, and the Python
`venv` package first. On Ubuntu/Debian the missing-venv repair is normally:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
```

Then clone and bootstrap:

```bash
git clone git@github.com:SimonTang02/sharkapoolu_beta.git
cd sharkapoolu_beta
./scripts/bootstrap.sh
source .venv/bin/activate
```

Use `./scripts/bootstrap.sh --with-browser` when the task needs Playwright. On
Linux, install its system libraries with the explicit administrator command
printed by the script. A headless server does not need TeX or browser packages
for core collection, scoring, reports, and tests. Install a TeX distribution
only for local PDF rendering.

Choose `JOBBOT_PRIVATE_DIR` before bootstrap when private data will live outside
the clone. Restore that directory only from an encrypted, separately authorized
backup; a public-code clone never contains candidate data. After restoration,
run `jobbot-private check` before any collector, CV, or application command.
Copying private data between machines is a separate sensitive operation and is
not implied by permission to clone or update the public repository.

For repository updates, use `git pull --ff-only` followed by the same bootstrap
script. Never solve an update conflict by deleting or overwriting the private
root.

## Commands and side effects

Run commands from the repository root. Prefer installed entry points after
bootstrap; direct `python3` entry points remain useful in development.

### Setup and validation

```bash
./scripts/bootstrap.sh                 # core editable install, templates, validation, tests
./scripts/bootstrap.sh --with-browser  # also install Playwright and Chromium
source .venv/bin/activate
make private-check
make config-check
make test
```

`bootstrap.sh` is idempotent and preserves existing private files. Use
`--skip-tests` only for a short repair at a revision whose tests already passed.

### Job discovery and reports

| Command | Effect |
| --- | --- |
| `jobbot init --config <config>` | Initialize the private SQLite schema |
| `jobbot scan --config <config>` | Fetch selected sources and update the database |
| `jobbot rescore --config <config>` | Recompute stored broad-relevance scores |
| `jobbot auth-status --config <config> --env-file <private-env>` | Report configured session coverage without values |
| `jobbot digest --config <config> --print` | Build a digest from stored jobs |
| `jobbot run --config <config>` | Scan and then build/send the configured digest |
| `make daily` | Run the complete daily pipeline |
| `make weekly` | Rebuild the weekly report from SQLite |

Narrow a scan with exact source names, company, source category, source type,
or browser transport instead of disabling unrelated sources globally. An HTTP
scan and a CDP-backed scan have different prerequisites; do not silently switch
transport when one fails.

Named workflows provide the reproducible module interface:

```bash
make workflow-plan WORKFLOW=http_refresh
make workflow WORKFLOW=http_refresh
python3 job_bot/run_modules.py --module weekly --config <config>
```

Always preview a new or materially changed workflow first. Run manifests are
private outputs and contain the effective-config hash, selected modules,
commands, durations, and return codes. They must never contain credential
values.

### CV and application preparation

```bash
cvbot --job-description <synthetic-or-private-file> \
  --company <company> --role <role>
applybot list
applybot keywords --role <role>
applybot session-audit
applybot login-preflight --campaign-id <id>
applybot dispatch --application-id <id>       # plan only
applybot dispatch --application-id <id> --execute
```

`dispatch` plans by default. Browser execution may open or reuse a dedicated
tab, fill approved fields, upload a specifically selected reviewed document,
and write private artifacts. It must stop at unresolved questions and before
final submission. Run login/session preflight before opening many application
tabs.

Use `prepare-profile` to bind reviewed documents to one application. Inspect a
rendered PDF and its manifest before allowing upload; successful compilation
alone is not review. Resume entry points live under the private root and use
shared classes/styles from `cv/latex/`:

```bash
make check-tools
make current
make visa
```

Commands that only validate, plan, score, or report are preferred before
commands that access the network, open a browser, save a server-side draft,
send mail, or mutate application state.

## Code interfaces and extension points

### Configuration and paths

- Load composed JSON through `job_bot.config_loader.load_composed_config` or the
  established `job_bot.bot.load_config` wrapper, then call
  `validate_config`. Do not implement a second merge algorithm.
- Resolve candidate-owned files only through `private_paths.py`.
- Keep optional integrations optional. Importing the package and running the
  core tests must not require network access, a browser, private data, or a
  proprietary SDK.
- New CLI operations that can write remotely, open many tabs, or alter
  application state need a plan/dry-run form first and a nonzero exit status on
  required-operation failure.

### Source adapters

- Declare each source in `job_bot/config/sources.json`; route its `type` to a
  collector in `job_bot` or `job_bot/sources/`.
- Return a stable URL and title. Include company, location, description,
  publication date, source name, and `role_kind` when available.
- Tolerate absent optional fields, bound pagination, apply configured filters,
  and record a source failure rather than fabricating postings.
- Add a deterministic fixture test for parsing, pagination, normalization,
  filtering, authentication absence, and failure behavior as applicable.
- An environment-variable name may reserve future authentication support; its
  presence in config does not imply that an adapter exists.

Reserved source interfaces include new `sources[].type` values, company or
platform credential namespaces, public API/HTML/feed/CDP transports, source
categories, workflow selectors, and notification sinks.

### Application adapters

- Register generic ATS routing and company-specific behavior in
  `job_bot/config/portals.json`. ATS mechanics may be shared, while field
  enumerations, consents, required sections, and limitations belong to the
  company profile.
- Use the shared portal registry, dispatcher, tab registry/manager, and artifact
  helpers. Resolve a resumed application by durable application identity and
  fingerprint; a CDP target ID alone is temporary.
- Probe login state without recording field or cookie values. Own only
  automation-created tabs and close temporary probes.
- Treat the first application for a company profile as a template-learning run
  requiring review. Do not generalize employer-specific questions from another
  tenant on the same ATS.
- Add mocked, deterministic tests for routing, unresolved questions, safety
  gates, tab preservation, and artifacts. Tests must prove the final-submit
  control is never invoked.

Reserved adapter hooks include session probes, draft support, environment-file
options, per-portal timeouts, generic host-suffix routing, alternate isolated
browser transports, and new ATS implementations.

### Candidate profiles and model-assisted features

Profile consumers should accept additive optional fields, reject incompatible
types, and use stable IDs when linking evidence or keywords. Update the example,
schema, semantic validator, docs, and tests together when changing a maintained
profile contract.

An optional model service may propose ranking or wording changes, but the local
evidence profile and validators remain authoritative. Generated prose cannot
create new candidate facts. Store prompts and outputs privately when they
contain job descriptions or candidate material.

## Development workflow

1. Inspect `git status` and the relevant docs/config/tests before editing.
   Preserve unrelated user work and do not reformat broad areas incidentally.
2. Identify whether the change touches public policy, private contracts,
   network collection, browser/application state, or release safety.
3. Prefer the smallest established interface. Add a new abstraction only when
   an existing extension point cannot express the behavior.
4. For config changes, validate the composed result and inspect the effective
   source/workflow summary. For workflows, run the plan form first.
5. Run focused deterministic tests while iterating, then the required release
   checks below.
6. Review the publishable file list before committing. Never stage private or
   generated material.

Use Python 3.10-compatible syntax and the standard library unless a dependency
provides clear value. Put runtime dependencies and optional groups in
`pyproject.toml`; update bootstrap and CI behavior when needed. Prefer
`pathlib.Path`, explicit timeouts, stable identifiers, structured JSON, atomic
private-output writes, and actionable errors that omit values.

## Testing and release standard

Tests use `unittest` discovery:

```bash
python3 -m unittest discover -s . -p 'test_*.py'
make test
```

Add focused tests for every behavior change that affects parsing, selection,
scoring, config composition/validation, profile validation, routing, safety
gates, lifecycle changes, or output contracts. Avoid tests that merely repeat
implementation details. Unit tests must use synthetic local fixtures and mock
network/browser boundaries.

Before a pull request, public commit, tag, or snapshot, run:

```bash
make release-check
make private-check        # when a local private tree is available
git diff --check
git status --short
git ls-files --cached --others --exclude-standard
```

`make release-check` runs the publishable-tree privacy audit, all unit tests,
and shared config validation. CI must be able to run it from a fresh clone with
no secrets and no private candidate files. If the repository has older commits
or may ever have tracked sensitive material, also run:

```bash
make history-audit
```

Deleting a file in the current tree does not remove it from Git history. Rotate
any exposed credential first, then use the reviewed clean-snapshot or history
rewrite process in [`docs/GITHUB_RELEASE.md`](docs/GITHUB_RELEASE.md). Do not
publish a historical repository merely because the current-tree audit passes.

The public audit must continue to reject private-tree contents, credential-like
filenames, databases, rendered PDFs, archives, browser state, private keys,
known token shapes, local absolute paths, symlinks, unexpected large files, and
candidate markers. Do not weaken an audit to make a release pass; move or redact
the offending data and add a regression test when appropriate.

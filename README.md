# Sharkapoolu

New users and coding agents: start with the complete
[operating and handoff guide](AGENT_HANDOFF.md) and
[commented public templates](examples/README.md), including a fictional
Mike Malon / NYU Computer Science resume and the shared-database settings.

Sharkapoolu is a local-first toolkit for job discovery, ranking, resume
tailoring, and review-assisted application preparation. It was built around
hardware and digital-design recruiting, but its source and scoring layers are
configurable. Candidate data stays outside the public Git history, and every
final application submission remains a human action.

## Features

- Collect and normalize jobs from HTTP feeds, career APIs, and authenticated
  browser sessions.
- Score roles with configurable evidence, geography, degree, and role rules.
- Generate daily and weekly reports from a local SQLite database.
- Share the private SQLite database between online WSL machines over SSH; see
  [setup and operating limits](docs/shared-database.md).
- Build resume-tailoring notes from an evidence profile and keyword library.
- Prepare supported application forms in a dedicated browser and stop for
  review before submission.
- Validate public configuration and private candidate files without printing
  secret or personal values.

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
test suite. Fill the generated files under `private_data/`, then validate again:

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
and update instructions.

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
| `make workflow-plan WORKFLOW=http_refresh` | Preview a named modular workflow |
| `make workflow WORKFLOW=http_refresh` | Run a named modular workflow |
| `make test` | Run unit tests |
| `make release-check` | Audit publishable files, test, and validate config |

The installed command-line entry points are `jobbot`, `applybot`, `cvbot`,
`jobbot-config`, and `jobbot-private`.

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

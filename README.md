# Sharkapoolu

An agent-driven toolkit for job discovery, tailored resumes, and application tracking.

> **First time using this?** Follow the [step-by-step beginner guide](docs/foolproof_guide.md) for Windows + WSL2 + VS Code installation, resume import, and messages to copy to your agent. The [Chinese release](https://github.com/SimonTang02/sharkapoolu_beta_zh) has its own Chinese guide.

Coding agents: start with the complete
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

- **Find relevant jobs.** Tell your agent your roles, locations, and graduation
  timing. It configures supported sources and ranking, then scans jobs into your
  database. Defaults focus on hardware; other careers may need adaptation.
- **Prepare materials from your resume.** Supply a PDF or LaTeX resume and verify
  the extracted facts. Your agent prepares editable LaTeX and per-job materials;
  install TeX to render PDFs and review each result before using it.
- **Get help with application forms.** Use a manual HTML kit with answers and
  attachments, or supported browser adapters to prepare fields. You handle
  login, verification, review, and final Submit.
- **Keep track of real applications.** Use the local database or manually edit
  UTF-8 CSV records. Mark submitted only after a receipt or your explicit success
  confirmation. Sharing a database over SSH is optional.
- **Choose functions and continue later.** One settings file controls modules,
  regions, review rounds, and preparation modes. Private task/handoff files let
  a new conversation continue; browser progress exports and receipts establish
  actual progress.

Start with one job. The [beginner guide](docs/foolproof_guide.md) explains what
bootstrap handles and what still needs you or an agent. Advanced browser,
reporting, and sharing options are covered in [installation](docs/installation.md),
[beginner settings](docs/beginner-settings.md), and [shared databases](docs/shared-database.md).

## Quick start

Python 3.10 or newer is required.

```bash
git clone https://github.com/SimonTang02/sharkapoolu_beta.git
cd sharkapoolu_beta
./scripts/bootstrap.sh --with-resume
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
./scripts/bootstrap.sh --with-browser --with-resume
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

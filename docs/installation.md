# Installation

Before choosing a workflow, read [setup ownership and readiness](getting-started.md).
It distinguishes generated blank files from candidate-confirmed facts and
documents the remaining strategy, browser, material and portal setup work.

For two online WSL machines that need the same private SQLite data, follow
[the shared database setup](shared-database.md). The database stays on one host,
and the other machine uses authenticated SSH for database operations.

## Requirements

- Git
- Python 3.10 or newer with `venv`
- Optional: Chromium dependencies for browser-assisted features
- Optional: TeX Live, TinyTeX, or Overleaf for PDF resume rendering

## Fresh clone

```bash
git clone git@github.com:SimonTang02/sharkapoolu_beta.git
cd sharkapoolu_beta
./scripts/bootstrap.sh
source .venv/bin/activate
```

`bootstrap.sh` is safe to run again. It preserves existing private files. It
creates a virtual environment, installs the package in editable mode, copies
missing templates into the ignored private tree, validates both configuration
layers, and runs tests.

Use `PYTHON=/path/to/python ./scripts/bootstrap.sh` to select another Python.
Use `--skip-tests` only for a quick repair after tests have already passed at
the same revision.

## Fill private configuration

The first run creates:

```text
private_data/credentials/passport.env
private_data/profiles/application_profile.json
private_data/cv/profile/evidence_profile.json
private_data/cv/profile/application_keywords.json
```

Edit those files locally, then run:

```bash
jobbot-private check
```

The checker reports paths and field names but never values. Details are in
[configuration.md](configuration.md).

To place personal data outside the clone, set one stable absolute location
before every command:

```bash
export JOBBOT_PRIVATE_DIR="$HOME/.local/share/sharkapoolu"
./scripts/bootstrap.sh
```

Keep that directory on encrypted storage or in an encrypted private backup.
Do not point it at a public Git repository.

An editable installation made by `bootstrap.sh` uses the clone's
`private_data/` by default. A wheel installed outside a checkout defaults to
`$XDG_DATA_HOME/sharkapoolu`, normally `~/.local/share/sharkapoolu`.

## Browser support

Install the optional browser package and Chromium:

```bash
./scripts/bootstrap.sh --with-browser
```

On Ubuntu, Debian, WSL, and some servers, Playwright also needs system
libraries. The command requires administrator access:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

By default browsers are stored in `.playwright-browsers/`. Both this directory
and the virtual environment are ignored by Git.

### Dedicated Windows Chrome through CDP

The `windows_cdp` mode connects WSL to a separate Windows Chrome profile. Keep
the endpoint in `private_data/credentials/passport.env`:

```dotenv
CHROME_CDP_URL=http://<wsl-gateway-address>:9223
```

Select `application_browser.mode: "windows_cdp"` in a private config override.
Use the scripts and network restrictions described in
[`job_bot/README.md`](../job_bot/README.md). Never expose the debugging port to
the LAN or reuse the ordinary personal Chrome profile.

## Optional local config override

The shared entry point is `job_bot/config/jobbot.json`. For machine-specific
paths or browser selection, copy the example to the default private location:

```bash
cp examples/job_bot.local.json private_data/config/job_bot.local.json
jobbot-config --config private_data/config/job_bot.local.json
```

The example's relative include assumes the default in-repository
`private_data/` layout. If `JOBBOT_PRIVATE_DIR` points elsewhere, replace the
include with an absolute path to this clone's `job_bot/config/jobbot.json`.

## Resume rendering

Place candidate-owned `.tex` entry points under `private_data/cv/source/` and
run:

```bash
make check-tools
make current
make visa
```

Shared classes and styles live in `cv/latex/`; rendered PDFs go to
`private_data/cv/build/`. Overleaf can compile the private source together with
those shared style files.

## First functional run

Start with read-only checks and previews:

```bash
make private-check
make config-check
jobbot auth-status --config job_bot/config/jobbot.json \
  --env-file private_data/credentials/passport.env
make workflow-plan WORKFLOW=http_refresh
```

Initialize the database, then run a selected workflow when the source list is
appropriate for the candidate:

```bash
jobbot init --config job_bot/config/jobbot.json
make workflow WORKFLOW=http_refresh
make weekly
```

## Updating an installation

```bash
git pull --ff-only
./scripts/bootstrap.sh
```

Private files are preserved. Review release notes and rerun
`jobbot-private check` whenever schemas or examples change.

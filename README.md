# 26fall_intern

This repository contains a local-first resume, job discovery, scoring, and
review-assisted application workflow for hardware engineering roles. Final
application submission always remains a human action.

Candidate identity, credentials, generated resumes, browser state, screenshots,
and application databases belong under the ignored `private_data/` directory.
Only `private_data/README.md`, which documents the local layout, is versioned.

## Workspace layout

- `cv/`: CV/cover-letter code, shared LaTeX resources, tests, and documentation.
- `job_bot/`: source collection, normalization, scoring, SQLite, and daily digest.
- `application_bot/`: browser-assisted, review-only application preparation.
- `private_data/`: ignored candidate identity, resumes, credentials, browser state,
  databases, application screenshots, and generated application documents.

## Configuration

`job_bot/config.china_hk_ic_foreign.json` is retained as a compatibility entry
point. It now composes the versioned files under `job_bot/config/`:

- `runtime.json`: database, concurrency/retry, browser, tabs, daily/weekly reporting, and email.
- `workflows.json`: named module sequences and reproducible experiment tracking.
- `sources.json`: job-source definitions only.
- `scoring.json`: Foundation scoring used by the collector.
- `strategy.json`: geographic/degree tracks, strategy foundations, and tiers.
- `portals.json`: ATS matching, session probes, and no-submit adapter routing.
- `field_mappings.json`: profile/document mappings, regional policy, and safety.

Includes are resolved relative to the file that declares them and merged in
order. Local overrides can therefore include `job_bot/config/jobbot.json` and
override only the needed keys without copying the source list.

Named objects inside lists can be changed with validated config `patches`,
including `$append`/`$remove` keyword operations. Use `make config-check` to
inspect the effective configuration and `make workflow-plan WORKFLOW=...` to
preview modular runs. See `job_bot/config/README.md` for the tuning workflow.

For a new clone, create the private directory structure described in
`private_data/README.md`, then keep local overrides and credentials there or in
the ignored `job_bot/config.local.json`. The checked-in examples contain only
placeholder values.

## Validation

Run the portable test and release checks from the repository root:

```bash
make test
make config-check
make public-audit
```

`make public-audit` checks the files Git would publish for private paths,
machine-specific absolute paths, credential-like files, generated documents,
large files, and common token formats. It also compares public files with the
local candidate profile when that profile is available.

Before publishing an existing Git history, read
[`docs/GITHUB_RELEASE.md`](docs/GITHUB_RELEASE.md). A clean snapshot is required
when earlier commits contain resumes or other personal data; deleting them only
from the latest commit does not remove them from Git history.

## Daily and weekly reports

Run `make daily` for collection, rescoring, a standalone daily delta, and a
regenerated current-week report. Run `make weekly` to rebuild only the weekly
report without visiting any job site.

Daily delta files are point-in-time notifications. `weekly_YYYY-Www.md` is not
built by appending those files: it is regenerated from SQLite and therefore
reflects corrected job state, application progress, source health, and the
latest login audit. `weekly_latest.md` is a convenient copy of the newest
generated week.

All candidate-specific LaTeX entry points live under
`private_data/cv/source/`; the project root contains no resume source or PDF.

## Local Render

If a local TinyTeX installation is available under the ignored `.TinyTeX/`
directory, render with:

```bash
make current
make visa
```

The generated PDFs will be placed in `private_data/cv/build/`.

## VSCode Live Preview

Install the VSCode extension `LaTeX Workshop`. This repository includes
`.vscode/settings.json`, which invokes `scripts/latexmk_cv.sh` and builds on
save. Open `private_data/cv/source/current.tex` or
`private_data/cv/source/visa.tex`, save the file, then open the PDF preview tab.

## Overleaf Workflow

Upload the contents of `private_data/cv/source/` together with
`cv/latex/resume.cls` to Overleaf. Do not upload `job_bot/`,
`application_bot/`, local databases, browser state, or `passport.env`. Compile
`main.tex` for the current internship resume, or set the Overleaf main document
to `visa.tex` for the visa version.

## Private document version strategy

Use three layers:

- `private_data/cv/archive/original_overleaf/` keeps the raw downloaded archive.
- `private_data/cv/source/current.tex` and `visa.tex` keep purpose-specific versions.
- Keep private document checkpoints outside the public Git history.

Suggested private checkpoint names:

- `baseline-overleaf-download`
- `intern-hardware-focus`
- `visa-academic-version`

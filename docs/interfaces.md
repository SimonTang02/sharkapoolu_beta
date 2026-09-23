# Extension interfaces

## Source adapters

Sources are declared in `job_bot/config/sources.json`. The `type` selects a
collector implemented by `job_bot`. HTTP adapters receive the composed source
object, apply bounded timeouts and filters, and return normalized postings.
Browser-backed source types use the dedicated CDP session and must remain
read-only unless a separate workflow explicitly documents a write.

A normalized posting must provide a stable URL and title. Company, location,
description, publication date, source name, and role kind should be included
when the upstream service exposes them. Adapters should tolerate absent optional
fields, paginate with a bound, and report source failure rather than fabricating
records.

Reserved source extension points:

- a new `sources[].type` and matching collector dispatch;
- per-source authentication environment-variable names;
- public API, HTML/RSS, or authenticated CDP transport;
- source categories for workflow selection;
- include/exclude and role-kind filters applied after normalization.

## Application adapters

`job_bot/config/portals.json` maps host suffixes or source platforms to adapter
scripts. An adapter may probe login state, open one automation-owned tab, fill
fields from the private profile, upload an explicitly selected document, and
write an audit artifact. It must identify unsupported or ambiguous questions
and stop for human review.

Every adapter must honor these contracts:

- `application_browser.auto_submit` is `false`.
- `application_profile.safety.allow_submit` is `false`.
- CAPTCHA, MFA, declarations, and legal or immigration answers are not guessed.
- Tabs and artifacts are registered through the shared management modules.
- A final Submit control is never activated.

Reserved adapter hooks include session probes, draft support, environment-file
options, per-portal timeouts, and generic routing by host suffix.

## Configuration overlays

JSON configuration supports ordered `includes`. Paths are relative to the file
that declares them. Later values override earlier mappings. `patches` target
named list entries and support controlled append/remove changes. Validate every
overlay with:

```bash
jobbot-config --config path/to/local.json
```

Private overlays belong under `private_data/config/`. They may change machine
paths, enabled sources, browser mode, report routing, or scheduling limits.
Secrets themselves belong in `passport.env`, not JSON.

## Candidate profiles

The three maintained JSON contracts have schema files in `schemas/` and
redacted examples in `examples/`. Consumers should accept additive optional
fields, reject incompatible types, and use stable IDs when linking records.
Any new fact with legal, eligibility, compensation, demographic, or declaration
meaning needs explicit candidate confirmation and a clear provenance field.

## Command-line and output contracts

Installed commands must return nonzero status for invalid configuration or a
failed required operation. Diagnostic output may include file paths, key names,
counts, and statuses; it must not print passwords, cookies, tokens, or candidate
values. Generated durable output must resolve through `private_paths.py`.

New CLI behavior should first expose a dry-run or plan form when it causes
network writes, opens many browser tabs, or changes application state.

## Reserved integrations

The architecture leaves room for:

- additional university and employer job sources;
- other ATS portal adapters;
- encrypted private-data backup outside the public repository;
- alternate browser transports behind the same adapter boundary;
- notification sinks selected by config;
- structured export/import of candidate profiles;
- an evidence-backed language model service that proposes edits while the local
  validator retains authority over allowed claims and safety gates.

An integration must remain optional: a fresh clone and the core test suite may
not require its credentials, account, proprietary SDK, or network availability.


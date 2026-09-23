# Configuration reference

Sharkapoolu separates shareable behavior from candidate-owned facts. Public
configuration is versioned in Git. Identity, claims, credentials, browser state,
databases, and generated documents live in the ignored private tree.

## Paths and precedence

`private_paths.py` defines every private location. In a source checkout the
default root is `private_data/`. A wheel installation uses
`$XDG_DATA_HOME/sharkapoolu` (normally `~/.local/share/sharkapoolu`) so it never
writes into `site-packages`. `JOBBOT_PRIVATE_DIR` overrides either default. Use
one stable absolute location on each machine.

The shared entry point is `job_bot/config/jobbot.json`. Its `includes` are
loaded in order, with later mappings overriding earlier ones. A local file can
include the shared entry point and override a few keys. Relative include paths
are resolved from the file containing them.

Validate the two layers separately:

```bash
jobbot-config --config job_bot/config/jobbot.json
jobbot-private check
jobbot-private paths
```

## Public configuration

### `runtime.json`

- `database.path`: SQLite destination. Keep it under the private root.
- `scan.max_workers`: maximum parallel source requests.
- `scan.retry_attempts` and `retry_backoff_seconds`: bounded retry policy.
- `scan.lifecycle_guard`: blocks suspiciously small or empty refreshes from
  replacing a previously healthy source result.
- `scan.auto_start_windows_chrome` and `browser_start_wait_seconds`: optional
  dedicated-browser startup behavior.
- `application_browser.mode`: `local_persistent` or `windows_cdp`.
- `application_browser.auto_submit`: must remain `false`.
- `application_browser.windows_cdp`: endpoint or environment-variable name for
  a restricted dedicated Chrome connection.
- `tab_management`: limits active tabs, protects populated forms and session
  anchors, and controls duplicate cleanup and screenshots.
- `digest`: report limit, minimum score, title filters, deduplication, and scan
  error visibility.
- `reporting`: timezone and weekly-report generation policy.
- `email`: SMTP transport and environment-variable names. `dry_run` should stay
  enabled until delivery is intentionally configured.

### `sources.json`

Each `sources[]` item describes one collector. Common fields include `name`,
`type`, company/tenant identifiers, `source_category`, `sync_active`,
`role_kinds`, search text, include/exclude patterns, and an official reference.
Adapter-specific endpoint and pagination fields are allowed. Disable a source
instead of deleting it when its definition may be useful later.

### `scoring.json`

- `bands`: score thresholds shown in collection reports.
- `foundation_groups`: primary role families and their evidence keywords.
- `modifiers`: bounded additions or deductions by title/body scope.
- `keyword_groups`: compatibility scoring weights and title bonuses.

Scores rank review order; they do not assert candidate qualification.

### `strategy.json`

Defines geographic and degree tracks, target direction order, classification
priority, A/B thresholds, stored-score bonuses, role-pattern classifiers,
foundation overrides, and track-specific eligibility windows. Update dates and
graduation assumptions when the candidate's recruiting cycle changes.

### `workflows.json`

`workflows` maps a name to ordered modules, an optional source selector,
parallelism, and error policy. `experiment_tracking` controls reproducibility
manifests and effective-config hashes. Always preview an unfamiliar workflow:

```bash
make workflow-plan WORKFLOW=<name>
```

### `portals.json`

- `session_audit`: login-probe concurrency and timeout.
- `company_profiles`: company matching and account rules.
- `adapters`: platform/host routing, scripts, timeouts, session probes, and
  draft capability.

Declaring an adapter does not authorize an application submission.

### `field_mappings.json`

Maps neutral profile paths to form concepts for identity and documents. Its
regional policy records which values require explicit confirmation. Safety
settings require authorized values, block inferred legal answers, capture a
review artifact, and keep submission disabled.

### `penn_channels.json`

Defines university career channels and campus-employment leads. Hour scenarios
support estimated monthly pay in reports. Login-required channels remain
browser-assisted rather than embedding institutional credentials.

## Private application profile

Create it from `examples/application_profile.json`. It is the canonical source
for facts copied into application forms.

### Top-level metadata

- `$schema`: editor hint pointing at the checked-in JSON Schema.
- `schema_version`: currently `1`; change only with a repository migration.

### `fields`

Holds stable contact and identity values: referral source, previous-employer
status, legal/preferred/native names, email, phone, postal address, country,
date of birth, and public profile URLs. Use the exact form expected by official
documents where a portal asks for legal identity. Leave an unknown value blank
or `null`; do not guess.

### `documents`

`resume_path` and `cover_letter_path` select reviewed upload files. Paths may be
relative to the project root. Confirm that each file matches the role and
language policy before opening an application adapter.

### `education`

Each record stores school, degree, field, GPA, and start/end month and year.
`portal_values` stores verified spellings or hierarchical choices required by a
specific portal without changing the neutral facts. Keep graduation month as
well as year when known.

### `languages`, `work_experience`, `projects`, and `skills`

These are reusable structured form entries. Language records contain the
language, native flag, and self-assessed proficiency. Experience and project
records may contain portal-supported fields, but every claim must match the
evidence profile or reviewed resume. `skills` is a list of concise labels.

### `workday_checkbox_groups` and `custom_answers`

These map exact portal prompts to candidate-confirmed answers. Keep uncertain
answers `null`. Text changes by a portal may invalidate an exact prompt match,
so review every resulting form.

### `answer_rules`

Stores narrowly scoped reusable answer rules for compatible prompts. Rules must
identify their scope and source of truth. Do not create a broad rule for a
legal, immigration, demographic, compensation, or declaration question.

### `voluntary_disclosures`

Contains optional demographic choices and terms acceptance. A blank value means
no selection. Terms must be reviewed for the particular application before
`accept_terms` is set.

### `explicit_authorization`

- `user_confirmed`: whether the candidate explicitly confirmed the recorded
  authorization facts.
- `location_scopes`: countries or jurisdictions covered by that confirmation.
- `work_authorized` and `sponsorship_required`: confirmed answers, or `null`.
- `company_consents`: company-specific confirmed consents.

Authorization in one country must not be reused for another country.

### `career_preferences`

Stores role/city adjustment preference and `resume_language_policy`. The latter
selects default resume language by employer group, lets an explicit job-language
requirement override the default, records the preferred page limit, requires
rendered-PDF review, and names the chosen Chinese font.

### `safety`

- `allow_sensitive_answers`: permits only already confirmed sensitive answers
  to be filled; it does not permit inference.
- `allow_server_draft`: permits an explicit adapter action to save a server-side
  draft.
- `allow_submit`: must remain `false`.

### `personal_facts_confirmation`

This optional compatibility object records dated provenance for candidate facts
that do not yet have a stable first-class field, such as an advisor/laboratory
clarification. Prefer a normal structured field when one exists. Each entry
should identify when and how the candidate confirmed it.

## Private evidence profile

`evidence_profile.json` is the canonical claim inventory used by CV tools.

- `identity`: display/headline names and cross-file email.
- `graduation_school` and `expected_graduation_date`: normalized current-degree
  completion facts.
- `tailored_summaries`: reviewed summaries keyed by target family.
- `candidate_summary` and `closing_strength`: reusable positioning statements.
- `evidence_groups`: named groups with match keywords and a factual evidence
  statement.
- `education_gpa`: reviewed GPA display by institution.
- `graduation_confirmation`: school, month/year, confirmation date, and source
  for the current graduation fact.

The checker compares the identity email with the application profile. Other
duplicated education facts still require human review.

## Private keyword library

`application_keywords.json` contains evidence-backed vocabulary usable by the
CV and application bots.

- `sources`: stable source IDs with paths/descriptions.
- `usage_rules`: restrictions applied to every selection.
- `technical_keywords`: technical skill records.
- `collaboration_personality_keywords`: teamwork and working-style records.
- `role_presets`: curated keyword IDs for a target role family.

Each keyword needs a unique `id`, English and Chinese labels, factual evidence,
an English example, valid `source_ids`, and `claim_status`. Optional fields can
record proficiency, matching variants, and a shorter resume label. Presets may
reference only IDs that exist in the matching section; the checker enforces
this.

Inspect selections without editing forms:

```bash
applybot keywords --help
cvbot --help
```

## Credentials and session pointers

`private_data/credentials/passport.env` uses `NAME=VALUE` lines and mode `600`.
Supported naming families include:

- `COMPANY_<SLUG>_{USERNAME,PASSWORD,COOKIE,STORAGE_STATE}`
- `PLATFORM_<SLUG>_{USERNAME,PASSWORD,COOKIE,STORAGE_STATE}`
- `CHROME_CDP_URL`
- `SMTP_USERNAME`, `SMTP_PASSWORD`, and `JOBBOT_EMAIL_TO`

Populate only variables used by enabled integrations. Prefer browser storage
state for SSO, MFA, or localStorage-backed sessions. A cookie value is a request
header for one exact target domain and must not be reused elsewhere.

## Local runtime override

`examples/job_bot.local.json` demonstrates a private overlay for database path,
browser endpoint, and email routing. Keep behavior changes here; keep secret
values in the environment file. When the private root is outside the clone,
adjust the shared-config include to an absolute path.

## Editing checklist

After changing a public configuration file:

```bash
make config-check
make test
```

After changing private facts or keywords:

```bash
make private-check
make public-audit
```

Review any generated resume PDF and application field report before use.

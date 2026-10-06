# Application bot

## Standard offline manual application kit

`manual-kit` renders reviewed materials into a new private delivery directory,
using the shared templates in `templates/manual_kit/`. It preserves original
job numbers and manifest order, supports any batch size, and provides role
filters, per-field copy buttons, document links, and browser-local progress with
receipt notes and JSON export. No database or company portal is accessed.

Every new kit also includes a campaign-specific `AGENT_HANDOFF.md`, its manifest
SHA-256, progress-key prefix, and a copyable new-conversation prompt. That file
identifies the materials and continuation rules; it does not certify current
progress. The agent still needs the latest private records and the candidate's
active job, export or receipt. See [setup ownership](../docs/getting-started.md)
for what bootstrap initializes and what requires candidate/agent assistance.

```bash
python3 application_bot/cli.py manual-kit \
  --manifest private_data/outputs/application_bot/example_source/Manifest.json \
  --output private_data/outputs/application_bot/example_delivery \
  --progress-key example-campaign-
```

The source bundle has a `Manifest.json` (see
[`manual-kit-manifest.schema.json`](../schemas/manual-kit-manifest.schema.json)
and the [fictional manifest](../examples/manual_kit_manifest_template.json)).
Each job needs its original positive `rank`, a unique one-level `folder`, an
HTTPS job/application URL, and `pdfs` entries with SHA-256 and
`visual_review: passed`. The generator checks hashes and copies the existing
PDF bytes; it never generates new CV claims or grants review approval.

Each role folder contains `Application_Data.json` with the same `rank`.
Optional sections are `common_fields`, `regional_authorization`,
`role_specific_answers` (label-to-answer objects), `education`,
`work_experience`, `projects` (lists of objects), `portal_notes`, and
`transcript_verified_education_facts`. Unconfirmed/empty values remain
unconfirmed. Optional role TXT/JSON references and manifest supporting documents
are copied without altering their content or official/unofficial labels.

Output must be below the canonical private root and must not exist. The
generator refuses to overwrite delivered kits. Choose a distinct, stable
`--progress-key` per campaign and keep the user's entry file address stable.
Existing browser progress is loaded without resetting keys; manifest or database
statuses do not prefill it. Exported progress keeps the `rank`, `status`,
`receipt` array format. Initial blank status is not evidence of no application.
Only receipts or explicit candidate confirmation authorize database submission
registration through the existing `mark_submitted.py` workflow.

This is the stable entry point for browser-assisted application preparation.
The implementation remains in `job_bot/application_bot.py` during the
compatibility migration because existing queues, tests, and commands depend on
that path.

The bot may open an application, fill approved profile data, upload a reviewed
resume, save artifacts, and stop at review by default. Final submission requires
explicit session authorization scoped to the relevant applications and a completed
review. Record authorization in an ignored local campaign manifest; authorization
for one campaign does not apply to unrelated applications. Never infer
legal/immigration answers or bypass CAPTCHA/MFA.

When preparing skill tags or personal-strength answers, consult
`private_data/cv/profile/application_keywords.md` (JSON path:
`private_paths.APPLICATION_KEYWORDS`). Select relevant, evidence-supported entries
for the particular field. The library's examples do not establish skill levels,
years of experience, or confirmed personality self-ratings. Profile preparation,
batch material generation, profile sync, and Workday preview
now call the shared selector. They preserve manual skill lists and fill an empty
skills list (or refresh an unchanged machine-generated list) from supported technical
entries. Collaboration examples remain under profile.application_keywords for review;
they are not personality answers. Other adapters consume prepared profiles according
to their existing field support. No browser action is triggered by keyword selection.

Workday checks legal-work and sponsorship answers against the job's location
at the point of filling, including direct `workday-preview` calls. The profile's
address country is not a substitute for this location. Missing, mixed, or
unconfirmed location scopes leave the question pending; mainland-China-only
permission does not cover Hong Kong. This guard does not certify an existing
browser answer or resolve conflicting identity/education facts.

Examples from the project root:

```bash
python3 application_bot/cli.py list
python3 application_bot/cli.py workday-preview --application-id 1 \
  --start-application --interactive
```

The unified CLI also exposes the config-driven operations:

```bash
python3 application_bot/cli.py session-audit
python3 application_bot/cli.py login-tabs
python3 application_bot/cli.py login-preflight --campaign-id 3 --campaign-id 4
python3 application_bot/cli.py dispatch --application-id 1
```

`session-audit` derives one probe per ATS session scope from `portals.json`,
checks unrelated tenants concurrently, records no cookie or field values, and
closes every temporary page. `login-tabs` reads that audit and opens only pages
that actually require login/MFA. `dispatch` maps an application to its adapter;
it writes a plan by default and runs nothing unless `--execute` is supplied.

Run `login-preflight` before dispatching a campaign. It opens or reuses exactly
one bot-owned inspection tab per company, even when multiple employers share
the same ATS. Complete login/MFA review there first; only then create the
application-specific tabs. Re-running preflight deduplicates its own company
tabs and never closes an application tab that may contain form state.

Portal adapters implement shared mechanics (Workday, iCIMS, Moka, Oracle), but
`job_bot/config/portals.json` also defines company profiles. Those profiles own
each employer's field enumerations, required sections, consent rules, and known
limitations. The first application is the template-learning run; subsequent
roles for the same company reuse that profile rather than relearning behavior
from another employer using the same ATS.

`nvidia-preview` remains available as a backward-compatible alias. Standard
Workday tenants can use `workday-preview`, but each tenant may require its own
account/session and custom-question review.

In Windows CDP mode, Workday login first checks whether Chrome Password Manager
has already populated both login fields. If so, the bot may click Sign In
without reading or exporting either credential. Browser-owned password prompts,
Windows Hello, MFA, verification codes, and CAPTCHA remain manual gates. If no
saved credential is populated, the existing per-company `passport.env`
credential fallback remains available.

Every completed fill test writes an append-only, timestamped screenshot and a
value-free JSONL record under the relevant application's `fill_tests/`
directory. Workday keeps its legacy `preview.png`, but historical screenshots
are no longer overwritten. MediaTek profile-only steps use
`private_data/outputs/job_bot/application_profiles/mediatek/fill_tests/`. These artifacts can
contain personal data and are stored with private permissions.

Application tabs are registered in SQLite by application ID, CDP target ID, a
persistent `window.name` label, canonical job URL, and a portal-specific job
fingerprint. Adapters resolve in that order and create a new tab only when every
check fails. A resumed Workday adapter preserves a matching application page
instead of navigating it back to the job listing. Target IDs identify only the
lifetime of an open tab; the application ID and job fingerprint remain the
durable identity.

Audit the dedicated Chrome, and optionally adopt legacy tabs whose job
fingerprint maps unambiguously to one application:

```bash
python3 application_bot/tab_manager.py
python3 application_bot/tab_manager.py --adopt
```

Safe cleanup is explicit. It screenshots each page before closing and, by
default, closes only blank tabs and clean exact-URL duplicates. Populated forms,
registered applications, and one authenticated session anchor per tenant are
preserved. Closing other clean legacy tabs requires the additional flag:

```bash
python3 application_bot/tab_manager.py --apply
python3 application_bot/tab_manager.py --apply --include-clean-legacy
```

Audit ten distinct portals already open in the dedicated Chrome without
clicking, filling, accepting policies, or submitting:

```bash
python3 application_bot/platform_audit.py --limit 10
```

The Markdown and JSON reports under `private_data/outputs/application_bot/` distinguish an
editable form from authentication, CAPTCHA/policy consent, an incomplete
profile, and a final-submit-only flow. This prevents one-click portals such as
MediaTek from being mistaken for draft-capable systems.

Bind job-specific PDFs to a private per-application profile before opening the
browser. Only empty contact fields explicitly present in `current.tex` are
hydrated; addresses and legal/immigration answers remain untouched:

```bash
python3 application_bot/cli.py prepare-profile \
  --application-id 1 \
  --resume /absolute/path/to/resume.pdf \
  --cover-letter /absolute/path/to/cover_letter.pdf
```

Inspect a role's current evidence-scoped keyword selection without opening a browser:

```bash
python3 application_bot/cli.py keywords --role "GPU Architecture Engineer"
```

The command also accepts `--job-description FILE`, `--library FILE`, and `--preset ID`.
Selections record the library SHA-256 and supporting sources for later review.

Before uploading a newly generated/revised CV, check its manifest and final rendered
pages. Keep the configured page limit; fix orphaned headings, sparse extra pages
and broken text extraction first. Compilation alone never marks a PDF reviewed.
Verify each selected website skill as a saved tag, not merely search text or the
highlighted dropdown option. For Workday skills, `aria-selected` may mean keyboard
focus: use the actual checkbox and verify selected pills plus final Review.

For Workday date segments, visually locate the month/year display and use a real
CDP mouse click plus keyboard entry, then move focus outside the date group before
saving. DOM input values alone can appear correct while the saved date is missing.
Use real text input for remote skill searches if synthetic setters return No Items.
Store employer-specific observations and campaign authorization in ignored local
reports rather than this shared documentation.

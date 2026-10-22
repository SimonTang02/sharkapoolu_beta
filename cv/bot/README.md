# CV and cover-letter bot

This module turns a job description into a fit report and a cover-letter draft
using only reviewed evidence from `evidence_profile.json`. It is deliberately
deterministic: it does not call an LLM, invent metrics, or submit anything.

Example:

```bash
python3 -m cv.bot.bot \
  --job-description /path/to/job_description.txt \
  --company NVIDIA \
  --role "ASIC Design Intern"
```

The Markdown review packet is written under `private_data/cv/reports/`. Treat
it as a draft: review relevance, truthfulness, tone, company name, and role name
before copying any text into an application.

For a job already collected by the monitor, no manual JD copy is needed:

```bash
python3 -m cv.bot.bot --job-url 'STORED_JOB_URL'
```

The bot reads the stored company, title, location, and description from the
local SQLite database. `--company` and `--role` may override imperfect source
labels without changing the database.

Generate a complete reviewed bundle with a job-specific LaTeX resume, resume
PDF, cover-letter source/PDF, review packet, and manifest:

```bash
python3 -m cv.bot.bot \
  --job-url 'STORED_JOB_URL' \
  --generate-bundle
```

Bundles are isolated under `private_data/cv/variants/`; the canonical source at
`private_data/cv/source/current.tex` is never overwritten. Generated PDFs
remain drafts until their manifest and rendered
pages have been reviewed.

## Structured project tailoring and current facts

The legacy source mode changes summary, skills and graduation date; it does not
rewrite project evidence. Its manifest now labels it
`legacy_source_requires_fact_migration`. This remains a draft, not factual approval.

For project-level tailoring, add optional `resume_content` to the private evidence
profile using `schemas/resume-content.schema.json`. The fictional examples
`examples/structured_evidence_template.json` and
`examples/resume_fact_ledger_template.json` show the complete shape. Do not copy
their fictional facts into a real candidate profile. Each statement references a
stable fact ID in the intake ledger, with `status: user_confirmed`, source SHA256
and dated confirmation. `unresolved`, missing and superseded facts stop generation.
The code validates these records; an Agent/person must still check whether the
statement accurately describes individual/team contributions and completion.

```bash
cvbot --job-description <private-jd.txt> --company <company> --role <role> \
  --profile <private-evidence-profile.json> --fact-ledger <private-ledger.json> \
  --application-profile <private-application-profile.json> \
  --resume-source <private-current.tex> --generate-bundle \
  --bundle-dir <new-private-output-directory>
```

Single-job and batch entry points both call `write_bundle`. Batch generation reads
the confirmed ledger from canonical `private_data/cv/profile/fact_ledger.json`;
copy the reviewed intake ledger there deliberately, preserving its history.
CLI defaults to the same ledger when structured content is enabled.
In structured mode the plan owns Summary, Technical Skills, Projects and optional
Research Experience sections. Keep exactly one of each required marker in the
LaTeX source. Old text in both managed project/research sections is replaced;
facts are deduplicated across them. Other sections, project headings and dates
still require factual review. Evidence-group prose cannot override selected facts
in the corresponding cover-letter PDF or review packet.

Projects are ranked by explicit title and JD keyword overlap, using candidate
keywords, with title matches weighted more strongly. Statements are selected
within a length-dependent content budget. There is no fixed three-project/two-
bullet rule and no fallback that invents experience for an unrelated role.
`content_plan.json` records selected exact statements, fact hashes, ranking and
omissions. Sparse evidence may produce fewer pages; never pad a resume to reach
two pages. An Agent should inspect omissions and improve evidence or keyword
coverage rather than weakening factual checks.

Length preferences come from the private application profile's
`career_preferences.resume_language_policy`: default `preferred_pages: 2` and
`max_pages_preferred: 2`. A `company_specific_length_guidance` entry changes the
preference only when it has explicit `preferred_pages`, HTTPS `url`, `kind` and
`checked_on`; optional `role` restricts applicability. The operator verifies that
the source actually supports the preference. A URL-only note is not enough to
infer a one-page preference. The budget affects content selection, while final
PDF page count is checked separately. It cannot guarantee exactly two pages.

New builds reject existing bundle directories. Use a new version directory for
every revision; old attachments are not overwritten or reused just because a PDF
exists. `manifest.json` records input files (profile, ledger, JD, source, templates,
generator and bibliography), resolved policy and output hashes. Programmatic
callers should pass all actual profile/JD/asset paths through `input_paths`.
External fonts/images included by private LaTeX must also be passed there if their
changes need automatic freshness checks.

```bash
cvbot verify-bundle <private-bundle/manifest.json>
```

Verification checks fingerprints, not semantic truth or human approval. A changed
input/output invalidates the old reviews; generate a new version and repeat the
affected review. Database-backed JD changes need a fresh job lookup and generation;
the verifier does not contact the database. All new manifests keep content,
rendered-page and candidate review pending. Compilation never sets them to passed.
Operator review and manual-kit export also recheck a versioned manifest adjacent
to an attachment. Operator attachment reviews must include that manifest; this
binds a review to its fact/asset versions as well as the PDF bytes. Copied legacy
attachments without an adjacent manifest remain subject to the older explicit
review workflow; do not strip provenance as a way to avoid regeneration.
Install `.[resume]` to check PDF text identity/page count with pypdf; without it,
PDF identity remains unknown and requires manual checking. Missing glyphs,
overfull boxes, wrong identity and known page-budget excess stop bundle creation.
The operator must inspect every rendered page, including cover letters, before
binding a document to an application.

## External-project decision

`cv/docs/external_tools.md` records the projects evaluated for later optional
integration. Resume Matcher is the strongest candidate for a separately
containerized local service. Its output should remain an advisory variant and
must not overwrite `current.tex` automatically.

## Shared application keyword library

Normal report and bundle generation reads `private_paths.APPLICATION_KEYWORDS`
through `cv.application_keywords.select_keywords`. Role titles take precedence over
JD text when selecting a preset; unsupported job keywords never become candidate
skills. Use `--keyword-library /path/to/library.json` to override the private default.
Missing optional libraries preserve the previous behavior; malformed libraries fail
with an error. Pure rendering helpers also accept an explicit `keyword_selection`.

A bundle uses up to ten supported technical labels in its Technical Skills section,
keeps project text from the source, and saves evidence and collaboration examples in
its review report and `application_keywords.json`, referenced by its manifest.
Existing bundles are not rewritten merely by editing the keyword library.

Both bots can also call the selector directly:

```python
from cv.application_keywords import select_keywords, apply_keyword_selection

selection = select_keywords("GPU Architecture Engineer", job_description)
prepared_profile = apply_keyword_selection(application_profile, selection)
```

The application helper preserves manual skills, factual answers, and safety flags.
It fills empty skills or updates an unchanged previously generated list; collaboration
wording is retained as review context, never promoted to personality self-ratings.

When the private evidence profile supplies `expected_graduation_date`, the renderer
uses it for every role kind, including internships, and records the resolved date
in the bundle manifest. Profiles without a confirmed date preserve their source
date unless an explicit override is passed. Only `graduation_school` is changed;
other degrees and dates are preserved.

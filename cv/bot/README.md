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

# CV workspace

This directory contains reusable, non-secret CV tooling:

- `bot/`: deterministic CV tailoring and cover-letter generation.
- `latex/`: shared LaTeX class and other reusable resources.
- `docs/`: reusable workflow notes and external-tool evaluations.

Candidate-specific material is grouped under `../private_data/cv/`:

- `source/`: canonical editable LaTeX sources.
- `build/`: locally rendered master PDFs.
- `variants/`: one isolated resume/cover-letter bundle per job.
- `profile/`: reviewed evidence and candidate-specific positioning notes.
- `reports/`: generated fit and cover-letter review packets.
- `archive/`: original downloads and historical source archives.

For application skills and personal-strength wording, consult the private
`profile/application_keywords.md` library and its JSON companion. Entries include
bilingual labels, supporting experience, scoped example sentences, and role
presets. `private_paths.APPLICATION_KEYWORDS` resolves the machine-readable file.
Treat collaboration traits as behavior-based suggestions, not personality
self-ratings. The CV generator reads the JSON during report/bundle generation and uses selected
technical labels in the generated Technical Skills section. Examples and evidence
are retained in the review report and bundle application_keywords.json.

There are no CV compatibility files at the project root. New code must import
paths from `private_paths.py`; local rendering and VS Code operate directly on
the canonical private source directory.

From the project root, render the master versions with:

```bash
make current
make visa
```

Do not edit generated PDFs. Review a job-specific bundle and its `manifest.json`
before using it in an application.

## Application PDF length and language

Aim for at most **two pages** for each application resume. Edit redundant content,
section order and spacing before reducing type size; keep project headings with
body text. Render and visually inspect **every page of the final PDF** before
uploading, then verify readable text extraction, GPA/dates and attachment identity.
A successful LaTeX build is not visual approval. Record the reviewed PDF hash in
the variant manifest; any subsequent PDF change invalidates that review.

The private `source/current.tex` can use `cv/latex/cvcompact.sty` for a compact
English layout. A Chinese master may use XeLaTeX; `scripts/latexmk_cv.sh` honors
the source engine directive. Keep machine-specific font paths in private source
files or local font configuration. Archived PDFs are historical evidence rather
than current uploads.

Select resume language from the specific employer/role's explicit instructions.
For domestic roles described in Chinese, prefer a natural Chinese narrative with
standard English tool names and selective terminology glosses; this is an editorial
default, not a claimed universal employer requirement. Keep English versions for
English-language applications. Preserve exact degree names and paper titles where
translation could mislead. Do not copy website requirements into candidate skills.

Keep language preferences in the private candidate profile. Employer-specific
instructions take precedence. Review actual rendered pages and preserve
selectable, extractable Chinese text.

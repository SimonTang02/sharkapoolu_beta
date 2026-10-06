# Manual application kit: new conversation handoff

Read the repository's `AGENTS.md` and `AGENT_HANDOFF.md` first. This file
describes one generated delivery bundle; it does not authorize portal actions.

## Resolve this campaign

- Bundle directory: `$output`
- Entry page: `index.html` in that directory; keep its file address stable.
- Targets: `$count` jobs, with the original ranks and order in `Manifest.json`.
- Manifest SHA-256 at generation: `$manifest_sha256`.
- Browser progress key prefix: `$progress_key`.
- Role files: `<folder>/Application_Data.json`, reviewed PDFs and available
  TXT/JSON references. Folder names and material hashes are in `Manifest.json`.
- Supporting documents: `Supporting_Documents/` when listed in the manifest.

## Determine what is current

1. Read this manifest and the repository's latest private handoff. Identify the
   canonical private root and whether this machine uses a local or SSH database.
2. Ask for the currently active original job number, exported browser progress,
   or a success receipt. Actual manual progress is unknown until supplied.
3. Browser-local progress and database submissions are separate. An empty
   tracker, generated material status, or whole-database submitted count does
   not establish this campaign's progress. Never read a personal Chrome profile
   to recover it, reset its keys, or populate its progress from assumptions.
4. For exports, match ranks to this exact manifest before interpreting statuses.
   Record submitted only from official receipt evidence or explicit candidate
   success confirmation. Preserve external submission time separately from
   the time a confirmation is recorded.
5. Resume from current canonical confirmed facts and actual portal fields.
   Prepared answers are a dated aid, not authority to infer qualifications,
   work permission, consent, or graduation facts. Retain unresolved answers.

## Continue safely

Preserve targets, original ranks, reviewed materials and their hashes. Do not
regenerate or overwrite this bundle, substitute jobs, or replay historical tab
cleanup. Verify eligibility, current fields, and actual uploaded files for
each application. Preserve transcript official/unofficial labels. The candidate
handles login challenges, consent, declarations and final submission.
Keep all final-submit guards false. This kit never updates the application DB.

Use the existing `mark_submitted.py` workflow only after qualifying evidence.
Check for an existing application before creating one. Store receipts, new
answers, issues and continuation records only in canonical private output;
do not place candidate facts in public code or handoff documentation.

## Suggested first message in a new conversation

Read this bundle's `AGENT_HANDOFF.md`, then `Manifest.json` and the repository
operating contract. Preserve existing browser progress and materials. Continue
with the job number or receipt I provide; do not submit an application for me.

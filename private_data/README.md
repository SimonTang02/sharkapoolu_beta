# Private candidate data

Everything below this directory is ignored by the main Git repository except
this README. It is the canonical home for candidate identity, credentials,
browser sessions, application evidence, generated resumes, cover letters, and
application databases.

Default layout:

- `credentials/passport.env`
- `profiles/application_profile.json`
- `browser/state/` and `browser/profiles/`
- `database/`
- `cv/source/` and `cv/build/`
- `cv/profile/` (evidence and positioning), `cv/variants/`, and `cv/reports/`
- `cv/archive/`
- `outputs/job_bot/` and `outputs/application_bot/`

Create the maintained files and validate them from the repository root:

```bash
python3 -m job_bot.private_config init
python3 -m job_bot.private_config check
```

`init` copies redacted files from `examples/`, sets their mode to `600`, and
keeps existing files. The matching contracts are under `schemas/`. Use
`--force` only when you intentionally want to replace the maintained private
files with blank examples.

Data ownership is intentionally split:

- `profiles/application_profile.json` is canonical for facts entered in forms.
- `cv/profile/evidence_profile.json` is canonical for claims and positioning.
- `cv/profile/application_keywords.json` is canonical for evidence-backed skill
  and collaboration vocabulary.
- `credentials/passport.env` contains secrets and session pointers.

Some education and identity facts are duplicated for compatibility. Run the
checker after changing them and review generated documents for consistency.

Set `JOBBOT_PRIVATE_DIR` before running a command to relocate the entire tree.
The directory should be backed up separately and protected with filesystem or
volume encryption. Moving files here does not remove personal information from
older Git commits; rewriting repository history is a separate destructive task.

See [`docs/configuration.md`](../docs/configuration.md) for every field and
[`docs/private-data-audit.md`](../docs/private-data-audit.md) for the structure
assessment.

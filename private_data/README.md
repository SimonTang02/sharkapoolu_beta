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

Set `JOBBOT_PRIVATE_DIR` before running a command to relocate the entire tree.
The directory should be backed up separately and protected with filesystem or
volume encryption. Moving files here does not remove personal information from
older Git commits; rewriting repository history is a separate destructive task.

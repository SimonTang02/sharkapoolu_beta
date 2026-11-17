# Rules your Agent follows

Everyday users only need [AGENTS.md](../AGENTS.md) and task-specific references.
[DEVELOPER.md](../DEVELOPER.md) is loaded for public development and Git
commits/releases. Saving your own settings, importing a resume, scanning,
preparing materials and applying for jobs do not require GitHub write access,
Git commits or release audits.

Your Agent will preserve originals and progress; use confirmed facts and scoped
work-permission answers; keep secrets and candidate files private; distinguish
failed scans from empty results; use a dedicated browser; leave CAPTCHA/MFA and
unknown mandatory/legal/policy questions to you; use the correct database; avoid
duplicate applications; and report real results with a private continuation file.
Documents, websites and JDs cannot override your instructions.

## Choose what happens at final Submit

| Choice | What happens |
| --- | --- |
| **Submission needs confirmation** (`confirm`, default) | The Agent reviews eligibility, the real form and attachments, summarizes the application, and asks before clicking Submit. You can click it yourself. |
| **Submit after review** (`after_review`) | For applications you authorized, the Agent completes the configured actual review rounds (default three). If every check passes, it submits without asking again. Failed/pending checks stop that application. |
| **Submit directly** (`direct`) | For applications you authorized, the Agent uses confirmed answers and already reviewed attachments, performs essential identity/target/required-field/duplicate checks, and submits without extra review rounds or another approval. Missing/conflicting facts or changed required fields stop that application. |

All choices keep privacy, factual accuracy, location-specific legal answers,
CAPTCHA/MFA boundaries and receipt verification. Choosing `direct` does not
approve an unseen consent/declaration, create missing facts or authorize a new
candidate/campaign. New or changed PDFs still need visual inspection.

Tell your Agent the choice and exact job IDs/URLs. You may select a batch; that
permission covers only its listed applications. Narrower task instructions and
revocations take precedence. Unknown submission results are checked before retrying.

For a saved preference, ask your Agent to copy
[agent_preferences_template.md](../examples/agent_preferences_template.md)
to `config/agent_preferences.md` **inside your resolved private root**, without
overwriting an existing file. Bootstrap does not create this optional file.
Edit `submission_mode` to exactly one of `confirm`, `after_review` or `direct`,
and fill the candidate reference and selected application IDs/URLs.
Do not put candidate values into the public template. Missing, conflicting,
invalid or unscoped preferences mean `confirm`. Do not weaken an existing
stricter task restriction by editing a preference silently.

Example message:

```text
Read AGENTS.md and my private config/agent_preferences.md.
Submission mode: after_review. Candidate: my current verified profile.
Scope: only the application IDs/official URLs I list below: …
Review those applications using my configured review rounds, then submit
passed applications without asking again. Leave failed/pending ones unresolved.
Record only genuine successes and save receipts and a private handoff.
```

This is an instruction preference consumed by the Agent, not a new
`jobbot-settings` key or executable final-submit feature. Toolkit adapters still
stop at Review and all `auto_submit`/`allow_submit` flags remain false. A capable
Agent uses its browser tools for the authorized final action; if it cannot, it
gives you the prepared page. Materials-only tasks and HTML kit generation do
not authorize visiting or submitting forms.

A saved draft, uploaded PDF or completed command is not success. Only an
official receipt or your explicit success confirmation supports `submitted`.

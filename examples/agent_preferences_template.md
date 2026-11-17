# Private Agent preferences

Copy this template to `config/agent_preferences.md` under the resolved private
root. Keep the public template blank; preserve an existing private file.
This block is read by the Agent, not parsed by toolkit CLI commands.

```yaml
submission_mode: confirm
candidate_profile: profiles/application_profile.json
application_ids: []
application_urls: []
```

Choose exactly one mode:
- `confirm`: review, summarize and obtain confirmation before Submit (default).
- `after_review`: configured actual review rounds, then submit passed applications.
- `direct`: submit using confirmed answers and already reviewed attachments,
  without extra review rounds or per-job approval.

IDs are canonical database application IDs, not kit ranks or job IDs.
Use exact official URLs when no application IDs exist. Lists define the allowed
scope; empty scope authorizes no automatic submission. The profile path is
relative to this candidate's private root. Ask about invalid/conflicting scope;
use `confirm` until resolved. Current narrower instructions/revocations prevail.
The setting does not approve unknown legal/consent answers or bypass CAPTCHA/MFA.
Scripts retain final-submit guards; see `docs/agent-rules.md`.

# Contributing

Use Python 3.10 or newer. Bootstrap the editable environment and redacted local
configuration:

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
```

Use `./scripts/bootstrap.sh --with-browser` only for browser changes.

Before opening a pull request, run:

```bash
make release-check
make private-check
```

The private configuration check may report blank-field warnings in a fresh
template. It must not report errors. Never include real resumes, candidate
identity, credentials, cookies, browser state, databases, screenshots, or
generated application artifacts in a commit or issue.

New collectors belong in `job_bot/sources/`; new application-site behavior
belongs in `application_bot/` or `job_bot/applications/`. Add a deterministic
fixture test and keep network access out of unit tests. Application adapters
must preserve the review gate and must never make final submission the default.

See `AGENTS.md` for repository invariants and `docs/interfaces.md` for extension
contracts.

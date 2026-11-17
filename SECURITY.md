# Security policy

Do not report a vulnerability by attaching real credentials, cookies, browser
state, resumes, application screenshots, or database files to a public issue.
Create a minimal synthetic reproduction and use GitHub's private vulnerability
reporting channel when it is available.

Treat every file below `private_data/` as sensitive except its tracked README.
If a credential enters Git history, revoke or rotate it before rewriting the
history. History removal alone does not invalidate a leaked credential.

Program adapters stop before final submission. A capable Agent's scoped browser
submission follows the three choices in [Agent rules](docs/agent-rules.md). A change
that weakens the submit guard, infers legal/immigration answers, bypasses MFA or
CAPTCHA, or exports browser credentials is a security-sensitive change and
requires explicit review.

# Public templates

All files ending in `_template` contain public examples. Mike Malon, his NYU
Computer Science degree, dates, contact and projects are fictional. None of the
examples establishes a real person's work authorization, nationality or consent.

| File | Purpose and filling instructions |
| --- | --- |
| `database_connection_template.json` | Every connection field is explained in `_comment`. Fill real settings only in private `config/database_connection.json`; prefer `jobbot-db configure`. |
| `database_template.sql` | Empty database schema with a comment for every column. Contains no candidate or application rows. Normal initialization uses `jobbot init`; application commands add campaign tables as needed. |
| `application_profile_template.json` | Fictional profile and section-by-section `_comment` guidance. Replace every demonstration value before real use. |
| `evidence_profile_template.json` | Fictional claim inventory with filling notes and no assumed legal answers. |
| `resume_template.tex` | Commented, one-page Mike Malon / NYU CS resume source; compatible with the generator's Summary and Technical Skills markers. |

The existing blank `application_profile.json`, `evidence_profile.json` and
`application_keywords.json` remain the bootstrap defaults. `_comment` is valid
JSON metadata, not a JavaScript comment; the profile readers tolerate it. Do not
add `//` or trailing commas to runtime JSON.

To try the fictional examples, use a separate clone or a temporary private root.
Copy profiles into their canonical locations, `resume_template.tex` to private
`cv/source/current.tex`, and retain a keyword library initialized by
`jobbot-private init`. Review [the handoff guide](../AGENT_HANDOFF.md) before using
the same commands with real material. Bootstrap never copies the fictional
person over an existing private profile.

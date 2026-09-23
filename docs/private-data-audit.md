# Private data structure audit

The candidate data model is split into four author-maintained files plus
generated state. This audit evaluates usability and consistency without
recording any candidate values.

## Findings

The earlier layout had three practical weaknesses:

1. The application template did not describe several sections already consumed
   by adapters, so a fresh user could not discover all supported fields.
2. Identity, graduation dates, and GPA can appear in application, evidence, and
   resume source files. These copies are useful to different tools but can
   silently drift.
3. Keyword presets referenced IDs by convention without a standalone integrity
   check.

The public runtime configuration was already reasonably modular: runtime,
sources, scoring, strategy, workflows, portals, and field mappings have separate
owners and can be composed without copying the full configuration.

## Changes made

- Replaced the partial application-profile template with complete redacted
  examples under `examples/`.
- Added JSON Schemas under `schemas/` for the application profile, evidence
  profile, and keyword library.
- Added `jobbot-private init`, which creates missing files with mode `600` and
  does not overwrite existing data unless `--force` is explicitly supplied.
- Added `jobbot-private check`, which validates types, safety gates,
  authorization scopes, credential syntax and permissions, duplicate records,
  keyword references, and cross-file email consistency without printing values.
- Added one canonical path module and support for relocating the entire private
  tree with `JOBBOT_PRIVATE_DIR`.

## Authoring assessment

The generated files are now self-contained enough to fill by hand. Stable facts
belong in `application_profile.json`; claim evidence and resume positioning
belong in `evidence_profile.json`; reusable application vocabulary belongs in
`application_keywords.json`; secrets and session endpoints belong in
`passport.env`.

Some factual duplication remains for compatibility with existing adapters.
Treat the application profile as the canonical source for form facts and the
evidence profile as the canonical source for claims. Run the checker after any
identity, education, graduation, or keyword change. Resume `.tex` files are
rendered artifacts from a data-governance perspective and should be reviewed
against both profiles before use.

The checker deliberately warns about blank identity fields in a newly generated
template. Warnings allow installation to finish; application preparation should
begin only after the candidate has filled and reviewed those fields.

## Remaining design opportunities

- A future schema version can replace duplicated education facts with stable
  record IDs shared by the application and evidence profiles.
- Portal-specific answer dictionaries can move into separate files if the
  application profile becomes difficult to review.
- An encrypted sync provider can back up `JOBBOT_PRIVATE_DIR`, but decryption
  and mount management should remain outside this repository.


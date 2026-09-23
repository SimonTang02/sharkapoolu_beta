# External CV and cover-letter tools

Reviewed on 2026-08-28 from the projects' official GitHub repositories.

## Recommendation

Use Resume Matcher as an optional, isolated analysis service for JD keyword
coverage, suggestions, and cover-letter drafts. Keep `current.tex` as the
canonical resume and require a diff plus PDF review before promoting a variant.

Do not make AIHawk the production application engine. Although it is a very
popular project, its repository is archived and its third-party provider
plugins have been removed. Its broad auto-application model also conflicts with
this project's per-site review and no-submit safety boundary.

The local `cv/bot` module is intentionally smaller: it selects only
reviewed evidence, produces a review packet, and has no network or submit path.

## Projects evaluated

- Resume Matcher: https://github.com/srbhr/Resume-Matcher
  - Active project with local Ollama support, multiple hosted LLM providers,
    master-resume/JD tailoring, cover-letter generation, and PDF export.
  - Best candidate for later Docker-based Synology experimentation.
- AIHawk: https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk
  - Roughly 30k stars, but archived in May 2026 and third-party application
    plugins are absent from the open repository.
  - Useful architectural reference, not a dependency for automatic submission.
- CoverLetterGPT: https://github.com/vincanger/coverlettergpt
  - Dedicated cover-letter and job-management application, but adds Wasp,
    PostgreSQL, authentication, payments, and external API complexity that the
    current local workflow does not need.
- tailor-resume: https://github.com/narendranathe/tailor-resume
  - Interesting deterministic LaTeX/evidence approach and a relevance gate,
    but currently a small project; borrow design ideas rather than adopting it
    as a core dependency.

## Integration boundary

Any later external integration must:

1. Run in a separate environment/container with a pinned version.
2. Receive a copy of the resume, never the only canonical source.
3. Produce an auditable diff or new variant under `private_data/cv/variants/`.
4. Never introduce an unverified skill, metric, employer, or credential.
5. Never send an application or overwrite `current.tex` without human review.

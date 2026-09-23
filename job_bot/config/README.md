# Composed configuration

`jobbot.json` is the canonical composition root. The older
`../config.china_hk_ic_foreign.json` includes it so existing commands continue
to work.

## Ownership by file

| File | Owns | Does not own |
|---|---|---|
| `runtime.json` | database, retry/concurrency, lifecycle guard, browser, report and email runtime | job preference |
| `workflows.json` | named sequences of independently runnable modules | credentials or selectors inside websites |
| `sources.json` | endpoints, pagination, source filters, source category and active-sync policy | global ranking |
| `scoring.json` | broad retrieval relevance: Foundation scores and resume-evidence modifiers | graduation/location eligibility |
| `strategy.json` | narrow application eligibility and priority for the current two tracks | HTTP/browser mechanics |
| `portals.json` | ATS detection, login probes and adapter routing | candidate facts |
| `field_mappings.json` | logical form mappings and no-submit safety | credentials |

The two keyword layers are deliberate. `scoring` answers “is this broadly
related to the candidate?” and writes `jobs.fit_score`. `strategy` answers
“is this role eligible and worth applying to under the current campaign?” It
applies geography, graduation term, degree, seniority and track-specific
ranking. A retrieval keyword should not silently bypass a strategy exclusion.

Merge rules are deterministic:

1. Includes are loaded in listed order, relative to the including file.
2. Objects are merged recursively.
3. Lists and scalar values are replaced by the later value.
4. The including file is the final overlay.
5. `patches` are applied after that file's merge.
6. Include cycles, ambiguous patches, duplicate IDs, invalid scores/workflows,
   unsafe lifecycle parameters, and an enabled final-submit policy are rejected
   before work starts.

## Small, reviewable experiments

Do not copy all of `sources.json` or `scoring.json` to change one value. An
overlay can patch exactly one named list item:

```json
{
  "includes": ["../jobbot.json"],
  "experiment": {
    "name": "rtl_cdc_v1",
    "hypothesis": "CDC should improve direct digital-design ranking"
  },
  "patches": [
    {
      "path": "scoring.foundation_groups",
      "match": {"name": "digital RTL design"},
      "set": {
        "base_score": 76,
        "keywords": {
          "$append": ["CDC", "clock-domain crossing"],
          "$remove": ["an obsolete keyword"]
        }
      }
    }
  ]
}
```

`$append` de-duplicates values, `$remove` removes exact values, and `$replace`
explicitly replaces the list. A patch must match exactly one object; a typo is
an error rather than a silent no-op. See
`experiments/keyword_tuning.example.json` for a runnable example.

Validate and inspect the effective config:

```bash
make config-check
make config-check CONFIG=job_bot/config/experiments/keyword_tuning.example.json
```

Evaluate keyword/weight changes without changing SQLite:

```bash
make workflow \
  WORKFLOW=score_experiment \
  CONFIG=job_bot/config/experiments/keyword_tuning.example.json
```

The experiment report records an effective-config SHA-256, score distribution,
largest deltas and top jobs. Only use the explicit `rescore` module after
reviewing that report.

## Independently runnable modules

Named workflows are defined in `workflows.json`:

- `daily`: existing complete daily pipeline.
- `digest_24h`: build/send only the rolling 24-hour digest from SQLite.
- `report_only`: rebuild all reports without network access or database scoring writes.
- `weekly_only`: database-only weekly rebuild.
- `http_refresh`: HTTP sources, rescore, score report, strategy report, weekly.
- `browser_refresh`: CDP sources followed by the same reports.
- `score_experiment`: read-only score simulation using an overlay.
- `login_audit`: read-only login/session probes.

Preview the exact argv commands before doing work, or execute them:

```bash
make workflow-plan WORKFLOW=http_refresh
make workflow WORKFLOW=http_refresh
```

The runner writes `module_run_*.json` with the config hash, selector, commands,
durations and return codes. It never contains credential values.

The low-level scanner can also select sources without editing JSON:

```bash
python3 job_bot/bot.py scan --source-browser http --max-workers 3
python3 job_bot/bot.py scan --company NVIDIA
python3 job_bot/bot.py scan \
  --source-category official_company_us_2027_internship
python3 job_bot/bot.py scan --source-type workday --exclude-source "NXP Greater China IC Design"
```

Different selector fields are intersected; repeated values within one field are
alternatives. Disabled sources are never selected.

## Parameters worth tuning

- `scan.max_workers`: network concurrency. Start with 3 on J1900 and 8 on the
  current workstation.
- `retry_attempts` / `retry_backoff_seconds`: transient network recovery, not a
  bypass for authentication or anti-bot controls.
- Per-source `max_pages`, `page_size`, `request_delay_seconds`: collector load
  and coverage.
- Foundation `base_score`, `body_only_adjustment`, `min_body_hits`: determines
  the role's underlying category before bonuses.
- Modifier `points`, `scope`, `keywords`: resume evidence, preference and
  explicit penalties.
- `scoring.bands`: reporting/queue bands for broad relevance.
- `strategy.minimum_score`, `tier_thresholds`, `tracks` and `patterns`: final
  campaign eligibility and priority.

`sync_active` is not an ordinary tuning switch. It means a successful source
response is a complete snapshot and missing jobs may be marked inactive. The
runtime lifecycle guard rejects empty or implausibly small snapshots before
changing active states. Override its thresholds per source only after proving
that source's pagination is complete.

Secrets and candidate facts never belong here. Keep them in the ignored
`private_data/` tree and refer to them through `private_paths.py`.

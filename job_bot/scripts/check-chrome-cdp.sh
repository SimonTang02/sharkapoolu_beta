#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/../.." && pwd)"
command_name="browser-health"

if [[ "${1:-}" == "--smoke" ]]; then
  command_name="browser-smoke"
  shift
fi

exec python3 "$project_root/job_bot/application_bot.py" "$command_name" \
  --config "$project_root/job_bot/config.china_hk_ic_foreign.json" \
  --env-file "$project_root/private_data/credentials/passport.env" \
  "$@"

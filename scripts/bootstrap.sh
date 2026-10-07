#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
with_browser=false
with_resume=false
run_tests=true

for argument in "$@"; do
  case "$argument" in
    --with-browser) with_browser=true ;;
    --with-resume) with_resume=true ;;
    --skip-tests) run_tests=false ;;
    -h|--help)
      echo "Usage: scripts/bootstrap.sh [--with-browser] [--with-resume] [--skip-tests]"
      exit 0
      ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done

cd "$project_root"
if [[ ! -x .venv/bin/python ]]; then
  if ! "$python_bin" -m venv .venv; then
    echo "Could not create .venv. On Ubuntu/WSL install python3-venv first." >&2
    exit 1
  fi
fi

.venv/bin/python -m pip install --upgrade pip
install_target="."
if $with_browser && $with_resume; then
  install_target='.[browser,resume]'
elif $with_browser; then
  install_target='.[browser]'
elif $with_resume; then
  install_target='.[resume]'
fi
.venv/bin/python -m pip install -e "$install_target"
if $with_browser; then
  .venv/bin/python -m playwright install chromium
fi

.venv/bin/python -m job_bot.private_config init
.venv/bin/python -m job_bot.private_config check
.venv/bin/python job_bot/config_inspect.py \
  --config job_bot/config.china_hk_ic_foreign.json

if $run_tests; then
  .venv/bin/python -m unittest discover -s . -p 'test_*.py'
fi

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
if $with_browser; then
  echo "Linux may still require: sudo .venv/bin/python -m playwright install-deps chromium"
fi

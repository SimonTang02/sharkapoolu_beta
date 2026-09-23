#!/usr/bin/env python3
"""Validate and summarize an effective composed job-bot configuration."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_bot.bot import load_config  # noqa: E402
from job_bot.run_modules import effective_config_hash  # noqa: E402
from job_bot.source_selector import uses_browser  # noqa: E402


DEFAULT_CONFIG = ROOT / "job_bot/config.china_hk_ic_foreign.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--effective-json",
        type=Path,
        help="Write the merged, patched, secret-free effective config",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    sources = config.get("sources", [])
    enabled = [source for source in sources if source.get("enabled", True) is not False]
    categories = Counter(str(source.get("source_category") or "uncategorized") for source in enabled)
    types = Counter(str(source.get("type") or "unknown") for source in enabled)
    print(f"Config: {args.config.resolve()}")
    print(f"SHA-256: {effective_config_hash(config)}")
    if config.get("experiment"):
        print(f"Experiment: {config['experiment'].get('name', 'unnamed')}")
    print(
        f"Sources: total={len(sources)} enabled={len(enabled)} "
        f"http={sum(not uses_browser(source) for source in enabled)} "
        f"cdp={sum(uses_browser(source) for source in enabled)}"
    )
    print("Source categories:")
    for name, count in sorted(categories.items()):
        print(f"  {name}: {count}")
    print("Source types:")
    for name, count in sorted(types.items()):
        print(f"  {name}: {count}")
    scoring = config.get("scoring", {})
    print(
        f"Scoring: algorithm={scoring.get('algorithm')} "
        f"purpose={scoring.get('purpose')}"
    )
    for group in scoring.get("foundation_groups", []):
        print(
            f"  foundation={group.get('name')} base={group.get('base_score')} "
            f"keywords={len(group.get('keywords', []))}"
        )
    strategy = config.get("strategy", {})
    print(
        f"Strategy: name={strategy.get('name')} purpose={strategy.get('purpose')} "
        f"minimum_score={strategy.get('minimum_score')}"
    )
    print("Workflows:")
    for name, workflow in sorted(config.get("workflows", {}).items()):
        print(f"  {name}: {' -> '.join(workflow.get('modules', []))}")
    if args.effective_json:
        args.effective_json.parent.mkdir(parents=True, exist_ok=True)
        args.effective_json.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Effective config: {args.effective_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

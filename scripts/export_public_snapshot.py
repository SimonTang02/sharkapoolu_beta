#!/usr/bin/env python3
"""Export the audited working tree into a new history-free directory."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from audit_public_repo import ROOT, audit_current_tree, publishable_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--init",
        action="store_true",
        help="initialize an empty Git repository with main as its initial branch",
    )
    args = parser.parse_args()

    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Destination must be outside the source repository")

    problems = audit_current_tree()
    if problems:
        for problem in sorted(set(problems)):
            print(problem)
        raise SystemExit("Public audit failed; snapshot was not created")

    paths = publishable_paths()
    destination.mkdir(parents=True)
    for relative in paths:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    if args.init:
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=destination,
            check=True,
        )
    print(f"Exported {len(paths)} files to {destination}")


if __name__ == "__main__":
    main()

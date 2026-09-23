#!/usr/bin/env python3
"""Use the resume's Hong Kong phone for the China/HK application campaign."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from private_paths import APPLICATION_PROFILE, JOBBOT_OUTPUT
from private_paths import CURRENT_RESUME_TEX

RESUME = CURRENT_RESUME_TEX
BASE_PROFILE = APPLICATION_PROFILE
APPLICATIONS = JOBBOT_OUTPUT / "applications"


def update(path: Path, phone: str) -> bool:
    if not path.is_file():
        return False
    profile = json.loads(path.read_text(encoding="utf-8"))
    scopes = profile.get("explicit_authorization", {}).get("location_scopes", [])
    if not {"mainland_china", "hong_kong"}.intersection(scopes):
        return False
    profile.setdefault("fields", {})["phone"] = phone
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return True


def main() -> None:
    resume = RESUME.read_text(encoding="utf-8")
    match = re.search(r"HK:\s*([+\d][\d ()-]+)", resume)
    if not match:
        raise SystemExit("No explicitly labelled HK phone was found in current.tex")
    phone = match.group(1).strip()
    paths = [BASE_PROFILE, *APPLICATIONS.glob("*/profile.json")]
    count = sum(update(path, phone) for path in paths)
    print(f"Updated {count} authorized China/Hong Kong profiles with the HK contact number")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Initialize and validate the ignored candidate configuration tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from private_paths import (  # noqa: E402
    APPLICATION_KEYWORDS,
    APPLICATION_PROFILE,
    CREDENTIALS_FILE,
    EVIDENCE_PROFILE,
    EASY_SETTINGS,
    MANUAL_DATABASE_DIR,
    PRIVATE_CONFIG,
    PRIVATE_ROOT,
    ensure_private_directories,
)


EXAMPLES = ROOT / "examples"
TEMPLATES = {
    MANUAL_DATABASE_DIR / "jobs.csv": EXAMPLES / "manual_jobs_template.csv",
    MANUAL_DATABASE_DIR / "applications.csv": EXAMPLES / "manual_applications_template.csv",
    EASY_SETTINGS: EXAMPLES / "easy_settings_template.json",
    APPLICATION_PROFILE: EXAMPLES / "application_profile.json",
    EVIDENCE_PROFILE: EXAMPLES / "evidence_profile.json",
    APPLICATION_KEYWORDS: EXAMPLES / "application_keywords.json",
    CREDENTIALS_FILE: ROOT / "job_bot" / "env.template",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
AUTHORIZED_LOCATION_SCOPES = {"mainland_china", "hong_kong", "united_states"}


@dataclass(frozen=True)
class Issue:
    level: str
    path: str
    message: str


def _issue(issues: list[Issue], level: str, path: str, message: str) -> None:
    issues.append(Issue(level, path, message))


def _load_json(path: Path, issues: list[Issue]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _issue(issues, "ERROR", str(path), "file is missing")
        return None
    except json.JSONDecodeError as exc:
        _issue(issues, "ERROR", str(path), f"invalid JSON at line {exc.lineno}")
        return None
    except OSError as exc:
        _issue(issues, "ERROR", str(path), f"cannot read file: {exc.strerror or exc}")
        return None
    if not isinstance(value, dict):
        _issue(issues, "ERROR", str(path), "root must be a JSON object")
        return None
    return value


def _expect_type(
    data: dict[str, Any], key: str, expected: type, path: str, issues: list[Issue]
) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        _issue(issues, "ERROR", f"{path}.{key}", f"must be {expected.__name__}")
        return None
    return value


def validate_application_profile(data: dict[str, Any], path: str = "application_profile") -> list[Issue]:
    issues: list[Issue] = []
    version = data.get("schema_version", 1)
    if version != 1:
        _issue(issues, "ERROR", f"{path}.schema_version", "supported value is 1")

    fields = _expect_type(data, "fields", dict, path, issues)
    documents = _expect_type(data, "documents", dict, path, issues)
    safety = _expect_type(data, "safety", dict, path, issues)
    for key in ("education", "languages", "work_experience", "projects", "skills"):
        if key in data and not isinstance(data[key], list):
            _issue(issues, "ERROR", f"{path}.{key}", "must be list")
    for key in (
        "workday_checkbox_groups",
        "custom_answers",
        "voluntary_disclosures",
        "explicit_authorization",
        "career_preferences",
        "personal_facts_confirmation",
    ):
        if key in data and not isinstance(data[key], dict):
            _issue(issues, "ERROR", f"{path}.{key}", "must be object")

    if fields is not None:
        for key, value in fields.items():
            if key == "previous_nvidia_worker":
                if value is not None and not isinstance(value, bool):
                    _issue(issues, "ERROR", f"{path}.fields.{key}", "must be boolean or null")
            elif key == "how_did_you_hear":
                valid = isinstance(value, str) or (
                    isinstance(value, list) and all(isinstance(item, str) for item in value)
                )
                if not valid:
                    _issue(issues, "ERROR", f"{path}.fields.{key}", "must be string or string list")
            elif not isinstance(value, str):
                _issue(issues, "ERROR", f"{path}.fields.{key}", "must be string")
        email = str(fields.get("email") or "").strip()
        if email and not EMAIL_PATTERN.fullmatch(email):
            _issue(issues, "ERROR", f"{path}.fields.email", "is not a valid email shape")
        for required in ("first_name", "last_name", "email", "phone", "country"):
            if not str(fields.get(required) or "").strip():
                _issue(issues, "WARNING", f"{path}.fields.{required}", "is blank")

    if documents is not None:
        for key in ("resume_path", "cover_letter_path"):
            if key in documents and not isinstance(documents[key], str):
                _issue(issues, "ERROR", f"{path}.documents.{key}", "must be string")

    if safety is not None:
        for key in ("allow_sensitive_answers", "allow_server_draft", "allow_submit"):
            if not isinstance(safety.get(key), bool):
                _issue(issues, "ERROR", f"{path}.safety.{key}", "must be boolean")
        if safety.get("allow_submit") is not False:
            _issue(issues, "ERROR", f"{path}.safety.allow_submit", "must remain false")

    authorization = data.get("explicit_authorization", {})
    if isinstance(authorization, dict):
        confirmed = authorization.get("user_confirmed", False)
        scopes = authorization.get("location_scopes", [])
        if confirmed is not False and confirmed is not True:
            _issue(issues, "ERROR", f"{path}.explicit_authorization.user_confirmed", "must be boolean")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            _issue(issues, "ERROR", f"{path}.explicit_authorization.location_scopes", "must be string list")
        elif unknown_scopes := set(scopes) - AUTHORIZED_LOCATION_SCOPES:
            _issue(
                issues,
                "ERROR",
                f"{path}.explicit_authorization.location_scopes",
                f"contains unsupported values: {', '.join(sorted(unknown_scopes))}",
            )
        if confirmed and not scopes:
            _issue(issues, "ERROR", f"{path}.explicit_authorization.location_scopes", "cannot be empty when confirmed")

    for section, identity_keys in (
        ("education", ("school", "degree", "from_year", "to_year")),
        ("work_experience", ("job_title", "company", "start_year", "end_year")),
        ("projects", ("name", "role", "start_year", "end_year")),
    ):
        entries = data.get(section, [])
        if not isinstance(entries, list):
            continue
        seen: set[tuple[str, ...]] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                _issue(issues, "ERROR", f"{path}.{section}[{index}]", "must be object")
                continue
            identity = tuple(str(entry.get(key) or "").strip().casefold() for key in identity_keys)
            if any(identity) and identity in seen:
                _issue(issues, "WARNING", f"{path}.{section}[{index}]", "appears to duplicate an earlier entry")
            seen.add(identity)
    return issues


def validate_evidence_profile(data: dict[str, Any], path: str = "evidence_profile") -> list[Issue]:
    issues: list[Issue] = []
    if data.get("schema_version", 1) != 1:
        _issue(issues, "ERROR", f"{path}.schema_version", "supported value is 1")
    identity = _expect_type(data, "identity", dict, path, issues)
    groups = _expect_type(data, "evidence_groups", list, path, issues)
    if identity is not None:
        email = str(identity.get("email") or "").strip()
        if email and not EMAIL_PATTERN.fullmatch(email):
            _issue(issues, "ERROR", f"{path}.identity.email", "is not a valid email shape")
    if groups is not None:
        names: set[str] = set()
        for index, group in enumerate(groups):
            item_path = f"{path}.evidence_groups[{index}]"
            if not isinstance(group, dict):
                _issue(issues, "ERROR", item_path, "must be object")
                continue
            name = str(group.get("name") or "").strip()
            if not name:
                _issue(issues, "WARNING", f"{item_path}.name", "is blank")
            elif name.casefold() in names:
                _issue(issues, "ERROR", f"{item_path}.name", "must be unique")
            names.add(name.casefold())
            if not isinstance(group.get("keywords", []), list):
                _issue(issues, "ERROR", f"{item_path}.keywords", "must be list")
            elif not all(isinstance(keyword, str) for keyword in group.get("keywords", [])):
                _issue(issues, "ERROR", f"{item_path}.keywords", "must contain only strings")
            if not str(group.get("evidence") or "").strip():
                _issue(issues, "WARNING", f"{item_path}.evidence", "is blank")
    return issues


def validate_keyword_library(data: dict[str, Any], path: str = "application_keywords") -> list[Issue]:
    issues: list[Issue] = []
    if data.get("schema_version") != 1:
        _issue(issues, "ERROR", f"{path}.schema_version", "supported value is 1")
    sources = _expect_type(data, "sources", dict, path, issues) or {}
    technical = _expect_type(data, "technical_keywords", list, path, issues) or []
    collaboration = _expect_type(data, "collaboration_personality_keywords", list, path, issues) or []
    presets = _expect_type(data, "role_presets", list, path, issues) or []
    ids: set[str] = set()
    technical_ids: set[str] = set()
    collaboration_ids: set[str] = set()
    required = {"id", "english", "chinese", "evidence", "example_en", "source_ids", "claim_status"}
    for section, entries, target in (
        ("technical_keywords", technical, technical_ids),
        ("collaboration_personality_keywords", collaboration, collaboration_ids),
    ):
        for index, entry in enumerate(entries):
            item_path = f"{path}.{section}[{index}]"
            if not isinstance(entry, dict):
                _issue(issues, "ERROR", item_path, "must be object")
                continue
            missing = sorted(key for key in required if key not in entry)
            if missing:
                _issue(issues, "ERROR", item_path, f"missing required keys: {', '.join(missing)}")
            entry_id = str(entry.get("id") or "")
            if not entry_id:
                _issue(issues, "ERROR", f"{item_path}.id", "must be a non-empty string")
            if entry_id in ids:
                _issue(issues, "ERROR", f"{item_path}.id", "must be unique")
            ids.add(entry_id)
            target.add(entry_id)
            source_ids = entry.get("source_ids", [])
            if not isinstance(source_ids, list) or not all(
                isinstance(source_id, str) for source_id in source_ids
            ):
                _issue(issues, "ERROR", f"{item_path}.source_ids", "must be a string list")
                source_ids = []
            for source_id in source_ids:
                if source_id not in sources:
                    _issue(issues, "ERROR", f"{item_path}.source_ids", f"unknown source: {source_id}")
    preset_ids: set[str] = set()
    for index, preset in enumerate(presets):
        item_path = f"{path}.role_presets[{index}]"
        if not isinstance(preset, dict):
            _issue(issues, "ERROR", item_path, "must be object")
            continue
        preset_id = str(preset.get("id") or "")
        if not preset_id or preset_id in preset_ids:
            _issue(issues, "ERROR", f"{item_path}.id", "must be present and unique")
        preset_ids.add(preset_id)
        references: dict[str, list[str]] = {}
        for key in ("technical_ids", "collaboration_ids", "role_match_terms"):
            values = preset.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                _issue(issues, "ERROR", f"{item_path}.{key}", "must be a string list")
                values = []
            references[key] = values
        unknown_technical = set(references["technical_ids"]) - technical_ids
        unknown_collaboration = set(references["collaboration_ids"]) - collaboration_ids
        if unknown_technical or unknown_collaboration:
            _issue(issues, "ERROR", item_path, "references unknown keyword IDs")
    return issues


def validate_credentials(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    if not path.is_file():
        return [Issue("ERROR", str(path), "file is missing")]
    names: set[str] = set()
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Issue("ERROR", str(path), f"cannot read file: {exc.strerror or exc}")]
    for line_number, raw in enumerate(contents.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            _issue(issues, "ERROR", f"{path}:{line_number}", "expected NAME=VALUE")
            continue
        name = line.split("=", 1)[0].strip()
        if not ENV_NAME_PATTERN.fullmatch(name):
            _issue(issues, "ERROR", f"{path}:{line_number}", "invalid environment variable name")
        if name in names:
            _issue(issues, "WARNING", f"{path}:{line_number}", f"duplicate variable: {name}")
        names.add(name)
    mode = stat.S_IMODE(path.stat().st_mode)
    if os.name == "nt":
        _issue(issues, "WARNING", str(path), "Windows privacy requires owner-restricted NTFS ACLs; Unix mode 600 cannot verify them")
    elif mode & 0o077:
        _issue(issues, "ERROR", str(path), f"permissions are {mode:o}; expected 600")
    return issues


def check_private_tree() -> list[Issue]:
    issues: list[Issue] = []
    if EASY_SETTINGS.is_file():
        try:
            from job_bot.operator_settings import load_settings
            load_settings(EASY_SETTINGS)
        except ValueError as exc:
            _issue(issues, "ERROR", str(EASY_SETTINGS), str(exc))
    application = _load_json(APPLICATION_PROFILE, issues)
    evidence = _load_json(EVIDENCE_PROFILE, issues)
    keywords = _load_json(APPLICATION_KEYWORDS, issues)
    if application is not None:
        issues.extend(validate_application_profile(application))
    if evidence is not None:
        issues.extend(validate_evidence_profile(evidence))
    if keywords is not None:
        issues.extend(validate_keyword_library(keywords))
    issues.extend(validate_credentials(CREDENTIALS_FILE))
    if PRIVATE_CONFIG.is_file():
        try:
            from job_bot.config_loader import ConfigError, load_composed_config, validate_config

            validate_config(load_composed_config(PRIVATE_CONFIG))
        except (ConfigError, OSError, ValueError) as exc:
            _issue(issues, "ERROR", str(PRIVATE_CONFIG), f"invalid runtime override: {exc}")
    if application is not None and evidence is not None:
        application_email = str(application.get("fields", {}).get("email") or "").casefold()
        evidence_email = str(evidence.get("identity", {}).get("email") or "").casefold()
        if application_email and evidence_email and application_email != evidence_email:
            _issue(issues, "ERROR", "cross_file.identity.email", "application and evidence profiles disagree")
    return issues


def initialize_private_tree(force: bool = False) -> tuple[list[Path], list[Path]]:
    ensure_private_directories()
    created: list[Path] = []
    skipped: list[Path] = []
    for destination, source in TEMPLATES.items():
        if not source.is_file():
            raise FileNotFoundError(f"private configuration template is missing: {source}")
        if destination.exists() and not force:
            skipped.append(destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o600)
        created.append(destination)
    return created, skipped


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create missing private files from examples")
    init_parser.add_argument("--force", action="store_true", help="replace existing private files")
    subparsers.add_parser("check", help="validate private files without printing their values")
    subparsers.add_parser("paths", help="show resolved private file locations")
    args = parser.parse_args()

    if args.command == "init":
        try:
            created, skipped = initialize_private_tree(force=args.force)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for path in created:
            print(f"CREATED {_relative(path)}")
        for path in skipped:
            print(f"KEPT {_relative(path)}")
        return 0
    if args.command == "paths":
        print(f"private_root={PRIVATE_ROOT}")
        for path in TEMPLATES:
            print(_relative(path))
        return 0

    issues = check_private_tree()
    for issue in issues:
        print(f"{issue.level} {issue.path}: {issue.message}")
    errors = sum(issue.level == "ERROR" for issue in issues)
    warnings = sum(issue.level == "WARNING" for issue in issues)
    print(f"Private configuration check: errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

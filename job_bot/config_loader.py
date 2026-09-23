"""Composable JSON configuration with recursive, relative includes."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


class ConfigError(RuntimeError):
    pass


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in {"includes", "patches"}:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _patched_value(current: Any, patch: Any, context: str) -> Any:
    """Merge a patch, with explicit append/remove operations for list values."""
    if isinstance(current, list) and isinstance(patch, dict) and any(
        key.startswith("$") for key in patch
    ):
        allowed = {"$append", "$remove", "$replace"}
        unknown = set(patch) - allowed
        if unknown:
            raise ConfigError(
                f"Unsupported list operation(s) at {context}: {', '.join(sorted(unknown))}"
            )
        if "$replace" in patch:
            replacement = patch["$replace"]
            if not isinstance(replacement, list):
                raise ConfigError(f"$replace must be a list at {context}")
            result = list(replacement)
        else:
            result = list(current)
        remove = patch.get("$remove", [])
        append = patch.get("$append", [])
        if not isinstance(remove, list) or not isinstance(append, list):
            raise ConfigError(f"$append/$remove must be lists at {context}")
        result = [item for item in result if item not in remove]
        for item in append:
            if item not in result:
                result.append(item)
        return result
    if isinstance(current, dict) and isinstance(patch, dict):
        result = dict(current)
        for key, value in patch.items():
            child_context = f"{context}.{key}" if context else key
            result[key] = (
                _patched_value(result[key], value, child_context)
                if key in result
                else value
            )
        return result
    return patch


def _resolve_path(config: dict[str, Any], dotted_path: str) -> Any:
    current: Any = config
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigError(f"Patch path does not exist: {dotted_path}")
        current = current[part]
    return current


def apply_patches(
    config: dict[str, Any], patches: Any, *, source: Path | None = None
) -> dict[str, Any]:
    """Patch named objects inside lists without copying the whole base list."""
    if patches in (None, []):
        return config
    if not isinstance(patches, list):
        raise ConfigError("'patches' must be a list")
    result = config
    for index, operation in enumerate(patches):
        context = f"patches[{index}]"
        if source:
            context = f"{source}:{context}"
        if not isinstance(operation, dict):
            raise ConfigError(f"Patch must be an object: {context}")
        path = str(operation.get("path", "")).strip()
        match = operation.get("match")
        changes = operation.get("set")
        if not path or not isinstance(match, dict) or not match:
            raise ConfigError(f"Patch requires path and non-empty match: {context}")
        if not isinstance(changes, dict):
            raise ConfigError(f"Patch 'set' must be an object: {context}")
        target = _resolve_path(result, path)
        if not isinstance(target, list):
            raise ConfigError(f"Patch target must be a list: {path}")
        matched = [
            item
            for item in target
            if isinstance(item, dict)
            and all(item.get(key) == value for key, value in match.items())
        ]
        if len(matched) != 1:
            raise ConfigError(
                f"Patch must match exactly one item at {path}; matched {len(matched)}: {context}"
            )
        item = matched[0]
        patched = _patched_value(item, changes, f"{path}[{match}]")
        item.clear()
        item.update(patched)
    return result


def load_composed_config(path: Path, _stack: tuple[Path, ...] = ()) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if resolved in _stack:
        chain = " -> ".join(str(item) for item in (*_stack, resolved))
        raise ConfigError(f"Configuration include cycle: {chain}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config not found: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"Config root must be an object: {resolved}")

    merged: dict[str, Any] = {}
    includes = payload.get("includes", [])
    if isinstance(includes, str):
        includes = [includes]
    if not isinstance(includes, list) or not all(isinstance(item, str) for item in includes):
        raise ConfigError(f"'includes' must be a string list: {resolved}")
    for include in includes:
        child = (resolved.parent / include).resolve()
        merged = deep_merge(
            merged, load_composed_config(child, (*_stack, resolved))
        )
    combined = deep_merge(merged, payload)
    return apply_patches(combined, payload.get("patches", []), source=resolved)


def validate_config(config: dict[str, Any]) -> None:
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        raise ConfigError("'sources' must be a list")
    source_names = [str(item.get("name", "")) for item in sources if isinstance(item, dict)]
    if any(not name for name in source_names):
        raise ConfigError("Every source must have a non-empty name")
    if len(source_names) != len(set(source_names)):
        raise ConfigError("Source names must be unique")
    adapters = config.get("portals", {}).get("adapters", [])
    adapter_ids = [str(item.get("id", "")) for item in adapters if isinstance(item, dict)]
    if any(not adapter_id for adapter_id in adapter_ids):
        raise ConfigError("Every portal adapter must have a non-empty id")
    if len(adapter_ids) != len(set(adapter_ids)):
        raise ConfigError("Portal adapter ids must be unique")
    for adapter in adapters:
        adapter_id = str(adapter.get("id", "<unnamed>"))
        if int(adapter.get("timeout_seconds", 180)) < 1:
            raise ConfigError(
                f"portal adapter {adapter_id!r} timeout_seconds must be at least 1"
            )
    company_profiles = config.get("portals", {}).get("company_profiles", [])
    company_profile_ids = [
        str(item.get("id", "")) for item in company_profiles if isinstance(item, dict)
    ]
    if any(not profile_id for profile_id in company_profile_ids):
        raise ConfigError("Every company portal profile must have a non-empty id")
    if len(company_profile_ids) != len(set(company_profile_ids)):
        raise ConfigError("Company portal profile ids must be unique")
    known_adapter_ids = set(adapter_ids)
    for profile in company_profiles:
        profile_id = str(profile.get("id", "<unnamed>"))
        if str(profile.get("adapter", "")) not in known_adapter_ids:
            raise ConfigError(
                f"company portal profile {profile_id!r} references an unknown adapter"
            )
        if not profile.get("company_patterns"):
            raise ConfigError(
                f"company portal profile {profile_id!r} requires company_patterns"
            )
    allow_submit = config.get("field_mappings", {}).get("safety", {}).get("allow_submit")
    if allow_submit is not False:
        raise ConfigError("field_mappings.safety.allow_submit must be false")
    workers = int(config.get("scan", {}).get("max_workers", 1))
    if workers < 1:
        raise ConfigError("scan.max_workers must be at least 1")
    retry_attempts = int(config.get("scan", {}).get("retry_attempts", 0))
    retry_backoff = float(config.get("scan", {}).get("retry_backoff_seconds", 0))
    if retry_attempts < 0:
        raise ConfigError("scan.retry_attempts cannot be negative")
    if retry_backoff < 0:
        raise ConfigError("scan.retry_backoff_seconds cannot be negative")
    lifecycle_guard = config.get("scan", {}).get("lifecycle_guard", {})
    minimum_fraction = float(
        lifecycle_guard.get("minimum_fraction_of_previous", 0.0)
    )
    if not 0.0 <= minimum_fraction <= 1.0:
        raise ConfigError(
            "scan.lifecycle_guard.minimum_fraction_of_previous must be between 0 and 1"
        )
    if int(lifecycle_guard.get("minimum_items", 0)) < 0:
        raise ConfigError("scan.lifecycle_guard.minimum_items cannot be negative")
    for source in sources:
        name = str(source.get("name", "<unnamed>"))
        for key in ("max_pages", "page_size"):
            if key in source and int(source[key]) < 1:
                raise ConfigError(f"source {name!r} {key} must be at least 1")
        for key in ("request_delay_seconds", "timeout_seconds"):
            if key in source and float(source[key]) < 0:
                raise ConfigError(f"source {name!r} {key} cannot be negative")
    weekly = config.get("reporting", {}).get("weekly", {})
    if str(weekly.get("week_start", "monday")).casefold() != "monday":
        raise ConfigError("reporting.weekly.week_start must currently be 'monday'")
    if int(weekly.get("max_items_per_section", 25)) < 1:
        raise ConfigError(
            "reporting.weekly.max_items_per_section must be at least 1"
        )
    scoring = config.get("scoring", {})
    algorithm = str(scoring.get("algorithm", "foundation_v2"))
    if algorithm not in {"foundation_v2", "weighted_keywords_v1"}:
        raise ConfigError(f"Unsupported scoring.algorithm: {algorithm}")
    foundations = scoring.get("foundation_groups", [])
    foundation_names = [str(item.get("name", "")) for item in foundations]
    if len(foundation_names) != len(set(foundation_names)):
        raise ConfigError("scoring foundation names must be unique")
    if algorithm == "foundation_v2" and not foundations:
        raise ConfigError("foundation_v2 requires scoring.foundation_groups")
    for foundation in foundations:
        score = int(foundation.get("base_score", -1))
        if not 0 <= score <= 100:
            raise ConfigError("scoring foundation base_score must be between 0 and 100")
        if not foundation.get("keywords"):
            raise ConfigError("every scoring foundation requires keywords")
    modifiers = scoring.get("modifiers", [])
    modifier_names = [str(item.get("name", "")) for item in modifiers]
    if len(modifier_names) != len(set(modifier_names)):
        raise ConfigError("scoring modifier names must be unique")
    bands = scoring.get("bands", {"high": 75, "relevant": 60, "adjacent": 45})
    band_values = [int(bands.get(key, 0)) for key in ("high", "relevant", "adjacent")]
    if not (100 >= band_values[0] > band_values[1] > band_values[2] >= 0):
        raise ConfigError("scoring bands must satisfy 100 >= high > relevant > adjacent >= 0")

    strategy = config.get("strategy", {})
    strategy_foundations = {
        str(item.get("name", "")) for item in strategy.get("foundations", [])
    }
    for modifier in strategy.get("score_modifiers", []):
        try:
            re.compile(str(modifier.get("pattern", "")), re.I)
        except re.error as exc:
            raise ConfigError(
                f"invalid strategy score modifier regex {modifier.get('name')!r}: {exc}"
            ) from exc
        if modifier.get("scope", "all") not in {"all", "title"}:
            raise ConfigError("strategy score modifier scope must be all or title")
    for override in strategy.get("foundation_overrides", []):
        if str(override.get("foundation", "")) not in strategy_foundations:
            raise ConfigError(
                f"strategy foundation override references unknown foundation: "
                f"{override.get('foundation')}"
            )
        try:
            re.compile(str(override.get("title_pattern", "")), re.I)
        except re.error as exc:
            raise ConfigError(f"invalid foundation override regex: {exc}") from exc

    supported_modules = {
        "penn_channels",
        "daily", "scan", "rescore", "digest", "scoring_report", "scoring_experiment", "strategy_full",
        "weekly", "session_audit",
    }
    workflows = config.get("workflows", {})
    if not isinstance(workflows, dict):
        raise ConfigError("workflows must be an object")
    for name, workflow in workflows.items():
        modules = workflow.get("modules", []) if isinstance(workflow, dict) else []
        if not modules or not isinstance(modules, list):
            raise ConfigError(f"workflow {name!r} requires a module list")
        unknown = set(modules) - supported_modules
        if unknown:
            raise ConfigError(
                f"workflow {name!r} contains unsupported modules: {', '.join(sorted(unknown))}"
            )
        if len(modules) != len(set(modules)):
            raise ConfigError(f"workflow {name!r} contains duplicate modules")
        if "max_workers" in workflow and int(workflow["max_workers"]) < 1:
            raise ConfigError(f"workflow {name!r} max_workers must be at least 1")
        browser = str(workflow.get("source_selector", {}).get("browser", "any"))
        if browser not in {"any", "http", "cdp"}:
            raise ConfigError(
                f"workflow {name!r} source_selector.browser must be any, http, or cdp"
            )

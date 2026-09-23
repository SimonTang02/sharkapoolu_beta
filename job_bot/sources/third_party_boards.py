"""Adapters for third-party job boards.

These adapters intentionally start conservative. The public pages for JobsDB,
BOSS Zhipin, and Shixiseng are uneven and often dynamic; each adapter keeps the
platform-specific assumptions in one place so stronger parsers or login/cookie
flows can be added without changing the core bot.
"""

from __future__ import annotations

from typing import Any


def prepare_jobsdb_hk_source(source: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(source)
    prepared.setdefault("timeout_seconds", 20)
    prepared.setdefault("platform_note", "JobsDB HK public search page")
    return prepared


def prepare_zhipin_source(source: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(source)
    prepared.setdefault("timeout_seconds", 12)
    prepared.setdefault("platform_note", "BOSS Zhipin public page; likely needs login/captcha-safe session support")
    return prepared


def prepare_shixiseng_source(source: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(source)
    prepared.setdefault("timeout_seconds", 20)
    prepared.setdefault("platform_note", "Shixiseng public internship search page")
    return prepared


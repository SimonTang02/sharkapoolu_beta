"""Adapters for university career portals.

Campus systems often sit behind SSO and 2FA. These adapters avoid storing raw
passwords in code; production use should rely on environment variables or a
short-lived browser session/cookie export controlled by the user.
"""

from __future__ import annotations

from typing import Any


def prepare_cuhk_careers_source(source: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(source)
    prepared.setdefault("timeout_seconds", 20)
    prepared.setdefault("platform_note", "CUHK CPDC / CU Careers portal; login or CUHK SSO may be required")
    prepared.setdefault(
        "headers",
        {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-HK;q=0.6,zh-TW;q=0.5",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        },
    )
    return prepared

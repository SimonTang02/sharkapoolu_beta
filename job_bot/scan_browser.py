"""Optionally reuse one explicitly owned CDP target for a complete scan."""

from __future__ import annotations

import os
from typing import Any


def target_id(page: Any) -> str:
    session = page.context.new_cdp_session(page)
    try:
        return str(session.send("Target.getTargetInfo")["targetInfo"]["targetId"])
    finally:
        session.detach()


def new_scan_page(context: Any) -> Any:
    owned_target = os.environ.get("JOBBOT_SCAN_TARGET_ID", "").strip()
    if not owned_target:
        return context.new_page()
    for page in context.pages:
        if page.is_closed():
            continue
        try:
            current_target = target_id(page)
        except Exception:
            continue
        if current_target == owned_target:
            return page
    raise RuntimeError("Dedicated scan tab is unavailable; refusing to use another tab")


def close_scan_page(page: Any) -> None:
    owned_target = os.environ.get("JOBBOT_SCAN_TARGET_ID", "").strip()
    if owned_target:
        if target_id(page) != owned_target:
            raise RuntimeError("Refusing to close a tab outside the dedicated scan target")
        # Keep the window and authenticated context alive between source scans.
        return
    page.close()

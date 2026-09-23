"""Health checks and endpoint normalization for an external Chrome CDP session."""

from __future__ import annotations

import errno
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class CdpHealthError(RuntimeError):
    """A safe, actionable Chrome DevTools connection error."""


@dataclass(frozen=True)
class CdpHealth:
    browser: str
    connect_url: str


def _start_instruction(endpoint: str) -> str:
    return (
        "Start the dedicated Windows JobApplyChrome with remote debugging on "
        "Windows localhost, then verify its WSL-only portproxy and firewall rule. "
        f"Configured WSL endpoint: {endpoint}"
    )


def _rewrite_websocket_authority(endpoint: str, advertised_url: str) -> str:
    endpoint_parts = urllib.parse.urlsplit(endpoint)
    websocket_parts = urllib.parse.urlsplit(advertised_url)
    if websocket_parts.scheme not in {"ws", "wss"} or not websocket_parts.netloc:
        raise CdpHealthError(
            "Chrome returned a malformed webSocketDebuggerUrl from /json/version"
        )
    websocket_scheme = "wss" if endpoint_parts.scheme == "https" else "ws"
    return urllib.parse.urlunsplit(
        (
            websocket_scheme,
            endpoint_parts.netloc,
            websocket_parts.path,
            websocket_parts.query,
            "",
        )
    )


def check_cdp_health(endpoint: str, timeout_seconds: float = 3.0) -> CdpHealth:
    endpoint = endpoint.strip().rstrip("/")
    parts = urllib.parse.urlsplit(endpoint)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise CdpHealthError(
            "Chrome CDP health checks require an HTTP(S) endpoint such as "
            "http://172.23.0.1:9223"
        )
    version_url = f"{endpoint}/json/version"
    request = urllib.request.Request(
        version_url,
        headers={"Accept": "application/json", "User-Agent": "job-bot-cdp-health/1"},
    )
    # The WSL gateway is a local transport. Never route this request through an
    # inherited corporate/system HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = response.read(256 * 1024)
    except urllib.error.HTTPError as exc:
        raise CdpHealthError(
            f"Chrome CDP health endpoint returned HTTP {exc.code}. "
            + _start_instruction(endpoint)
        ) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise CdpHealthError(
                "Timed out while connecting to the Chrome CDP endpoint. "
                + _start_instruction(endpoint)
            ) from exc
        if isinstance(reason, OSError) and reason.errno == errno.ECONNREFUSED:
            raise CdpHealthError(
                "Connection to the Chrome CDP endpoint was refused. "
                + _start_instruction(endpoint)
            ) from exc
        raise CdpHealthError(
            f"Could not reach the Chrome CDP endpoint ({reason}). "
            + _start_instruction(endpoint)
        ) from exc
    except (socket.timeout, TimeoutError) as exc:
        raise CdpHealthError(
            "Timed out while connecting to the Chrome CDP endpoint. "
            + _start_instruction(endpoint)
        ) from exc
    except OSError as exc:
        raise CdpHealthError(
            f"Could not reach the Chrome CDP endpoint ({exc}). "
            + _start_instruction(endpoint)
        ) from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CdpHealthError(
            "Chrome CDP /json/version returned malformed JSON"
        ) from exc
    if not isinstance(data, dict):
        raise CdpHealthError("Chrome CDP /json/version returned an unexpected payload")

    browser = data.get("Browser")
    websocket_url = data.get("webSocketDebuggerUrl")
    if not isinstance(browser, str) or not browser.strip():
        raise CdpHealthError("Chrome CDP /json/version did not contain Browser")
    if not isinstance(websocket_url, str) or not websocket_url.strip():
        raise CdpHealthError(
            "Chrome CDP /json/version did not contain webSocketDebuggerUrl"
        )
    if not re.search(r"\b(?:Chrome|Chromium)/\d+", browser, re.I):
        raise CdpHealthError(
            f"Unsupported CDP browser reported by the endpoint: {browser}"
        )

    return CdpHealth(
        browser=browser.strip(),
        connect_url=_rewrite_websocket_authority(endpoint, websocket_url.strip()),
    )

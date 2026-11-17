#!/usr/bin/env python3
"""Fill known Beisen ATS application fields and stop before the final Submit.

Beisen (北森) powers the ``*.zhiye.com`` campus portals and ``wecruit.hotjob.cn``
boards.  A job-detail page renders a ``立即投递`` button; that button runs an
async deliver flow which calls ``POST /api/Submission/CheckJobAd`` and, on
success, navigates to the application form:

    /form?fromPage=job&jobAdId=<jobId>

The application form is submitted by a single ``提交``/``确认投递`` control, so
this adapter stops at the editable form and never clicks that control.

Only profile-backed identity fields are filled and the reviewed resume is
uploaded.  Custom and legal questions are inventoried for the human reviewer
and never answered automatically.

Click-strategy findings (live CDP, recorded in the report):

* Trusted ``Input.dispatchMouseEvent`` is dropped by Chromium while the tab is
  hidden/backgrounded; no native event reaches the page at all.  It is therefore
  excluded from the primary click strategy list.
* Untrusted ``PointerEvent``/``MouseEvent`` dispatch, direct React
  ``__reactEventHandlers$`` invocation, and fiber-traversal invocation all reach
  the Beisen deliver handler on hidden tabs.
* For zhiye the most robust "open application" step is deriving the form URL
  from the detail URL, so ``apply_url`` does that and no click is required in
  the happy path.  ``click_deliver_button`` is kept as a fallback for profiles
  whose form URL cannot be derived.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application_bot.ats_form import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_ENV,
    ApplicationContext,
    classify_application_body,
    contact_values,
    fill_mapped_fields,
    inventory_questions,
    is_submit_control,
    run_adapter,
    upload_resume,
)


# Beisen-specific final-submit verbs.  The shared ``is_submit_control`` already
# covers ``提交申请``/``确认申请``; this extends it to ``确认投递`` and bare
# ``提交`` without weakening the shared guard.
SUBMIT_LABEL_PATTERN = re.compile(r"提交|确认投递|確認投遞|确认申请", re.I)


# The adapter never clicks these controls; they are named so the refusal is
# explicit and asserted by tests.  ``提交`` is the Beisen final-submit verb.
SUBMIT_CONTROL_SELECTORS = (
    "button:has-text('提交')",
    "button:has-text('确认投递')",
    "button:has-text('提交申请')",
    "button[type='submit']",
    "div.phoenix-button:has-text('提交')",
    "div.phoenix-button:has-text('确认投递')",
)

# Selector families that indicate an editable Beisen application form is open.
# The zhiye form is pre-filled from the logged-in Beisen account, so the resume
# upload control and the delivery header are the most reliable form markers.
FORM_SELECTORS = (
    "input[type='file']",
    "input[name='resume']",
    "input[name='Resume']",
    ".phoenix-upload",
    "[class*='resume-upload']",
    "[class*='upload-resume']",
)

# Body-text markers used as a secondary form signal when the phoenix upload
# component does not expose a file input in the DOM snapshot.
FORM_BODY_MARKERS = (
    "你正在投递职位",
    "正在投递职位",
    "投递职位",
)

# Generic Beisen identity field selectors.  These are defensive fallbacks: the
# live test posting could not render a form (see report), so the exact field
# ids/names have not been confirmed against a healthy job yet.
FIELD_MAP = (
    ("input[name='name'], input[placeholder*='姓名']", "full_name"),
    ("input[name='email'], input[type='email']", "email"),
    ("input[name='phone'], input[placeholder*='手机'], input[placeholder*='电话']", "phone"),
    ("input[name='city'], input[placeholder*='城市'], input[placeholder*='现居']", "city"),
)

# Read-only inventory of custom/legal questions.  Never used to answer them.
QUESTION_SELECTOR = (
    "input:not([type='file']):not([type='hidden']):not([type='checkbox'])"
    ":not([type='radio']):not([type='submit']):not([type='search']), "
    "textarea"
)

# The deliver/apply button.  zhiye renders it as a phoenix button with the
# text ``立即投递``.
DELIVER_BUTTON_TEXTS = ("立即投递", "投递", "立即申请")
DELIVER_BUTTON_SELECTOR = "div.phoenix-button__content"

# Preferred click strategies.  Trusted CDP input is deliberately absent:
# Chromium drops it on hidden/background tabs, which is the exact state the
# zhiye job-detail tab is in during CDP-assisted runs.
CLICK_STRATEGIES = ("untrusted_dispatch", "react_handler", "fiber_traversal")

# JavaScript for the click strategies.  Each function receives a CSS selector
# for the deliver button and returns a small JSON-serializable result.
_UNTRUSTED_CLICK_JS = """
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return {ok: false, reason: 'not_found'};
  const down = {bubbles: true, cancelable: true, view: window, pointerId: 1,
                isPrimary: true, pointerType: 'mouse', button: 0, buttons: 1};
  el.dispatchEvent(new PointerEvent('pointerdown', down));
  el.dispatchEvent(new PointerEvent('pointerup', Object.assign({}, down, {buttons: 0})));
  el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window, button: 0, buttons: 1}));
  el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window, button: 0, buttons: 0}));
  el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window, button: 0, buttons: 0}));
  return {ok: true, events: ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click']};
}
"""

_REACT_HANDLER_CLICK_JS = """
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return {ok: false, reason: 'not_found'};
  const key = Object.keys(el).find(k => k.startsWith('__reactEventHandlers$'));
  const handlers = el[key];
  if (!handlers || typeof handlers.onClick !== 'function') {
    return {ok: false, reason: 'no_onclick_handler'};
  }
  const event = {
    stopPropagation() {}, preventDefault() {}, persist() {},
    isDefaultPrevented() { return false; }, isPropagationStopped() { return false; },
    nativeEvent: {}, currentTarget: el, target: el, type: 'click',
  };
  handlers.onClick(event);
  return {ok: true, handler: String(handlers.onClick).slice(0, 80)};
}
"""

_FIBER_CLICK_JS = """
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return {ok: false, reason: 'not_found'};
  const key = Object.keys(el).find(k => k.startsWith('__reactInternalInstance$'));
  let fiber = el[key];
  const event = {
    stopPropagation() {}, preventDefault() {}, persist() {},
    isDefaultPrevented() { return false; }, isPropagationStopped() { return false; },
    nativeEvent: {}, currentTarget: el, target: el, type: 'click',
  };
  for (let depth = 0; fiber && depth < 25; depth++) {
    const props = fiber.memoizedProps;
    if (props && typeof props.onClick === 'function') {
      props.onClick(event);
      return {ok: true, depth, handler: String(props.onClick).slice(0,80)};
    }
    fiber = fiber.return;
  }
  return {ok: false, reason: 'no_fiber_onclick'};
}
"""

_CLICK_JS = {
    "untrusted_dispatch": _UNTRUSTED_CLICK_JS,
    "react_handler": _REACT_HANDLER_CLICK_JS,
    "fiber_traversal": _FIBER_CLICK_JS,
}


def _query_param(url: str, *names: str) -> str:
    query = parse_qs(urlsplit(str(url or "")).query)
    for name in names:
        values = query.get(name) or []
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    return ""


def job_id_from_url(url: str) -> str:
    """Extract the stable Beisen job identifier from a URL query string.

    zhiye uses ``jobId`` (detail) and ``jobAdId`` (form); hotjob and other
    Beisen tenants reuse ``postId``/``positionId``/``pid``.
    """
    return _query_param(url, "jobId", "jobAdId", "postId", "positionId", "pid", "job_id")


def apply_url(url: str) -> str:
    """zhiye profile: derive the application form URL from a job-detail URL.

    ``/campus/detail?jobId=<id>`` becomes ``/form?fromPage=job&jobAdId=<id>``
    (the exact route produced by the live deliver handler).  An existing form
    URL is returned unchanged; a URL without a recognizable job id is returned
    unchanged for manual resolution.
    """
    raw = str(url or "").strip()
    if not raw:
        return raw
    parsed = urlsplit(raw)
    if parsed.path.rstrip("/").endswith("/form"):
        return raw
    job_id = _query_param(raw, "jobId", "jobAdId", "postId", "positionId", "pid")
    if not job_id:
        return raw
    form_path = "/form"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, form_path, f"fromPage=job&jobAdId={job_id}", "")
    )


def is_final_submit_label(label: str) -> bool:
    """True when an accessible name identifies a Beisen final-submit control."""
    text = " ".join(str(label or "").split())
    return is_submit_control(text) or bool(SUBMIT_LABEL_PATTERN.search(text))


def resolve_field_values(profile: dict[str, Any]) -> dict[str, str]:
    return contact_values(profile)


def classify_body(body: str, form_present: bool = False) -> tuple[str, str]:
    return classify_application_body(body, form_present=form_present)


def form_present(page: Any) -> bool:
    for selector in FORM_SELECTORS:
        try:
            if page.locator(selector).count():
                return True
        except Exception:
            continue
    try:
        body = page.locator("body").first.inner_text()
        text = " ".join(str(body or "").split())
        if any(marker in text for marker in FORM_BODY_MARKERS):
            return True
    except Exception:
        pass
    return False


def choose_click_strategy(page: Any = None) -> list[str]:
    """Return click strategies in preferred order for opening the deliver form.

    Trusted CDP ``Input.dispatchMouseEvent`` is intentionally excluded: live
    verification showed Chromium drops trusted input for hidden/background
    tabs, while the three JS-driven strategies below all reach the Beisen
    deliver handler.
    """
    return list(CLICK_STRATEGIES)


def _run_click_strategy(page: Any, selector: str, strategy: str) -> dict[str, Any]:
    if strategy not in _CLICK_JS:
        return {"strategy": strategy, "ok": False, "reason": "unknown_strategy"}
    try:
        result = page.evaluate(_CLICK_JS[strategy], selector)
        return {"strategy": strategy, **dict(result)}
    except Exception as exc:  # browser-level failure; never rethrown to the caller
        return {"strategy": strategy, "ok": False, "reason": str(exc)[:200]}


def click_deliver_button(
    page: Any, selector: str = DELIVER_BUTTON_SELECTOR
) -> dict[str, Any]:
    """Attempt the ordered click strategies against the Beisen deliver button.

    Each strategy returns whether it ran; the caller is responsible for
    observing whether the form opened (URL change, new modal, network request).
    No strategy here clicks a final submission control.
    """
    attempts: list[dict[str, Any]] = []
    for strategy in choose_click_strategy(page):
        attempts.append(_run_click_strategy(page, selector, strategy))
    clicked = any(attempt.get("ok") for attempt in attempts)
    return {"clicked": clicked, "strategies": attempts, "submit_clicked": False}


def fill_form(page: Any, context: ApplicationContext) -> dict[str, Any]:
    values = resolve_field_values(context.profile)
    filled = fill_mapped_fields(page, FIELD_MAP, values)
    resume_uploaded = upload_resume(page, context.resume_path, "input[type='file']")
    if resume_uploaded:
        filled.append("resume")

    questions = inventory_questions(page, QUESTION_SELECTOR)
    note = (
        "Beisen application prepared without submit. Profile-backed identity fields "
        f"({', '.join(filled) or 'none'}) were filled; "
        + ("the tailored resume was uploaded. " if resume_uploaded else "the resume was NOT uploaded. ")
        + f"{len(questions)} additional form question(s) remain for human review; no "
        "legal, consent, or demographic answer was selected. The final submit "
        "control was not clicked."
    )
    return {
        "filled_fields": filled,
        "unanswered_questions": questions,
        "submit_clicked": False,
        "note": note,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application-id", type=int, required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    args = parser.parse_args()
    run_adapter(
        platform="beisen",
        adapter="beisen",
        config_path=Path(args.config),
        env_path=Path(args.env),
        application_id=args.application_id,
        apply_url=apply_url,
        form_present=form_present,
        fill_form=fill_form,
    )


if __name__ == "__main__":
    main()

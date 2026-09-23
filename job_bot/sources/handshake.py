"""Penn Handshake student pages, read through an existing Chrome login.

This is a browser adapter, not Handshake's institution-only EDU API.
No password, cookie export, undocumented API, or application action is used.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

LOGIN_URL = "https://upenn.joinhandshake.com/login"
JOB_LINKS = '[data-hook^="job-result-card |"] a[href^="/job-search/"]'


def canonical_job_url(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {
        "upenn.joinhandshake.com", "app.joinhandshake.com",
    } or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Not an official Penn/Handshake job URL")
    match = re.fullmatch(r"/(?:(?:stu/|public/)?jobs|job-search)/(\d+)/?", parts.path)
    if not match:
        raise ValueError("Not an individual Handshake job")
    job_id = match.group(1)
    return job_id, f"https://app.joinhandshake.com/jobs/{job_id}"


def assert_student_page(url: str, text: str) -> None:
    parts = urlsplit(url)
    if parts.hostname not in {"upenn.joinhandshake.com", "app.joinhandshake.com"} or re.search(
        r"/(login|signin|sign_in|sso|student_onboardings)(?:/|$)", parts.path, re.I
    ) or re.search(r"Log.In Using Your PennKey|Continue with email|sign in to continue", text, re.I):
        raise RuntimeError(f"Handshake login required: open {LOGIN_URL} in JobApplyChrome and complete PennKey/MFA manually")
    if re.search(r"verify you are human|unusual traffic|access denied|checking your browser", text, re.I):
        raise RuntimeError("Handshake browser challenge requires manual attention; scan stopped")


CARD_SCRIPT = r"""links => links.map(a => {
  const modern = a.closest('[data-hook^="job-result-card |"]');
  if (modern) {
    const region = modern.querySelector('[role="region"][aria-labelledby]');
    const title = document.getElementById(region?.getAttribute('aria-labelledby'))?.innerText.trim() || '';
    const company = modern.querySelector('img[alt]')?.alt || '';
    const footer = modern.querySelector('[data-hook="job-result-card-footer"]');
    const location = [...(footer?.querySelectorAll('span') || [])].find(e => !e.hasAttribute('aria-hidden') && !/^(Promoted|New|.*ago)$/.test(e.innerText.trim()))?.innerText.trim() || '';
    return {url:a.href,title,company,location,description:modern.innerText.trim()};
  }
  let card = a;
  for (let n = 0; n < 6 && card.parentElement; n++) {
    const parent = card.parentElement;
    const ids = new Set([...parent.querySelectorAll('a[href]')]
      .map(x => x.href.match(/\/(?:stu\/|public\/)?jobs\/(\d+)/)?.[1]).filter(Boolean));
    if (ids.size > 1 || parent.matches('main,body')) break;
    card = parent;
  }
  const employer = card.querySelector('a[href*="/employers/"]');
  return {url: a.href, title: a.innerText.trim(),
    company: employer?.innerText.trim() || '',
    location: '', description: card.innerText.trim()};
})"""


DETAIL_SCRIPT = r"""() => {
  const jobs = [];
  function visit(x) {
    if (!x || typeof x !== 'object') return;
    if (Array.isArray(x)) { x.forEach(visit); return; }
    if (x['@type'] === 'JobPosting' || (Array.isArray(x['@type']) && x['@type'].includes('JobPosting'))) jobs.push(x);
    if (x['@graph']) visit(x['@graph']);
  }
  for (const e of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { visit(JSON.parse(e.textContent)); } catch {}
  }
  const root = document.querySelector('[data-hook="job-details-page"]') || document.querySelector('main') || document.querySelector('[role="main"]');
  const employer = root?.querySelector('a[href^="/e/"], a[href*="/employers/"]');
  const section = label => [...(root?.querySelectorAll('h2,h3') || [])]
    .find(e => e.innerText.trim() === label)?.parentElement.parentElement.innerText.trim() || '';
  return {structured: jobs, title: root?.querySelector('h1')?.innerText.trim() || '',
    company: employer?.getAttribute('aria-label') || employer?.innerText.trim() || '',
    description: [section('At a glance'), section('Job description')].filter(Boolean).join('\n\n')};
}"""


def normalize_detail(card: dict[str, Any], detail: dict[str, Any]) -> dict[str, str]:
    job_id, url = canonical_job_url(card["url"])
    structured = detail.get("structured") or []
    data = structured[0] if len(structured) == 1 else {}
    organization = data.get("hiringOrganization") or {}
    if not isinstance(organization, dict):
        organization = {}
    locations = data.get("jobLocation") or []
    if isinstance(locations, dict):
        locations = [locations]
    names = []
    for location in locations:
        address = location.get("address", {}) if isinstance(location, dict) else {}
        if isinstance(address, dict):
            names.append(", ".join(str(address[k]) for k in ("addressLocality", "addressRegion", "addressCountry") if address.get(k)))
    title = data.get("title") or detail.get("title") or card.get("title")
    if not title or str(title).casefold() in {"view job", "learn more", "apply", "jobs"}:
        raise RuntimeError("Handshake job title could not be verified; parser needs review")
    return {
        "external_id": job_id, "url": url, "title": str(title),
        "company": str(organization.get("name") or detail.get("company") or card.get("company") or ""),
        "location": "; ".join(filter(None, names)) or card.get("location", ""),
        "description": str(data.get("description") or detail.get("description") or card.get("description") or ""),
        "published_at": str(data.get("datePosted") or ""),
    }


def wait_for_search(page: Any, query: str, previous: list[str] | None = None) -> None:
    """Wait out initial recommendations and subsequent semantic-search loading."""
    deadline = time.monotonic() + 30
    last = None
    stable = 0
    while time.monotonic() < deadline:
        body = page.locator("body").inner_text()
        assert_student_page(page.url, body)
        state = page.evaluate("""selector => ({
            query: document.querySelector('input[name="query"]')?.value || '',
            urls: [...document.querySelectorAll(selector)].map(a => a.href),
            loading: /Finding jobs\.\.\./i.test(document.body.innerText)
        })""", JOB_LINKS)
        empty = bool(re.search(r"no jobs found|no results found|no matching jobs", body, re.I))
        ready = state["query"] == query and not state["loading"] and (state["urls"] or empty)
        if ready and (previous is None or state["urls"] != previous):
            signature = (tuple(state["urls"]), empty)
            stable = stable + 1 if signature == last else 0
            last = signature
            if stable >= 2:
                return
        else:
            stable = 0
            last = None
        page.wait_for_timeout(350)
    raise RuntimeError("Handshake search did not settle or pagination did not advance; partial scan rejected")


def collect(page: Any, source: dict[str, Any]) -> list[dict[str, str]]:
    """Bounded search; incomplete results must never drive active-job expiry."""
    max_pages = min(10, max(1, int(source.get("max_pages", 3))))
    max_jobs = min(100, max(1, int(source.get("max_jobs", 40))))
    cards: dict[str, dict[str, str]] = {}
    urls = source.get("search_urls") or [source["url"]]
    for search_url in urls:
        query_start = len(cards)
        query_limit = max(1, max_jobs // len(urls))
        parts = urlsplit(search_url)
        if parts.scheme != "https" or parts.hostname not in {"upenn.joinhandshake.com", "app.joinhandshake.com"} or parts.path not in {"/stu/postings", "/job-search"}:
            raise ValueError("Handshake search must use the official student postings page")
        response = page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        if response and response.status >= 400:
            raise RuntimeError(f"Handshake returned HTTP {response.status}")
        for number in range(max_pages):
            wait_for_search(page, parse_qs(parts.query).get("query", [""])[0])
            body = page.locator("body").inner_text()
            assert_student_page(page.url, body)
            found = page.locator(JOB_LINKS).evaluate_all(CARD_SCRIPT)
            valid = 0
            for card in found:
                try:
                    job_id, _ = canonical_job_url(card["url"])
                except ValueError:
                    continue
                valid += 1
                if job_id not in cards and len(cards) < max_jobs and len(cards) - query_start < query_limit:
                    cards[job_id] = card
            if not valid and not re.search(r"no jobs found|no results found|no matching jobs", body, re.I):
                raise RuntimeError("Handshake returned no recognizable job cards; parser needs review")
            if len(cards) - query_start >= query_limit or number + 1 == max_pages:
                break
            next_button = page.get_by_role("button", name=re.compile(r"^next(?: page)?$", re.I))
            if next_button.count() != 1 or not next_button.is_visible() or not next_button.is_enabled():
                break
            previous = [x["url"] for x in found]
            next_button.evaluate("button => button.click()")
            wait_for_search(page, parse_qs(parts.query).get("query", [""])[0], previous)
        if len(cards) >= max_jobs:
            break
    results = []
    for card in cards.values():
        _, url = canonical_job_url(card["url"])
        patterns = source.get('title_include_patterns') or []
        if patterns and card.get('title') and not any(re.search(p, card['title'], re.I) for p in patterns):
            continue
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if response and response.status >= 400:
            raise RuntimeError(f"Handshake job detail returned HTTP {response.status}")
        try:
            page.locator('[data-hook="job-details-page"] h1, main h1, [role="main"] h1').first.wait_for(state="visible", timeout=15000)
        except Exception:
            assert_student_page(page.url, page.locator("body").inner_text())
            raise RuntimeError("Handshake job detail layout not recognized") from None
        assert_student_page(page.url, page.locator("body").inner_text())
        try:
            actual_id, _ = canonical_job_url(page.url)
        except ValueError:
            raise RuntimeError("Handshake detail redirected away from the selected job") from None
        if actual_id != canonical_job_url(card["url"])[0]:
            raise RuntimeError("Handshake detail redirected to a different job")
        description_heading = page.get_by_role("heading", name="Job description", exact=True)
        if description_heading.count() == 1:
            section = description_heading.locator("../..")
            more = section.get_by_role("button", name=re.compile(r"^Show more|^More$", re.I))
            if more.count() == 1 and more.is_visible():
                # A sticky email suggestion can cover this read-only control.
                # Activate exactly this description expander, never coordinates
                # underneath an overlay or any application action.
                # Server-rendered controls may precede React event binding.
                # Retry only while this exact expander still says "More".
                for _ in range(15):
                    if more.count() == 0 or not more.is_visible():
                        break
                    more.evaluate("button => button.click()")
                    page.wait_for_timeout(350)
                if more.count() and more.is_visible():
                    raise RuntimeError("Handshake description expander did not become ready")
        detail = page.evaluate(DETAIL_SCRIPT)
        if not detail.get("structured") and len(detail.get("description", "")) < 50:
            raise RuntimeError("Handshake job description not recognized; incomplete detail rejected")
        results.append(normalize_detail(card, detail))
    return results


def fetch_handshake(source: dict[str, Any], config: dict[str, Any]) -> list[Any]:
    from job_bot.bot import JobPosting, classify_role_kind, configured_cdp_connect_url, filter_jobs, strip_html
    from job_bot.applications.nvidia_workday import _playwright_api
    from job_bot.scan_browser import new_scan_page, close_scan_page

    if source.get("sync_active"):
        raise ValueError("Handshake bounded searches require sync_active=false")
    connect_url = configured_cdp_connect_url(config)
    with _playwright_api()() as playwright:
        browser = playwright.chromium.connect_over_cdp(connect_url, timeout=30000)
        try:
            if not browser.contexts:
                raise RuntimeError("Dedicated Chrome exposed no persistent context")
            page = new_scan_page(browser.contexts[0])
            try:
                try:
                    rows = collect(page, source)
                except (RuntimeError, ValueError):
                    raise
                except Exception as exc:
                    # Playwright call logs can contain personal banner text or
                    # SSO query strings. Keep scanner errors free of those logs.
                    import traceback
                    frames = traceback.extract_tb(exc.__traceback__)
                    frame = next((f for f in reversed(frames) if f.filename == __file__), None)
                    step = f"{frame.name}:{frame.lineno}" if frame else "browser"
                    raise RuntimeError(f"Handshake browser operation failed ({type(exc).__name__}, {step}); inspect the student page and retry") from None
            finally:
                close_scan_page(page)
        finally:
            browser.close()  # Disconnect; do not terminate Chrome.
    jobs = []
    for row in rows:
        row["description"] = strip_html(row["description"])
        job = JobPosting(source_name=source["name"], platform="handshake", **row)
        job.role_kind = classify_role_kind(job, source)
        jobs.append(job)
    return filter_jobs(jobs, source)

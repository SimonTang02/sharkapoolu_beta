#!/usr/bin/env python3
"""Inspect visible controls in an already-open application portal.

The probe deliberately omits field values so it can be used without leaking
contact details or credentials into terminal logs.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / ".python_packages"
if LOCAL_PACKAGES.is_dir() and str(LOCAL_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGES))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from job_bot.application_bot import resolve_browser_connection  # noqa: E402
from job_bot.applications.nvidia_workday import _playwright_api  # noqa: E402
from job_bot.bot import load_config, load_env_file  # noqa: E402
from private_paths import CREDENTIALS_FILE  # noqa: E402
from application_bot.artifacts import capture_long_page  # noqa: E402


def short(value: str | None, limit: int = 180) -> str:
    return " ".join((value or "").split())[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="hostname substring of the open page")
    parser.add_argument(
        "--application-id",
        type=int,
        help="Select the registered tab label jobbot-application-ID",
    )
    parser.add_argument("--config", default=str(ROOT / "job_bot/config.china_hk_ic_foreign.json"))
    parser.add_argument("--env", default=str(CREDENTIALS_FILE))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--screenshot")
    parser.add_argument(
        "--full-page-screenshot",
        action="store_true",
        help="Capture the whole document, expanding SPA scroll containers when possible.",
    )
    parser.add_argument(
        "--preserve-scroll",
        action="store_true",
        help="Keep the current section in view for a viewport screenshot.",
    )
    parser.add_argument("--parent-text", action="store_true")
    parser.add_argument("--ancestor-depth", type=int, default=1)
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--open-combobox", help="visible text of a combobox to open")
    parser.add_argument("--combobox-index", type=int, default=0)
    parser.add_argument("--ancestors", action="store_true")
    parser.add_argument(
        "--list-options",
        action="store_true",
        help="List options currently visible without opening or closing a control.",
    )
    parser.add_argument("--scroll-offset", type=int)
    parser.add_argument("--click-button", help="open a non-final editor before probing")
    parser.add_argument("--button-index", type=int, default=0)
    parser.add_argument("--navigate-url")
    parser.add_argument("--all-pages", action="store_true")
    parser.add_argument("--page-index", type=int, default=-1)
    parser.add_argument("--body-text", type=int)
    parser.add_argument("--click-placeholder")
    parser.add_argument("--placeholder-index", type=int, default=0)
    parser.add_argument("--click-text")
    parser.add_argument("--hover-text")
    parser.add_argument("--hover-selector")
    parser.add_argument("--click-selector")
    parser.add_argument("--selector-index", type=int, default=0)
    parser.add_argument(
        "--press-keys",
        help="comma-separated keyboard keys to send after opening a control",
    )
    parser.add_argument("--fill-selector")
    parser.add_argument("--fill-selector-value")
    parser.add_argument("--fill-selector-index", type=int, default=0)
    parser.add_argument(
        "--dom-click-text",
        help="dispatch a DOM click to the deepest exact-text element",
    )
    parser.add_argument("--text-index", type=int, default=-1)
    parser.add_argument("--click-link")
    parser.add_argument(
        "--press-link",
        help="Focus a visible accessible link and activate it with Enter",
    )
    parser.add_argument(
        "--wait-after-ms",
        type=int,
        default=700,
        help="Wait after a requested click/navigation before probing the page",
    )
    parser.add_argument("--upload", help="local file to set on a file input")
    parser.add_argument("--upload-index", type=int, default=0)
    parser.add_argument("--fill-placeholder", help="placeholder of one text field to fill")
    parser.add_argument("--fill-value", help="value used with --fill-placeholder")
    parser.add_argument(
        "--inspect-text",
        help="print value-free DOM metadata for elements whose visible text matches",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env))
    config = load_config(Path(args.config))
    _, cdp_url = resolve_browser_connection(config)
    sync_playwright = _playwright_api()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=30_000)
        pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if args.host.lower() in (urlsplit(page.url).hostname or "").lower()
        ]
        if not pages and args.navigate_url:
            pages = [browser.contexts[0].new_page()]
        if not pages:
            raise SystemExit(f"No open page matching host substring: {args.host}")
        if args.application_id is not None:
            label = f"jobbot-application-{args.application_id}"
            matching_pages = []
            for candidate in pages:
                try:
                    if candidate.evaluate("window.name") == label:
                        matching_pages.append(candidate)
                except Exception:
                    continue
            if not matching_pages:
                raise SystemExit(
                    f"No open page matching application label: {label}"
                )
            pages = matching_pages
        if args.all_pages:
            for candidate in pages:
                print(candidate.url)
            return
        page = pages[args.page_index]
        if args.navigate_url:
            page.goto(args.navigate_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_500)
        if args.upload:
            upload_path = Path(args.upload).expanduser().resolve()
            if not upload_path.is_file():
                raise RuntimeError(f"Upload file does not exist: {upload_path}")
            file_inputs = page.locator("input[type=file]")
            if file_inputs.count() <= args.upload_index:
                raise RuntimeError(
                    f"File input index {args.upload_index} is unavailable"
                )
            file_inputs.nth(args.upload_index).set_input_files(
                str(upload_path), timeout=10_000
            )
            page.wait_for_timeout(args.wait_after_ms)
        if args.fill_placeholder:
            if args.fill_value is None:
                raise RuntimeError("--fill-placeholder requires --fill-value")
            fields = page.locator(
                f"input[placeholder='{args.fill_placeholder}'], "
                f"textarea[placeholder='{args.fill_placeholder}']"
            )
            if not fields.count():
                raise RuntimeError(
                    f"No field with placeholder: {args.fill_placeholder}"
                )
            fields.first.fill(args.fill_value)
            page.wait_for_timeout(args.wait_after_ms)
        if args.click_button:
            page.get_by_role("button", name=args.click_button, exact=True).nth(
                args.button_index
            ).click(
                force=True, timeout=5_000
            )
            page.wait_for_timeout(args.wait_after_ms)
        if args.click_placeholder:
            page.locator(f"input[placeholder='{args.click_placeholder}']").nth(
                args.placeholder_index
            ).click(force=True, timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.press_keys:
            for key in (item.strip() for item in args.press_keys.split(",")):
                if key:
                    page.keyboard.press(key)
                    page.wait_for_timeout(120)
        if args.dom_click_text:
            clicked = page.evaluate(
                """text => {
                    const matches = [...document.querySelectorAll('body *')]
                        .filter(el => (el.innerText || '').trim() === text)
                        .sort((a, b) => b.querySelectorAll('*').length - a.querySelectorAll('*').length);
                    if (!matches.length) return false;
                    const target = matches[matches.length - 1];
                    target.click();
                    return true;
                }""",
                args.dom_click_text,
            )
            if not clicked:
                raise RuntimeError(
                    f"No exact DOM text matching: {args.dom_click_text}"
                )
            page.wait_for_timeout(args.wait_after_ms)
        if args.fill_selector:
            if args.fill_selector_value is None:
                raise RuntimeError(
                    "--fill-selector requires --fill-selector-value"
                )
            fill_targets = page.locator(args.fill_selector)
            visible_targets = [
                fill_targets.nth(index)
                for index in range(fill_targets.count())
                if fill_targets.nth(index).is_visible()
            ]
            if len(visible_targets) <= args.fill_selector_index:
                raise RuntimeError(
                    f"Visible selector index {args.fill_selector_index} is unavailable: "
                    f"{args.fill_selector}"
                )
            visible_targets[args.fill_selector_index].fill(
                args.fill_selector_value
            )
            page.wait_for_timeout(args.wait_after_ms)
            visible_options = [
                page.get_by_role("option").nth(index)
                for index in range(page.get_by_role("option").count())
                if page.get_by_role("option").nth(index).is_visible()
            ]
            if visible_options:
                print(f"VISIBLE_OPTIONS_AFTER_FILL {len(visible_options)}")
                for index, option in enumerate(visible_options[: args.limit]):
                    print(f"VISIBLE_OPTION_AFTER_FILL {index}: {short(option.inner_text())}")
        if args.hover_text:
            matches = page.get_by_text(args.hover_text, exact=True)
            if not matches.count():
                matches = page.get_by_text(args.hover_text, exact=False)
            visible_matches = [
                matches.nth(index)
                for index in range(matches.count())
                if matches.nth(index).is_visible()
            ]
            if not visible_matches:
                raise RuntimeError(f"No visible text matching: {args.hover_text}")
            visible_matches[-1].hover(timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.hover_selector:
            hover_target = page.locator(args.hover_selector)
            visible_targets = [
                hover_target.nth(index)
                for index in range(hover_target.count())
                if hover_target.nth(index).is_visible()
            ]
            if not visible_targets:
                raise RuntimeError(
                    f"No visible element matching selector: {args.hover_selector}"
                )
            visible_targets[0].hover(timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.click_text:
            matches = page.get_by_text(args.click_text, exact=True)
            if not matches.count():
                matches = page.get_by_text(args.click_text, exact=False)
            visible_matches = [
                matches.nth(index)
                for index in range(matches.count())
                if matches.nth(index).is_visible()
            ]
            if not visible_matches:
                raise RuntimeError(f"No visible text matching: {args.click_text}")
            index = args.text_index if args.text_index >= 0 else len(visible_matches) - 1
            if index >= len(visible_matches):
                raise RuntimeError(
                    f"Visible text index {index} is unavailable: {args.click_text}"
                )
            visible_matches[index].click(force=True, timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.click_selector:
            targets = page.locator(args.click_selector)
            visible_targets = [
                targets.nth(index)
                for index in range(targets.count())
                if targets.nth(index).is_visible()
            ]
            if len(visible_targets) <= args.selector_index:
                raise RuntimeError(
                    f"Selector index {args.selector_index} is unavailable: "
                    f"{args.click_selector}"
                )
            visible_targets[args.selector_index].click(force=True, timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
            if args.scroll_offset is not None and page.get_by_role("option").count():
                page.get_by_role("option").first.evaluate(
                    """(el, offset) => {
                        let p=el.parentElement;
                        while(p && p.scrollHeight <= p.clientHeight) p=p.parentElement;
                        if (p) p.scrollTop=offset;
                    }""",
                    args.scroll_offset,
                )
                page.wait_for_timeout(800)
            visible_options = [
                page.get_by_role("option").nth(index)
                for index in range(page.get_by_role("option").count())
                if page.get_by_role("option").nth(index).is_visible()
            ]
            if visible_options:
                print(f"VISIBLE_OPTIONS {len(visible_options)}")
                for index, option in enumerate(visible_options[: args.limit]):
                    print(f"VISIBLE_OPTION {index}: {short(option.inner_text())}")
        if args.click_link:
            links = page.get_by_role("link", name=args.click_link, exact=False)
            visible_links = [links.nth(i) for i in range(links.count()) if links.nth(i).is_visible()]
            if not visible_links:
                raise RuntimeError(f"No visible link matching: {args.click_link}")
            visible_links[0].click(timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.press_link:
            links = page.get_by_role("link", name=args.press_link, exact=False)
            visible_links = [links.nth(i) for i in range(links.count()) if links.nth(i).is_visible()]
            if not visible_links:
                raise RuntimeError(f"No visible link matching: {args.press_link}")
            visible_links[0].focus()
            visible_links[0].press("Enter", timeout=5_000)
            page.wait_for_timeout(args.wait_after_ms)
        if args.open_combobox:
            page.keyboard.press("Escape")
            matches = page.get_by_role("combobox", name=args.open_combobox, exact=True)
            if not matches.count():
                matches = page.get_by_role("combobox").filter(has_text=args.open_combobox)
            matches.nth(args.combobox_index).click()
            page.wait_for_timeout(500)
            options = page.get_by_role("option")
            if args.scroll_offset is not None and options.count():
                options.first.evaluate(
                    """(el, offset) => {
                        let p=el.parentElement;
                        while(p && p.scrollHeight <= p.clientHeight) p=p.parentElement;
                        p.scrollTop=offset;
                    }""",
                    args.scroll_offset,
                )
                page.wait_for_timeout(800)
                options = page.get_by_role("option")
            print(f"OPTIONS {options.count()}")
            for index in range(min(options.count(), args.limit)):
                print(f"OPTION {index}: {short(options.nth(index).inner_text())}")
                if args.html:
                    print(f"  HTML {short(options.nth(index).evaluate('el => el.outerHTML'), 700)!r}")
                if args.ancestors and index == 0:
                    ancestors = options.nth(index).evaluate(
                        """el => { const out=[]; let p=el.parentElement; while(p && out.length<8) { out.push({tag:p.tagName, cls:p.className, sh:p.scrollHeight, ch:p.clientHeight, st:p.scrollTop}); p=p.parentElement; } return out; }"""
                    )
                    print(f"  ANCESTORS {ancestors}")
            return
        if args.list_options:
            visible_options = [
                page.get_by_role("option").nth(index)
                for index in range(page.get_by_role("option").count())
                if page.get_by_role("option").nth(index).is_visible()
            ]
            print(f"VISIBLE_OPTIONS_NOW {len(visible_options)}")
            for index, option in enumerate(visible_options[: args.limit]):
                print(f"VISIBLE_OPTION_NOW {index}: {short(option.inner_text())}")
        if args.screenshot:
            screenshot_path = Path(args.screenshot)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            if not args.preserve_scroll:
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(300)
            if args.full_page_screenshot:
                capture = capture_long_page(
                    page,
                    screenshot_path,
                    use_cdp=True,
                    full_page=True,
                )
                print(f"SCREENSHOT_MODE {capture['mode']}")
                for path in capture["screenshot_paths"]:
                    print(f"SCREENSHOT {path}")
            else:
                try:
                    page.screenshot(
                        path=str(screenshot_path),
                        full_page=False,
                        timeout=20_000,
                        animations="disabled",
                        caret="hide",
                    )
                except Exception:
                    # Some extension-heavy Windows Chrome pages never settle for
                    # Playwright's screenshot lifecycle. Raw CDP still captures the
                    # rendered viewport without navigating or changing the form.
                    session = page.context.new_cdp_session(page)
                    captured = session.send(
                        "Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": False},
                    )
                    screenshot_path.write_bytes(base64.b64decode(captured["data"]))
                screenshot_path.chmod(0o600)
                print(f"SCREENSHOT {args.screenshot}")
        print(f"TITLE {short(page.title())}")
        print(f"URL {page.url}")
        if args.body_text:
            print(page.locator("body").inner_text(timeout=5_000)[: args.body_text])
        if args.inspect_text:
            matches = page.evaluate(
                """text => [...document.querySelectorAll('body *')]
                    .filter(el => (el.innerText || '').trim() === text)
                    .slice(0, 12)
                    .map(el => {
                        const clickable = el.closest(
                            'a, button, [role="button"], [role="link"], [onclick]'
                        );
                        const ancestors = [];
                        for (let p = el; p && ancestors.length < 5; p = p.parentElement) {
                            ancestors.push({
                                tag: p.tagName.toLowerCase(),
                                id: p.id || '',
                                className: String(p.className || '').slice(0, 180),
                            });
                        }
                        return {
                            tag: el.tagName.toLowerCase(),
                            id: el.id || '',
                            className: String(el.className || '').slice(0, 240),
                            clickableTag: clickable ? clickable.tagName.toLowerCase() : '',
                            href: clickable ? (clickable.getAttribute('href') || '') : '',
                            outerHTML: el.outerHTML.slice(0, 900),
                            ancestors,
                        };
                    })""",
                args.inspect_text,
            )
            for index, match in enumerate(matches):
                print(f"TEXT_MATCH {index}: {match}")
        count = 0
        for frame_index, frame in enumerate(page.frames):
            controls = frame.locator(
                "input, textarea, select, button, a[href], [role=button], "
                "[role=link], [role=checkbox], [contenteditable=true]"
            )
            try:
                total = controls.count()
            except Exception:
                continue
            for index in range(total):
                if count >= args.limit:
                    return
                control = controls.nth(index)
                try:
                    # Hidden file inputs are often activated by a visible
                    # upload button and remain valid Playwright upload targets.
                    input_type = control.get_attribute("type") or ""
                    if not control.is_visible() and input_type != "file":
                        continue
                    tag = control.evaluate("el => el.tagName.toLowerCase()")
                    typ = input_type
                    name = control.get_attribute("name") or ""
                    aria = control.get_attribute("aria-label") or ""
                    placeholder = control.get_attribute("placeholder") or ""
                    text = control.inner_text(timeout=500) if tag in {"button", "div", "span", "a"} else ""
                    file_count = (
                        int(control.evaluate("el => el.files ? el.files.length : 0"))
                        if typ == "file"
                        else 0
                    )
                    print(
                        f"F{frame_index} {tag}:{typ} name={short(name, 70)!r} "
                        f"aria={short(aria, 100)!r} placeholder={short(placeholder, 100)!r} "
                        f"text={short(text, 120)!r}"
                        + (f" files={file_count}" if typ == "file" else "")
                    )
                    if args.parent_text:
                        parent_text = control.evaluate(
                            """(el, depth) => {
                                let p=el;
                                for(let i=0;i<depth && p;i++) p=p.parentElement;
                                return p ? p.innerText : '';
                            }""",
                            max(1, args.ancestor_depth),
                        )
                        print(f"  PARENT {short(parent_text, 240)!r}")
                    if args.html:
                        outer = control.evaluate("el => el.outerHTML")
                        print(f"  HTML {short(outer, 500)!r}")
                    count += 1
                except Exception:
                    continue


if __name__ == "__main__":
    main()

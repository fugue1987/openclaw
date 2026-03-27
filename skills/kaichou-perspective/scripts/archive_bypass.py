import sys
import time
import argparse
import re
import urllib.request
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Archive mirror domains to try in order
ARCHIVE_MIRRORS = [
    "https://archive.md/",
    "https://archive.ph/",
    "https://archive.today/",
]

# Regex for snapshot short links: 4+ alphanumeric chars after any archive domain
SNAPSHOT_RE = re.compile(
    r"https?://archive\.(md|today|is|ph|li|vn|fo)/[A-Za-z0-9]+/?$"
)


def resolve_redirects(url):
    """
    Resolves email marketing redirects (like click.e.economist.com) to get the actual target URL.
    This bypasses initial tracking wrappers before archiving/cleaning.
    """
    if "click.e.economist.com" not in url and "?" not in url:
        return url

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

    try:
        res = opener.open(req, timeout=5)
        if res.getcode() in [301, 302, 303, 307, 308]:
            target = res.headers.get('Location')
            if target and target.startswith('http'):
                print(f"Resolved redirect: {target}", file=sys.stderr)
                return target
    except Exception as e:
        if hasattr(e, 'headers') and e.headers.get('Location'):
            target = e.headers.get('Location')
            if target and target.startswith('http'):
                print(f"Resolved redirect (via exception): {target}", file=sys.stderr)
                return target

    return url


def is_archive_snapshot_url(url):
    """
    Check if the provided URL is already a direct link to an archive snapshot.
    e.g., https://archive.md/LN2MA
    """
    return bool(SNAPSHOT_RE.match(url))


def clean_url_for_search(url):
    """
    Remove query parameters from the URL before searching the archive.
    This increases the chance of finding the canonical snapshot.
    """
    if not is_archive_snapshot_url(url) and '?' in url:
        return url.split('?')[0]
    return url


def get_archived_content(url_to_search, cdp_url="http://localhost:9222"):
    """
    Attempts to retrieve paywalled content via archive.today mirrors using an existing Chrome session.

    Exit codes / prefixes for agent consumption:
      - "ERROR:CDP_CONNECT: ..."   — Chrome not reachable on CDP port
      - "ERROR:NO_SNAPSHOT: ..."    — No archived snapshot found
      - "ERROR:TIMEOUT: ..."        — Page load / network timed out
      - "ERROR:UNKNOWN: ..."        — Unexpected failure
    """
    # 1. Resolve any marketing redirects (e.g. from emails)
    resolved_url = resolve_redirects(url_to_search)

    # 2. Clean the URL (remove utm tags etc.)
    final_url = clean_url_for_search(resolved_url)

    with sync_playwright() as p:
        # --- Connect to Chrome ---
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            return f"ERROR:CDP_CONNECT: Could not connect to Chrome at {cdp_url}. Is Chrome running with --remote-debugging-port? ({e})"

        context = browser.contexts[0]
        page = None
        opened_new_tab = False

        try:
            # Reuse an existing archive tab if available
            for p_obj in context.pages:
                if any(domain in p_obj.url for domain in ['archive.md', 'archive.ph', 'archive.is', 'archive.li', 'archive.today']):
                    page = p_obj
                    break

            # If the user passed a direct snapshot URL, just go there and extract
            if is_archive_snapshot_url(final_url):
                print(f"Direct snapshot URL detected. Navigating to: {final_url}", file=sys.stderr)
                if not page:
                    page = context.new_page()
                    opened_new_tab = True
                page.bring_to_front()
                if page.url != final_url:
                    page.goto(final_url, timeout=15000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)
            else:
                # --- Try each mirror in order ---
                for mirror_url in ARCHIVE_MIRRORS:
                    try:
                        if not page:
                            page = context.new_page()
                            opened_new_tab = True

                        print(f"Searching archive for: {final_url} on {mirror_url}", file=sys.stderr)
                        page.goto(mirror_url, timeout=15000)
                        page.bring_to_front()

                        # archive.today has two inputs:
                        #   1st: "My url is alive and I want to archive its content"
                        #   2nd: "I want to search the archive for saved snapshots"
                        inputs = page.locator("input[type='text'], input[type='url']").all()
                        if len(inputs) < 2:
                            search_input = page.locator("input[name='q']")
                        else:
                            search_input = inputs[1]

                        search_input.fill(final_url)
                        search_input.press("Enter")

                        page.wait_for_load_state("networkidle", timeout=20000)
                        current_url = page.url
                        print(f"Current Page URL: {current_url}", file=sys.stderr)

                        # Check if we landed on a search results page or a snapshot page
                        if final_url in current_url and "/https" in current_url:
                            # Search results page — find the newest snapshot link
                            links = page.locator("a").all()
                            snapshot_href = None
                            for link in links:
                                href = link.get_attribute("href")
                                if href and SNAPSHOT_RE.match(href) and not href.endswith(".zip"):
                                    snapshot_href = href
                                    break

                            if snapshot_href:
                                print(f"Found snapshot: {snapshot_href}", file=sys.stderr)
                                page.goto(snapshot_href, timeout=15000)
                                page.wait_for_load_state("domcontentloaded", timeout=15000)
                                time.sleep(2)
                            else:
                                continue  # Try next mirror

                    except PlaywrightTimeout:
                        print(f"ERROR:TIMEOUT on mirror {mirror_url}, trying next...", file=sys.stderr)
                        continue
                    except Exception as e:
                        print(f"Error on mirror {mirror_url}: {e}", file=sys.stderr)
                        continue

                    # If we reached here, we have a page to extract from — break out of mirror loop
                    break
                else:
                    # All mirrors exhausted
                    return f"ERROR:NO_SNAPSHOT: No archived snapshot found for {final_url} across all mirrors."

            # --- Extract content ---
            content = page.evaluate("""() => {
                const selectors = ['article', 'main', '.article-content', '.story-body'];
                for (let sel of selectors) {
                    let el = document.querySelector(sel);
                    if (el) return el.innerText;
                }
                return document.body.innerText;
            }""")

            if content and len(content.strip()) > 100:
                return content

            return f"ERROR:NO_SNAPSHOT: Content extracted but too short ({len(content.strip()) if content else 0} chars)."

        except Exception as e:
            return f"ERROR:UNKNOWN: {str(e)}"

        finally:
            # Clean up: close only tabs we opened
            if opened_new_tab and page:
                try:
                    page.close()
                except Exception:
                    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaichou Perspective: Archive Bypass Script")
    parser.add_argument("url", help="The paywalled URL to retrieve or a direct archive.md snapshot URL")
    parser.add_argument("--cdp", default="http://localhost:9222", help="CDP URL (default: http://localhost:9222)")

    args = parser.parse_args()

    result = get_archived_content(args.url, args.cdp)
    print(result)

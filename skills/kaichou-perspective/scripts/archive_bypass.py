import sys
import re
import time
import argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Archive mirror domains to try in order
ARCHIVE_MIRRORS = [
    "https://archive.md/",
    "https://archive.ph/",
    "https://archive.today/",
]

# Regex for snapshot short links: 4+ alphanumeric chars after any archive domain
SNAPSHOT_RE = re.compile(
    r"https?://archive\.(md|today|is|ph|li)/([a-zA-Z0-9]{4,})$"
)


def get_archived_content(url_to_search, cdp_url="http://localhost:9222"):
    """
    Attempts to retrieve paywalled content via archive.today mirrors using an existing Chrome session.

    Exit codes / prefixes for agent consumption:
      - "ERROR:CDP_CONNECT: ..."   — Chrome not reachable on CDP port
      - "ERROR:NO_SNAPSHOT: ..."    — No archived snapshot found
      - "ERROR:TIMEOUT: ..."        — Page load / network timed out
      - "ERROR:UNKNOWN: ..."        — Unexpected failure
    """
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

            # --- Try each mirror in order ---
            for mirror_url in ARCHIVE_MIRRORS:
                try:
                    if not page:
                        page = context.new_page()
                        opened_new_tab = True

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

                    search_input.fill(url_to_search)
                    search_input.press("Enter")

                    page.wait_for_load_state("networkidle", timeout=20000)
                    current_url = page.url
                    print(f"Current Page URL: {current_url}", file=sys.stderr)

                    # Check if we landed on a search results page or a snapshot page
                    if url_to_search in current_url and "/https" in current_url:
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

                except PlaywrightTimeout:
                    print(f"Timeout on mirror {mirror_url}, trying next...", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"Error on mirror {mirror_url}: {e}", file=sys.stderr)
                    continue

            return f"ERROR:NO_SNAPSHOT: No archived snapshot found for {url_to_search} across all mirrors."

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
    parser.add_argument("url", help="The paywalled URL to retrieve")
    parser.add_argument("--cdp", default="http://localhost:9222", help="CDP URL (default: http://localhost:9222)")

    args = parser.parse_args()

    result = get_archived_content(args.url, args.cdp)
    print(result)

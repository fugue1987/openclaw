---
name: kaichou-perspective
description: "Access restricted or paywalled web content by leveraging third-party archiving services (e.g., archive.md, archive.today). Use when direct web fetching via HTTP or standard browser profiles fails due to paywalls, subscription requirements, or access restrictions. Provides automated browser workflows to retrieve archived snapshots of articles."
metadata:
  openclaw:
    category: "multimedia"
    requires:
      bins: ["python"]
      pip: ["playwright"]
---

# Kaichou Perspective (会长的洞察)

## Overview

"Kaichou Perspective" enables the agent to bypass web-based obstacles such as paywalls and access restrictions by using lateral thinking—leveraging public archive mirrors. This skill is named in honor of the meticulous and strategic approach required to maintain information flow in a restricted environment.

## Quick Start

When a URL returns a paywall or a "subscription required" message:

1.  **Ensure Chrome is running** with remote debugging enabled (`--remote-debugging-port=9222`).
2.  **Call the bypass script**:
    ```bash
    python scripts/archive_bypass.py "https://example.com/paywalled-article"
    ```
3.  **Analyze the returned text**, which represents the full body of the archived snapshot.

## Workflow

### 1. Identify the Obstacle
If a direct fetch (e.g., via `web_fetch`) results in limited text, a "subscribe" prompt, or a 403 error, the agent should switch to the Kaichou Perspective.

### 2. Search Archive Mirrors
The `archive_bypass.py` script automates the following procedure:
- Attaches to the user's running Chrome instance via CDP (port 9222).
- Tries multiple archive mirrors in order: `archive.md` → `archive.ph` → `archive.today`.
- Enters the target URL into the archive's search field (2nd input = snapshot search).
- Identifies the most recent snapshot link using regex pattern matching.

### 3. Extraction
The script extracts the main article text by looking for standard semantic tags (`<article>`, `<main>`, `.article-content`, `.story-body`), falling back to `document.body.innerText`.

## Error Handling

The script returns structured error prefixes for agent decision-making:

| Prefix | Meaning | Suggested Agent Action |
|--------|---------|----------------------|
| `ERROR:CDP_CONNECT` | Chrome not reachable | Prompt user to start Chrome with debug port |
| `ERROR:NO_SNAPSHOT` | No archived version found | Inform user, suggest alternative approaches |
| `ERROR:TIMEOUT` | Archive mirror timed out | Retry later or try manually |
| `ERROR:UNKNOWN` | Unexpected failure | Report error details to user |

## Dependencies

- Python 3.8+
- `playwright` (see `requirements.txt`)
- Chrome running with `--remote-debugging-port=9222`

## Security Note

This skill connects to the user's main browser context (`browser.contexts[0]`) to leverage existing login states. Any page operations run within the user's authenticated session. The script only navigates to trusted archive mirror domains.

## Examples

**User Request**: "I can't read this Bloomberg article, can you help?"
**Agent Response**: [Triggers kaichou-perspective]
1. Connects to Chrome on port 9222.
2. Runs `scripts/archive_bypass.py [Bloomberg_URL]`.
3. Tries archive.md first, falls back to archive.ph if needed.
4. Presents the full article summary to the user.

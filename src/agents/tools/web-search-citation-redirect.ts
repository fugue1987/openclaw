import { fetchWithWebToolsNetworkGuard } from "./web-guarded-fetch.js";
import type { SsrFPolicy } from "../../infra/net/ssrf.js";

const REDIRECT_TIMEOUT_MS = 5000;

// Allow RFC2544 benchmark range (198.18.0.0/15) — Google grounding redirect
// URLs (vertexaisearch.cloud.google.com) resolve to this range when behind
// certain VPN/proxy DNS configurations.
const CITATION_REDIRECT_SSRF_POLICY: SsrFPolicy = {
  allowRfc2544BenchmarkRange: true,
};

/**
 * Resolve a citation redirect URL to its final destination using a HEAD request.
 * Returns the original URL if resolution fails or times out.
 */
export async function resolveCitationRedirectUrl(url: string): Promise<string> {
  try {
    const { finalUrl, release } = await fetchWithWebToolsNetworkGuard({
      url,
      init: { method: "HEAD" },
      timeoutMs: REDIRECT_TIMEOUT_MS,
      policy: CITATION_REDIRECT_SSRF_POLICY,
    });
    await release();
    return finalUrl || url;
  } catch {
    return url;
  }
}

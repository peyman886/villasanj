# ADR-0008 — Ethical, reproducible crawling

Status: Accepted (M0 approval, 2026-10-01) · Date: 2026-10-01

## Context

Target platforms: jajiga, jabama, otaghak, shab (region Ramsar–Tonekabon, 1.5–3k listings). The research
report could not read their robots.txt, and it notes that jabama (and a review site) blocked automated
access during research. The brief requires: read and respect robots.txt; per-domain rate limits; an
identifying user agent; no login, captcha or anti-bot circumvention; raw pages stored with timestamps;
snapshots by default in development; **stop and report if a platform forbids crawling.**

Rough volume per platform: ~750 listings × (listing + calendar + reviews + 6 scenario quotes) ≈ 7k
requests. At 1 request per 3 s that is ≈ 6 h per platform, plus photos from CDN hosts.

## Decision

1. **Audit before code** (M2/M4): for each platform, fetch and snapshot `robots.txt` and the ToS page,
   and write `docs/sources/<platform>.md` with the allowed/disallowed paths relevant to us, the
   crawl-delay, ToS clauses on automated access, and a go/no-go. **The owner signs off before the first
   listing request.** A disallow or ToS prohibition means stop and report.
2. **`PoliteFetcher`** wraps every fetcher:
   - robots.txt check per URL (protego, cached as a snapshot, refreshed daily);
   - one in-flight request per host; default 1 req / 3 s + jitter, raised to `Crawl-delay` if larger;
   - exponential backoff on 429/5xx, honouring `Retry-After`;
   - **stop-on-block**: 403 bursts, captcha/challenge markers or bot-wall pages mark the platform `BLOCKED`
     and halt the run. There is no retry with different headers, no proxy rotation and no stealth
     plugins, ever;
   - identifying UA: `VillasanjBot/0.1 (+<project URL>; research prototype; contact: <CRAWL__CONTACT>)`.
3. **Data we fetch:** only public, logged-out pages and the public JSON endpoints those pages
   themselves call, and only if (a) the host's robots.txt allows the path, (b) no credentials or signed
   anti-bot tokens are required, and (c) ToS does not prohibit it. Each case is recorded in the audit
   doc. Playwright is a normal browser used only when content needs JavaScript; it is never used to
   evade detection.
4. **Snapshots first:** every response (body, status, selected headers without cookies, request params,
   `fetched_at`, fetcher) is stored content-addressed in the `BlobStore` with a `snapshot` row. Parsing
   is a pure function of the snapshot. `CRAWL__MODE=offline` is the default; live mode needs an
   explicit flag per run.
5. **Minimise load and footprint:** fetch photos at ≤ 800 px (the CDN resize variant if offered);
   crawl off-peak when possible; one scenario-capture run per window, not continuous polling.
6. **Privacy:** no reviewer names stored; host display names are used only for matching and not shown
   beyond what the platform shows; no phone numbers stored.
7. **Redistribution:** snapshots and photos never enter git. Contract-test fixtures are trimmed to the
   relevant markup and scrubbed of personal data. The UI shows thumbnails + summaries with source
   attribution and deep links; the booking always happens on the source platform. The demo narrative
   states that the production path is **partnership/feeds**, as Torob does with shops.

## Alternatives considered

- **Third-party scraping services / proxy networks.** Rejected: that is circumvention by another name.
- **Live crawling during development.** Rejected: it is non-reproducible and loads the platforms for
  no benefit.

## Consequences

- (+) A platform that blocks us is a reported finding, not a technical challenge to defeat.
- (+) Every parsed field is reproducible from a stored snapshot.
- (−) The full crawl takes hours per platform; it is scheduled, resumable (Postgres frontier) and
  measured.
- (−) If jabama forbids crawling, the OCP demo uses otaghak or shab (ROADMAP M2 Plan B).

## Amendment (M2 implementation, 2026-10-01)

1. **Accept header.** The fetcher sends standard content negotiation
   (`Accept: text/html,…;q=0.9,*/*;q=0.8`). jabama serves a reduced page shell to `Accept: */*` (149 KB
   without listings vs 729 KB with them). The user agent still identifies the bot. Nothing else about
   the request imitates a browser, and cookies are never stored.
2. **Reconnaissance rendering.** To discover where client-rendered data comes from, a page may be
   rendered once in a browser with the bot user agent and **all third-party trackers blocked**
   (analytics, ad, error-reporting and retargeting hosts answered locally with 204). The production
   crawler only uses plain HTTP to the endpoints found this way, and only after robots.txt allows
   them. The platforms' own ad-impression endpoints are never called.
3. **Photos are fetched on demand, not in bulk.** jabama publishes only 1632×1224 originals (~330 KB)
   and no smaller variant, so bulk download would mean ~7 GB and ~17 h of CDN load for ~3.5k listings.
   Photos are fetched for the listings entity resolution actually needs: every shab listing (749 px
   images, within the ≤ 800 px rule) and jabama listings that are blocking candidates for some shab
   listing (decided in M3). Photo hosts are crawled by their own process (`--kind photo`) so each
   host keeps its own pacing.
4. **Hosts without robots.txt.** `api.shab.ir/robots.txt` answers 404, which RFC 9309 treats as "no
   restrictions". The 404 response itself is stored as a snapshot.

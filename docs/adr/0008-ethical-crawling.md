# ADR-0008 — Ethical, reproducible crawling

Status: Proposed · Date: 2026-10-01

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

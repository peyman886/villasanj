# ADR-0011 — Platform scope after the robots.txt/ToS audit

Status: Accepted (owner decision, 2026-10-01) · Date: 2026-10-01 · Evidence: [`docs/sources/README.md`](../sources/README.md)

## Context

The research report planned four platforms: jajiga, jabama, otaghak, shab. The M2 audit (ADR-0008)
found:

- **jajiga** and **otaghak**: Terms of Service explicitly prohibit crawlers, scraping and data mining.
- **mihmansho** (the largest alternative): Terms prohibit any copying or use of site material without
  written permission.
- **jabama**: robots.txt allows everything; Terms contain no clause on automated access.
- **shab**: robots.txt explicitly allows listing pages (`/houses/show/*`); Terms contain no explicit
  clause, only a vague ban on using the service "for advertising and other purposes".
- **homsa**, **mizboon**: unreachable (DNS failure, expired TLS certificate).

The brief says: if a platform forbids crawling, stop and report. Cross-platform entity resolution needs
at least two permitted platforms.

## Decision

1. **Crawl only jabama and shab** (owner approved both on 2026-10-01). jabama is the first adapter;
   **shab is the second adapter and the Open/Closed proof** in M2 (it replaces jabama in that role).
2. **jajiga, otaghak and mihmansho are not crawled.** Not even pages their robots.txt allows: the
   Terms of Service win. Their Terms allow use with written permission, so the owner sends permission
   requests (drafts in [`docs/outreach/`](../outreach/permission-request-fa.md)). A granted permission
   is recorded here and adds exactly one `SourceAdapter`, with no core change.
3. The ADR-0008 limits apply unchanged to jabama and shab.
4. Browser rendering triggers third-party trackers (observed on jajiga's rules page), so the crawler
   uses plain HTTP and renders pages only where content is unavailable otherwise.

## Consequences

- (−) Fewer platforms means fewer cross-platform pairs. H1 overlap is measured on jabama×shab only,
  and shab's inventory is smaller (≈ 8k nationally per the research report), so the regional pair
  count may be low. M2 counts both platforms' regional inventory from their sitemaps before the full
  crawl. If the pair count is too small for meaningful H1–H3 statistics, the region is widened (decision
  at the M3 review).
- (−) The research report's preferred northern platform (jajiga) is missing; this is stated openly
  in the demo.
- (+) Compliance becomes part of the story: the production path is partnership/feeds, exactly like
  Torob with shops, and the architecture adds a partner with one adapter.
- ROADMAP M2/M4 are updated: M4 "coverage" now means *permission-gated* adapters (if any permission
  arrives) plus widening the region on the two permitted platforms.

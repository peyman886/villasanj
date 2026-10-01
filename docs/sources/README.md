# Source platforms: robots.txt and Terms of Service audit

Audit date: **2026-10-01** (07:23–07:30 UTC). Performed under ADR-0008 *before* any listing request.

Method: one request per document, ≥ 3 s apart per host, identifying user agent
`VillasanjBot/0.1 (research prototype; contact: <CRAWL__CONTACT>)`. Two pages whose terms load
client-side (jajiga rules, shab usage rules) were rendered once in a browser with the same user agent.
Raw responses are kept locally in `data/audit/` (git-ignored); their SHA-256 prefixes are listed below,
so the evidence can be verified. ToS clauses are paraphrased with their clause numbers. Read the
originals before relying on them, and note that **this is not legal advice**.

## Summary

| Platform | robots.txt | Terms of Service on automated access / reuse | Verdict |
|---|---|---|---|
| jajiga | Allows `/` except `/i/*`, `*gstnum*`, `*utm_*` | **Explicitly prohibits** bots, crawlers, scraping and data mining (§10-3, §10-4); reviews additionally protected (§8-3…§8-9). Updated 1405/06/01. | ❌ **No-go** without written permission |
| jabama | `User-Agent: *` with no rules (everything allowed) | No clause on automated access or content reuse found (terms updated 1399/10/29). | ✅ **Go**, with ADR-0008 limits |
| otaghak | Disallows `/api`, `/rooms-`, `/Booking`, multi-parameter queries, … | **Explicitly prohibits** scripts for crawling, indexing or data mining on any part of the service; content reuse needs written permission. | ❌ **No-go** without written permission |
| shab | Allows `/houses/show/*`; disallows reserve/payment/chat paths | No explicit clause. The user obligations include a vague ban on using the service "for advertising and other purposes". | ⚠️ **Owner decision** (ambiguous) |
| mihmansho | Allows public pages; blocks several SEO bots by name | **Any copying or use of site material without written permission is prohibited** (§2 of general terms). | ❌ **No-go** without written permission |
| homsa | `www.homsa.net` does not resolve (also tried `homsa.com`, `homsa.ir`) | — | ⛔ Unreachable / likely inactive |
| mizboon | TLS certificate expired on `www.mizboon.com` | — (we do not bypass TLS) | ⛔ Unreachable / likely inactive |

A ToS that *does not prohibit* crawling is not an explicit permission. For jabama (and shab, if
approved) we still apply ADR-0008: public logged-out pages only, 1 request per 3 s per host, stop on any
block signal, snapshots instead of repeated fetches, no republication beyond thumbnails, short excerpts
with attribution and deep links.

## Per platform

### jajiga (`www.jajiga.com`)
- robots.txt (`bd26af99d7594546`, 133 B): `Allow: /`, `Disallow: /i/*`, `Disallow: *gstnum*`,
  `Disallow: *utm_*`, sitemap at `/public/sitemap/sitemap.xml`. Note: `gstnum` looks like the guest-count
  parameter, so even robots.txt rules out fetching per-guest-count pages.
- Terms: `/rules`, text served from `/static/rules-fa.md` (rendered: `64c3d2bd4adc7edf`). Last updated
  1 Shahrivar 1405.
  - §10-3: running programs or scripts for indexing, studying or any data mining on the service is not allowed.
  - §10-4: public availability is not a licence; automated tools, robots, crawlers, scraping and
    unauthorised APIs for extracting or collecting the platform's data are prohibited.
  - §8-3 to §8-9: user reviews are treated as jajiga's proprietary data asset; extraction, aggregation
    or republication by third parties (explicitly including similar platforms and search engines) needs
    jajiga's written permission.
- Framework: Next.js (`__NEXT_DATA__` present).

### jabama (`www.jabama.com`)
- robots.txt (`72195c8e2795b282`, 15 B): `User-Agent: *` with no directives, so everything is allowed.
- Terms: `/help/faq/policy/` (`f8b9e303cb9e7334`), updated 1399/10/29; privacy: `/help/faq/privacy/`
  (`8e609a48b68750aa`). Neither contains a clause on automated access, crawling or reuse of listing data.
  Relevant for pricing: hosts accept that the price shown on jabama is final and that charging guests
  any extra fee is not allowed.

### otaghak (`www.otaghak.com`)
- robots.txt (`3d6c2e98c4211ed1`, 1,852 B): disallows `/api`, `/rooms-`, `/Booking`, `*?*&`,
  `*utm_*`, `/user`, `/admin`, …; publishes room and image sitemaps.
- Terms: `/term-of-service/` (`e60c5caacea89b6c`). Users may not run programs or scripts for crawling,
  indexing, data mining or similar activities on any part of the service; all content and data are the
  company's property, and use requires written permission.

### shab (`www.shab.ir`)
- robots.txt (`701e62c35f2eac9f`, 11,680 B): allows `/houses/show/*`; disallows edit, reserve, payment,
  chat and promo paths; per-city sitemaps (including northern cities).
- Terms: `/terms` (`1591b120f0ecc09d`; usage tab rendered: `8fe1dc6f8b92abca`). No clause about bots,
  crawling or data reuse. Among prohibited user conduct: breaking laws, using the service "for
  advertising and other purposes", using other people's information without consent, and attempting
  to damage or break into the system.

### mihmansho (`www.mihmansho.com`)
- robots.txt (`a5c780ae81dff926`, 436 B): blocks MJ12bot, serpstatbot, BLEXBot and CCBot completely;
  for other agents, disallows account, login, files and comment endpoints.
- Terms: `/terms-conditions` (`679ca32ff4371d98`). §2: any copying or use of the website's material
  without written permission is prohibited and legally actionable.

### homsa, mizboon
- `www.homsa.net` (the domain from the research report) does not resolve; `homsa.com` and `homsa.ir`
  did not answer either.
- `www.mizboon.com` serves an expired TLS certificate. We do not disable certificate checks, so it
  was not audited further.

## Consequences for the plan

Two of the four planned platforms (jajiga, otaghak) forbid crawling, and so does the largest
alternative (mihmansho). Cross-platform entity resolution needs at least two permitted platforms.
The options, and the decision taken, are recorded in [`docs/ROADMAP.md`](../ROADMAP.md) under M2.

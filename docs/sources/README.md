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

## Crawl-time observations (M2)

| Host | robots.txt | Notes |
|---|---|---|
| `www.jabama.com` | no rules, no Crawl-delay | Listings, calendars and prices are embedded in Next.js flight data; full pages need `Accept: text/html`. The neighbourhood field was empty on all 300 sampled stay pages. |
| `cdn.jabama.com` | `User-Agent: *` (no rules) | Photos only as 1632×1224 originals. |
| `gw.jabama.com` | not requested | API gateway seen during reconnaissance; not needed, so never crawled. |
| `www.shab.ir` | as audited above, no Crawl-delay | House pages embed listing data in `__NEXT_DATA__`. |
| `api.shab.ir` | **404** (RFC 9309: no restrictions) | Calendar endpoint keyed by Jalali dates. |
| `s3gw.shab.ir` | **403**, S3 error `AccessDenied` with `BucketName=robots.txt` | An object-storage gateway with no robots.txt object, not a site policy. RFC 9309 treats any 4xx as "unavailable", meaning no restrictions, and the crawler applied that. The owner can choose a stricter rule (treat a 403 robots.txt as "stop"). Originals range from 538×424 to 1600×1200 (199-photo sample, average 593 KB). |

### Live crawl, 2026-10-01 (UTC)

| | jabama | shab |
|---|---|---|
| Window | 07:51–11:11 (pages); one photo probe | 08:09–09:31 (pages, calendars); 11:03–11:15 (photo sample) |
| Requests stored as snapshots | 3,081: 121 search, 2,954 stay (2,952 × 200, 2 × 404), 5 robots, 1 photo | 1,410: 4 sitemaps, 602 houses, 598 calendars, 199 photos, 7 robots (3 × 200, 2 × 404, 2 × 403) |
| Not stored | — | 45 thumbnail requests for the crop experiment below (same polite fetcher) |
| Retries / give-ups / blocks | 0 / 0 / 0 | 0 / 0 / 0 |
| Regional inventory | Search pages declare 2,800 (Ramsar) and 976 (Tonekabon) results. We collected 2,772 and 973 unique stays (784 in both), 2,961 in total; 8 lie outside the region box, and 2 returned 404 by the time we fetched them. | City sitemaps list 516 (Ramsar) + 85 (Tonekabon) = 601 houses. All were fetched; 4 publish coordinates outside the region (Tehran, Gilan, a placeholder), so their calendars were not requested. |

The 31 stays missing against the declared jabama counts (28 + 3) were not on any page we fetched.
The likely reason is that the result order shifted during a 3-hour crawl, but this is **not verified**.
A second pass over the 121 search pages would find them.

### Photo renditions (shab, measured)

shab publishes `thumbnail_path` (400×300) and sometimes `hq_thumbnail_path` (800×600) next to the
original. On 45 pairs fetched politely, the pHash distance between thumbnail and original was 0–2
for 4:3 originals (n = 16) and 0–4 for near-4:3 originals (n = 13). For portrait originals (n = 16)
it was **20–32**: the thumbnails are landscape crops, so to pHash they look like a different photo.
Portrait photos are 19% of the sample. Decision: originals are kept as the matching evidence. Every
thumbnail size would hide those matches, and the 800 px variant saves only ~40% (352 KB vs 593 KB
on average). Crop-robust embeddings in M3 are the second line of defence.

## Consequences for the plan

Two of the four planned platforms (jajiga, otaghak) forbid crawling, and so does the largest
alternative (mihmansho). Cross-platform entity resolution needs at least two permitted platforms.
The options, and the decision taken, are recorded in [`docs/ROADMAP.md`](../ROADMAP.md) under M2.

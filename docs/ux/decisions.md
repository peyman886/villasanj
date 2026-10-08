# UX decisions (M12)

Status labels: **decided** (do it), **corrects research** (the report in `research-ux.md` says
otherwise; this file wins).

The owner's instruction for M12: **no questions.** Every point that used to be an open question is
decided below (D8). New uncertainties are resolved by the agent in the direction most consistent
with the product rules, recorded in `docs/ARCHITECTURE.md` §10 and in the wave report.

## D1. Scope and order

- **decided:** desktop first, recorded at 1920×1080 with browser zoom 125% (effective viewport
  1536×864). Every "above the fold" criterion is tested at both 1440×900 and 1536×864.
- **decided:** mobile is wave 3. It must not break before then (no horizontal scroll at 390×844), but
  it is not polished until the desktop video paths are done.
- **decided:** the three video scenes drive priority (search with the map; one villa in two
  listings; the two-platform calendar). See `research-ux.md` part 5.

## D2. Product rules are untouched

- **decided:** no change to any rule in `CLAUDE.md`. The redesign changes presentation only: no new
  data, no new numbers, no merged prices, no exact locations, no "booked" wording.
- **decided:** the LLM explanation keeps ADR-0007 (slots, deterministic renderer, verifier). Moving
  it into the first card and streaming it are presentation changes only.
- **decided:** the match-evidence section shows only evidence the ER pipeline actually recorded for
  that pair (shared photo hashes, distance between approximate points, structural features, judge
  verdict, human label). It never invents a reason. Host names are not displayed; at most «نام
  میزبان در دو آگهی یکسان است» if that feature exists in the recorded evidence.
- **decided:** numbers in mockups and in the research report («۴۱ ویلا»، «از ۶ میلیون»، «۸٬۵۴۰٬۰۰۰»)
  are illustrations. Every number on screen comes from data; every number in `/docs` and on the home
  proof strip comes from an artifact or `/metrics`.

## D3. Where the research is corrected

| # | Research says | Decision | Why |
|---|---|---|---|
| R1 | Stale price after 48 h | **corrects research:** keep the existing 24 h stale flag (ROADMAP M6 crit. 4); only its presentation changes («قیمتِ N روز پیش»). | One definition of stale in API and UI. |
| R2 | Compact distances like «~۲ کیلومتر» | **corrects research:** use the range rule in `copy-and-numbers.md` §3 («حدود X» only for narrow ranges, otherwise «X تا Y»). | A point estimate from a wide range is a fabricated precision. |
| R3 | Surface colour #FAF8F4 (warm off-white) | **corrects research:** keep the current near-white surface unless the owner prefers otherwise. | Warm cream is a common generic look; the brand already has a distinct green. |
| R4 | "Progressive disclosure should be skipped when side-by-side comparison is needed" attributed to NN/g | **corrects research:** the idea is kept, but do not cite it as NN/g in `/docs`; the report itself found it in secondary sources. | No unsourced attribution in a product whose promise is provenance. |
| R5 | Horizontal filter bar justified as "better than a sidebar" | **corrects research:** the bar is used because Villasanj has fewer than 8 filter types and the intent is already chips; Baymard's 2024 update recommends caution with horizontal toolbars. | Correct reason, same outcome. |
| R6 | Contrast ratios in the token table | **corrects research:** they are approximate; the axe E2E suite and a contrast check are the evidence (≥ 4.5:1 for text). | Measured, not estimated. |
| R7 | "First token of the explanation < 1.5 s" | **corrects research:** applies to cached demo paths. Uncached explanations keep the current latency (owner accepted, M10 crit. 4); the card shows a skeleton line until the first token. | Do not promise what the uncached path cannot meet. |
| R8 | Hero image of a Caspian beach or forest | **decided (D8.2):** a designed OSM map of Ramsar–Tonekabon. Listing photos are hotlinked third-party content and are **not** used as the hero. | Licensing and the crawling-ethics ADR. |

## D4. Calendar

- **decided:** Jalali month view; weeks start on Saturday; Friday and sourced official holidays
  styled as days off.
- **decided:** each day split **top = jabama, bottom = shab** (not left/right: in RTL a vertical
  split collides with reading direction and is too narrow on mobile).
- **decided:** states by colour **and** pattern: available = solid platform colour; unavailable =
  grey hatch; not observed = dashed outline; hidden night = gold outline around the whole day.
- **decided:** the hidden-nights summary line is hidden when the count is 0.
- **decided:** the split-day calendar is new and untested by any public study. The agent does not
  block on validation; the final report recommends a 5-second test with 3 people before recording
  ("on which platform is the 13th free?") as an optional step for the owner.

## D5. Search

- **decided:** split view, list right, map left; MapLibre with the existing offline basemap; price
  pins show the cheaper platform's short price; the approximate area is drawn as a circle on hover
  and selection, never as an exact point.
- **decided:** the budget ambiguity is resolved by default to «کل سفر» when the query does not say,
  with a two-state chip to flip it; results never wait for an answer. (The current wording "تا وقتی
  نگفته‌اید، سخت‌گیرانه‌تر حساب شده" becomes the chip's tooltip.)
- **decided:** "کنار گذاشته شد" and the drive-time distribution move into a drawer next to the
  results header; empty buckets are not rendered.

## D6. Villa page

- **decided:** gallery deduplicated by perceptual hash across member listings, using the same
  hashes and threshold family as ER (tune the display threshold so near-identical crops collapse).
- **decided:** the sticky booking card inherits dates and guests from the search URL; changing them
  re-quotes both platforms from stored observations (no live request to a platform).
- **decided:** scenario matrix becomes a closed drawer «قیمت‌های نمونه»; heading «قیمت نهایی» is
  removed everywhere.
- **decided:** the aggregate rating stays (ratings are not prices) but is labelled with both counts:
  «★ ۴٫۸۹ · ۲۰۵ امتیاز · ۱۳ نظر».

## D7. Home

- **decided:** stats, principles and the dark docs box leave the home page; one proof strip remains
  and links to `/metrics`; footer link «برای داوران» → `/docs` and `/docs/demo`.

## D8. Former open questions, now decided

| # | Topic | Decision |
|---|---|---|
| D8.1 | Local copies of listing photos | Not added. Photos stay hotlinked (product rule 7). The video is recorded online after opening the demo paths once so the browser has the photos. Photos are never committed. |
| D8.2 | Hero visual | A designed OpenStreetMap treatment of the Ramsar–Tonekabon coast from the existing offline basemap, with the ODbL attribution. No stock photo, no listing photo. |
| D8.3 | Platform colours | jabama #2563EB, shab #7C3AED (never the platforms' brand colours), always with the platform name and, in the calendar, a pattern. Adjust only if the contrast check fails. |
| D8.4 | Demo villa | The agent picks it with a rule and writes the rule and the result into the wave-1 report: two platforms; ≥ 3 hidden nights in the next 30 days of the latest capture; ≥ 1 spec field with «دو عدد متفاوت»; ≥ 3 shared photo pairs in the ER evidence; a cited review summary; ties broken by the most reviews. If no villa meets every condition, relax in this order and say so in the report: hidden nights ≥ 1, then shared photo pairs ≥ 2, then no contradiction required. `docs/demo-script.md` is updated to use it. |
| D8.5 | Stale threshold | 24 h, unchanged (R1). |
| D8.6 | Approval between waves | The owner wants M12 to run end to end. Waves end with a written checkpoint (report + commit), not a stop. |

# Current UI audit (screenshots of 2026-10-07, localhost:3300)

Severity: **bug** = wrong or inconsistent; **hierarchy** = right content, wrong weight or place;
**polish** = visual quality. Each item names its fix (see `brief.md` and `M12-plan.md`).

## Cross-cutting

| # | Finding | Severity | Fix |
|---|---|---|---|
| X1 | Everything is shown at the same volume: facts, caveats, methodology, provenance. The page reads like an audit report. | hierarchy | "Truth available, not loud" (`brief.md`). |
| X2 | A dotted underline under every number (clickable provenance) on every page. Visually it turns the page into a bill. | polish | Keep provenance on hover/focus/tap for prices, distances and calendar values; drop the permanent underline on search cards. |
| X3 | Section intros explain methodology ("هیچ مقداری میانگین یا ترکیب نمی‌شود…", "«تأیید نشد» یعنی…"). | hierarchy | One short line at most; methodology to tooltips or `/docs`. |
| X4 | Yellow/amber is used for warnings everywhere, so nothing stands out. | polish | Amber only for "دو عدد متفاوت" and price age; see tokens in `research-ux.md` §4.8. |
| X5 | Number formatting: "۱۰۰/۰٪" (slash as decimal, meaningless trailing zero). | bug | `copy-and-numbers.md`. |

## Home (`/`)

| # | Finding | Severity | Fix |
|---|---|---|---|
| H1 | Under the hero, four stats cards (100.0%, 20.7%, 305, 3,588) speak to judges, not travellers. | hierarchy | Move to `/metrics`; keep one proof strip. |
| H2 | "Principles" cards and the dark "گزارش فنی کامل پروژه" box sell the docs on a product page. | hierarchy | Footer link "برای داوران" → `/docs`. |
| H3 | The merged-villas grid (photos + jabama/shab badges) is the best section but sits low. | hierarchy | Move directly under the hero; add the platform price gap per card. |
| H4 | The search box is a free-text field only; no visible dates or guests. | hierarchy | Keep natural language as the hero; sample-query chips below. Dates and guests become editable chips on the results page. |

## Search (`/search`)

| # | Finding | Severity | Fix |
|---|---|---|---|
| S1 | No map. Location (sea, forest) is the main decision factor for a Caspian villa. | hierarchy | Split view with price pins (`research-ux.md` §1.1). |
| S2 | The first result starts near the bottom of the first screen: the yellow budget box, the "چرا گزینه‌ی اول؟" box and the sidebar are above or beside it. | hierarchy | First full card above the fold at 1440×900 and 1536×864. |
| S3 | The yellow box "بودجه برای هر شب است یا کل اقامت؟" blocks the flow. | hierarchy | Two-state budget chip; results never wait for the answer. |
| S4 | The LLM explanation is a large separate box above the list. | hierarchy | Stream it inside the first card (slot rendering and verifier unchanged, ADR-0007). |
| S5 | Sidebar drive-time histogram shows zero rows ("۳ ساعت: ۰ آگهی · ۴ ساعت: ۰ آگهی"). | polish | Move to the "کنار گذاشته شد" drawer; never render empty buckets. |
| S6 | Header says "۳۱۶ آگهی مناسب" but the list is deduplicated villas ("هر ویلای واقعی یک بار می‌آید"). | bug | Count villas: "۳۱۶ ویلا". |
| S7 | Card drive time: "۴ ساعت و ۱۵ دقیقه تا ۴ ساعت و ۲۰ دقیقه از میدان آزادی تهران، بدون ترافیک". | hierarchy | Compact form per the range rule in `copy-and-numbers.md` ("حدود ۴ ساعت از تهران"); full text in the tooltip. |
| S8 | Card distance: "۱٫۵ تا ۲٫۴ کیلومتر تا ساحل در خط مستقیم". | hierarchy | Compact range "۱٫۵ تا ۲٫۴ کیلومتر تا دریا"; "خط مستقیم" and blur radius in the tooltip. |
| S9 | Amber chip "هزینه‌های جانبی منتشر نشده؛ ممکن است از بودجه بیشتر شود" on every card. | hierarchy | Remove from cards; "از" carries it; one explanation per page. |
| S10 | Price column reads "حداقل ۱۰٬۵۰۰٬۰۰۰ تومان" with "کل اقامت در جاباما" above it. | polish | Torob two-line price: "از ۱۰٫۵ میلیون تومان" / "برای ۲ شب، ۶ نفر · در ۲ پلتفرم". |
| S11 | The second platform appears only as a small chip "+ شب"; the core differentiator is invisible. | hierarchy | Mini offer row with both platforms, cheaper one marked. |
| S12 | Large rank numbers on every photo. | polish | Only the first card gets "بهترین تطابق". |
| S13 | Single photo per card. | polish | Carousel of 3 to 5 deduplicated photos. |

## Villa page (`/villas/<id>`)

| # | Finding | Severity | Fix |
|---|---|---|---|
| V1 | **Duplicate photos in the gallery** (the same living room twice, side by side; one from each platform). For an ER product this is the worst place to show a duplicate. | bug | Deduplicate the gallery by perceptual hash across member listings. |
| V2 | A technical paragraph at the top: "اینکه این آگهی‌ها یک ویلا هستند را قواعد تطبیق، داور مدل‌زبانی… تعیین کرده‌اند". | hierarchy | Badge "یک ویلا در ۲ آگهی · چرا مطمئنیم؟" → match-evidence section; paragraph to `/docs`. |
| V3 | Sticky card has no date or guest picker; it is fixed to "آخر هفته‌ی عادی برای ۴ نفر". | hierarchy | Date range + guests in the card, inherited from search. |
| V4 | Wording bug: "هر نفر نفری دست‌کم ۲٬۱۲۵٬۰۰۰ تومان". | bug | "نفری از ۲٫۱ میلیون". |
| V5 | Each price row repeats the fee caveat and a "قدیمی" badge. | hierarchy | Age as text ("قیمتِ ۳ روز پیش"); fee caveat once per page. |
| V6 | Rating "۴٫۸۹ (۲۰۵ رأی در همه‌ی پلتفرم‌ها)" while reviews say "جاباما: ۷ نظر · شب: ۶ نظر" and the summary covers 12. Readers will think the numbers contradict each other. | bug | Label both: "۲۰۵ امتیاز · ۱۳ نظر متنی". |
| V7 | Section "قیمت نهایی در هر پلتفرم" shows values that are all "حداقل". "Final price" contradicts "at least". | bug | Rename: "قیمت‌های نمونه"; closed drawer. |
| V8 | The scenario matrix (weekend / midweek / holiday × 4 and 8 people × 2 platforms) repeats the fee caveat in every cell. | hierarchy | Drawer; caveat once. |
| V9 | The calendar is a long table, one row per night, with text like "پر یا بسته · ۷ م" ("م" for million is unclear). | hierarchy | Jalali month view, split days (`brief.md`). |
| V10 | The calendar uses "پر". jabama's unavailable nights do not say booked or closed (CLAUDE.md gotcha). | bug | "ناموجود" everywhere; never "پر" or "رزرو شده". Also in `docs/demo-script.md`. |
| V11 | The showcase villa's calendar header says "۰ شب از ۳۰ شب پیش رو" are hidden nights. | polish | Hide the hidden-nights line when it is 0; pick a demo villa that has hidden nights. |
| V12 | Specs table lists every field for both platforms; only one row differs (متراژ, "ناهمخوان"). | hierarchy | Icon line for agreed fields; table only for contradictions; label "دو عدد متفاوت". |
| V13 | Truth check has a progress bar (reads like an exam score) and repeats "پلتفرم دقت نقطه را اعلام نکرده؛ تا ۵۰۰ متر خطا فرض شده" under every claim. | hierarchy | Highlights at the top; grouped list below; blur note once per section. |
| V14 | Review summary citations "(بر اساس نظر ۲، نظر ۳، نظر ۴، …)" crowd every line. | polish | One count chip per point that filters the list. |
| V15 | No navigation between the long sections. | hierarchy | Sticky anchor nav. |

## What already works (keep)

- The hero line "یک ویلا، همه‌ی حقیقت" and the natural-language search with removable chips.
- The merged-villas grid on the home page.
- Platform badges on photos, the approximate-location circle on the map.
- The cited review summary (pros and cons with sources).
- The provenance model itself: every value still has a source and an age; only its presentation
  changes.

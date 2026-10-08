# UX redesign brief

## Goal

Villasanj is judged in a 5-minute video against Torob's criterion: **tasteful, bold and usable**
(«باسلیقه، جسورانه و قابل‌استفاده»). The redesign must make three things obvious within seconds:

1. **Torob's DNA:** one real villa, several platforms, the cheaper offer first ("از X در N پلتفرم").
2. **The AI core:** we know two listings are the same villa, and we can show why.
3. **Honesty without noise:** every number still has a source and an age, but the page does not
   shout about it.

Audience: (a) a Tehran group of 4 to 10 planning a weekend on the Caspian coast; (b) a Torob
reviewer watching the video. Design for (a); stage the video for (b).

## The one principle

> **Truth should be available, not loud.**

- Methodology, provenance and caveats move one layer down (tooltip, drawer, `/docs`, `/metrics`).
- Uncertainty moves **into the format of the number** instead of a sentence next to it:
  "از ۸٫۵ میلیون" instead of "۸٬۵۰۰٬۰۰۰" plus a yellow warning.
- The **platform comparison is never hidden.** Progressive disclosure is for secondary
  information; side-by-side comparison is the primary task and stays visible.

## Design direction

| Take from | What exactly |
|---|---|
| HomeToGo | Visual discipline: neutral surfaces, one signature accent used only on the main CTA and key moments, large borderless photos, compact spec lines, one primary CTA per card, split view with price pins, 1+4 gallery with "+N photos", sticky booking card with dates and guests, highlights with an icon and a one-line subtitle, amenity grid, anchor/tab navigation on the listing page. |
| Torob | The two-line price on every card ("از X" / "در N پلتفرم"), the seller list sorted by price (our "پلتفرم‌ها" list), "ارزان‌ترین" wording. A Torob reviewer should recognise this in under a second. |
| Airbnb | Approximate-location circle (users already understand it), total-price-first display, badges that are backed by stated criteria. |
| Google Hotels | The booking module: one row per partner for the chosen dates and guests. |
| Google Flights | Calendar with a price in each day as the base pattern for our two-platform calendar. |
| Iranian sites | Conventions only: Jalali calendar starting on Saturday, toman, "شروع از", base + extra guests, "رزرو آنی". |

Keep the current identity (dark green, Vazirmatn); it fits the forest-and-sea subject and separates us
from HomeToGo's purple. Change the discipline, not the brand: fewer warning colours, more white
space, one gradient reserved for the primary CTA and the "one villa in two listings" badge.

**Spend boldness in one place.** The memorable things are (1) the "why we are sure" match evidence
and (2) the two-platform calendar. Everything around them stays quiet. Do not turn every section into
an identical rounded card with the same shadow; hierarchy must come from size, weight and space.

## Target per page (summary; full spec in `research-ux.md` part 4, decisions in `decisions.md`)

### Home
- Above the fold: slim header, hero with the tagline and a large natural-language search box, three
  sample-query chips, and the first row of "ویلاهایی که در هر دو پلتفرم پیدا کردیم" peeking in.
- The merged-villas grid (today's best section) comes right after the hero; each card shows the
  price difference between platforms.
- Stats cards, principles and the dark "technical report" box leave the home page. Keep **one**
  proof strip ("۳٬۲۸۳ ویلا · ۳۰۵ ویلا در هر دو پلتفرم · دقت تطبیق ۱۰۰٪") linking to `/metrics`,
  and a footer link "برای داوران" to `/docs`.

### Search
- **Split view:** results on the right, sticky MapLibre map on the left with short price pins
  ("۸٫۵م"). Hovering a card highlights its pin and vice versa. Pins show the approximate area, never
  a fake exact point.
- Horizontal bar of editable intent chips ("برداشت ما"): dates open a Jalali picker, guests a
  stepper, budget a two-state chip "[کل سفر] / هر شب". The yellow disambiguation box is removed:
  pick the most likely reading, show results immediately, let the chip flip it.
- Results header: "۴۱ ویلا · از ۶ میلیون برای ۲ شب", sort control, link "درباره‌ی رتبه‌بندی".
- The LLM "why first?" text streams **inside the first card**, not in a separate box above results.
- The sidebar (drive-time histogram, excluded counts, provenance note) becomes a drawer
  "چرا N ویلا کنار گذاشته شد؟" next to the results header.
- Result card (order and weight in `research-ux.md` §4.3): photo carousel without duplicates,
  title, compact spec line, compact location line, one evidence-backed highlight, rating with
  counts, **two-line Torob price**, mini offer row (cheaper platform marked), one CTA
  "مقایسه‌ی پیشنهادها", a one-line "چرا اینجا؟". No fee warning on cards.

### Villa page
- Header: title, place, badge "یک ویلا در ۲ آگهی · چرا مطمئنیم؟" (opens the match-evidence
  section). The technical ER paragraph moves to `/docs`.
- Gallery 1+4 with "+N عکس", **deduplicated across platforms** by perceptual hash.
- Highlights row (3 to 5): evidence-backed facts, e.g. "استخر سرپوشیده · در عکس‌ها دیده شد",
  "۱۵ دقیقه پیاده تا جنگل · روی نقشه تأیید شد", "★ ۴٫۸۹ · ۲۰۵ امتیاز در ۲ پلتفرم".
- Sticky anchor navigation: اقامت · مکان · تقویم · قیمت‌ها · نظرها · حقیقت‌سنجی.
- **Sticky booking card:** Jalali date range + guests (inherited from search), an availability line
  with its age, then the "پلتفرم‌ها" list: one row per platform, cheaper first, each with its own
  price, age, "رزرو آنی" if any, and "دیدن در جاباما ↗". The fee explanation appears **once** here.
  States: two platforms, one platform, stale price, unavailable on one, hidden nights.
- The scenario price matrix becomes a closed drawer "قیمت‌های نمونه".
- **Two-platform calendar:** Jalali month view, each day split top (jabama) / bottom (shab), states
  by colour *and* pattern, hidden nights outlined, tooltip with both observations and their ages;
  selecting a range updates the booking card.
- **"چرا مطمئنیم این دو آگهی یک ویلاست؟":** 3 to 4 pairs of shared photos side by side with a
  label ("همان استخر"), then 2 to 3 non-photo evidence lines, then "قواعد ✓ · داور مدل زبانی ✓ ·
  برچسب انسانی ✓". This is the AI wow moment of the video.
- Specs: a compact icon line for what both platforms agree on; a two-column table only for
  contradictions ("دو عدد متفاوت": ۳۰۰ | ۲۲۰ متر).
- Truth check: summary as highlights at the top; full list below grouped as تأیید شد / تأیید نشد /
  با نقشه نمی‌خواند, each with its evidence. No progress bar.
- Reviews: keep the cited summary (the best section today) but replace "نظر ۲، نظر ۳، …" with one
  count chip per point ("۷ نظر") that filters the review list.

### Mobile
Results full width with a large floating "نقشه" button that keeps list state when the user returns.
The booking card becomes a bottom bar with price and "مقایسه‌ی پیشنهادها". Same hierarchy, same rules.

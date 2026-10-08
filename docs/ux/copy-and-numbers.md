# Copy, numbers and visual guardrails

These rules apply to every user-facing string in the redesigned pages. They are compatible with the
product rules (no fabricated number, LLM writes no digits, observations have an age). Where a rule
here touches the LLM explanation, it is enforced by the deterministic renderer, not by the prompt.

## 1. Vocabulary (one word per concept)

| Concept | Use | Never |
|---|---|---|
| Price known only as a lower bound | «از ۸٫۵ میلیون تومان» | «حداقل»، «قیمت نهایی» |
| The list of platform offers | «پلتفرم‌ها» (like Torob's «فروشنده‌ها») | «پیشنهادها» as a section title |
| Cheaper offer | «ارزان‌تر» | «بهترین قیمت» (we do not know the final price) |
| Night not bookable on a platform | «ناموجود» / «برای این تاریخ در شب خالی نیست» | «پر»، «رزرو شده»، «پر یا بسته» |
| Night free on one platform, not on the other | «شب پنهان» (with a one-line tooltip) | — |
| No observation for a night | «هنوز این روز را ندیده‌ایم» | blank cell |
| Price age | «قیمتِ ۳ روز پیش»، «۲ ساعت پیش» | «قدیمی» as a badge |
| Two listings disagree on a field | «دو عدد متفاوت» | «ناهمخوان»، «تناقض» |
| Claim supported by evidence | «تأیید شد» | — |
| No evidence for a claim | «تأیید نشد» | «نادرست»، «دروغ» |
| Best case still contradicts the claim | «با نقشه نمی‌خواند» | «رد شد» |
| One villa found on two platforms | «یک ویلا در ۲ آگهی» | «ادغام‌شده» in UI copy |
| Ratings vs written reviews | «۲۰۵ امتیاز»، «۱۳ نظر» | «۲۰۵ رأی» next to «۱۳ نظر» without both labels |
| Count of results | «۳۱۶ ویلا» | «۳۱۶ آگهی» when results are deduplicated villas |
| Leaving to a platform | «دیدن در جاباما ↗» | «رزرو» (we do not book) |
| Card CTA | «مقایسه‌ی پیشنهادها» | several CTAs per card |
| Ranking explanation link | «درباره‌ی رتبه‌بندی» | — |
| LLM explanation title | «چرا این گزینه اول است؟» | — |

### The fee caveat: exactly once per page

Search page: one line under the results header, «قیمت‌ها بدون کارمزد پلتفرم‌اند؛ برای همین «از» نوشته‌ایم.»
Villa page: under the platform rows in the booking card, «هیچ‌کدام از دو پلتفرم کارمزدش را منتشر
نمی‌کند؛ برای همین قیمت‌ها «از» هستند و مبلغ نهایی را در خود پلتفرم ببینید.»
Nowhere else.

### Empty and error states

- No results: say which condition removed the most villas and offer to drop it: «با این شرط‌ها
  ویلایی پیدا نکردیم. اگر «استخر» را برداریم ۱۴ ویلا هست.» + button. The count must be computed,
  never estimated.
- Data refresh failed: «الان نتوانستیم به‌روز کنیم. آخرین داده‌ی ما مال ۲ ساعت پیش است.»
- No LLM available: the template fallback already exists; it must look identical in layout.

## 2. Numbers

- **Digits:** Persian digits everywhere in Persian text, including chips, pins, calendar cells and
  tooltips. No Latin digits in Persian UI (jabama mixes them; we do not).
- **Separators:** thousands «٬» (U+066C), decimal «٫» (U+066B): «۸٬۵۰۰٬۰۰۰»، «۸٫۵ میلیون»، «۲۰٫۷٪».
  Never «/» as a decimal separator. Never «٫» as a thousands separator (it collides with «۸٫۵»).
- **Percent:** no trailing zero decimals: «۱۰۰٪», not «۱۰۰/۰٪» or «۱۰۰٫۰٪».
- **Short money:** card and headline «۸٫۵ میلیون تومان»; map pin «۸٫۵م»; booking card rows the full
  number «۸٬۵۴۰٬۰۰۰ تومان». «تومان» always after the number.
- **Rounding direction:** a lower bound («از») is always rounded **down** (8,540,000 → «از ۸٫۵
  میلیون»). Rounding up would make «از» false. Upper bounds round up. Point values are not rounded
  in the booking card.
- **The headline price on a card** is the cheaper platform's own offer, attributed to it in the
  line below («در جاباما» or «در ۲ پلتفرم» with the offer row). It is never a combination of the
  two (product rule 3).
- **Per person:** «نفری از ۲٫۱ میلیون» (one word, no «هر نفر نفری»).

## 3. Ranges (distances, drive times, areas)

The product stores ranges; the UI must not turn them into fake points. Rule for the compact form
shown on cards and highlights:

- If the range is narrow, i.e. `(max − min) / midpoint ≤ 0.15`, show «حدود X» with X the rounded
  midpoint, and the exact range in the tooltip. Example: 4:15 to 4:20 → «حدود ۴ ساعت از تهران».
- Otherwise show the range in short form: «۱٫۵ تا ۲٫۴ کیلومتر تا دریا». No «حدود» for wide ranges.
- The tooltip always carries the method: «فاصله‌ی خط مستقیم از محدوده‌ی تقریبی آگهی تا ساحل
  (OpenStreetMap)»؛ «زمان رانندگی بدون ترافیک از میدان آزادی».
- Drive times are always free-flow; the word «بدون ترافیک» lives in the tooltip, not on the card.
- Area contradictions show both values: «۲۲۰ تا ۳۰۰ متر» on the card, «دو عدد متفاوت» on the villa
  page.

## 4. Visual guardrails

- **One accent, used sparingly.** Brand dark green for links and secondary buttons; the brand
  gradient only on the main CTA and the «یک ویلا در ۲ آگهی» badge.
- **Platform colours** are fixed and never the platforms' own brand colours (we do not speak for
  them); the platform name is always next to the colour. jabama always before shab (top half of a
  calendar day, first column, first row when prices are equal).
- **Colour is never the only carrier of meaning:** calendar states also use a pattern
  (solid / hatched / dashed outline); verdicts also use an icon and a word.
- **Amber** only for «دو عدد متفاوت» and price age. **Red** only for «با نقشه نمی‌خواند».
- **Hierarchy from size, weight and space, not from boxes.** Avoid the generic kit of identical
  rounded cards with the same soft shadow on every section; result cards have a border and no
  shadow, the booking card is the only element with a permanent shadow.
- **Spec lines** use «∙» between items («۳ خوابه ∙ تا ۱۰ مهمان ∙ ۲۲۰ تا ۳۰۰ متر»), as on HomeToGo
  and jajiga. Do not use dot-joined meta strings as decoration elsewhere.
- **Motion:** one orchestrated moment per page (chips arriving after query understanding; photo
  pairs locking together in the match evidence); motion that answers an action (hover card ↔ pin,
  opening a drawer) is fine; no fade-in on every section. Respect `prefers-reduced-motion`.
- **Type:** Vazirmatn (SIL OFL). Persian line-height around 1.75 for body text; prices weight 700;
  nothing under 13 px in screens used in the video.
- **RTL:** list right, map left; map zoom controls on the left; carousel "next" points left;
  directional arrows mirrored; Jalali calendar weeks start on Saturday, Friday styled as a day off,
  official holidays marked from the sourced holiday calendar.

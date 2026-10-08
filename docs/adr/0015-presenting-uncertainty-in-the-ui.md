# ADR-0015 — Presenting uncertainty in the UI

Status: Accepted (2026-10-08, M12 wave 1) · Extends ADR-0007 (numbers in LLM text) to presentation ·
Sources: `docs/ux/brief.md`, `docs/ux/copy-and-numbers.md`, `docs/ux/decisions.md`

## Context

Until M11 every value on the product pages carried its uncertainty as a sentence next to it: a
yellow fee warning on each search card, «حداقل» before every price, a «قدیمی» badge on each row,
the blur radius under every distance claim. The values were honest; the pages read like an audit
report. M12 moves uncertainty **into the format of the number** and says each caveat once, without
changing a single stored value or product rule.

## Decision

1. **One formatting module.** Every number on the product pages goes through
   `frontend/src/lib/numbers.ts` (table-driven tests). Persian digits; «٬» (U+066C) between
   thousands, «٫» (U+066B) as the decimal mark; no trailing zero decimals («۱۰۰٪», never «۱۰۰٫۰٪»).
   Titles and review text keep their words but show Persian digits.
2. **«از» carries "at least".** A price whose platform fees are unknown is shown as «از X». A
   lower bound is always rounded **down** (8,540,000 → «از ۸٫۵ میلیون»), an upper bound up, a point
   value to the nearest; the booking card shows the full number. «حداقل» and «قیمت نهایی» are not
   used. In a running sentence, where «از X» does not read, the backend's slot text says
   «دست‌کم X» (the LLM explanation; ADR-0007's renderer, not the model, writes it).
3. **Ranges stay ranges.** A stored range is said as «حدود X» only when it is narrow
   (`(max − min) / midpoint ≤ 0.15`); otherwise «X تا Y». The method (straight line, free flow,
   blur circle) moves to the provenance card.
4. **Each caveat once per page.** The fee caveat: one line under the search results header, and
   one line under the platform rows of the villa's booking card. Nowhere else.
5. **Age, not judgement.** An observation shows its age («قیمتِ ۳ روز پیش»); the 24 h stale rule
   (ROADMAP M6 crit. 4) only colours that text. No «قدیمی» badge.
6. **One vocabulary.** `frontend/src/lib/copy.ts` holds the words for recurring ideas
   («ناموجود», «ارزان‌تر», «دو عدد متفاوت», «یک ویلا در ۲ آگهی», …) and the list of forbidden
   strings, which the E2E suite asserts on the search page and the demo villa.
7. **Colour is never the only carrier.** Calendar states differ by fill, hatch and outline; the
   platform's name always sits next to its colour; amber only for «دو عدد متفاوت» and a price's
   age, red only for «با نقشه نمی‌خواند».
8. **Provenance stays one click away.** Every price, distance, drive time, calendar value and spec
   keeps its source card; on search cards the dotted underline appears on hover and focus only.

## Consequences

- No data, rule or computation changes; the API gained only read fields (locations, photos and
  hashes, recorded match evidence) the pages need to show existing data.
- The LLM explanation's prompt carries the new slot text, so its cache entries changed once
  (re-warmed for the demo paths).
- A component that formats a number on its own is a review finding; the forbidden-strings check
  catches regressions in wording.

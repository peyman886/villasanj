# M12: UX redesign and public release

**Owner's instructions for M12 (amend the working agreement in `CLAUDE.md` for this milestone):**

- **No questions to the owner.** All open points are decided in `decisions.md`. For anything new,
  choose the option most consistent with the product rules and `docs/ux/`, record it in
  `docs/ARCHITECTURE.md` §10 and in the wave report, and continue.
- **No waiting for approval between waves.** Each wave ends with a checkpoint: `make lint` and
  `make test` green, a written report in `reports/m12-wave-<n>-<date>.md`, `CLAUDE.md` and the
  roadmap updated, and Conventional Commits. Then the next wave starts.
- **The milestone ends with a public release** of the repository (`docs/release/public-release.md`).
- Everything else in the working agreement still holds: never fabricate data or results, never
  print or commit `.env` or keys, run tests and lint after every change, fix failures first.

## Before writing code (plan step)

1. Read `docs/ux/README.md` and every file it lists, then `docs/ux/screenshots/current/` and the
   reference screenshots in `docs/ux/references/`.
2. Optionally open the live references named in `docs/ux/README.md` (design reference only; rules
   there).
3. Use the `ui-skills-root` skill before UI work and `playwright-cli` for browser checks (owner's
   tooling preferences).
4. Write the wave plan into the wave report (no approval needed): files and components touched, new shared components (e.g. `PriceFrom`,
   `RangeText`, `OfferRows`, `JalaliSplitCalendar`, `MatchEvidence`), tests, and the expected LLM
   spend (expected **$0** for code; re-warming the demo cache after UI changes is the only spend,
   estimate it with `--dry-run` and stay under the project cap).
5. Add M12 to `frontend/src/content/milestones.ts` with the criteria below and run `make roadmap`.
6. Record the presentation rules as **ADR-0015 "Presenting uncertainty in the UI"** (the «از» rule,
   rounding direction, the range rule, the fee caveat once, observation age wording). It extends
   ADR-0007 to presentation.

## Shared foundations (first, inside wave 1)

- Number and range formatting in one pure module with table-driven tests: Persian digits, «٬» and
  «٫», short money, rounding direction by bound type, the range rule of
  `copy-and-numbers.md` §3. No component formats numbers on its own.
- Copy strings for the vocabulary in `copy-and-numbers.md` §1 in one place, so the E2E suite can
  assert forbidden words.
- Design tokens (colour, type scale, spacing, radii, shadow) in one place; components use tokens
  only. Starting point: `research-ux.md` §4.8, corrected by `decisions.md` R3 and Q3.

## Wave 1: essential for the video

| # | Change | Acceptance criterion (testable) |
|---|---|---|
| 1.1 | Formatting module and vocabulary | Unit tests ≥ 40 table-driven cases (digits, separators, short money, lower bound rounds down, upper bound rounds up, narrow vs wide range). E2E: no Latin digit inside Persian text nodes on `/`, `/search`, `/villas/<demo>`; none of the forbidden strings «حداقل»، «قیمت نهایی»، «پر یا بسته»، «رزرو شده»، «۱۰۰/۰٪»، «هر نفر نفری» appears. |
| 1.2 | Split view search with price pins | At 1440×900 and 1536×864 the map and the **first full result card** are visible without scrolling. Hovering card n highlights pin n (and the reverse) within 100 ms. Pins never show a point more precise than the stored approximate location (the circle is drawn on hover/selection). |
| 1.3 | Intent chips and budget chip | Nothing between the chip bar and the first card is taller than 80 px. The yellow disambiguation box is gone. Flipping the budget chip updates results without a full page reload and keeps the other chips. |
| 1.4 | Result card | Every two-platform card shows «از X» and «در ۲ پلتفرم» plus an offer row with both platforms, the cheaper marked «ارزان‌تر». Single-platform cards show «در جاباما» or «در شب» and no offer row. The word «کارمزد» appears exactly once on `/search` (the line under the results header). Only the first card carries «بهترین تطابق». Results header counts «ویلا», not «آگهی». |
| 1.5 | LLM explanation in the first card | No separate «چرا گزینه‌ی اول؟» box above results. On cached demo paths the first token appears within 1.5 s of the card rendering; uncached shows a skeleton line. Verifier and fallback unchanged (existing tests stay green). |
| 1.6 | Villa page booking card | Date range and guests are editable in the card and initialised from the search URL. Changing them re-quotes both rows from stored observations. Cheaper row first. Each row shows its own price, its age («قیمتِ N روز پیش» when stale under the existing 24 h rule) and «دیدن در … ↗». The fee caveat appears exactly once on the page. States covered by E2E: two platforms, one platform, stale, unavailable on one. |
| 1.7 | Gallery dedup | No two photos in the gallery have a perceptual-hash distance below the display threshold (unit test on a fixture villa with a known duplicate; E2E on the demo villa). Layout 1+4 with «+N عکس». |
| 1.8 | Two-platform Jalali calendar | Weeks start on Saturday. Each day has a top (jabama) and bottom (shab) half. Available, unavailable, not observed and hidden night are distinguishable in a grayscale screenshot (pattern + outline). Keyboard: arrows move days (RTL-aware), Enter selects a range, the booking card updates. Screen reader label per day includes both platforms' states and ages. The hidden-nights line is absent when the count is 0. |
| 1.9 | «چرا مطمئنیم؟» match evidence | Opened from the header badge. Shows ≥ 3 shared photo pairs when the pair has them (fewer: shows what exists, never padding), 2 to 3 recorded non-photo evidence lines, and the decision trail (rules / judge / human). Every item maps to a stored ER evidence record (test). The technical ER paragraph is no longer at the top of the page. |

**Checkpoint after wave 1:** report with before/after screenshots in `docs/ux/screenshots/after/`
(git-ignored) for the three video scenes at 1536×864, the E2E and axe results, LLM spend from the
ledger, and the demo villa chosen by the rule in `decisions.md` D8.4. Commit, then continue.

## Wave 2: important

| # | Change | Acceptance criterion |
|---|---|---|
| 2.1 | Evidence-backed highlights on the villa page | 3 to 5 highlights, each with an icon, one line and its source label («در عکس‌ها دیده شد»، «روی نقشه تأیید شد»). Only verified facts become highlights. The truth-check progress bar is removed; the full list below is grouped تأیید شد / تأیید نشد / با نقشه نمی‌خواند and the blur note appears once per group. |
| 2.2 | Sticky anchor navigation | Active section highlighted on scroll; clicking moves focus to the section heading. |
| 2.3 | Specs | Agreed fields as one icon line; a two-column table only for fields that differ, labelled «دو عدد متفاوت»; card shows the area as a range. |
| 2.4 | Review citations | Each summary point has one count chip; clicking it filters the review list to the cited reviews; points supported by fewer than 2 reviews are not shown. Rating line shows both «امتیاز» and «نظر» counts. |
| 2.5 | Home | No stats cards, principles or dark docs box. The merged-villas grid sits directly under the hero, each card with the platform price gap. One proof strip linking to `/metrics`; footer link «برای داوران». Every number on the home page comes from an artifact or `/metrics` (existing docs rule). |
| 2.6 | Scenario matrix and drawers | «قیمت‌های نمونه» drawer closed on load; «کنار گذاشته شد» drawer on search; no empty histogram buckets. |
| 2.7 | Tokens and contrast | All text/background pairs ≥ 4.5:1 (axe); amber and red used only where `copy-and-numbers.md` §4 allows (lint-style test on the token usage if practical, otherwise a review checklist in the report). |
| 2.8 | Demo script | `docs/demo-script.md` updated to the new UI paths and vocabulary («ناموجود» not «پر»؛ «از» not «حداقل»), every number still naming its report. |

**Checkpoint after wave 2:** report, commit, continue.

## Wave 3: nice to have

| # | Change | Acceptance criterion |
|---|---|---|
| 3.1 | Mobile search | At 390×844 a floating «نقشه» button is always visible; returning from the map restores the list scroll position and filters. |
| 3.2 | «جست‌وجو در همین محدوده» | Moving the map shows the button; clicking adds a «محدوده‌ی نقشه» chip that can be removed like any other. |
| 3.3 | Mobile villa page | Booking card becomes a bottom bar with the cheaper price and «مقایسه‌ی پیشنهادها». |
| 3.4 | Copy and motion polish | No detached «می » or « ها» (ZWNJ check over rendered text); with `prefers-reduced-motion` no animation longer than 200 ms. |

**Checkpoint after wave 3:** report, commit, then the public release.

## Tests and evidence

- Unit (Vitest): formatting module, range rule, gallery dedup selection, calendar state mapping,
  match-evidence mapping to ER records.
- E2E (Playwright, existing suite extended): the criteria above on the demo paths, axe with no
  critical violations, keyboard paths for chips, calendar and booking card, forbidden-strings check,
  above-the-fold checks at 1440×900 and 1536×864.
- Visual evidence: before/after screenshots per wave in `docs/ux/screenshots/after/` (git-ignored),
  named by page and viewport. Reports describe them in words; they are not committed.
- Existing suites (`make test`, `make lint`, `make test-e2e`) stay green; provenance clicks still
  work for every number that keeps a source card.

## Out of scope for M12

New platforms, new data, booking, price history, price alerts, image search, host profiles,
learning-to-rank changes, any change to ER, pricing or truth-check logic. If a UI need seems to
require new data, drop that part, keep the rest of the change, and record it in the wave report.

## Final step: public release

After the wave-3 checkpoint, follow `docs/release/public-release.md` exactly. It is the last task of
M12; the milestone is done when the repository is public (or, if publishing is impossible from this
machine, when everything is ready and the report gives the one command left).

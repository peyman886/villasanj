# ADR-0007 — Provenance everywhere; LLMs never write numbers

Status: Proposed · Date: 2026-10-01

## Context

The product's value is **trust** («همه‌ی حقیقت»). The inviolable rule is: *no fabricated number; every
price and claim has a source and a timestamp; unknown components are shown as ranges; LLM output is
generated only from existing fields and is verified.* LLMs are good at Persian prose and bad at
faithfully copying numbers, doing date arithmetic in the Jalali calendar, and resisting plausible
embellishment.

## Decision

1. **Provenance is a type.** Every user-visible observed value is a `Sourced[T]` carrying
   `Provenance(source, snapshot_id, observed_at, method)`. Derived values (`method=DERIVED`) reference
   their inputs' provenance. An API DTO without provenance cannot be constructed (enforced by a
   property test).
2. **Ranges, not guesses.** Money is `MoneyRange`. A missing component with a known bound (e.g. a
   platform's published fee range) yields a bounded range. A missing component with **no** source yields
   an **open upper bound** (`≥ X`), and the UI says what is unknown. We never invent a cap.
3. **Research-report figures are not product data.** Commission and fee percentages from the research
   report are secondary and some are unsourced. They inform design only. Product fee policies must be
   sourced from the platform itself (observed checkout breakdowns where public, or the platform's own
   published pages), each with a snapshot id.
4. **Slot-based generation.** For explanations and summaries the LLM receives a list of `Fact`s with IDs
   and writes text containing **slots** (`{F3}`), never digits. A deterministic renderer fills slots with
   formatted values and provenance links. Comparative statements ("ارزان‌تر") are only allowed when a
   precomputed comparative fact exists.
5. **Deterministic verifier** (runs on every generated text):
   - no Persian, Arabic or Latin digits outside slots;
   - every slot id exists in the provided fact set;
   - comparative words match the comparative facts' direction;
   - review-summary points cite ≥ 1 existing review id of that villa; points with a single supporting
     review are labelled as a single opinion;
   - extracted claim spans are verbatim substrings of the source text (after normalization).
   On failure: one retry with the verifier's error, then a **deterministic template fallback**. The
   fallback rate is a tracked metric.
6. **Dates are resolved by code.** Query understanding returns relative date expressions
   (`next_weekend`, `jalali(1405-08-01..03)`). A deterministic resolver with a Jalali + official-holiday
   table produces concrete `DateRange`s. Numbers in the parsed intent (guests, budget) must appear in
   the query text after normalization, or be flagged as inferred and shown as an editable chip.
7. **Observations, not states.** Availability and prices are shown with their observation age
   («۳ ساعت پیش مشاهده شد»). Stale observations (default > 24 h) are flagged.
8. **Truth-check tone.** Verdicts never accuse. `CONTRADICTED` requires best-case evidence to
   contradict the claim; UI copy uses «تأیید نشد» / «با شواهد موجود جور درنمی‌آید» and shows the
   evidence. Obfuscated coordinates always produce distance **ranges**.

## Alternatives considered

- **Free-form LLM text + post-hoc fact checking by another LLM.** More expensive and still
  probabilistic. Slots make the dominant failure (wrong number) structurally impossible.
- **Hide unknowns and show the lowest price ("شروع از").** This is exactly the market's UX failure the
  product exists to fix.

## Consequences

- (+) Every number in the demo can be clicked back to a snapshot.
- (+) The verifier is cheap, deterministic and unit-testable.
- (−) Prose is a little less fluid because of the slots. This is accepted, and template fallbacks keep
  the UI usable when generation fails.

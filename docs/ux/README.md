# UX redesign (M12): start here

The engine, data, ER, pricing and truth check are done and measured. This milestone changes **how the
product looks and reads**, not what it computes. Nothing here relaxes a product rule in `CLAUDE.md`.

Today the product reads like an audit report: every fact, warning and source is shown at the same
volume. The goal is a product a traveller would choose and a Torob reviewer would remember, with the
same honesty one click away instead of on every line.

## Reading order

1. [`brief.md`](brief.md): goal, audience, the one principle, design direction, target per page.
2. [`current-ui-audit.md`](current-ui-audit.md): what is wrong today, screen by screen, from the
   owner's screenshots (including bugs and wording errors to fix).
3. [`copy-and-numbers.md`](copy-and-numbers.md): one vocabulary for UI copy, number and range
   formatting rules, visual guardrails.
4. [`decisions.md`](decisions.md): what is decided, where the research is corrected or overridden,
   and the questions only the owner can answer.
5. [`M12-plan.md`](M12-plan.md): scope, waves, acceptance criteria, tests and stop points.
6. [`../release/public-release.md`](../release/public-release.md): the last step of M12, making the
   repository public safely.
7. [`research-ux.md`](research-ux.md): the deep-research report (Persian). Evidence, page-by-page
   critique, design specification, tokens, microcopy, video scenes. **The owner saves it here under
   this name.** Use it for *why*; use the files above for *what*.

## Source of truth when documents disagree

1. Product rules and the working agreement in `CLAUDE.md`. Never overridden by a UX document.
2. `decisions.md`.
3. `M12-plan.md`, then `copy-and-numbers.md`, then `brief.md`.
4. `research-ux.md`.

If a research recommendation conflicts with a product rule, the rule wins; record the conflict in
`decisions.md`.

**M12 runs without questions to the owner.** Every open point already has a decision in
`decisions.md`. When something new comes up, choose the option most consistent with the product
rules and this folder, record it in `docs/ARCHITECTURE.md` §10 (assumptions) and in the wave report,
and continue.

## Reference material

- `docs/ux/screenshots/`: screenshots of the current app (`current/`) and of the redesign
  (`after/`). **Git-ignored:** they contain listing photos and review text from jabama and shab,
  which are third-party content and must not be in the public repository.
- `docs/ux/references/`: screenshots of HomeToGo, jabama and other third-party sites
  (**git-ignored**, like `challenge.html`).
- Live references you may open in the owner's browser (playwright-cli skill first, per the owner's
  tooling preferences):
  - HomeToGo search: <https://www.hometogo.co.uk/> (search a UK region with dates and guests).
  - HomeToGo listing: <https://www.hometogo.co.uk/rental/ff49c41a64801134?duration=7&arrival=2026-11-05&persons=3&adults=3>
  - jabama listing: <https://www.jabama.com/stay/villa-431060>
  - Torob: any product page on <https://torob.com/> (the two-line "از X / در N فروشگاه" card and the
    seller list sorted by price).

### Rules for opening third-party sites

- **Design reference only.** Do not extract listings, prices or reviews into the catalog, fixtures
  or reports; data collection belongs to the crawler under ADR-0008.
- A handful of page views per site at human pace. No loops, no pagination sweeps.
- Screenshots go to `docs/ux/references/` (git-ignored). Never commit third-party content.
- Roles of the references: **HomeToGo** = visual language and interaction. **Torob** = price display
  ("از X در N"). **Iranian villa sites** = only the conventions users already know (Jalali calendar,
  toman, "شروع از", extra guests, instant booking), not aesthetics. **Airbnb / Google Hotels /
  Google Flights** = specific patterns named in `brief.md`.

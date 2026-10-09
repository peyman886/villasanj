# Public release (2026-10-09)

The last step of M12, following `docs/release/public-release.md`.

- **Repository:** https://github.com/peyman886/villasanj (visibility PUBLIC, default branch `main`)
- **Tag:** `v1.0.0`, "Villasanj v1.0.0: Torob AI Product Engineer challenge submission (M0–M12)"
- **History:** published in full (165 commits), not rewritten: no check found anything in history
  that the release rule says to remove.
- **Size:** 1.59 MiB packed; no tracked file over 1 MB in any commit.
- **Topics:** entity-resolution, information-retrieval, nlp, persian, llm, nextjs, fastapi,
  postgis, maplibre, price-comparison, vacation-rentals (each matches the stack).
- **LLM ledger at release:** $12.76 of the $30 cap.

## Audit (counts and paths only)

| # | Check | Result |
|---|---|---|
| A1 | Secrets in history and tree | gitleaks 8.30.1 over all commits and over a fresh clone's tree: 1 finding, a deliberately fake key in `backend/tests/unit/shared/infrastructure/test_avalai_provider.py` (starts with "test", 40 characters; compared with `.env`: not a real value). Recorded in `.gitleaksignore`; both scans then report 0. The real `AVALAI_API_KEY` value occurs 0 times in the history's diffs. No key rotation is needed on account of the repository. |
| A2 | `.env` files | `.env` was never tracked in any commit. `.env.example` now lists every key without a value (its four non-secret defaults moved into comments); settings treat an empty value as "left out" (tested). |
| A3 | Third-party content | No path under `var/` or `data/`, no `challenge.html`, no screenshot folder, no image, dump, map extract or model file in any commit. `.gitignore` covers `.env*`, `var/`, `data/`, `challenge.html`, `docs/ux/screenshots/`, `docs/ux/references/`. |
| A4 | Personal data | Tracked files: 0 phone numbers (2 regex hits are hashes in `backend/uv.lock`), 0 e-mail addresses other than `example.test` test values, 0 occurrences of the `CRAWL__CONTACT` value; history diffs: the same. Fixtures carry no host or reviewer names. Note: commit metadata carries the owner's own Git author name and e-mail (as configured in Git); kept, since they are the owner's authorship and not content. |
| A5 | Full third-party texts | Fixture reviews and descriptions are synthetic («نظر آزمایشی…», «توضیحات مصنوعی برای تست…»). The only Persian passages over 15 words in fixtures are platform boilerplate (a cancellation policy, a pricing note); eval sets hold our own queries. Listing titles in reports are a few words. |
| A6 | File sizes | Largest blob in history < 1 MB; repository 1.59 MiB. |
| A7 | Clean clone | `git clone` into a temporary folder, `uv sync`, `npm ci`, no `.env`, no data: `make test` green (backend 851, Vitest 140). |
| A8 | Lint and tests in the working copy | `make lint` and `make test` green before the tag. On the rebuilt stack the quality report is green too (`reports/quality-2026-10-09.json`: unit 849, integration 41, Vitest 140, E2E 87, smoke 2; E2E grew to 89 with the dark-mode and polish suites). |

## Front matter

`LICENSE` (MIT, Peyman Naseri, the Git author name of every commit; `git config user.name` itself
is unset in this checkout), a public section at the top of `README.md` (the two-line pitch, three
measured bullets with their reports, the challenge, "built with an AI coding agent", data and
licences, that `make demo` needs an unpublished local bundle), the repository description and
topics.

## What the owner may want to do

- Nothing is required. `gh` was logged in, so no command was left for the owner.
- Optional before recording: the 5-second calendar test with three people (decisions.md D4).

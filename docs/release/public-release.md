# Public release (last step of M12)

Goal: the repository is public on GitHub, safe to read by anyone, and makes a good first impression
on a Torob reviewer. The owner asked for **no questions**: every choice below is already made. If a
check fails, fix it with the rule given here; never publish with a failing check.

## 1. Pre-publication audit (all must pass)

Run each check, write the result into `reports/public-release-<date>.md` (counts and file paths only,
never secret values), and fix failures before continuing.

| # | Check | Pass condition | If it fails |
|---|---|---|---|
| A1 | Secrets in the **whole history** and the working tree (`gitleaks` over all commits, plus a search for the AvalAI key prefix and `.env` ever being tracked) | 0 findings | See §2 (history). Also write in the report that the owner should rotate the AvalAI key. Never print the value. |
| A2 | `.env` and any `*.env` except `.env.example` | Never tracked in any commit; `.env.example` has no values | §2 |
| A3 | Third-party content tracked: crawled snapshots, raw platform HTML/JSON outside trimmed fixtures, listing photos, `var/`, `data/` (demo bundle, audit, basemap downloads), `challenge.html`, `docs/ux/screenshots/`, `docs/ux/references/` | None tracked now or in history | Add to `.gitignore`, `git rm --cached`; for history see §2 |
| A4 | Personal data in tracked files (fixtures, reports, eval sets, docs): host names, reviewer names, phone numbers (`09\d{9}` and `+98` forms), e-mail addresses other than a deliberate public contact, exact addresses. Also search for the value of `CRAWL__CONTACT` by loading it from `.env` inside the command and printing **only the match count**. | 0 matches | Scrub (replace with neutral placeholders such as «میزبان»), regenerate the affected report from data if it is generated, commit as `fix(privacy): …` |
| A5 | Full third-party texts in tracked files: complete review texts or complete listing descriptions | None. Short claim phrases (≤ 15 words) in eval sets are allowed, with the listing id. | Trim to the claim phrase or remove the text and keep the id |
| A6 | File sizes | No tracked file > 5 MB; total repository size reported | Remove from tracking; for history see §2 |
| A7 | Clean-clone check: clone the repo into a temporary folder and run `make test` there (no network, no Docker needed) | Green | Fix and recommit |
| A8 | `make lint` and `make test` in the working copy | Green | Fix first |

`.gitignore` must contain at least: `.env`, `var/`, `data/` (or its generated subfolders),
`challenge.html`, `docs/ux/screenshots/`, `docs/ux/references/`, the snapshot and photo stores, and
any local LLM cache dump.

## 2. History rule

- **Default: publish the full history.** The milestone-by-milestone Conventional Commits are part of
  the story ("built with an AI coding agent, milestone by milestone, with acceptance criteria").
- If A1, A2, A3 or A6 finds something **in history**: rewrite history on a copy with
  `git filter-repo` (remove the offending paths, or replace secret strings), rerun every check on
  the rewritten copy, and publish that.
- If `git filter-repo` is not available or the rewrite still fails a check: publish a **fresh
  history** with one commit (`feat: Villasanj, Torob for villas (public release)`) and keep the old
  history only locally (a `backup/pre-public` branch that is never pushed). Say so in the report.
- Never use `--force` against an existing public remote. The remote is created new in §4.

## 3. Repository front matter

1. **Licence:** add `LICENSE` with the MIT licence for the source code, copyright holder = the
   owner's name as written in the git author config (read from `git config user.name`).
2. **README.md (public-facing top section, above the existing content):**
   - One line in Persian and one in English: «ویلاسنج: یک ویلا، همه‌ی حقیقت» / "Torob for villas:
     one real villa, every platform's offer, every claim checked."
   - Three short bullets: entity resolution across jabama and shab (precision with CI from the
     latest ER report), all-in prices per platform with provenance, truth check against
     OpenStreetMap. Numbers only from generated reports, with the report linked.
   - "Built for Torob's AI Product Engineer challenge" and "Demo video: link in the submission".
   - "Built with an AI coding agent, milestone by milestone": link to `docs/ROADMAP.md` and the ADRs.
   - **Data and licences:** no crawled data, photos or reviews are in this repository; a fresh clone
     has an empty catalog (crawl politely per ADR-0008 or use your own snapshots). Map data ©
     OpenStreetMap contributors (ODbL). Vazirmatn under SIL OFL. jabama and shab are trademarks of
     their owners; this project is not affiliated with them.
   - Keep the existing quick start, but state plainly that `make demo` needs a local data bundle
     that is not published.
3. **Repository description:** «ترب برای ویلا · Torob-style comparison for Iranian villa rentals:
   cross-platform entity resolution, all-in prices with provenance, claim truth-check.»
4. **Topics:** `entity-resolution`, `information-retrieval`, `nlp`, `persian`, `llm`, `nextjs`,
   `fastapi`, `postgis`, `maplibre`, `price-comparison`, `vacation-rentals`. Use only topics that
   match the actual stack (check `backend/pyproject.toml` and `frontend/package.json`).

## 4. Commit, tag, publish

1. Commit the front matter: `docs(release): add licence, public README and data notice`.
2. Make sure the working tree is clean and on the main branch.
3. Annotated tag: `v1.0.0` with message "Villasanj v1.0.0: Torob AI Product Engineer challenge
   submission (M0–M12)".
4. Create and push the public repository with the GitHub CLI:
   `gh repo create villasanj --public --source . --remote origin --push --description "<§3.3>"`,
   then `git push origin v1.0.0` and add the topics with `gh repo edit --add-topic`.
   If the name `villasanj` is taken on the account, use `villasanj-torob`.
5. Verify with `gh repo view` that visibility is PUBLIC and the default branch and the tag exist,
   and that the README is served (fetch it via `gh api`).
6. If `gh` is missing or not authenticated: do **not** look for tokens or create one. Finish
   everything else, and end the report with the exact commands the owner must run (install/login
   and the `gh repo create … --push` line). That is the only owner action allowed in M12.

## 5. Final report

`reports/public-release-<date>.md`: audit table (A1–A8 with counts), history decision (full,
rewritten or fresh, and why), repository URL, tag, size, and the reminder about key rotation if A1
ever found a key in history. Update `CLAUDE.md` status and the roadmap (`make roadmap`), commit
`docs: record public release`, push.

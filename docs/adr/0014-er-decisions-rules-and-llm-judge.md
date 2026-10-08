# ADR-0014 — Entity resolution decisions: the rule score, an LLM judge in a score zone, the owner's labels

Status: Accepted (2026-10-03) · Refines ADR-0009 stages 3–6 · Replaces the "Splink model" of
ROADMAP M5 · Reproduce with `er judge-eval`, `er judge-zone`, `er villas`, `er villas-eval`

## Context

- M3 measured the transparent rule score against the owner's 362 labelled pairs (gold-v1): at the
  threshold −0.25 chosen by ADR-0009's rule, precision **98.1%** (Wilson 93.0–99.5%) and recall
  **67.1%** (44.6–83.8%), weighted by stratum. Precision already met M5's bar; recall did not.
- Two of the three missed matches (score −1.5, geo band) share no photo among the five coverage
  photos of each listing; their evidence is "location overlaps, same bedrooms, area or capacity
  differs". In the same stratum, 5 labelled non-matches have exactly that evidence and 4 more score
  higher (−0.5: close, same bedrooms, no shared photo), so no threshold separates them. The third
  miss (−1.0) shares photos but differs in price, capacity and area. The two false matches (1.56 and
  1.75) share a location, the same bedrooms and low-weight (common) photos.
- The H5 ablation (`er ablations`): photo evidence alone never reaches the precision bar (best F1
  0.56 at 50% precision: units of a complex share photos), the other evidence alone neither (15%),
  the two together do.
- ROADMAP M5 planned a Splink model. Splink fits Fellegi–Sunter weights for comparisons of record
  attributes; our strongest evidence is pair-level (a one-to-one photo matching weighted by
  document frequency), and the pairs we miss cannot be separated by re-weighting the same
  evidence: a model that merges "close, same bedrooms, no shared photo" merges the non-matches
  above with them.

## Decision

1. **No Splink.** The rule score stays the first decider; its threshold comes from the gold set.
2. **An LLM judge decides a score zone.** It sees both listings' photo grids and structured facts
   (ADR-0009 stage 4, prompt `er_judge` v1) and answers match / non_match / unsure with a
   confidence. Bake-off on the 142 gold pairs scored −3 to 3, each model alone (`er judge-eval`):

   | Model | False matches | Recall (weighted) | Unsure | Cost / 142 | p95 |
   |---|---|---|---|---|---|
   | **gemini-3.8-flash** (chosen) | 0 | 93.8% | 1.4% | $0.32 | 34 s |
   | gpt-5.4-mini (fallback) | 0 | 79.8% | 1.4% | $0.31 | 5.5 s |
   | gemini-3.5-flash | 1 | 94.4% | 0.7% | $0.79 | 31 s |

   gemini-3.8-flash merges neither rule false match (one "non_match" at 1.0, one "unsure" at 0.85,
   which waits for a human). Latency does not matter in a batch job.
3. **The zone is [−2, 3).** Every cross-platform match the rules miss scores in [−2, −0.25)
   (none among the 110 labelled cross-platform pairs below −2), and both false matches are inside
   it. In the zone a confident "match" (≥ 0.8) merges, a confident "non_match" vetoes even a
   rule match, and "unsure" or any verdict below 0.8 waits for a human without merging. Above 3
   the rules merge; below −2 nothing merges. About 2,900 candidate pairs, run once
   (`er judge-zone`) and cached. The operating point lives in `config/er.toml`.
4. **Waiting pairs go to a human queue.** `er villas` appends them to the `er-human` label queue
   (append-only: running again adds nothing, labelled pairs stay as history), and a label there
   rebuilds the villas after the API responds (one rebuild at a time). A rebuild with the same
   labels yields the same villas and ids (M5 criterion 7).
5. **The owner's labels win.** A "same villa" label is a must-link, a "not the same villa" label a
   cannot-link no machine decision overrides. Clustering is greedy, strongest first, at most one
   listing per platform (product rule 4, also a unique index); refused merges are reported.
6. **Evaluation stays honest.** The policy is scored end to end on the gold set with the labels
   *not* applied (`er villas-eval`: weighted pairwise precision and recall, plus B-cubed). The judge
   was chosen on these same gold pairs, so the end-to-end numbers are optimistic by however much
   that choice fits them; a gold-v2 sample from the new villas is the clean test.

## Consequences

- (+) Recall can rise without losing precision: the judge sees the photos the rule score only
  hashes, including rooms the hashes cannot align.
- (+) Every merge is traceable to a decider (rule, judge, human) and the judge's rationale is stored.
- (−) A full zone run cost $9.58 for 2,885 pairs (2,989 calls, about $0.0034 a judged pair,
  75 minutes at four at a time); new candidates are judged incrementally.
- (−) The judge still sees only the five coverage photos of each listing; where they show
  different rooms it says "unsure", and those pairs wait for a human.
- (−) The same-platform pairs the owner labelled "same villa" are units of one complex with shared
  photos (ROADMAP M3 results); the judge's prompt treats shared areas alone as "unsure", which is
  the protocol's reading.


## Amendment (end-to-end evaluation, 2026-10-03): the judge is advisory until labels can verify it

`er judge-zone` judged 2,885 production candidates in [−2, 3) (1 failed): below the threshold
86 confident matches, 2,277 non-matches, 190 unsure; at or above it 189 matches, 87 non-matches
(vetoes of rule matches), 23 unsure. The three gold matches the rules miss got confident matches
(0.95–0.99). End to end on gold-v1 (`reports/er-eval-2026-10-03.md`, labels not applied):

| Policy | Precision (95% CI) | Recall | Bar |
|---|---|---|---|
| rules alone at −0.25 | 98.1% (93.0–99.5%) | 67.1% | yes |
| judge merges and vetoes in [−2, 3) | 100.0% (81.6–100%) | 94.8% | **no** |
| judge merges, no vetoes | 98.7% (81.3–99.9%) | 100.0% | no |
| judge in [−0.25, 3) only | 100.0% (96.0–100%) | 61.9% | yes |

Two findings decide it:

1. **Judge merges below the threshold cannot be verified yet.** They sit in the geo band, where
   gold-v1 has 30 labelled pairs, each standing for about 84 candidates, and only 2–3 of them are
   matches. With no error observed the interval is still 81.6–100%: the effective sample is too
   small to show 92%. The band holds about 2,300 non-matching candidates, so a false-merge rate
   of only 1% would mean about 23 wrong merges among the judge's 86.
2. **Its vetoes contradict the owner's labels on units of one complex.** Five of the seven
   labelled pairs the judge vetoes are labelled "same villa"; in each the judge names different
   unit numbers in one complex («واحد ۲» / «واحد ۴», cottage 1 / cottage 2), the same pattern as the
   41 same-platform labels in the M3 results. The labelling protocol's rule 2 marks such pairs N or
   U, so whether the judge or the labels are right is the owner's call.

Decision: following the rule of ADR-0009 (the highest recall that clears the bar),
`config/er.toml` sets `judge_merges = false` and `judge_vetoes = false`. The machine merges are
the rules' (98.1%, 67.1%); the judge orders the human queue `er-human`: 83 suggested matches
first, then 81 disputes of rule matches, then 212 unsure, most confident first. A confirmed
suggestion is a must-link, so recall rises only with human-verified precision. Turning the judge's
merges on needs either more labels in the geo band (the queue's own labels serve) or a gold-v2
sample there; re-run `er report` and flip the flags when a policy with the judge clears the bar.
If the owner relabels the complex-unit pairs as different villas, the vetoing policies gain and
the rules lose precision, so the same report decides again.

`expected_output_tokens` for `er_judge` is now 340 (mean of the production run; the bake-off's
173 underestimated the zone run by about a third).


## Amendment (label revision, 2026-10-04): the judge vetoes, a human merges

The owner confirmed the finding above: pairs of different units of one complex had been labelled
"same villa" by mistake. Under the protocol's rule 2 they are N, or U when the listings cannot tell
which unit is which. `eval/labels/gold-v1-revisions-2026-10-04.toml` lists the 48 revised labels
with a reason each (41 same-platform: 38 → N, 3 → U; 7 cross-platform: 4 → N, 3 → U); `er
revise-labels` applied them, and `er.label_revision` keeps every original decision. The owner's own
U labels were not touched. `reports/er-eval-2026-10-04.md` scores every policy on both versions of
the labels:

| Policy (revised labels) | Precision (95% CI) | Recall | Bar |
|---|---|---|---|
| rules alone at −0.25 | 91.9% (84.7–95.9%) | 65.0% | no |
| rules alone at 2 (what the gold set now picks for the rules) | 100% (95.1–100%) | 33.2% | yes |
| advisory judge (the 2026-10-03 policy) | 91.9% (84.7–95.9%) | 65.0% | no |
| **judge vetoes, a human merges** | **100% (95.9–100%)** | **65.0%** | **yes** |
| judge merges and vetoes | 100% (81.4–100%) | 100% | no |

The rules' new false merges are exactly the complex units, and the judge vetoes all of them
without losing a true match on gold. By ADR-0009's rule (the highest recall that clears the bar)
`config/er.toml` now sets `judge_vetoes = true` (merges stay off: below the threshold the gold set
still has too few labels to show the judge's precision). The canonical villas went from 3,267 (321
on both platforms) to 3,283 (305); H1–H3 follow the policy (`reports/hypotheses-2026-10-04.md`).
The bake-off, re-scored from the cache on the revised labels, separates the models further
(ADR-0005). Decision 2's "merges neither rule false match" is superseded: the judge is now the
precision guard of the rules.


## Amendment (the human queue labelled, 2026-10-08)

The owner labelled all 376 pairs of `er-human` (74 same villa, 263 not, 39 unsure; where photos
were missing the owner chose unsure or not, and opened listings on the platforms to tell units of
one property apart). `reports/er-eval-2026-10-08.md`, section "The human queue against the judge":

| Why queued | Same villa | Not the same | Unsure |
|---|---|---|---|
| judge suggested a match below the threshold | 70 | 2 | 11 |
| judge vetoed a rule match | 1 | 77 | 3 |
| judge unsure | 3 | 184 | 25 |

The judge's suggested matches were confirmed in 70 of 72 decided pairs (97.2%, Wilson 90.4–99.2%)
and its vetoes in 77 of 78 (98.7%, 93.1–99.8%). These are the judge's own pairs, not a random
sample, so they measure its calls in the zone, not the matcher's precision. The suggestions'
lower bound is still under 92%, so `judge_merges` stays off for new candidates; every pair the
judge suggested is decided by the owner anyway. With the labels as must-links the catalog has 3,211
villas, 377 on both platforms (was 305); the gold-v1 evaluation is unchanged.

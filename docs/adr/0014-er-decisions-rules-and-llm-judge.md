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
   it. In the zone a confident "match" (≥ 0.8) merges, a "non_match" vetoes even a rule match,
   and "unsure" waits for a human. Above 3 the rules merge; below −2 nothing merges. About 2,900
   candidate pairs, run once (`er judge-zone`) and cached.
4. **The owner's labels win.** A "same villa" label is a must-link, a "not the same villa" label a
   cannot-link no machine decision overrides. Clustering is greedy, strongest first, at most one
   listing per platform (product rule 4, also a unique index); refused merges are reported.
5. **Evaluation stays honest.** The policy is scored end to end on the gold set with the labels
   *not* applied (`er villas-eval`: weighted pairwise precision and recall, plus B-cubed). The judge
   was chosen on these same gold pairs, so the end-to-end numbers are optimistic by however much
   that choice fits them; a gold-v2 sample from the new villas is the clean test.

## Consequences

- (+) Recall can rise without losing precision: the judge sees the photos the rule score only
  hashes, including rooms the hashes cannot align.
- (+) Every merge is traceable to a decider (rule, judge, human) and the judge's rationale is stored.
- (−) A full zone run costs about $6.5 and hours of wall time; new candidates are judged
  incrementally.
- (−) The judge still sees only the five coverage photos of each listing; where they show
  different rooms it says "unsure", and those pairs wait for a human.
- (−) The same-platform pairs the owner labelled "same villa" are units of one complex with shared
  photos (ROADMAP M3 results); the judge's prompt treats shared areas alone as "unsure", which is
  the protocol's reading.

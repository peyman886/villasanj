# Relevance evaluation: relevance-v1

`uv run villasanj discovery relevance-eval --queue relevance-v1`: 11 of 30 queries fully judged by `owner` (381 judgements). Pooled: the shipped ranking's top 20 and each baseline's top 10, shown blind; unjudged villas count as not relevant. Recall@20 counts grades 1 and 2 as relevant.

| System | nDCG@10 | Recall@20 | Queries |
|---|---|---|---|
| ranking | 0.786 | 0.630 | 11 |
| price | 0.581 | 0.386 | 11 |
| rating | 0.581 | 0.362 | 11 |

Systems: `ranking` is the shipped order (confirmed requested features first, then 60% price per person and night, 40% Bayesian rating); `price` is cheapest first; `rating` is best rated first, over the same filtered villas.

Per query, nDCG@10 of the shipped ranking against each baseline:

- vs `price`: better on 9, equal on 0, worse on 2
- vs `rating`: better on 10, equal on 0, worse on 1

Caveats: the baselines' places 11-20 were not pooled, so their Recall@20 is a lower bound and nDCG@10 is the fair comparison. Grades given: 2: 178, 1: 157, 0: 46; most pooled villas fit the query, so the grades separate the orders less than a stricter scale would.

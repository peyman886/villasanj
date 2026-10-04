# Judge evaluation: gpt-5.4-mini

`uv run villasanj er judge-eval --low -3 --high 3` on gold `gold-v1` (labels of `owner`), band [-3, 3]: 141 pairs, 141 judged, unsure 1.4%, cost $0.0000 (0 when replayed from the cache; the first run's cost and latency are in ADR-0005).

| Label | Verdicts |
|---|---|
| match | {'match': 50, 'non_match': 19, 'unsure': 2} |
| non_match | {'match': 3, 'non_match': 67} |

| Match at confidence ≥ | Precision | Recall |
|---|---|---|
| 0.0 | 94.9% [62.7%, 99.5%] | 80.7% [52.2%, 94.1%] |
| 0.7 | 94.9% [62.7%, 99.5%] | 80.7% [52.2%, 94.1%] |
| 0.8 | 94.9% [62.7%, 99.5%] | 80.7% [52.2%, 94.1%] |
| 0.9 | 96.5% [64.1%, 99.8%] | 80.7% [52.2%, 94.1%] |

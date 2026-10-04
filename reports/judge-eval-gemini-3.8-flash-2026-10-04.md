# Judge evaluation: gemini-3.8-flash

`uv run villasanj er judge-eval --low -3 --high 3` on gold `gold-v1` (labels of `owner`), band [-3, 3]: 141 pairs, 141 judged, unsure 1.4%, cost $0.0000 (0 when replayed from the cache; the first run's cost and latency are in ADR-0005).

| Label | Verdicts |
|---|---|
| match | {'match': 71} |
| non_match | {'non_match': 68, 'unsure': 2} |

| Match at confidence ≥ | Precision | Recall |
|---|---|---|
| 0.0 | 100.0% [75.4%, 100.0%] | 100.0% [75.4%, 100.0%] |
| 0.7 | 100.0% [75.4%, 100.0%] | 100.0% [75.4%, 100.0%] |
| 0.8 | 100.0% [75.4%, 100.0%] | 100.0% [75.4%, 100.0%] |
| 0.9 | 100.0% [75.4%, 100.0%] | 100.0% [75.4%, 100.0%] |

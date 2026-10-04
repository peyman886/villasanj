# Judge evaluation: gemini-3.5-flash

`uv run villasanj er judge-eval --low -3 --high 3` on gold `gold-v1` (labels of `owner`), band [-3, 3]: 141 pairs, 141 judged, unsure 0.7%, cost $0.0000 (0 when replayed from the cache; the first run's cost and latency are in ADR-0005).

| Label | Verdicts |
|---|---|
| match | {'match': 70, 'unsure': 1} |
| non_match | {'match': 2, 'non_match': 68} |

| Match at confidence ≥ | Precision | Recall |
|---|---|---|
| 0.0 | 97.8% [72.7%, 99.9%] | 99.2% [74.2%, 100.0%] |
| 0.7 | 97.8% [72.7%, 99.9%] | 99.2% [74.2%, 100.0%] |
| 0.8 | 97.8% [72.7%, 99.9%] | 99.2% [74.2%, 100.0%] |
| 0.9 | 97.8% [72.7%, 99.9%] | 99.2% [74.2%, 100.0%] |

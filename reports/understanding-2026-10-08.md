# Query understanding evaluation

`uv run villasanj discovery eval-understanding ../eval/query-understanding/reviewed-v1.jsonl --fresh` on 50 cases (`reviewed-v1.jsonl`). Slots are compared one by one over the union of expected and predicted slots; invented numbers are counted on the final intents (target 0); latency uses uncached calls only.

| Measure | Value |
|---|---|
| Slot accuracy | 99.3% |
| Exact match | 98.0% |
| Invented numbers | 0 |
| Failed cases | 0 |
| Cost | $0.0671 |
| Latency gpt-5.4-mini | 50 uncached calls, p50 1345 ms, p95 2085 ms |

| Slot | Right / seen |
|---|---|
| bedrooms_min | 5/5 |
| budget.basis | 9/9 |
| budget.max_toman | 9/9 |
| dates.day | 4/4 |
| dates.kind | 28/28 |
| dates.month | 6/6 |
| dates.weekday | 4/4 |
| dates.which | 13/13 |
| dates.year | 3/3 |
| features | 16/17 |
| guests | 24/24 |
| max_drive.minutes | 2/2 |
| nights | 7/7 |
| places | 9/9 |

Cases with a wrong slot:

- حداکثر ۴۵ دقیقه تا ساحل با ماشین: features

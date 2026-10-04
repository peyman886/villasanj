# Performance report

Generated 2026-10-04 06:08 UTC against `http://127.0.0.1:8801` by `make perf-report`.

| Path | Samples | p50 ms | p95 ms | max ms | Target |
|---|---|---|---|---|---|
| villa + offers | 50 | 16.7 | 17.8 | 25.3 | 300.0 |
| listing + offer | 50 | 4.4 | 5.7 | 6.3 | 300.0 |
| search (cached understanding) | 10 | 2110.4 | 2169.1 | 2169.1 | - |

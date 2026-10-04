# Performance report

Generated 2026-10-04 07:01 UTC against `http://127.0.0.1:8800` by `make perf-report`.

| Path | Samples | p50 ms | p95 ms | max ms | Target |
|---|---|---|---|---|---|
| villa + offers | 50 | 8.5 | 10.4 | 33.6 | 300.0 |
| listing + offer | 50 | 3.3 | 4.4 | 7.9 | 300.0 |
| search (cached understanding) | 10 | 2095.5 | 2134.7 | 2134.7 | - |

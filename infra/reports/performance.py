"""reports/performance-<date>.json: API latency on the paths with a target (ROADMAP M7 crit. 5).

Measures against a running API (default http://127.0.0.1:8800, or API_URL) with the standard
library: villa + offers on sampled two-platform villas, listing + offer on sampled listings, and a
cached search. Usage: make perf-report
"""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = os.environ.get("API_URL", "http://127.0.0.1:8800").rstrip("/")
SAMPLE = 50
SEARCH = "ویلای استخردار در رامسر برای ۶ نفر آخر هفته بعد زیر ۲۰ میلیون"


def get(path: str) -> object:
    with urllib.request.urlopen(f"{API}{path}", timeout=60) as response:
        return json.loads(response.read())


def post(path: str, body: dict[str, object]) -> object:
    request = urllib.request.Request(
        f"{API}{path}", data=json.dumps(body).encode(), headers={"content-type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def summary(name: str, times: list[float], target: float | None) -> dict[str, object]:
    ordered = sorted(times)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return {
        "name": name,
        "samples": len(ordered),
        "p50_ms": round(statistics.median(ordered), 1),
        "p95_ms": round(p95, 1),
        "max_ms": round(ordered[-1], 1),
        "target_ms": target,
    }


def timed(fn) -> float:  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def main() -> int:
    scenario = get("/scenarios")[0]  # type: ignore[index]
    query = urllib.parse.urlencode(
        {"check_in": scenario["check_in"], "check_out": scenario["check_out"], "guests": 4}
    )
    villas = [v["villa_id"] for v in get(f"/villas/sample?n={SAMPLE}&seed=perf")]  # type: ignore[union-attr]
    listings = get(f"/listings/sample?n={SAMPLE}&seed=perf")
    measurements = [
        summary(
            "villa + offers",
            [
                timed(lambda v=v: (get(f"/villas/{v}"), get(f"/villas/{v}/offers?{query}")))
                for v in villas
            ],
            300.0,
        ),
        summary(
            "listing + offer",
            [
                timed(
                    lambda x=x: (
                        get(f"/listings/{x['platform']}/{x['external_id']}"),
                        get(f"/listings/{x['platform']}/{x['external_id']}/offer?{query}"),
                    )
                )
                for x in listings  # type: ignore[union-attr]
            ],
            300.0,
        ),
    ]
    post("/search", {"query": SEARCH, "explain": False})  # warm: the understanding is cached
    measurements.append(
        summary(
            "search (cached understanding)",
            [
                timed(lambda: post("/search", {"query": SEARCH, "explain": False}))
                for _ in range(10)
            ],
            None,
        )
    )
    now = datetime.now(UTC)
    artifact = {
        "version": 1,
        "kind": "performance",
        "command": "make perf-report",
        "generated_at": now.isoformat(),
        "provenance": {"api": API, "sample": SAMPLE, "scenario": scenario["slug"], "guests": 4},
        "data": {"measurements": measurements},
    }
    path = ROOT / "reports" / f"performance-{now:%Y-%m-%d}"
    path.with_suffix(".json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Performance report",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC against `{API}` by `make perf-report`.",
        "",
        "| Path | Samples | p50 ms | p95 ms | max ms | Target |",
        "|---|---|---|---|---|---|",
        *(
            f"| {m['name']} | {m['samples']} | {m['p50_ms']} | {m['p95_ms']} | {m['max_ms']} | {m['target_ms'] or '-'} |"
            for m in measurements
        ),
        "",
    ]
    path.with_suffix(".md").write_text("\n".join(lines))
    print(f"wrote {path}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

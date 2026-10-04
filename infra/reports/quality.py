"""reports/quality-<date>.json: every test suite's measured result, for the documentation portal.

Runs the suites the way `make test`, `make test-integration`, `make test-e2e` and `make test-smoke`
do, with machine-readable reporters, plus lint and the domain coverage. Standard library only.
Usage: make quality-report (or: cd backend && uv run python ../infra/reports/quality.py [--skip-e2e])   (E2E and smoke need the app running)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str, float]:
    start = time.monotonic()
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    return done.returncode, done.stdout + done.stderr, time.monotonic() - start


def junit(name: str, path: Path, seconds: float) -> dict[str, object]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    return {"name": name, "passed": total - failed - skipped, "failed": failed, "skipped": skipped, "seconds": round(seconds, 1)}


def playwright(name: str, report: dict[str, object], seconds: float) -> dict[str, object]:
    stats = report.get("stats", {})
    assert isinstance(stats, dict)
    return {
        "name": name,
        "passed": int(stats.get("expected", 0)),
        "failed": int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0)),
        "skipped": int(stats.get("skipped", 0)),
        "seconds": round(seconds, 1),
    }


def main() -> int:
    skip_e2e = "--skip-e2e" in sys.argv
    suites: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        code, _, secs = run(
            ["uv", "run", "pytest", "-q", "--cov", "--cov-report=", f"--junitxml={out / 'unit.xml'}"], BACKEND
        )
        suites.append(junit("backend: unit + architecture", out / "unit.xml", secs))
        for name, include in (("domain", "*/domain/*"), ("pricing domain", "*/pricing/domain/*"), ("all", "*")):
            _, text, _ = run(["uv", "run", "coverage", "report", f"--include={include}"], BACKEND)
            total = re.search(r"^TOTAL\s+.*?(\d+(?:\.\d+)?)%\s*$", text, re.M)
            if total:
                coverage.append({"name": name, "percent": float(total.group(1))})
        code, _, secs = run(["uv", "run", "pytest", "-m", "integration", "-q", f"--junitxml={out / 'int.xml'}"], BACKEND)
        suites.append(junit("backend: integration (Postgres)", out / "int.xml", secs))
        code, text, secs = run(["npx", "vitest", "run", "--reporter=json", f"--outputFile={out / 'vitest.json'}"], FRONTEND)
        report = json.loads((out / "vitest.json").read_text())
        suites.append(
            {
                "name": "frontend: unit",
                "passed": report["numPassedTests"],
                "failed": report["numFailedTests"],
                "skipped": report["numPendingTests"],
                "seconds": round(secs, 1),
            }
        )
        if not skip_e2e:
            for name, grep in (("E2E (Playwright, axe)", ["--grep-invert", "@smoke"]), ("smoke (sampled pages)", ["--grep", "@smoke"])):
                target = out / f"{name[:5]}.json"
                code, text, secs = run(
                    ["npx", "playwright", "test", *grep, "--reporter=json"],
                    FRONTEND,
                    {"PLAYWRIGHT_JSON_OUTPUT_NAME": str(target)},
                )
                suites.append(playwright(name, json.loads(target.read_text()), secs))
    lint_code, _, lint_secs = run(["make", "lint"], ROOT)
    commit = run(["git", "rev-parse", "--short", "HEAD"], ROOT)[1].strip()
    now = datetime.now(UTC)
    artifact = {
        "version": 1,
        "kind": "quality",
        "command": "make quality-report",
        "generated_at": now.isoformat(),
        "provenance": {"commit": commit, "e2e": not skip_e2e},
        "data": {"suites": suites, "coverage": coverage, "lint": {"ok": lint_code == 0, "seconds": round(lint_secs, 1)}},
    }
    path = ROOT / "reports" / f"quality-{now:%Y-%m-%d}"
    path.with_suffix(".json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Quality report",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC at commit `{commit}` by `make quality-report`.",
        "",
        "| Suite | Passed | Failed | Skipped | Seconds |",
        "|---|---|---|---|---|",
        *(f"| {s['name']} | {s['passed']} | {s['failed']} | {s['skipped']} | {s['seconds']} |" for s in suites),
        "",
        "| Coverage | Percent |",
        "|---|---|",
        *(f"| {c['name']} | {c['percent']}% |" for c in coverage),
        "",
        f"Lint (`make lint`): {'clean' if lint_code == 0 else 'FAILED'}.",
        "",
    ]
    path.with_suffix(".md").write_text("\n".join(lines))
    failed = sum(int(s["failed"]) for s in suites) + (lint_code != 0)
    print(f"wrote {path}.json; failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

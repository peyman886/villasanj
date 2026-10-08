"""Pick the demo villa by the rule in docs/ux/decisions.md D8.4 (M12), from the running API.

Rule: on two platforms; >= 3 hidden nights in the 30 nights from START; >= 1 spec field the two
listings state differently; >= 3 shared photo pairs in the recorded ER evidence; a cited review
summary; ties broken by the most reviews. If no villa meets every condition, relax in this order
and say so: hidden nights >= 1, then photo pairs >= 2, then no contradiction required.

Two conditions added in M12 wave 1 (recorded in docs/ARCHITECTURE.md §10): both platforms are
bookable for the demo stay (the demo search's dates and group, so the booking card shows two
prices and «ارزان‌تر»), and hidden nights are at most half the window (a platform closed for the
whole month makes every night "hidden", which hides the point of the scene).

Reads only (the review summary is asked for the few finalists, in rank order, and is cached).

    cd backend && uv run python ../scripts/pick_demo_villa.py [API_URL] [START]
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8801"
START = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
WINDOW = 30
DEMO_STAY = {"check_in": "2026-10-15", "check_out": "2026-10-17", "guests": 6}  # the demo query

STEPS = [  # (name, min hidden nights, min photo pairs, needs a contradiction)
    ("strict", 3, 3, True),
    ("hidden >= 1", 1, 3, True),
    ("photo pairs >= 2", 1, 2, True),
    ("no contradiction", 1, 2, False),
]


async def facts(client: httpx.AsyncClient, villa_id: str, limit: asyncio.Semaphore) -> dict:
    async with limit:
        end = START + timedelta(days=WINDOW)
        villa, calendar, match, reviews, offers = await asyncio.gather(
            client.get(f"/villas/{villa_id}"),
            client.get(f"/villas/{villa_id}/calendar", params={"start": START, "end": end}),
            client.get(f"/villas/{villa_id}/match"),
            client.get(f"/villas/{villa_id}/reviews"),
            client.get(f"/villas/{villa_id}/offers", params=DEMO_STAY),
        )
    pairs = match.json()
    return {
        "id": villa_id,
        "platforms": len(villa.json()["members"]),
        "hidden": sum(n["hidden"] for n in calendar.json()),
        "conflicts": [c["field"] for c in villa.json()["conflicts"]],
        "photo_pairs": max((len(p["photo_pairs"]) for p in pairs), default=0),
        "reviews": len(reviews.json()),
        "text_reviews": sum(bool(r["text"]) for r in reviews.json()),
        "bookable": sum(o["status"] == "bookable" for o in offers.json()),
    }


async def main() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=60) as client:
        every = await client.get("/villas/sample", params={"n": 1000, "seed": "demo"})
        ids = sorted(v["villa_id"] for v in every.json())
        limit = asyncio.Semaphore(8)
        found = await asyncio.gather(*(facts(client, v, limit) for v in ids))
        print(f"villas on two platforms examined: {len(found)} (window {START} + {WINDOW} nights)")
        for name, hidden, photos, contradiction in STEPS:
            passing = [
                f
                for f in found
                if f["platforms"] >= 2
                and f["hidden"] >= hidden
                and f["photo_pairs"] >= photos
                and (f["conflicts"] or not contradiction)
                and f["bookable"] >= 2
                and f["hidden"] <= WINDOW // 2
            ]
            passing.sort(key=lambda f: (-f["text_reviews"], f["id"]))
            print(f"[{name}] {len(passing)} villas pass before the summary check")
            for f in passing[:10]:
                summary = await client.get(f"/villas/{f['id']}/review-summary")
                cited = summary.status_code == 200 and summary.json() is not None
                print(f"  {f} summary={'yes' if cited else 'no'}")
                if cited:
                    print(f"CHOSEN ({name}): {f['id']}")
                    return
        print("no villa meets even the most relaxed rule")


asyncio.run(main())

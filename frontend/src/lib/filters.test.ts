import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  filterChips,
  filterParams,
  filtersFrom,
  histogram,
  passes,
  villasPassing,
  type Facet,
  type Filters,
} from "@/lib/filters";

// The server's own cases: the panel's live count must agree with the search (filters.py).
const shared = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "../../../backend/tests/fixtures/filter_cases.json"),
    "utf8",
  ),
) as {
  rows: Facet[];
  cases: { name: string; filters: Filters; listings: string[]; villas: number }[];
};

describe("filters agree with the server", () => {
  it.each(shared.cases.map((c) => [c.name, c] as const))("%s", (_, c) => {
    expect(shared.rows.filter((r) => passes(r, c.filters)).map((r) => r.listing)).toEqual(
      c.listings,
    );
    expect(villasPassing(shared.rows, c.filters)).toBe(c.villas);
  });
});

describe("filters in the URL", () => {
  it("round-trip in a fixed order and drop what is malformed", () => {
    const f: Filters = {
      price_max: 20_000_000,
      per_night: true,
      features: ["pool", "parking"],
      platforms: ["shab"],
      instant: true,
      coast_max_m: 1000,
    };
    const params = filterParams(f);
    expect(params).toEqual([
      ["pmax", "20000000"],
      ["pn", "1"],
      ["amen", "pool,parking"],
      ["plat", "shab"],
      ["instant", "1"],
      ["sea", "1000"],
    ]);
    expect(filtersFrom(Object.fromEntries(params))).toEqual(f);
    expect(
      filtersFrom({ pmax: "-3", rooms: "99", amen: "pool,spa", type: "castle", rating: "x" }),
    ).toEqual({ features: ["pool"] });
  });

  it("each active filter is one removable chip in plain words", () => {
    const chips = filterChips({ price_max: 20_000_000, features: ["pool"], coast_max_m: 1000 });
    expect(chips.map((c) => c.text)).toEqual([
      "قیمت تا ۲۰ میلیون تومان",
      "استخر",
      "تا ۱ کیلومتر از دریا",
    ]);
    expect(chips[1]?.without).toEqual({ price_max: 20_000_000, features: [], coast_max_m: 1000 });
  });
});

describe("the price histogram", () => {
  it("counts the listings every other filter leaves, per stay or per night", () => {
    const h = histogram(shared.rows, { platforms: ["jabama"], price_max: 1 }, 4);
    expect(h).not.toBeNull();
    expect(h?.bins.reduce((a, b) => a + b, 0)).toBe(2); // price bounds ignored, platform kept
    const night = histogram(shared.rows, { per_night: true }, 4);
    expect(night?.min).toBe(2_000_000);
    expect(histogram([], {})).toBeNull();
  });
});

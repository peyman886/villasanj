import { describe, expect, it } from "vitest";

import {
  budgetChoices,
  displaySegments,
  driveBuckets,
  excludedTotal,
  intentChips,
  type SearchOut,
} from "./search";

function result(overrides: Partial<SearchOut> = {}): SearchOut {
  return {
    query: "ویلا زیر ۵ میلیون",
    intent: {},
    dates: null,
    missing: [],
    places: [],
    unresolved_places: [],
    unhandled: [],
    budget_readings: null,
    excluded: {},
    total_results: 0,
    drive_coverage: {},
    results: [],
    explanation: null,
    ...overrides,
  };
}

describe("search texts", () => {
  it("shows the query as understood, with the user's own numbers", () => {
    const chips = intentChips(
      result({
        intent: {
          guest_parts: [4, 2],
          budget: { max_toman: 5_000_000, basis: "unknown" },
          features: ["pool"],
        },
        dates: {
          check_in: "2026-10-08",
          check_out: "2026-10-10",
          text: "پنجشنبه ۱۶ مهر تا شنبه ۱۸ مهر",
          flexible: false,
          caveats: [],
        },
        places: ["رامسر"],
      }),
    );
    expect(chips.map((c) => c.text)).toEqual([
      "پنجشنبه ۱۶ مهر تا شنبه ۱۸ مهر",
      "۶ نفر",
      "تا ۵ میلیون تومان",
      "رامسر",
      "استخر",
    ]);
    expect(chips.map((c) => c.key)).toEqual([
      "dates",
      "guests",
      "budget",
      "place:رامسر",
      "feature:pool",
    ]);
    expect(intentChips(result({ intent: { party: "couple" } }))).toEqual([
      { key: "guests", text: "دو نفر (زوج)" },
    ]);
  });

  it("offers the budget readings only when they change the results", () => {
    expect(budgetChoices(result())).toEqual([]);
    const choices = budgetChoices(result({ budget_readings: { per_night: 12, whole_stay: 4 } }));
    expect(choices.map((c) => [c.label, c.count])).toEqual([
      ["هر شب", 12],
      ["کل اقامت", 4],
    ]);
    expect(choices[0]?.query).toBe("ویلا زیر ۵ میلیون شبی");
  });

  it("reads an unstated budget as the whole stay until the user flips it", () => {
    const unstated = result({ intent: { budget: { max_toman: 5_000_000, basis: "unknown" } } });
    expect(intentChips(unstated)[0]?.basis).toEqual({
      current: "whole_stay",
      stated: false,
      chosen: false,
    });
    const flipped = result({ intent: { budget: { max_toman: 5_000_000, basis: "per_night" } } });
    expect(intentChips(flipped, ["basis:per_night"])[0]?.basis).toEqual({
      current: "per_night",
      stated: false,
      chosen: true,
    });
    expect(intentChips(flipped)[0]?.basis?.stated).toBe(true); // the query said «شبی»
  });

  it("shows only drive limits that have results", () => {
    expect(driveBuckets(result({ drive_coverage: { "5": 40, "3": 0, "4": 12 } }))).toEqual([
      { hours: 4, count: 12 },
      { hours: 5, count: 40 },
    ]);
    expect(excludedTotal(result({ excluded: { over_budget: 3, not_bookable: 10 } }))).toBe(13);
  });
});

describe("explanation segments", () => {
  it("keeps punctuation with the value before it", () => {
    const provenance = {
      method: "observed" as const,
      observed_at: "2026-10-01T09:00:00Z",
      oldest_input_at: "2026-10-01T09:00:00Z",
      source: null,
      snapshot_id: null,
      inputs: 0,
    };
    const shown = displaySegments([
      { text: "قیمت ", slot: null, provenance: null },
      { text: "حداقل ۲ تومان", slot: "F1", provenance },
      { text: "؛ و بعد", slot: null, provenance: null },
      { text: "آزاد بود", slot: "F2", provenance },
      { text: ".", slot: null, provenance: null },
    ]);
    expect(shown.map((s) => [s.text, s.tail])).toEqual([
      ["قیمت ", ""],
      ["حداقل ۲ تومان", "؛"],
      [" و بعد", ""],
      ["آزاد بود", "."],
    ]);
  });
});

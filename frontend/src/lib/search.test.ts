import { describe, expect, it } from "vitest";

import {
  budgetChoices,
  displaySegments,
  exclusionSummary,
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
    budget_readings: null,
    excluded: {},
    total_results: 0,
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
    expect(chips).toEqual([
      "پنجشنبه ۱۶ مهر تا شنبه ۱۸ مهر",
      "۶ نفر",
      "تا ۵٬۰۰۰٬۰۰۰ تومان (شبی یا کل اقامت؟)",
      "رامسر",
      "استخر",
    ]);
    expect(intentChips(result({ intent: { party: "couple" } }))).toEqual(["دو نفر (زوج)"]);
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

  it("summarises exclusions, largest first", () => {
    expect(exclusionSummary({ over_budget: 3, not_bookable: 10 })).toEqual([
      "۱۰ مورد: همه‌ی شب‌ها آزاد نبود",
      "۳ مورد: بالاتر از بودجه",
    ]);
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

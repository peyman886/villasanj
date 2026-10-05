import { describe, expect, it } from "vitest";

import { gradeFor, intentRows, queryVerdictFor } from "@/lib/reviews";

const key = (code: string, extra: Partial<{ altKey: boolean; ctrlKey: boolean }> = {}) => ({
  code,
  altKey: false,
  ctrlKey: false,
  metaKey: false,
  ...extra,
});

describe("intentRows", () => {
  it("says each slot of a drafted intent in Persian", () => {
    const rows = Object.fromEntries(
      intentRows({
        dates: { kind: "weekend", which: "next" },
        nights: 2,
        guest_parts: [4, 2],
        budget: { max_toman: 5000000, basis: "per_night" },
        max_drive: { value: 2.5, unit: "hours" },
        places: ["رامسر"],
        features: ["pool", "near_sea"],
      }),
    );
    expect(rows["تاریخ"]).toBe("آخر هفته‌ی بعد");
    expect(rows["نفرات"]).toBe("۴ + ۲");
    expect(rows["بودجه"]).toContain("هر شب");
    expect(rows["رانندگی از تهران"]).toContain("ساعت");
    expect(rows["امکانات"]).toBe("استخر، نزدیک دریا");
  });

  it("names dates the resolver reads and leaves out what is not said", () => {
    expect(intentRows({ dates: { kind: "weekend" } })).toEqual([["تاریخ", "این آخر هفته"]]);
    expect(intentRows({ dates: { kind: "jalali_day", month: 8, day: 15 } })[0]?.[1]).toBe(
      "۱۵ آبان",
    );
    expect(intentRows({})).toEqual([]);
  });
});

describe("review keys", () => {
  it("reads the physical keys, so a Persian layout works too", () => {
    expect(queryVerdictFor(key("KeyY"))).toBe(true);
    expect(queryVerdictFor(key("KeyN"))).toBe(false);
    expect(queryVerdictFor(key("KeyY", { ctrlKey: true }))).toBeNull();
    expect(gradeFor(key("Digit2"))).toBe(2);
    expect(gradeFor(key("Numpad0"))).toBe(0);
    expect(gradeFor(key("Digit3"))).toBeNull();
  });
});

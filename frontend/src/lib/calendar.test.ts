import { describe, expect, it } from "vitest";

import {
  addDays,
  dayAria,
  inStay,
  jalali,
  months,
  nextSelection,
  stateOf,
  weekdayIndex,
  type VillaNight,
} from "@/lib/calendar";

const provenance = (observed_at: string) => ({
  method: "observed" as const,
  observed_at,
  oldest_input_at: observed_at,
  inputs: 0,
  note: null,
  snapshot_id: null,
  source: null,
});

function night(day: string, jabama?: string, shab?: string, hidden = false): VillaNight {
  const seen = (availability: string, price: number | null) => ({
    night: day,
    availability,
    price:
      price === null
        ? null
        : { low_toman: price, high_toman: price, low_rial: price * 10, high_rial: price * 10 },
    extra_guest_price: null,
    is_holiday: false,
    min_nights: null,
    provenance: provenance("2026-10-08T08:00:00Z"),
  });
  const by_platform: VillaNight["by_platform"] = {};
  if (jabama) by_platform.jabama = seen(jabama, 4_200_000);
  if (shab) by_platform.shab = seen(shab, null);
  return { night: day, by_platform, hidden };
}

describe("the Jalali month grid", () => {
  it("knows the Jalali date and the Iranian weekday", () => {
    expect(jalali("2026-10-08")).toEqual({ year: 1405, month: 7, day: 16 });
    expect(weekdayIndex("2026-10-10")).toBe(0); // a Saturday
    expect(weekdayIndex("2026-10-16")).toBe(6); // a Friday
  });

  it("splits a window into Jalali months whose weeks start on Saturday", () => {
    const grid = months("2026-10-08", 30); // 16 Mehr to 14 Aban
    expect(grid.map((m) => m.key)).toEqual(["1405-7", "1405-8"]);
    expect(grid[0]?.title).toContain("مهر");
    const firstWeek = grid[0]?.weeks[0] ?? [];
    expect(firstWeek).toHaveLength(7);
    expect(firstWeek.indexOf("2026-10-08")).toBe(weekdayIndex("2026-10-08")); // a Thursday
    const days = grid.flatMap((m) => m.weeks.flat()).filter(Boolean);
    expect(days).toHaveLength(30);
    expect(days.at(-1)).toBe(addDays("2026-10-08", 29));
  });
});

describe("day states and labels", () => {
  it("maps each platform's observation to a state", () => {
    const n = night("2026-10-15", "available", "unavailable");
    expect(stateOf(n, "jabama")).toBe("available");
    expect(stateOf(n, "shab")).toBe("unavailable");
    expect(stateOf(night("2026-10-15", "booked"), "jabama")).toBe("unavailable");
    expect(stateOf(n, "other")).toBe("unseen");
    expect(stateOf(undefined, "jabama")).toBe("unseen");
  });

  it("says both platforms, their ages and a hidden night", () => {
    const label = dayAria(
      "2026-10-15",
      night("2026-10-15", "available", "unavailable", true),
      { jabama: "جاباما", shab: "شب" },
      () => "۲ ساعت پیش",
    );
    expect(label).toBe(
      "پنجشنبه ۲۳ مهر؛ جاباما: خالی، از ۴٫۲ میلیون تومان (۲ ساعت پیش)؛ شب: ناموجود (۲ ساعت پیش)؛ شب پنهان",
    );
    const unseen = dayAria("2026-10-16", undefined, { jabama: "جاباما" }, () => "");
    expect(unseen).toBe("جمعه ۲۴ مهر؛ جاباما: هنوز این روز را ندیده‌ایم");
  });
});

describe("choosing a stay", () => {
  it("takes a check-in, then a later check-out", () => {
    expect(nextSelection("2026-10-15", null)).toEqual({ pending: "2026-10-15", range: null });
    expect(nextSelection("2026-10-17", "2026-10-15")).toEqual({
      pending: null,
      range: ["2026-10-15", "2026-10-17"],
    });
    expect(nextSelection("2026-10-14", "2026-10-15")).toEqual({
      pending: "2026-10-14",
      range: null,
    });
  });

  it("marks the nights of the stay (check-out excluded)", () => {
    expect(inStay("2026-10-15", "2026-10-15", "2026-10-17")).toBe(true);
    expect(inStay("2026-10-16", "2026-10-15", "2026-10-17")).toBe(true);
    expect(inStay("2026-10-17", "2026-10-15", "2026-10-17")).toBe(false);
    expect(inStay("2026-10-16", null, null)).toBe(false);
  });
});

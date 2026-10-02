import { describe, expect, it } from "vitest";

import type { CalendarNight, Offer, Provenance, Review } from "@/lib/api/client";

import {
  addDays,
  calendarWeeks,
  faAge,
  faDay,
  faMillions,
  faMonthYear,
  faShare,
  faStayed,
  faToman,
  iranToday,
  offerText,
} from "./listing";

const PROVENANCE: Provenance = {
  method: "observed",
  observed_at: "2026-10-01T09:00:00Z",
  oldest_input_at: "2026-10-01T09:00:00Z",
  source: { platform: "p", url: "https://example.test/1" },
  snapshot_id: "s1",
  inputs: 0,
};

function money(low: number, high: number | null) {
  return { low_rial: low * 10, high_rial: high && high * 10, low_toman: low, high_toman: high };
}

describe("money", () => {
  it("shows exact amounts, ranges and open upper bounds", () => {
    expect(faToman(money(2_500_000, 2_500_000))).toBe("۲٬۵۰۰٬۰۰۰ تومان");
    expect(faToman(money(2_000_000, 3_000_000))).toBe("۲٬۰۰۰٬۰۰۰ تا ۳٬۰۰۰٬۰۰۰ تومان");
    expect(faToman(money(2_000_000, null))).toBe("حداقل ۲٬۰۰۰٬۰۰۰ تومان");
    expect(faMillions(4_300_000)).toBe("۴٫۳");
    expect(faMillions(850_000)).toBe("۰٫۸۵");
  });

  it("shares a total per person without narrowing what is known", () => {
    const rial = (low: number, high: number | null) => ({
      low_rial: low,
      high_rial: high,
      low_toman: Math.floor(low / 10),
      high_toman: high === null ? null : Math.floor(high / 10),
    });
    expect(faShare(rial(12_500_000, 12_500_000))).toBe("نفری ۱٬۲۵۰٬۰۰۰ تومان");
    expect(faShare(rial(12_343_333, 12_343_334))).toBe("نفری حدود ۱٬۲۳۴٬۰۰۰ تومان");
    expect(faShare(rial(12_345_678, null))).toBe("نفری دست‌کم ۱٬۲۳۴٬۰۰۰ تومان");
    expect(faShare(rial(10_005_000, 20_001_000))).toBe("نفری ۱٬۰۰۰٬۰۰۰ تا ۲٬۰۰۱٬۰۰۰ تومان");
  });

  it("explains an offer without a total instead of inventing one", () => {
    const offer: Offer = {
      listing_id: "p:1",
      check_in: "2026-10-15",
      check_out: "2026-10-17",
      guests: 4,
      status: "unavailable",
      kind: null,
      total: null,
      per_person: null,
      caveats: [],
      age_hours: 2,
      stale: false,
      provenance: PROVENANCE,
      nights: [],
    };
    expect(offerText(offer)).toBe("دست‌کم یک شب پر یا بسته بود");
    expect(offerText({ ...offer, status: "bookable", total: money(5, null) })).toBe(
      "حداقل ۵ تومان",
    );
  });
});

describe("dates", () => {
  it("speaks Jalali with Persian digits", () => {
    expect(faDay("2026-10-15")).toBe("پنجشنبه ۲۳ مهر");
    expect(faMonthYear("2026-10-15")).toBe("مهر ۱۴۰۵");
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(iranToday(new Date("2026-10-01T20:29:00Z"))).toBe("2026-10-01");
    expect(iranToday(new Date("2026-10-01T20:30:00Z"))).toBe("2026-10-02");
  });

  it("says how old an observation is", () => {
    const now = new Date("2026-10-01T12:00:00Z");
    expect(faAge("2026-10-01T11:30:00Z", now)).toBe("۳۰ دقیقه پیش");
    expect(faAge("2026-10-01T09:00:00Z", now)).toBe("۳ ساعت پیش");
    expect(faAge("2026-09-28T12:00:00Z", now)).toBe("۳ روز پیش");
  });

  it("keeps the precision a platform gave for a stay", () => {
    const review: Review = {
      id: "r",
      rating: 5,
      text: null,
      stayed_on: "2026-09-25",
      stayed_precision: "month",
      host_replied: false,
      provenance: PROVENANCE,
    };
    expect(faStayed(review)).toBe("اقامت در مهر ۱۴۰۵");
    expect(faStayed({ ...review, stayed_precision: "day" })).toBe("اقامت ۳ مهر ۱۴۰۵");
    expect(faStayed({ ...review, stayed_on: null })).toBe("تاریخ اقامت نامعلوم");
  });
});

describe("calendar", () => {
  it("lays nights out in Saturday-first weeks", () => {
    const night: CalendarNight = {
      night: "2026-10-01",
      availability: "available",
      price: money(1, 1),
      extra_guest_price: null,
      min_nights: 1,
      is_holiday: false,
      provenance: PROVENANCE,
    };
    const weeks = calendarWeeks([night], "2026-10-01", 3); // Thursday, Friday, Saturday
    expect(weeks).toHaveLength(2);
    expect(weeks[0]?.slice(0, 5)).toEqual([null, null, null, null, null]);
    expect(weeks[0]?.[5]).toEqual({ day: "2026-10-01", night });
    expect(weeks[0]?.[6]).toEqual({ day: "2026-10-02", night: null });
    expect(weeks[1]?.[0]).toEqual({ day: "2026-10-03", night: null });
    expect(weeks[1]?.slice(1)).toEqual([null, null, null, null, null, null]);
  });
});

describe("map circle", () => {
  it("lies at the radius around the pin and closes", async () => {
    const { circleRing } = await import("@/components/listing-map");
    const ring = circleRing(36.9, 50.66, 400, 8);
    expect(ring).toHaveLength(9);
    expect(ring[0]).toEqual(ring[8]);
    const [lon = 0, lat = 0] = ring[0] ?? [];
    expect(lon).toBeCloseTo(50.66, 6); // the first point is due north
    expect((lat - 36.9) * 111_195).toBeCloseTo(400, 0);
  });
});

import { describe, expect, it } from "vitest";

import type { Listing, Offer } from "@/lib/api/client";
import { availabilityText, bookingRows, unavailableText } from "@/lib/booking";
import type { Money } from "@/lib/numbers";
import { cardOffers, cheapestShown, headline, stayText, type SearchOut } from "@/lib/search";

const provenance = {
  method: "derived" as const,
  observed_at: "2026-10-03T10:00:00Z",
  oldest_input_at: "2026-10-03T10:00:00Z",
  inputs: 2,
  note: null,
  snapshot_id: null,
  source: null,
};
const money = (low: number, high: number | null = null): Money => ({
  low_toman: low,
  high_toman: high,
  low_rial: low * 10,
  high_rial: high === null ? null : high * 10,
});

type Result = SearchOut["results"][number];

function result(total: Money | null, alsoOn: Partial<Result["also_on"][number]>[] = []): Result {
  return {
    listing_id: "shab:1",
    platform: "shab",
    platform_name: "شب",
    external_id: "1",
    title: "ویلا",
    photo: null,
    photos: [],
    location: null,
    bedrooms: 2,
    max_capacity: 6,
    area_m2: 120,
    rating: null,
    rating_count: null,
    stale: false,
    confirmed: [],
    total,
    per_person: null,
    total_provenance: provenance,
    price_per_person_night_toman: null,
    confirmed_features: 0,
    score: 1,
    contributions: [],
    cautions: [],
    geo: null,
    mentions: [],
    villa_id: alsoOn.length ? "v-1" : null,
    also_on: alsoOn.map((o) => ({
      listing_id: "jabama:9",
      platform: "jabama",
      platform_name: "جاباما",
      external_id: "9",
      status: "bookable",
      total: money(9_000_000),
      total_provenance: provenance,
      stale: false,
      area_m2: 130,
      ...o,
    })),
    listing_provenance: provenance,
  };
}

describe("a result card's offers (never merged)", () => {
  it("lists jabama first and marks the strictly cheaper bookable offer", () => {
    const offers = cardOffers(result(money(8_500_000), [{}]));
    expect(offers.map((o) => o.platform)).toEqual(["jabama", "shab"]);
    expect(offers.map((o) => o.cheaper)).toEqual([false, true]);
    expect(headline(offers)?.platform).toBe("shab");
  });

  it("marks nothing on a tie and leads with jabama", () => {
    const offers = cardOffers(result(money(9_000_000), [{}]));
    expect(offers.some((o) => o.cheaper)).toBe(false);
    expect(headline(offers)?.platform).toBe("jabama");
  });

  it("an unavailable platform is never the headline or the cheaper one", () => {
    const offers = cardOffers(
      result(money(8_500_000), [{ status: "unavailable", total: money(1_000_000) }]),
    );
    expect(offers.find((o) => o.platform === "jabama")?.bookable).toBe(false);
    expect(offers.some((o) => o.cheaper)).toBe(false);
    expect(headline(offers)?.platform).toBe("shab");
  });

  it("says the lowest shown lower bound and what the price is for", () => {
    const search = {
      results: [result(money(8_500_000), [{}]), result(money(12_000_000))],
      dates: {
        check_in: "2026-10-15",
        check_out: "2026-10-17",
        text: "",
        flexible: false,
        caveats: [],
      },
      intent: { guest_parts: [4, 2] },
    } as unknown as SearchOut;
    expect(cheapestShown(search)).toBe(8_500_000);
    expect(stayText(search)).toBe("۲ شب، ۶ نفر");
  });
});

const listing = (platform: string, name: string): Listing =>
  ({ id: `${platform}:1`, platform, platform_name: name }) as Listing;
const offer = (platform: string, status: string, low: number | null): Offer =>
  ({
    listing_id: `${platform}:1`,
    status,
    total: low === null ? null : money(low),
    nights: [],
    stale: false,
    provenance,
  }) as unknown as Offer;

describe("the booking card's rows", () => {
  const members = [listing("jabama", "جاباما"), listing("shab", "شب")];

  it("puts the cheaper bookable platform first", () => {
    const rows = bookingRows(members, [
      offer("jabama", "bookable", 9_000_000),
      offer("shab", "bookable", 8_500_000),
    ]);
    expect(rows.map((r) => [r.listing.platform, r.cheaper])).toEqual([
      ["shab", true],
      ["jabama", false],
    ]);
    expect(availabilityText(rows)).toBe("در هر دو پلتفرم برای این تاریخ خالی دیده شد");
  });

  it("an unavailable platform goes last and says «خالی نیست», never «پر»", () => {
    const rows = bookingRows(members, [
      offer("jabama", "unavailable", 7_000_000),
      offer("shab", "bookable", 8_500_000),
    ]);
    expect(rows.map((r) => r.listing.platform)).toEqual(["shab", "jabama"]);
    expect(rows[0]?.cheaper).toBe(false); // nothing to compare against
    const last = rows[1];
    expect(last && unavailableText(last, 6)).toBe("برای این تاریخ در جاباما خالی نیست");
    expect(availabilityText(rows)).toBe("فقط در شب برای این تاریخ خالی دیده شد");
  });

  it("a missing offer and the other states have their own words", () => {
    const rows = bookingRows(members, [offer("shab", "too_many_guests", null)]);
    const [a, b] = rows;
    expect(a && unavailableText(a, 12)).toMatch(/ندیده‌ایم|کافی نیست/);
    expect(b && unavailableText(b, 12)).toMatch(/ندیده‌ایم|کافی نیست/);
    expect(availabilityText(rows)).toBe("برای این تاریخ در هیچ پلتفرمی خالی دیده نشد");
  });
});

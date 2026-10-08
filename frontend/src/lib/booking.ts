/**
 * The booking card's rows (M12 1.6): one row per platform with its own offer for the chosen stay
 * (never a merged price, rule 3), the cheaper bookable one first, and how to say each state.
 */

import type { Listing, Offer } from "@/lib/api/client";
import { faNum } from "@/lib/numbers";
import { platformRank } from "@/lib/platforms";

export type BookingRow = {
  listing: Listing;
  offer: Offer | null;
  bookable: boolean;
  cheaper: boolean;
};

export function bookingRows(members: Listing[], offers: Offer[]): BookingRow[] {
  const rows = members.map((listing) => {
    const offer = offers.find((o) => o.listing_id === listing.id) ?? null;
    const bookable = offer?.status === "bookable" && offer.total !== null;
    return { listing, offer, bookable, cheaper: false };
  });
  const lows = rows.filter((r) => r.bookable).map((r) => r.offer?.total?.low_toman ?? Infinity);
  const min = Math.min(...lows);
  if (lows.length > 1 && lows.filter((l) => l === min).length === 1) {
    for (const r of rows) r.cheaper = r.bookable && r.offer?.total?.low_toman === min;
  }
  return rows.sort(
    (a, b) =>
      Number(b.bookable) - Number(a.bookable) ||
      (a.offer?.total?.low_toman ?? Infinity) - (b.offer?.total?.low_toman ?? Infinity) ||
      platformRank(a.listing.platform) - platformRank(b.listing.platform),
  );
}

/** Why a platform has no price for this stay, in the product's words («ناموجود», never «پر»). */
export function unavailableText(row: BookingRow, guests: number): string {
  const name = row.listing.platform_name;
  switch (row.offer?.status) {
    case "unavailable":
      return `برای این تاریخ در ${name} خالی نیست`;
    case "too_many_guests":
      return `ظرفیت ${name} برای ${faNum(guests)} نفر کافی نیست`;
    case "below_min_nights":
      return `${name} برای این تاریخ اقامت طولانی‌تری می‌خواهد`;
    default:
      return `این تاریخ را هنوز در ${name} ندیده‌ایم`;
  }
}

/** The availability line above the rows. */
export function availabilityText(rows: BookingRow[]): string {
  const free = rows.filter((r) => r.bookable);
  if (rows.length > 1 && free.length === rows.length) {
    return "در هر دو پلتفرم برای این تاریخ خالی دیده شد";
  }
  if (free.length === 1) {
    return rows.length > 1
      ? `فقط در ${free[0]?.listing.platform_name} برای این تاریخ خالی دیده شد`
      : `در ${free[0]?.listing.platform_name} برای این تاریخ خالی دیده شد`;
  }
  return "برای این تاریخ در هیچ پلتفرمی خالی دیده نشد";
}

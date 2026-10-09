/** Persian text for the search page: chips, questions, cautions and exclusions (M8 groundwork). */

import type { components } from "@/lib/api/schema";

import type { Provenance } from "@/lib/api/client";
import { faNumber } from "@/lib/listing";
import { faNum, shortToman, type Money } from "@/lib/numbers";
import { platformRank } from "@/lib/platforms";

export type SearchOut = components["schemas"]["SearchOut"];
export type SearchResultOut = components["schemas"]["ResultOut"];

export const FEATURE_TEXT: Record<string, string> = {
  pool: "استخر",
  jacuzzi: "جکوزی",
  near_sea: "نزدیک دریا",
  sea_view: "منظره‌ی دریا",
  forest: "جنگلی",
  fireplace: "شومینه",
  parking: "پارکینگ",
  barbecue: "باربیکیو",
};

export const CAUTION_TEXT: Record<string, string> = {
  may_exceed_budget:
    "پلتفرم هزینه‌های جانبی را منتشر نکرده؛ مبلغ نهایی ممکن است از بودجه بیشتر شود",
  capacity_unknown: "ظرفیت منتشر نشده",
  bedrooms_unknown: "تعداد اتاق خواب منتشر نشده",
  price_unknown: "قیمت معلوم نیست",
  feature_unconfirmed: "یکی از امکانات خواسته‌شده تأیید نشد",
  feature_only_described: "یکی از امکانات خواسته‌شده فقط در متن آگهی آمده",
  drive_unknown: "زمان رانندگی معلوم نیست",
  may_exceed_drive: "بسته به جای دقیق ویلا، ممکن است از سقف زمان رانندگی بیشتر شود",
  claim_contradicted: "یکی از فاصله‌های اعلام‌شده در آگهی با نقشه نمی‌خواند",
};

export const EXCLUSION_TEXT: Record<string, string> = {
  not_bookable: "همه‌ی شب‌های سفر آزاد نبود",
  too_small: "ظرفیت کم",
  few_bedrooms: "اتاق خواب کمتر از تعداد خواسته‌شده",
  over_budget: "بالاتر از بودجه",
  feature_denied: "امکان خواسته‌شده را ندارد",
  too_far: "دورتر از زمان رانندگی خواسته‌شده",
};

export const MISSING_TEXT: Record<string, string> = {
  dates: "تاریخ سفر را بگویید (مثلاً «آخر هفته‌ی بعد» یا «۱۵ آبان سه شب»).",
  exact_stay: "این بازه شب‌های مشخصی ندارد؛ از کدام شب تا کدام شب؟",
  unresolvable_dates: "این تاریخ گذشته یا ناممکن است؛ تاریخ دیگری بگویید.",
  guests: "چند نفرید؟ تا نگویید، قیمت‌ها برای یک نفر حساب می‌شوند.",
};

export const DATE_CAVEAT_TEXT: Record<string, string> = {
  partial_weekend: "امروز جمعه است؛ از این آخر هفته فقط شب جمعه مانده.",
  next_year: "این تاریخ امسال گذشته؛ همین تاریخ در سال بعد را جستیم.",
  lunar_holidays_unknown:
    "تعطیلات قمری این بازه هنوز در تقویم پلتفرم‌ها دیده نشده؛ ممکن است تعطیلی دیگری هم باشد.",
};

export const COMPONENT_TEXT: Record<string, string> = {
  price: "قیمت برای هر نفر در هر شب",
  rating: "امتیاز مهمان‌ها",
};

export const BASIS_TEXT = { whole_stay: "کل سفر", per_night: "هر شب" } as const;

type Intent = {
  guest_parts?: number[];
  party?: string;
  nights?: number;
  bedrooms_min?: number;
  budget?: { max_toman: number; basis: string };
  max_drive?: { value: number; unit: string };
  features?: string[];
};

export type Chip = { key: string; text: string; basis?: Basis };
/** How the budget chip reads the budget: stated by the query, or chosen (or defaulted) by us. */
export type Basis = { current: "per_night" | "whole_stay"; stated: boolean; chosen: boolean };

/**
 * The query as understood, one chip per constraint (the numbers are the user's own). The key
 * names what removing the chip drops ("budget", "place:رامسر", ...); removing the dates makes the
 * page ask for them again.
 */
export function intentChips(result: SearchOut, drop: string[] = []): Chip[] {
  const intent = result.intent as Intent;
  const chips: Chip[] = [];
  if (result.dates) chips.push({ key: "dates", text: result.dates.text });
  const parts = intent.guest_parts ?? [];
  if (parts.length > 0) {
    const total = parts.reduce((sum, n) => sum + n, 0);
    chips.push({ key: "guests", text: `${faNumber(total)} نفر` });
  } else if (intent.party === "couple") {
    chips.push({ key: "guests", text: "دو نفر (زوج)" });
  } else if (intent.party === "solo") {
    chips.push({ key: "guests", text: "یک نفر" });
  }
  if (intent.nights && !result.dates) {
    chips.push({ key: "nights", text: `${faNumber(intent.nights)} شب` });
  }
  if (intent.bedrooms_min) {
    chips.push({ key: "bedrooms", text: `دست‌کم ${faNumber(intent.bedrooms_min)} خواب` });
  }
  if (intent.budget) {
    const { basis: said, max_toman: max } = intent.budget;
    const chosen = drop.some((d) => d.startsWith("basis:"));
    chips.push({
      key: "budget",
      text: `تا ${shortToman(max, "point")}`,
      basis: {
        // An unstated basis is read as the whole stay until the user flips it (D5).
        current: said === "per_night" ? "per_night" : "whole_stay",
        stated: said !== "unknown" && !chosen,
        chosen,
      },
    });
  }
  if (intent.max_drive) {
    const unit = intent.max_drive.unit === "hours" ? "ساعت" : "دقیقه";
    chips.push({
      key: "drive",
      text: `تا ${faNumber(intent.max_drive.value)} ${unit} رانندگی`,
    });
  }
  for (const place of result.places) chips.push({ key: `place:${place}`, text: place });
  for (const feature of intent.features ?? []) {
    chips.push({ key: `feature:${feature}`, text: FEATURE_TEXT[feature] ?? feature });
  }
  return chips;
}

export type BudgetChoice = { label: string; count: number; query: string };

/**
 * When "زیر ۵ میلیون" could mean per night or for the whole stay and the two readings give
 * different results, the two choices with their counts. Each choice re-runs the query with the
 * basis said in words, so the user's own text stays the source of every number.
 */
export function budgetChoices(result: SearchOut): BudgetChoice[] {
  const readings = result.budget_readings;
  if (!readings) return [];
  return [
    { label: "هر شب", count: readings.per_night ?? 0, query: `${result.query} شبی` },
    {
      label: "کل سفر",
      count: readings.whole_stay ?? 0,
      query: `${result.query} برای کل اقامت`,
    },
  ];
}

export const EXAMPLE_QUERIES = [
  "ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد زیر ۲۰ میلیون",
  "تعطیلات بعدی یه ویلای جنگلی تو تنکابن برای ۴ نفر، شبی تا ۳ میلیون",
  "امشب یه ویلا برای من و همسرم نزدیک دریا",
];

export type Segment = SearchOut["explanation"] extends infer E
  ? E extends { segments: (infer S)[] }
    ? S
    : never
  : never;
export type DisplaySegment = Segment & { tail: string };

/**
 * Punctuation right after a filled value («…(۱۱ ساعت پیش)».) is kept with the value, so a line
 * never starts with a lone «.» or «؛» after a source button.
 */
export function displaySegments(segments: Segment[]): DisplaySegment[] {
  const out: DisplaySegment[] = [];
  for (const segment of segments) {
    const previous = out.at(-1);
    if (!segment.slot && previous?.slot) {
      const match = /^[.،؛:!؟)»]+/.exec(segment.text);
      if (match) {
        previous.tail = match[0];
        const rest = segment.text.slice(match[0].length);
        if (rest) out.push({ ...segment, text: rest, tail: "" });
        continue;
      }
    }
    out.push({ ...segment, tail: "" });
  }
  return out;
}

/** One platform's own offer on a result card (prices are never merged, rule 3). */
export type CardOffer = {
  listingId: string;
  platform: string;
  platformName: string;
  total: Money | null;
  provenance: Provenance;
  bookable: boolean;
  stale: boolean;
  cheaper: boolean; // the strictly cheaper of two bookable, priced offers
};

/** The result's own offer and its other platforms', jabama first. */
export function cardOffers(result: SearchResultOut): CardOffer[] {
  const offers: CardOffer[] = [
    {
      listingId: result.listing_id,
      platform: result.platform,
      platformName: result.platform_name,
      total: result.total,
      provenance: result.total_provenance,
      bookable: true, // a result is bookable by construction (the ranking excludes the rest)
      stale: result.stale,
      cheaper: false,
    },
    ...result.also_on.map((o) => ({
      listingId: o.listing_id,
      platform: o.platform,
      platformName: o.platform_name,
      total: o.total,
      provenance: o.total_provenance,
      bookable: o.status === "bookable",
      stale: o.stale,
      cheaper: false,
    })),
  ].sort((a, b) => platformRank(a.platform) - platformRank(b.platform));
  const priced = offers.filter((o) => o.bookable && o.total !== null);
  const lows = priced.map((o) => o.total?.low_toman ?? Infinity);
  const min = Math.min(...lows);
  if (priced.length > 1 && lows.filter((l) => l === min).length === 1) {
    for (const o of priced) o.cheaper = o.total?.low_toman === min;
  }
  return offers;
}

/** The card's headline: the cheaper platform's own offer (jabama first on a tie). */
export function headline(offers: CardOffer[]): CardOffer | null {
  const priced = offers.filter((o) => o.bookable && o.total !== null);
  return priced.find((o) => o.cheaper) ?? priced[0] ?? null;
}

/** «از ۸٫۵ میلیون برای ۲ شب»: the lowest lower bound among the shown results. */
export function cheapestShown(result: SearchOut): number | null {
  const lows = result.results.flatMap((r) =>
    cardOffers(r)
      .filter((o) => o.bookable && o.total)
      .map((o) => o.total?.low_toman ?? Infinity),
  );
  return lows.length ? Math.min(...lows) : null;
}

/** «۲ شب، ۶ نفر»: what the card's price is for. */
export function stayText(result: SearchOut): string | null {
  if (!result.dates) return null;
  const nights = Math.round(
    (Date.parse(result.dates.check_out) - Date.parse(result.dates.check_in)) / 86_400_000,
  );
  const guests = ((result.intent as Intent).guest_parts ?? []).reduce((a, b) => a + b, 0);
  return guests ? `${faNum(nights)} شب، ${faNum(guests)} نفر` : `${faNum(nights)} شب`;
}

/** Drive limits with at least one result (empty buckets are never shown, S5). */
export function driveBuckets(result: SearchOut): { hours: number; count: number }[] {
  return Object.entries(result.drive_coverage)
    .map(([hours, count]) => ({ hours: Number(hours), count }))
    .filter((b) => b.count > 0)
    .sort((a, b) => a.hours - b.hours);
}

export function excludedTotal(result: SearchOut): number {
  return Object.values(result.excluded).reduce((a, b) => a + b, 0);
}

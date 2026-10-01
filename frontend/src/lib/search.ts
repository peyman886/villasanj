/** Persian text for the search page: chips, questions, cautions and exclusions (M8 groundwork). */

import type { components } from "@/lib/api/schema";

import { faNumber } from "@/lib/listing";

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
  may_exceed_budget: "هزینه‌های جانبی منتشر نشده؛ ممکن است از بودجه بیشتر شود",
  capacity_unknown: "ظرفیت منتشر نشده",
  bedrooms_unknown: "تعداد اتاق خواب منتشر نشده",
  price_unknown: "قیمت معلوم نیست",
  feature_unconfirmed: "یکی از امکانات خواسته‌شده تأیید نشد",
  feature_only_described: "یکی از امکانات خواسته‌شده فقط در توضیحات آمده",
};

export const EXCLUSION_TEXT: Record<string, string> = {
  not_bookable: "همه‌ی شب‌ها آزاد نبود",
  too_small: "ظرفیت کم",
  few_bedrooms: "اتاق خواب کمتر از خواسته",
  over_budget: "بالاتر از بودجه",
  feature_denied: "امکان خواسته‌شده را ندارد",
};

export const MISSING_TEXT: Record<string, string> = {
  dates: "تاریخ سفر را بگویید (مثلاً «آخر هفته‌ی بعد» یا «۱۵ آبان سه شب»).",
  exact_stay: "این بازه شب‌های مشخصی ندارد؛ از کدام شب تا کدام شب؟",
  unresolvable_dates: "این تاریخ گذشته یا ناممکن است؛ تاریخ دیگری بگویید.",
  guests: "چند نفرید؟ قیمت‌ها بدون تعداد نفر برای یک نفر حساب شده‌اند.",
};

export const DATE_CAVEAT_TEXT: Record<string, string> = {
  partial_weekend: "امروز جمعه است؛ از این آخر هفته فقط شب جمعه مانده.",
  next_year: "این تاریخ امسال گذشته؛ سال بعد در نظر گرفته شد.",
  lunar_holidays_unknown:
    "تعطیلات قمری این بازه هنوز در تقویم پلتفرم‌ها دیده نشده؛ ممکن است تعطیلی دیگری هم باشد.",
};

export const COMPONENT_TEXT: Record<string, string> = {
  price: "قیمت برای هر نفر در هر شب",
  rating: "امتیاز مهمان‌ها",
};

const BASIS_TEXT: Record<string, string> = {
  per_night: "هر شب",
  whole_stay: "کل اقامت",
  unknown: "شبی یا کل اقامت؟",
};

type Intent = {
  guest_parts?: number[];
  party?: string;
  nights?: number;
  bedrooms_min?: number;
  budget?: { max_toman: number; basis: string };
  max_drive?: { value: number; unit: string };
  features?: string[];
};

/** The query as understood, one chip per constraint (the numbers are the user's own). */
export function intentChips(result: SearchOut): string[] {
  const intent = result.intent as Intent;
  const chips: string[] = [];
  if (result.dates) chips.push(result.dates.text);
  const parts = intent.guest_parts ?? [];
  if (parts.length > 0) {
    const total = parts.reduce((sum, n) => sum + n, 0);
    chips.push(`${faNumber(total)} نفر`);
  } else if (intent.party === "couple") {
    chips.push("دو نفر (زوج)");
  } else if (intent.party === "solo") {
    chips.push("یک نفر");
  }
  if (intent.nights && !result.dates) chips.push(`${faNumber(intent.nights)} شب`);
  if (intent.bedrooms_min) chips.push(`دست‌کم ${faNumber(intent.bedrooms_min)} خواب`);
  if (intent.budget) {
    const basis = BASIS_TEXT[intent.budget.basis] ?? "";
    chips.push(`تا ${faNumber(intent.budget.max_toman)} تومان (${basis})`);
  }
  if (intent.max_drive) {
    const unit = intent.max_drive.unit === "hours" ? "ساعت" : "دقیقه";
    chips.push(`حداکثر ${faNumber(intent.max_drive.value)} ${unit} رانندگی`);
  }
  chips.push(...result.places);
  for (const feature of intent.features ?? []) chips.push(FEATURE_TEXT[feature] ?? feature);
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
      label: "کل اقامت",
      count: readings.whole_stay ?? 0,
      query: `${result.query} برای کل اقامت`,
    },
  ];
}

export function exclusionSummary(excluded: Record<string, number>): string[] {
  return Object.entries(excluded)
    .sort(([, a], [, b]) => b - a)
    .map(([reason, count]) => `${faNumber(count)} مورد: ${EXCLUSION_TEXT[reason] ?? reason}`);
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

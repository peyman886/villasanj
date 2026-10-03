/** Persian text for the listing page: money, offer states, dates and provenance (M7 groundwork). */

import type { CalendarNight, Offer, Provenance, Review } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Money = components["schemas"]["MoneyOut"];

const TIME_ZONE = "Asia/Tehran";
const numberFormat = new Intl.NumberFormat("fa-IR");
const millionsFormat = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 });
const relative = new Intl.RelativeTimeFormat("fa", { numeric: "auto" });
const dayFormat = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: TIME_ZONE,
});
const fullDayFormat = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: TIME_ZONE,
});
const dateTimeFormat = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: TIME_ZONE,
});
const dayOfMonthFormat = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  day: "numeric",
  timeZone: TIME_ZONE,
});

export const STATUS_TEXT: Record<string, string> = {
  bookable: "آزاد در آخرین مشاهده",
  unavailable: "دست‌کم یک شب پر یا بسته بود",
  too_many_guests: "ظرفیت برای این تعداد کافی نیست",
  below_min_nights: "کمتر از حداقل شب‌های اقامت",
  unknown: "برای همه‌ی شب‌ها مشاهده‌ی قابل‌استفاده نداریم",
};

export const CAVEAT_TEXT: Record<string, string> = {
  night_price_from_rate_card: "قیمت بعضی شب‌ها از نرخ‌نامه‌ی آگهی است، نه از تقویم",
  night_price_unknown: "قیمت بعضی شب‌ها معلوم نیست",
  extra_guest_price_from_rate_card: "هزینه‌ی نفر اضافه از نرخ‌نامه‌ی آگهی است",
  extra_guest_price_unknown: "هزینه‌ی نفر اضافه معلوم نیست",
  capacity_unknown: "ظرفیت پایه‌ی آگهی منتشر نشده است",
  fees_unknown: "کارمزد و هزینه‌های جانبی پلتفرم منتشر نشده؛ مبلغ نهایی ممکن است بیشتر باشد",
};

export const AVAILABILITY_TEXT: Record<string, string> = {
  available: "آزاد",
  unavailable: "پر یا بسته",
  booked: "رزروشده",
  blocked: "بسته",
  unknown: "نامعلوم",
};

/** Truth-check verdicts (product rule 5: «تأیید نشد», never an accusation). */
export const CLAIM_VERDICT_TEXT: Record<string, string> = {
  contradicted: "با نقشه نمی‌خواند",
  inconsistent: "با فهرست امکانات نمی‌خواند",
  not_confirmed: "تأیید نشد",
  supported: "تأیید شد",
  consistent: "با فهرست امکانات می‌خواند",
  shared: "امکان مشاع",
  not_checked: "بررسی نشد",
};

/** Display order: what needs a look first. */
export const CLAIM_VERDICT_ORDER = Object.keys(CLAIM_VERDICT_TEXT);

export const METHOD_TEXT: Record<Provenance["method"], string> = {
  observed: "مشاهده‌شده در صفحه‌ی پلتفرم",
  derived: "محاسبه‌شده از مقادیر مشاهده‌شده",
  llm_extracted: "استخراج‌شده با مدل زبانی",
  human: "ثبت‌شده توسط انسان",
};

export function faNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "نامشخص" : numberFormat.format(value);
}

/** "۲٬۵۰۰٬۰۰۰ تومان", a range, or an open upper bound ("حداقل …") when costs are unknown. */
export function faToman(money: Money): string {
  const low = numberFormat.format(money.low_toman);
  if (money.high_toman === null) return `حداقل ${low} تومان`;
  if (money.high_toman === money.low_toman) return `${low} تومان`;
  return `${low} تا ${numberFormat.format(money.high_toman)} تومان`;
}

const SHARE_STEP = 1_000; // a person's share is shown to the thousand toman

/**
 * Each person's share of a total ("نفری حدود ۱٬۲۳۴٬۰۰۰ تومان"), rounded to a thousand toman
 * outwards for ranges and open totals (so the true share stays inside), to the nearest for an
 * exact one (then said with «حدود» unless it is already round).
 */
export function faShare(share: Money): string {
  const fmt = (toman: number) => numberFormat.format(toman);
  const step = SHARE_STEP * 10; // in rial: rial fields are exact, toman ones are rounded down
  const down = (Math.floor(share.low_rial / step) * step) / 10;
  if (share.high_rial === null) return `نفری دست‌کم ${fmt(down)} تومان`;
  if (share.high_rial - share.low_rial <= 1) {
    // an exact total, or one that does not divide evenly (its share is a one-rial range)
    const nearest = (Math.round(share.low_rial / step) * step) / 10;
    return nearest * 10 === share.low_rial
      ? `نفری ${fmt(nearest)} تومان`
      : `نفری حدود ${fmt(nearest)} تومان`;
  }
  const up = (Math.ceil(share.high_rial / step) * step) / 10;
  return `نفری ${fmt(down)} تا ${fmt(up)} تومان`;
}

/** Toman in millions for tight cells ("۴٫۳"); the exact amount is always one click away. */
export function faMillions(toman: number): string {
  return millionsFormat.format(toman / 1_000_000);
}

export function offerText(offer: Offer): string {
  if (offer.total === null) return STATUS_TEXT[offer.status] ?? offer.status;
  return faToman(offer.total);
}

function noon(day: string): Date {
  return new Date(`${day}T12:00:00Z`); // a calendar day: noon UTC is the same day in Iran
}

export function faDay(day: string): string {
  return dayFormat.format(noon(day));
}

export function faFullDay(day: string): string {
  return fullDayFormat.format(noon(day));
}

export function faDayOfMonth(day: string): string {
  return dayOfMonthFormat.format(noon(day));
}

export function faMonthYear(day: string): string {
  const parts = fullDayFormat.formatToParts(noon(day));
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("month")} ${part("year")}`;
}

export function faDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso));
}

/** "۳ ساعت پیش": how old an observation is (a price is an observation, not a state). */
export function faAge(iso: string, now: Date): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return relative.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 48) return relative.format(-hours, "hour");
  return relative.format(-Math.round(hours / 24), "day");
}

export function faStayed(review: Review): string {
  if (review.stayed_on === null) return "تاریخ اقامت نامعلوم";
  if (review.stayed_precision === "month") return `اقامت در ${faMonthYear(review.stayed_on)}`;
  return `اقامت ${faFullDay(review.stayed_on)}`;
}

/** Today's calendar day in Iran, as YYYY-MM-DD ("tonight" means this day). */
export function iranToday(now: Date): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(now);
}

export function addDays(day: string, days: number): string {
  const date = noon(day);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export type CalendarCell = { day: string; night: CalendarNight | null };

const SATURDAY = 6; // Date.getUTCDay(); Iranian weeks start on Saturday

/** Weeks (Saturday first) covering [start, start + days), with each day's newest observation. */
export function calendarWeeks(
  nights: CalendarNight[],
  start: string,
  days: number,
): (CalendarCell | null)[][] {
  const byDay = new Map(nights.map((n) => [n.night, n]));
  const lead = (noon(start).getUTCDay() - SATURDAY + 7) % 7;
  const cells: (CalendarCell | null)[] = Array.from({ length: lead }, () => null);
  for (let offset = 0; offset < days; offset += 1) {
    const day = addDays(start, offset);
    cells.push({ day, night: byDay.get(day) ?? null });
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, week) => cells.slice(week * 7, week * 7 + 7));
}

export const WEEKDAY_HEADERS = [
  "شنبه",
  "یکشنبه",
  "دوشنبه",
  "سه‌شنبه",
  "چهارشنبه",
  "پنجشنبه",
  "جمعه",
];

/** Where a published distance claim points (the backend's `ClaimTarget`). */
export const CLAIM_TARGET_TEXT: Record<string, string> = {
  sea: "دریا",
  city_center: "مرکز شهر",
  supermarket: "سوپرمارکت",
  bakery: "نانوایی",
  restaurant: "رستوران",
  medical: "مرکز درمانی",
  forest: "جنگل",
  shopping: "مراکز خرید",
  recreation: "مراکز تفریحی",
  shrine: "زیارتگاه",
  other: "مقصدهای دیگر",
  not_understood: "عبارت نامفهوم",
};

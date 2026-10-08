/**
 * The two-platform Jalali calendar (M12 1.8, decisions.md D4), as pure functions: months that
 * start on Saturday, each day's state on each platform, and the words a screen reader says.
 * A day is split top (jabama) and bottom (shab); states are told apart by fill, hatch and
 * outline as well as colour, so the calendar reads in grayscale.
 */

import type { components } from "@/lib/api/schema";
import { shortAmount } from "@/lib/numbers";
import { PLATFORM_ORDER } from "@/lib/platforms";

export type VillaNight = components["schemas"]["VillaNightOut"];
export type DayState = "available" | "unavailable" | "unseen";

const TZ = "Asia/Tehran";
const parts = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", {
  year: "numeric",
  month: "numeric",
  day: "numeric",
  timeZone: TZ,
});
const monthName = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  month: "long",
  year: "numeric",
  timeZone: TZ,
});
const dayLabel = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: TZ,
});
const dayNumber = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric", timeZone: TZ });

function noon(day: string): Date {
  return new Date(`${day}T12:00:00Z`); // a calendar day: noon UTC is the same day in Iran
}

export function addDays(day: string, days: number): string {
  const date = noon(day);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((noon(b).getTime() - noon(a).getTime()) / 86_400_000);
}

/** The Jalali year, month and day of a Gregorian ISO day. */
export function jalali(day: string): { year: number; month: number; day: number } {
  const p = parts.formatToParts(noon(day));
  const get = (type: string) => Number(p.find((x) => x.type === type)?.value);
  return { year: get("year"), month: get("month"), day: get("day") };
}

/** 0 for Saturday … 6 for Friday (an Iranian week). */
export function weekdayIndex(day: string): number {
  return (noon(day).getUTCDay() + 1) % 7;
}

export const WEEKDAYS_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
export const WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];

export type Month = { key: string; title: string; weeks: (string | null)[][] };

/** Jalali months covering [start, start + days), weeks from Saturday; days outside are null. */
export function months(start: string, days: number): Month[] {
  const grouped: { key: string; title: string; days: string[] }[] = [];
  for (let i = 0; i < days; i += 1) {
    const day = addDays(start, i);
    const j = jalali(day);
    const key = `${j.year}-${j.month}`;
    let current = grouped.at(-1);
    if (current?.key !== key) {
      current = { key, title: monthName.format(noon(day)), days: [] };
      grouped.push(current);
    }
    current.days.push(day);
  }
  return grouped.map((m) => {
    const cells: (string | null)[] = Array.from(
      { length: weekdayIndex(m.days[0] ?? start) },
      () => null,
    );
    cells.push(...m.days);
    while (cells.length % 7) cells.push(null);
    return {
      key: m.key,
      title: m.title,
      weeks: Array.from({ length: cells.length / 7 }, (_, w) => cells.slice(w * 7, w * 7 + 7)),
    };
  });
}

export function stateOf(night: VillaNight | undefined, platform: string): DayState {
  const seen = night?.by_platform[platform];
  if (!seen) return "unseen";
  return seen.availability === "available" ? "available" : "unavailable";
}

export function faDay(day: string): string {
  return dayLabel.format(noon(day));
}

export function faDayNumber(day: string): string {
  return dayNumber.format(noon(day));
}

const STATE_TEXT: Record<DayState, string> = {
  available: "خالی",
  unavailable: "ناموجود",
  unseen: "هنوز این روز را ندیده‌ایم",
};

/**
 * What a screen reader says for a day: «پنجشنبه ۱۳ آبان؛ جاباما: خالی، از ۴٫۲ میلیون تومان
 * (۲ ساعت پیش)؛ شب: ناموجود (۱ روز پیش)؛ شب پنهان».
 */
export function dayAria(
  day: string,
  night: VillaNight | undefined,
  names: Record<string, string>,
  age: (iso: string) => string,
): string {
  const platforms = [...PLATFORM_ORDER].filter((p) => p in names);
  const said = platforms.map((p) => {
    const state = stateOf(night, p);
    const seen = night?.by_platform[p];
    const price =
      state === "available" && seen?.price
        ? `، از ${shortAmount(seen.price.low_toman, "lower")} تومان`
        : "";
    const when = seen ? ` (${age(seen.provenance.observed_at)})` : "";
    return `${names[p]}: ${STATE_TEXT[state]}${price}${when}`;
  });
  const hidden = night?.hidden ? ["شب پنهان"] : [];
  return [faDay(day), ...said, ...hidden].join("؛ ");
}

/** The selected stay as nights: check-in inclusive, check-out exclusive. */
export function inStay(day: string, checkIn: string | null, checkOut: string | null): boolean {
  return checkIn !== null && checkOut !== null && day >= checkIn && day < checkOut;
}

/** The next selection after choosing ``day``: a new check-in, or the check-out after it. */
export function nextSelection(
  day: string,
  pending: string | null,
): { pending: string | null; range: [string, string] | null } {
  if (pending === null || day <= pending) return { pending: day, range: null };
  return { pending: null, range: [pending, day] };
}

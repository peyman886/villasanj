/** Persian formatting for measured values: percentages, intervals, ratios, durations. */

import type { Interval } from "@/lib/artifacts";

const percent1 = new Intl.NumberFormat("fa-IR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const percent0 = new Intl.NumberFormat("fa-IR", { style: "percent", maximumFractionDigits: 0 });
const decimal2 = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 });
const decimal3 = new Intl.NumberFormat("fa-IR", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const integer = new Intl.NumberFormat("fa-IR");
const dateTime = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Tehran",
});

export function faPercent(value: number | null | undefined, digits: 0 | 1 = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return (digits === 0 ? percent0 : percent1).format(value);
}

/** "۹۸٫۱٪ (۹۳٫۰ تا ۹۹٫۵٪)": the estimate with its 95% interval. */
export function faInterval(interval: Interval | null | undefined): string {
  if (!interval || interval.estimate === null) return "—";
  return `${percent1.format(interval.estimate)} (${percent1.format(interval.low).replace("٪", "")} تا ${percent1.format(interval.high)})`;
}

export function faRange(interval: Interval | null | undefined): string {
  if (!interval) return "—";
  return `${percent1.format(interval.low).replace("٪", "")} تا ${percent1.format(interval.high)}`;
}

export function faInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : integer.format(value);
}

export function faDecimal(value: number | null | undefined, digits: 2 | 3 = 2): string {
  if (value === null || value === undefined) return "—";
  return (digits === 3 ? decimal3 : decimal2).format(value);
}

export function faRatio(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${decimal2.format(value)}×`;
}

const dateOnly = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  day: "numeric",
  month: "long",
  timeZone: "Asia/Tehran",
});

export function faDate(iso: string): string {
  return dateOnly.format(new Date(iso));
}

export function faWhen(iso: string): string {
  return dateTime.format(new Date(iso));
}

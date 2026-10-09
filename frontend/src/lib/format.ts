/** Persian formatting for measured values: percentages, intervals, ratios, durations. */

import type { Interval } from "@/lib/artifacts";
import type { Locale } from "@/lib/i18n";

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
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return (digits === 0 ? percent0 : percent1).format(value);
}

/** "۹۸٫۱٪ (۹۳٫۰ تا ۹۹٫۵٪)": the estimate with its 95% interval. */
export function faInterval(interval: Interval | null | undefined): string {
  if (!interval || interval.estimate === null) return "-";
  return `${percent1.format(interval.estimate)} (${percent1.format(interval.low).replace("٪", "")} تا ${percent1.format(interval.high)})`;
}

export function faRange(interval: Interval | null | undefined): string {
  if (!interval) return "-";
  return `${percent1.format(interval.low).replace("٪", "")} تا ${percent1.format(interval.high)}`;
}

export function faInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : integer.format(value);
}

export function faDecimal(value: number | null | undefined, digits: 2 | 3 = 2): string {
  if (value === null || value === undefined) return "-";
  return (digits === 3 ? decimal3 : decimal2).format(value);
}

export function faRatio(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${decimal2.format(value)}×`;
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

// English counterparts for the English documentation (/en/docs): Latin digits, Gregorian dates.
const enPercent1 = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const enPercent0 = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });
const enDecimal2 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const enDecimal3 = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const enInteger = new Intl.NumberFormat("en-US");
const enDate = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Tehran",
});
const enDateTime = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Tehran",
});

export type Formatter = {
  percent: (value: number | null | undefined, digits?: 0 | 1) => string;
  interval: (interval: Interval | null | undefined) => string;
  range: (interval: Interval | null | undefined) => string;
  int: (value: number | null | undefined) => string;
  decimal: (value: number | null | undefined, digits?: 2 | 3) => string;
  ratio: (value: number | null | undefined) => string;
  date: (iso: string) => string;
  when: (iso: string) => string;
};

const FA: Formatter = {
  percent: faPercent,
  interval: faInterval,
  range: faRange,
  int: faInt,
  decimal: faDecimal,
  ratio: faRatio,
  date: faDate,
  when: faWhen,
};

const missing = (value: unknown) => value === null || value === undefined;

const EN: Formatter = {
  percent: (value, digits = 1) =>
    missing(value) || Number.isNaN(value)
      ? "-"
      : (digits === 0 ? enPercent0 : enPercent1).format(value as number),
  interval: (i) =>
    !i || i.estimate === null
      ? "-"
      : `${enPercent1.format(i.estimate)} (${enPercent1.format(i.low).replace("%", "")} to ${enPercent1.format(i.high)})`,
  range: (i) =>
    i ? `${enPercent1.format(i.low).replace("%", "")} to ${enPercent1.format(i.high)}` : "-",
  int: (value) => (missing(value) ? "-" : enInteger.format(value as number)),
  decimal: (value, digits = 2) =>
    missing(value) ? "-" : (digits === 3 ? enDecimal3 : enDecimal2).format(value as number),
  ratio: (value) => (missing(value) ? "-" : `${enDecimal2.format(value as number)}×`),
  date: (iso) => enDate.format(new Date(iso)),
  when: (iso) => enDateTime.format(new Date(iso)),
};

/** The formatter for a language: `const f = formatFor(locale); f.percent(0.98)`. */
export function formatFor(locale: Locale): Formatter {
  return locale === "en" ? EN : FA;
}

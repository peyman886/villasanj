/**
 * Every number the product pages show, formatted in one place (M12, ADR-0015).
 *
 * - Persian digits, «٬» (U+066C) between thousands and «٫» (U+066B) as the decimal mark.
 * - A lower bound («از») is rounded down and an upper bound up, so a short number never claims
 *   more than the data; a point value is rounded to the nearest.
 * - A stored range stays a range unless it is narrow ((max − min) / midpoint ≤ 0.15), when it is
 *   said as «حدود X» with the exact range in the tooltip (copy-and-numbers.md §3).
 *
 * No component formats a number on its own.
 */

import type { components } from "@/lib/api/schema";

export type Money = components["schemas"]["MoneyOut"];
export type Bound = "lower" | "upper" | "point";

const LATIN = /[0-9]/g;
const PERSIAN_ZERO = 0x06f0;

/** Latin digits to Persian ones; everything else untouched. */
export function faDigits(text: string): string {
  return text.replace(LATIN, (d) => String.fromCharCode(PERSIAN_ZERO + Number(d)));
}

const formats = new Map<number, Intl.NumberFormat>();

function format(digits: number): Intl.NumberFormat {
  let found = formats.get(digits);
  if (!found) {
    found = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: digits, useGrouping: true });
    formats.set(digits, found);
  }
  return found;
}

/** «۸٬۵۰۰٬۰۰۰», «۲۰٫۷»: at most ``digits`` decimals and never a trailing zero. */
export function faNum(value: number, digits = 0): string {
  return format(digits).format(value);
}

/** A share in [0, 1] as a percent: «۱۰۰٪», «۲۰٫۷٪» (no «۱۰۰٫۰٪»). */
export function faPct(share: number, digits = 1): string {
  return `${faNum(share * 100, digits)}٪`;
}

function rounded(value: number, step: number, bound: Bound): number {
  const units = value / step;
  // A tiny epsilon keeps 8.5 / 0.1 = 84.99999 from rounding down to 8.4.
  const whole =
    bound === "lower"
      ? Math.floor(units + 1e-9)
      : bound === "upper"
        ? Math.ceil(units - 1e-9)
        : Math.round(units);
  return whole * step;
}

const MILLION = 1_000_000;
const BILLION = 1_000_000_000;
const THOUSAND = 1_000;

/**
 * Toman in a short form for cards and headlines: «۸٫۵ میلیون تومان», «۸۵۰ هزار تومان».
 * One decimal of a million; ``bound`` decides the rounding direction.
 */
export function shortToman(toman: number, bound: Bound): string {
  if (toman >= BILLION) return `${faNum(rounded(toman / BILLION, 0.1, bound), 1)} میلیارد تومان`;
  if (toman >= MILLION) {
    const millions = rounded(toman / MILLION, 0.1, bound);
    if (millions >= 1) return `${faNum(millions, 1)} میلیون تومان`;
  }
  return `${faNum(rounded(toman / THOUSAND, 1, bound))} هزار تومان`;
}

/** The short amount without the currency, for tight rows: «۸٫۵ میلیون». */
export function shortAmount(toman: number, bound: Bound): string {
  return shortToman(toman, bound).replace(" تومان", "");
}

/** Millions with one decimal, rounded down (a calendar cell; the legend names the unit). */
export function millions(toman: number): string {
  return faNum(rounded(toman / MILLION, 0.1, "lower"), 1);
}

/** The map pin: «۸٫۵م» (always a lower bound, so rounded down). */
export function pinToman(toman: number): string {
  if (toman >= MILLION) return `${faNum(rounded(toman / MILLION, 0.1, "lower"), 1)}م`;
  return `${faNum(rounded(toman / THOUSAND, 1, "lower"))}ه`;
}

/** The exact amount for the booking card rows: «۸٬۵۴۰٬۰۰۰ تومان». */
export function fullToman(toman: number): string {
  return `${faNum(toman)} تومان`;
}

/** Whether an offer's total is only a lower bound (fees unknown) or a range. */
export function isExact(money: Money): boolean {
  return money.high_toman !== null && money.high_toman === money.low_toman;
}

/**
 * A price as the card shows it: «از ۸٫۵ میلیون تومان» when only the lower bound is known
 * (rounded down), the short point value when it is exact.
 */
export function priceFrom(money: Money): string {
  return isExact(money)
    ? shortToman(money.low_toman, "point")
    : `از ${shortToman(money.low_toman, "lower")}`;
}

/** The booking card: the exact low amount, with «از» when that is all we know. */
export function priceFull(money: Money): string {
  if (isExact(money)) return fullToman(money.low_toman);
  if (money.high_toman === null) return `از ${fullToman(money.low_toman)}`;
  return `${faNum(money.low_toman)} تا ${fullToman(money.high_toman)}`;
}

/** «نفری از ۲٫۱ میلیون»: a person's share of a lower-bound or exact total. */
export function perPerson(money: Money, people: number): string {
  const share = money.low_toman / people;
  const text = shortToman(share, isExact(money) ? "point" : "lower").replace(" تومان", "");
  return isExact(money) ? `نفری ${text}` : `نفری از ${text}`;
}

/** True when a range is narrow enough to say «حدود X» (copy-and-numbers.md §3). */
export function isNarrow(low: number, high: number): boolean {
  if (high < low) return isNarrow(high, low);
  const mid = (low + high) / 2;
  return mid === 0 ? high === low : (high - low) / mid <= 0.15;
}

/** Metres as a short distance: «۷۰۰ متر», «۱٫۵ کیلومتر». */
export function distance(metres: number, bound: Bound = "point"): string {
  if (metres < 1000) return `${faNum(rounded(metres, 50, bound))} متر`;
  return `${faNum(rounded(metres / 1000, 0.1, bound), 1)} کیلومتر`;
}

/** A distance range: «حدود ۷۰۰ متر» when narrow, else «۱٫۵ تا ۲٫۴ کیلومتر». */
export function distanceRange(low: number, high: number): string {
  if (isNarrow(low, high)) return `حدود ${distance((low + high) / 2)}`;
  if (low < 1000 && high >= 1000) {
    return `${distance(low, "lower")} تا ${distance(high, "upper")}`;
  }
  const [lo, hi] = [distance(low, "lower"), distance(high, "upper")];
  const unit = high < 1000 ? " متر" : " کیلومتر";
  return `${lo.replace(unit, "")} تا ${hi}`;
}

/** Minutes as a short duration: «۴۵ دقیقه», «۲ ساعت و ۱۵ دقیقه», «۴ ساعت». */
export function duration(minutes: number, bound: Bound = "point"): string {
  const step = minutes < 60 ? 5 : minutes < 180 ? 15 : 60;
  const total = Math.max(step, rounded(minutes, step, bound));
  const hours = Math.floor(total / 60);
  const rest = Math.round(total - hours * 60);
  if (hours === 0) return `${faNum(rest)} دقیقه`;
  return rest ? `${faNum(hours)} ساعت و ${faNum(rest)} دقیقه` : `${faNum(hours)} ساعت`;
}

/** A drive-time range in seconds: «حدود ۴ ساعت» when narrow, else «۲ تا ۳ ساعت». */
export function durationRange(lowSeconds: number, highSeconds: number): string {
  const [low, high] = [lowSeconds / 60, highSeconds / 60];
  if (isNarrow(low, high)) return `حدود ${duration((low + high) / 2)}`;
  return `${duration(low, "lower")} تا ${duration(high, "upper")}`;
}

/** Areas the listings state, as one compact value: «۲۲۰ تا ۳۰۰ متر» when they differ. */
export function areaText(values: (number | null | undefined)[]): string | null {
  const known = [...new Set(values.filter((v): v is number => typeof v === "number"))];
  if (known.length === 0) return null;
  const [low, high] = [Math.min(...known), Math.max(...known)];
  return low === high ? `${faNum(low)} متر` : `${faNum(low)} تا ${faNum(high)} متر`;
}

/** A rating on the 1–5 scale: «۴٫۸۹». */
export function rating(value: number): string {
  return faNum(Math.round(value * 100) / 100, 2);
}

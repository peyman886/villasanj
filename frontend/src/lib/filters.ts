/**
 * The search filter panel (M12): what the filters are, how they live in the URL, the chips they
 * become, and the live count. ``passes`` mirrors ``backend/src/villasanj/discovery/domain/filters.py``
 * rule for rule; both run the cases in ``backend/tests/fixtures/filter_cases.json``. The search
 * itself is always filtered on the server; this copy only counts while the panel is open.
 */

import type { components } from "@/lib/api/schema";
import { distance, faNum, shortAmount } from "@/lib/numbers";
import { FEATURE_TEXT } from "@/lib/search";

export type Facet = components["schemas"]["FacetOut"];
type FiltersIn = components["schemas"]["FiltersIn"];

export type Filters = {
  price_min?: number | undefined;
  price_max?: number | undefined;
  per_night?: boolean | undefined;
  bedrooms_min?: number | undefined;
  capacity_min?: number | undefined;
  features?: string[] | undefined;
  property_types?: string[] | undefined;
  platforms?: string[] | undefined;
  multi_platform?: boolean | undefined;
  instant?: boolean | undefined;
  rating_min?: number | undefined;
  coast_max_m?: number | undefined;
};

export const FEATURES = [
  "pool",
  "jacuzzi",
  "near_sea",
  "sea_view",
  "forest",
  "fireplace",
  "parking",
  "barbecue",
] as const;

/** The types the catalog holds, most common first (catalog.listing.property_type). */
export const PROPERTY_TYPES: [string, string][] = [
  ["villa", "ویلا"],
  ["cottage", "کلبه"],
  ["apartment", "آپارتمان"],
  ["suite", "سوئیت"],
  ["complex", "مجتمع"],
  ["ecotourism", "بوم‌گردی"],
  ["traditional", "خانه‌ی سنتی"],
];

export const PLATFORMS: [string, string][] = [
  ["jabama", "جاباما"],
  ["shab", "شب"],
];

export const RATINGS = [4.5, 4] as const;
export const SEA_DISTANCES = [500, 1000, 2000, 5000] as const;

// URL keys: short, readable, and never colliding with q, drop or area.
const KEYS = {
  price_min: "pmin",
  price_max: "pmax",
  per_night: "pn",
  bedrooms_min: "rooms",
  capacity_min: "cap",
  features: "amen",
  property_types: "type",
  platforms: "plat",
  multi_platform: "both",
  instant: "instant",
  rating_min: "rating",
  coast_max_m: "sea",
} as const satisfies Record<keyof Filters, string>;

type Params = Record<string, string | string[] | undefined>;

function one(params: Params, key: string): string | undefined {
  const v = params[key];
  return Array.isArray(v) ? v[0] : v;
}

function num(params: Params, key: string, min = 0, max = Infinity): number | undefined {
  const v = Number(one(params, key));
  return Number.isFinite(v) && v >= min && v <= max ? v : undefined;
}

function list(params: Params, key: string, allowed: readonly string[]): string[] | undefined {
  const raw = one(params, key);
  if (!raw) return undefined;
  const items = raw.split(",").filter((x) => allowed.includes(x));
  return items.length ? [...new Set(items)] : undefined;
}

/** Filters from the page's search params; anything malformed is ignored, never guessed. */
export function filtersFrom(params: Params): Filters {
  const f: Filters = {
    price_min: num(params, KEYS.price_min),
    price_max: num(params, KEYS.price_max),
    per_night: one(params, KEYS.per_night) === "1" || undefined,
    bedrooms_min: num(params, KEYS.bedrooms_min, 1, 20),
    capacity_min: num(params, KEYS.capacity_min, 1, 50),
    features: list(params, KEYS.features, FEATURES),
    property_types: list(
      params,
      KEYS.property_types,
      PROPERTY_TYPES.map(([k]) => k),
    ),
    platforms: list(
      params,
      KEYS.platforms,
      PLATFORMS.map(([k]) => k),
    ),
    multi_platform: one(params, KEYS.multi_platform) === "1" || undefined,
    instant: one(params, KEYS.instant) === "1" || undefined,
    rating_min: num(params, KEYS.rating_min, 0, 5),
    coast_max_m: num(params, KEYS.coast_max_m),
  };
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined)) as Filters;
}

/** The filters as URL params (in a fixed order, so equal filters give equal URLs). */
export function filterParams(f: Filters): [string, string][] {
  const out: [string, string][] = [];
  for (const [field, key] of Object.entries(KEYS) as [keyof Filters, string][]) {
    const v = f[field];
    if (v === undefined || v === false) continue;
    if (Array.isArray(v)) {
      if (v.length) out.push([key, v.join(",")]);
    } else out.push([key, v === true ? "1" : String(v)]);
  }
  return out;
}

/** The filters as the search API takes them (only the fields that are set). */
export function filtersBody(f: Filters): FiltersIn {
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined)) as FiltersIn;
}

export function isEmpty(f: Filters): boolean {
  return filterParams(f).length === 0;
}

export function activeCount(f: Filters): number {
  return filterParams(f).length;
}

function price(row: Facet, perNight: boolean): number | null {
  if (row.total_toman === null) return null;
  return perNight ? row.total_toman / Math.max(1, row.nights) : row.total_toman;
}

/** The same rule as the server's ``passes`` (shared cases in filter_cases.json). */
export function passes(row: Facet, f: Filters): boolean {
  const p = price(row, f.per_night ?? false);
  return (
    (f.price_min === undefined || (p !== null && p >= f.price_min)) &&
    (f.price_max === undefined || (p !== null && p <= f.price_max)) &&
    (f.bedrooms_min === undefined || (row.bedrooms !== null && row.bedrooms >= f.bedrooms_min)) &&
    (f.capacity_min === undefined ||
      (row.max_capacity !== null && row.max_capacity >= f.capacity_min)) &&
    (f.features ?? []).every((x) => row.features.includes(x)) &&
    (!f.property_types?.length ||
      (row.property_type !== null && f.property_types.includes(row.property_type))) &&
    (!f.platforms?.length || f.platforms.includes(row.platform)) &&
    (!f.multi_platform || row.multi_platform) &&
    (!f.instant || row.instant === true) &&
    (f.rating_min === undefined || (row.rating !== null && row.rating >= f.rating_min)) &&
    (f.coast_max_m === undefined || (row.coast_low_m !== null && row.coast_low_m <= f.coast_max_m))
  );
}

/** Villas that would show: one card per villa. */
export function villasPassing(rows: Facet[], f: Filters): number {
  return new Set(rows.filter((r) => passes(r, f)).map((r) => r.villa)).size;
}

/** How many villas a single option would add to the current filters (for the quick tiles). */
export function countWith(rows: Facet[], f: Filters, change: Filters): number {
  return villasPassing(rows, { ...f, ...change });
}

export type Histogram = { min: number; max: number; bins: number[]; step: number };

/** Price spread of the listings left by every other filter (rounded to a clean step). */
export function histogram(rows: Facet[], f: Filters, bins = 24): Histogram | null {
  const perNight = f.per_night ?? false;
  const others: Filters = { ...f, price_min: undefined, price_max: undefined };
  const prices = rows
    .filter((r) => passes(r, others))
    .map((r) => price(r, perNight))
    .filter((p): p is number => p !== null)
    .sort((a, b) => a - b);
  if (prices.length === 0) return null;
  const unit = perNight ? 100_000 : 500_000;
  const min = Math.floor((prices[0] ?? 0) / unit) * unit;
  // The top 2% are folded into the last bar so one outlier does not flatten the rest.
  const top = prices[Math.min(prices.length - 1, Math.floor(prices.length * 0.98))] ?? min;
  const max = Math.max(min + unit, Math.ceil(top / unit) * unit);
  const step = (max - min) / bins;
  const counts = Array.from({ length: bins }, () => 0);
  for (const p of prices) {
    const i = Math.min(bins - 1, Math.max(0, Math.floor((p - min) / step)));
    counts[i] = (counts[i] ?? 0) + 1;
  }
  return { min, max, bins: counts, step };
}

export type FilterChip = { key: string; text: string; without: Filters };

/** One removable chip per active filter, in the panel's own words. */
export function filterChips(f: Filters): FilterChip[] {
  const chips: FilterChip[] = [];
  const drop = (patch: Filters): Filters => ({ ...f, ...patch });
  const per = f.per_night ? " هر شب" : "";
  if (f.price_min !== undefined || f.price_max !== undefined) {
    const lo = f.price_min !== undefined ? shortAmount(f.price_min, "point") : null;
    const hi = f.price_max !== undefined ? shortAmount(f.price_max, "point") : null;
    const text = lo && hi ? `${lo} تا ${hi}` : lo ? `از ${lo}` : `تا ${hi}`;
    chips.push({
      key: "price",
      text: `قیمت${per} ${text} تومان`,
      without: drop({ price_min: undefined, price_max: undefined, per_night: undefined }),
    });
  }
  if (f.bedrooms_min !== undefined) {
    chips.push({
      key: "rooms",
      text: `دست‌کم ${faNum(f.bedrooms_min)} خواب`,
      without: drop({ bedrooms_min: undefined }),
    });
  }
  if (f.capacity_min !== undefined) {
    chips.push({
      key: "cap",
      text: `ظرفیت ${faNum(f.capacity_min)} نفر به بالا`,
      without: drop({ capacity_min: undefined }),
    });
  }
  for (const x of f.features ?? []) {
    chips.push({
      key: `amen:${x}`,
      text: FEATURE_TEXT[x] ?? x,
      without: drop({ features: (f.features ?? []).filter((y) => y !== x) }),
    });
  }
  for (const x of f.property_types ?? []) {
    chips.push({
      key: `type:${x}`,
      text: PROPERTY_TYPES.find(([k]) => k === x)?.[1] ?? x,
      without: drop({ property_types: (f.property_types ?? []).filter((y) => y !== x) }),
    });
  }
  for (const x of f.platforms ?? []) {
    chips.push({
      key: `plat:${x}`,
      text: `فقط ${PLATFORMS.find(([k]) => k === x)?.[1] ?? x}`,
      without: drop({ platforms: (f.platforms ?? []).filter((y) => y !== x) }),
    });
  }
  if (f.multi_platform) {
    chips.push({
      key: "both",
      text: "در هر دو پلتفرم",
      without: drop({ multi_platform: undefined }),
    });
  }
  if (f.instant) {
    chips.push({ key: "instant", text: "رزرو آنی", without: drop({ instant: undefined }) });
  }
  if (f.rating_min !== undefined) {
    chips.push({
      key: "rating",
      text: `امتیاز ${faNum(f.rating_min, 1)} به بالا`,
      without: drop({ rating_min: undefined }),
    });
  }
  if (f.coast_max_m !== undefined) {
    chips.push({
      key: "sea",
      text: `تا ${distance(f.coast_max_m)} از دریا`,
      without: drop({ coast_max_m: undefined }),
    });
  }
  return chips;
}

/** Gold-set labelling: API shapes, keyboard shortcuts and Persian formatting (ADR-0009). */

export type Label = "match" | "non_match" | "unsure";

export const LABELS: readonly Label[] = ["match", "non_match", "unsure"];

export type ListingCard = {
  id: string;
  platform: string;
  platform_name: string;
  url: string;
  title: string;
  description: string | null;
  property_type: string | null;
  city: string | null;
  locality: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  area_m2: number | null;
  base_capacity: number | null;
  max_capacity: number | null;
  base_price_toman: number | null;
  rating: number | null;
  rating_count: number | null;
  photos: string[];
};

export type Distance = { centre_m: number; min_m: number; max_m: number | null };

export type LabelTask = {
  queue: string;
  position: number;
  total: number;
  labeled: number;
  pair: string;
  current_label: Label | null;
  left: ListingCard;
  right: ListingCard;
  distance: Distance | null;
};

export const LABEL_TEXT: Record<Label, string> = {
  match: "همان ویلاست",
  non_match: "ویلای دیگری است",
  unsure: "مطمئن نیستم",
};

/** Physical keys, so shortcuts work whether the keyboard layout is Persian or English. */
export const LABEL_KEYS: Record<string, Label> = {
  KeyM: "match",
  KeyN: "non_match",
  KeyU: "unsure",
};

export type Shortcut = { kind: "label"; label: Label } | { kind: "previous" } | { kind: "next" };

type KeyLike = {
  code: string;
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  repeat: boolean;
};

/** The page reads right to left, so ArrowLeft moves forward and ArrowRight moves back. */
export function shortcutFor(event: KeyLike): Shortcut | null {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat) return null;
  const label = LABEL_KEYS[event.code];
  if (label) return { kind: "label", label };
  if (event.code === "ArrowLeft") return { kind: "next" };
  if (event.code === "ArrowRight") return { kind: "previous" };
  return null;
}

/** Property types as the platforms publish them (seen in the 2026-10-01 crawl). */
const PROPERTY_TYPES: Record<string, string> = {
  villa: "ویلا",
  cottage: "کلبه",
  apartment: "آپارتمان",
  suite: "سوئیت",
  complex: "مجتمع",
  ecotourism: "بوم‌گردی",
  boomgardi: "بوم‌گردی",
  traditional: "خانه‌ی سنتی",
  inn: "مسافرخانه",
};

export function faPropertyType(value: string | null): string {
  if (value === null) return "نامشخص";
  return PROPERTY_TYPES[value] ?? value;
}

const numberFormat = new Intl.NumberFormat("fa-IR");

export function faNumber(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined) return "نامشخص";
  return `${numberFormat.format(value)}${suffix}`;
}

export function faDistance(distance: Distance | null): string {
  if (distance === null) return "موقعیت یکی از دو آگهی منتشر نشده است";
  const centre = `فاصله‌ی نقطه‌های منتشرشده ${faNumber(Math.round(distance.centre_m))} متر`;
  if (distance.min_m === distance.centre_m) return centre;
  return `${centre}؛ با احتساب شعاع ابهام، دست‌کم ${faNumber(Math.round(distance.min_m))} متر`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isCard(value: unknown): value is ListingCard {
  return (
    isObject(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.url === "string" &&
    Array.isArray(value.photos)
  );
}

export function isLabelTask(value: unknown): value is LabelTask {
  return (
    isObject(value) &&
    typeof value.pair === "string" &&
    typeof value.position === "number" &&
    typeof value.total === "number" &&
    typeof value.labeled === "number" &&
    (value.current_label === null || LABELS.includes(value.current_label as Label)) &&
    isCard(value.left) &&
    isCard(value.right)
  );
}

export type TaskResult = { kind: "ready"; task: LabelTask } | { kind: "done" } | { kind: "error" };

/** One labelling task from the API (server side) or the same-origin proxy (browser). */
export async function fetchTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<TaskResult> {
  const params = new URLSearchParams({ labeler });
  if (position !== undefined) params.set("position", String(position));
  try {
    const response = await fetch(
      `${baseUrl}/er/queues/${encodeURIComponent(queue)}/task?${params}`,
      { cache: "no-store", signal: AbortSignal.timeout(10_000) },
    );
    if (response.status === 204) return { kind: "done" };
    const body: unknown = await response.json();
    return response.ok && isLabelTask(body) ? { kind: "ready", task: body } : { kind: "error" };
  } catch {
    return { kind: "error" };
  }
}

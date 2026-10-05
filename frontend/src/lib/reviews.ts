/** The owner's remaining reviews (M8): the query set, search relevance, and the hub's progress. */

import type { components } from "@/lib/api/schema";

import { faNumber } from "@/lib/listing";
import { FEATURE_TEXT } from "@/lib/search";

export type QueryReviewTask = components["schemas"]["QueryReviewTaskOut"];
export type RelevanceTask = components["schemas"]["RelevanceTaskOut"];
export type RelevanceItem = components["schemas"]["RelevanceItemOut"];
export type QueueProgress = components["schemas"]["QueueProgressOut"];

export type Fetched<T> = { kind: "ready"; value: T } | { kind: "missing" } | { kind: "error" };

async function getJson<T>(url: string): Promise<Fetched<T>> {
  try {
    const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    if (response.status === 404) return { kind: "missing" };
    if (!response.ok) return { kind: "error" };
    return { kind: "ready", value: (await response.json()) as T };
  } catch {
    return { kind: "error" };
  }
}

function query(params: Record<string, string | number | undefined>): string {
  const out = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) out.set(key, String(value));
  }
  return out.toString();
}

export function fetchQueryReviewTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<Fetched<QueryReviewTask>> {
  return getJson(`${baseUrl}/reviews/queries/task?${query({ queue, labeler, position })}`);
}

export function fetchRelevanceTask(
  baseUrl: string,
  queue: string,
  labeler: string,
  position?: number,
): Promise<Fetched<RelevanceTask>> {
  return getJson(`${baseUrl}/reviews/relevance/task?${query({ queue, labeler, position })}`);
}

export function fetchReviewProgress(baseUrl: string): Promise<Fetched<QueueProgress[]>> {
  return getJson(`${baseUrl}/reviews/progress`);
}

type KeyLike = { code: string; altKey: boolean; ctrlKey: boolean; metaKey: boolean };

const noModifier = (event: KeyLike) => !(event.altKey || event.ctrlKey || event.metaKey);

/** Physical keys, so a Persian layout works too: Y correct, N needs a fix. */
export function queryVerdictFor(event: KeyLike): boolean | null {
  if (!noModifier(event)) return null;
  if (event.code === "KeyY") return true;
  if (event.code === "KeyN") return false;
  return null;
}

/** 0, 1, 2 on the digit row or the keypad. */
export function gradeFor(event: KeyLike): 0 | 1 | 2 | null {
  if (!noModifier(event)) return null;
  const digit = /^(?:Digit|Numpad)([0-2])$/.exec(event.code)?.[1];
  return digit === undefined ? null : (Number(digit) as 0 | 1 | 2);
}

export const GRADE_TEXT: Record<0 | 1 | 2, string> = {
  2: "مرتبط",
  1: "تا حدی",
  0: "نامرتبط",
};

const MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];
const WEEKDAYS: Record<string, string> = {
  saturday: "شنبه",
  sunday: "یکشنبه",
  monday: "دوشنبه",
  tuesday: "سه‌شنبه",
  wednesday: "چهارشنبه",
  thursday: "پنجشنبه",
  friday: "جمعه",
};
const WHICH: Record<string, string> = { this: "این", next: "بعد", after_next: "بعد از بعد" };
const DATE_KIND: Record<string, string> = {
  tonight: "امشب",
  tomorrow: "فردا",
  day_after_tomorrow: "پس‌فردا",
  nowruz: "نوروز",
  next_holiday: "تعطیلات بعدی",
};
const BASIS: Record<string, string> = {
  per_night: "هر شب",
  whole_stay: "کل اقامت",
  unknown: "مبنا گفته نشده",
};
const PARTY: Record<string, string> = { solo: "یک نفر", couple: "زوج" };

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function dateText(dates: Json): string {
  const kind = String(dates.kind);
  const which = typeof dates.which === "string" ? WHICH[dates.which] : undefined;
  const year = typeof dates.year === "number" ? ` ${faNumber(dates.year)}` : "";
  const month = typeof dates.month === "number" ? MONTHS[dates.month - 1] : undefined;
  switch (kind) {
    case "weekend":
      return which === undefined || which === "این" ? "این آخر هفته" : `آخر هفته‌ی ${which}`;
    case "weekday": {
      const day = typeof dates.weekday === "string" ? WEEKDAYS[dates.weekday] : "روز هفته";
      return `${day} ${which === "این" || which === undefined ? "همین هفته" : `هفته‌ی ${which}`}`;
    }
    case "jalali_day":
      return `${typeof dates.day === "number" ? faNumber(dates.day) : "؟"} ${month ?? "؟"}${year}`;
    case "jalali_month":
      return `ماه ${month ?? "؟"}${year}`;
    case "nowruz":
      return `نوروز${year}`;
    default:
      return DATE_KIND[kind] ?? kind;
  }
}

/** A SearchIntent as Persian rows (what the drafted case expects the system to understand). */
export function intentRows(intent: Record<string, unknown>): [string, string][] {
  const rows: [string, string][] = [];
  if (isObject(intent.dates)) rows.push(["تاریخ", dateText(intent.dates)]);
  if (typeof intent.nights === "number") rows.push(["شب‌ها", faNumber(intent.nights)]);
  if (Array.isArray(intent.guest_parts) && intent.guest_parts.length) {
    const parts = intent.guest_parts.map((n) => faNumber(Number(n)));
    rows.push(["نفرات", parts.join(" + ")]);
  }
  if (typeof intent.party === "string") rows.push(["گروه", PARTY[intent.party] ?? intent.party]);
  if (typeof intent.bedrooms_min === "number") {
    rows.push(["اتاق خواب", `دست‌کم ${faNumber(intent.bedrooms_min)}`]);
  }
  if (isObject(intent.budget)) {
    const max = Number(intent.budget.max_toman);
    const basis = BASIS[String(intent.budget.basis ?? "unknown")] ?? String(intent.budget.basis);
    rows.push(["بودجه", `تا ${faNumber(max)} تومان (${basis})`]);
  }
  if (isObject(intent.max_drive)) {
    const unit = intent.max_drive.unit === "hours" ? "ساعت" : "دقیقه";
    rows.push(["رانندگی از تهران", `حداکثر ${faNumber(Number(intent.max_drive.value))} ${unit}`]);
  }
  if (Array.isArray(intent.places) && intent.places.length) {
    rows.push(["مکان", intent.places.map(String).join("، ")]);
  }
  if (Array.isArray(intent.features) && intent.features.length) {
    rows.push([
      "امکانات",
      intent.features.map((f) => FEATURE_TEXT[String(f)] ?? String(f)).join("، "),
    ]);
  }
  if (Array.isArray(intent.unhandled) && intent.unhandled.length) {
    rows.push(["خواسته‌های بیرون از فیلدها", intent.unhandled.map(String).join("، ")]);
  }
  return rows;
}

/** The hub's description of each queue, in the order the owner should work through them. */
export const QUEUES: {
  queue: string;
  title: string;
  href: string;
  description: string;
  unit: string;
  open: boolean; // still needed for a criterion or the product
}[] = [
  {
    queue: "queries-v1",
    title: "بازبینی مجموعه‌ی ۵۰ پرسش جستجو",
    href: "/label/queries",
    description:
      "برای هر پرسش، برداشتی که باید از آن فهمیده شود نوشته شده است. درست است یا اصلاح لازم دارد؟ معیار ۱ از M8 تا پایان این بازبینی موقت است.",
    unit: "پرسش",
    open: true,
  },
  {
    queue: "relevance-v1",
    title: "داوری مرتبط‌بودن نتیجه‌ها برای ۳۰ پرسش",
    href: "/label/relevance",
    description:
      "برای هر پرسش، ویلاهای چند رتبه‌بندی بدون رتبه و بدون نام سیستم آمده‌اند. هر کدام مرتبط، تا حدی یا نامرتبط است؟ معیار ۲ از M8 با این داوری سنجیده می‌شود.",
    unit: "پرسش",
    open: true,
  },
  {
    queue: "er-human",
    title: "صف انسانی تطبیق ویلاها (er-human)",
    href: "/label?queue=er-human",
    description:
      "جفت‌هایی که داور مدل‌زبانی پیشنهاد داده یا درباره‌شان مطمئن نیست. اول ۸۳ پیشنهاد «یکی است»: هر تأیید یک ادغام تازه با دقت تأییدشده است. هر برچسب ویلاها را دوباره می‌سازد.",
    unit: "جفت",
    open: true,
  },
  {
    queue: "gold-v1",
    title: "gold set تطبیق ویلاها",
    href: "/label?queue=gold-v1",
    description: "۳۶۲ جفت طبقه‌بندی‌شده که دقت و بازیابی تطبیق با آن‌ها سنجیده می‌شود.",
    unit: "جفت",
    open: false,
  },
  {
    queue: "photos-v1",
    title: "برچسب عکس‌ها",
    href: "/label/photos",
    description: "برچسب امکانات روی عکس‌ها؛ آستانه‌ی هر برچسب تصویری از این‌ها آمده است.",
    unit: "عکس",
    open: false,
  },
  {
    queue: "claims-v1",
    title: "ادعاهای توضیحات",
    href: "/label/claims",
    description: "امکاناتی که توضیح هر آگهی ادعا می‌کند؛ دقت و بازیابی استخراج ادعا.",
    unit: "توضیح",
    open: false,
  },
  {
    queue: "summaries-v1",
    title: "بازبینی کور خلاصه‌ی نظرها",
    href: "/label/summaries",
    description: "آیا خلاصه به نظرها وفادار است؟ نتیجه: ۲۰ از ۲۰.",
    unit: "خلاصه",
    open: false,
  },
];

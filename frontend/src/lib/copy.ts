/**
 * The product's words for its recurring ideas, in one place (docs/ux/copy-and-numbers.md §1).
 * Components take these strings instead of writing their own, and the E2E suite asserts that the
 * words on the left of that table never appear (FORBIDDEN).
 */

/** The name and the one line said about it (home, metadata, README and the docs share these). */
export const BRAND = {
  name: "ویلاسنج",
  tagline: "قبل از رزرو، بسنجید",
  description:
    "ویلاسنج آگهی‌های یک ویلا را در جاباما و شب پیدا می‌کند و قیمت، تقویم و نظرهایش را کنار هم نشان می‌دهد؛ هر عدد با منبعش.",
  en: {
    name: "Villasanj",
    tagline: "Compare before you book",
    description:
      "Villasanj finds the same villa on Jabama and Shab and shows its prices, calendar and reviews side by side, every number with its source.",
  },
} as const;

export const COPY = {
  from: "از",
  platforms: "پلتفرم‌ها",
  cheaper: "ارزان‌تر",
  unavailable: "ناموجود",
  hiddenNight: "شب پنهان",
  notSeen: "هنوز این روز را ندیده‌ایم",
  twoValues: "دو عدد متفاوت",
  verified: "تأیید شد",
  notVerified: "تأیید نشد",
  mapDisagrees: "با نقشه نمی‌خواند",
  compareOffers: "مقایسه‌ی پیشنهادها",
  aboutRanking: "درباره‌ی رتبه‌بندی",
  whyFirst: "چرا این گزینه اول است؟",
  bestMatch: "بهترین تطابق",
  samplePrices: "قیمت‌های نمونه",
  whySure: "چرا مطمئنیم؟",
  /** Said exactly once on the search page, under the results header. */
  feeSearch: "قیمت‌ها بدون کارمزد پلتفرم‌اند؛ برای همین «از» نوشته‌ایم.",
  /** Said exactly once on the villa page, under the platform rows of the booking card. */
  feeVilla:
    "هیچ‌کدام از دو پلتفرم کارمزدش را منتشر نمی‌کند؛ برای همین قیمت‌ها «از» هستند و مبلغ نهایی را در خود پلتفرم ببینید.",
  refreshFailed: "الان نتوانستیم به‌روز کنیم.",
} as const;

/** «دیدن در جاباما ↗»: leaving for a platform (we never book). */
export function seeOn(platformName: string): string {
  return `دیدن در ${platformName} ↗`;
}

/** «یک ویلا در ۲ آگهی». */
export function oneVillaIn(listings: string): string {
  return `یک ویلا در ${listings} آگهی`;
}

/** «در ۲ پلتفرم» or «در جاباما». */
export function onPlatforms(count: string, onlyName?: string): string {
  return onlyName ? `در ${onlyName}` : `در ${count} پلتفرم`;
}

/** «قیمتِ ۳ روز پیش»: an observation's age, never a «قدیمی» badge. */
export function priceAge(age: string): string {
  return `قیمتِ ${age}`;
}

/** Strings the redesigned pages must never show (asserted on /, /search and the demo villa). */
export const FORBIDDEN = [
  "حداقل",
  "قیمت نهایی",
  "پر یا بسته",
  "رزرو شده",
  "رزروشده",
  "۱۰۰/۰٪",
  "۱۰۰٫۰٪",
  "هر نفر نفری",
  "ناهمخوان",
  "قدیمی",
] as const;

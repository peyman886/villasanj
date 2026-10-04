/** The documentation portal's pages, in reading order (sidebar, breadcrumbs, previous/next). */

export type DocPage = { href: string; title: string; summary: string };
export type DocGroup = { title: string; pages: DocPage[] };

export const DOCS_NAV: DocGroup[] = [
  {
    title: "شروع",
    pages: [
      {
        href: "/docs",
        title: "نمای کلی",
        summary: "ویلاسنج در یک نگاه: وضعیت، سنجه‌ها و راه‌های ورود",
      },
      {
        href: "/docs/overview",
        title: "خلاصه‌ی اجرایی",
        summary: "مسئله، هدف، دامنه‌ی چالش و محدودیت‌ها",
      },
      {
        href: "/docs/demo",
        title: "راهنمای دمو و بازبین",
        summary: "مسیر بازبینی، دموی آفلاین و سناریوی ۵ دقیقه‌ای",
      },
    ],
  },
  {
    title: "معماری و داده",
    pages: [
      {
        href: "/docs/architecture",
        title: "معماری",
        summary: "معماری شش‌ضلعی، bounded contextها، جریان داده و مدل منبع",
      },
      {
        href: "/docs/catalog-ingestion",
        title: "جمع‌آوری و کاتالوگ",
        summary: "crawl اخلاقی، snapshot، نرمال‌سازی و خط لوله‌ی عکس",
      },
      {
        href: "/docs/geo",
        title: "داده‌ی جغرافیایی",
        summary: "PostGIS، خط ساحل، POI، OSRM و نقشه‌ی آفلاین",
      },
    ],
  },
  {
    title: "هسته‌ی محصول",
    pages: [
      {
        href: "/docs/entity-resolution",
        title: "تطبیق ویلاها",
        summary: "از آگهی‌ها تا ویلای واقعی: blocking، ارزیابی، داور و صف انسانی",
      },
      {
        href: "/docs/pricing",
        title: "قیمت و تقویم",
        summary: "پیشنهاد نهایی با منبع، بازه‌ها و تقویم یکپارچه",
      },
      {
        href: "/docs/search-ranking",
        title: "جستجو و رتبه‌بندی",
        summary: "فهم پرسش، محافظ‌ها، رتبه‌بندی شفاف و توضیح",
      },
      {
        href: "/docs/truth-check",
        title: "حقیقت‌سنجی",
        summary: "ادعاهای فاصله و امکانات، شاهد عکس و ناهمخوانی بین پلتفرم‌ها",
      },
      {
        href: "/docs/reviews",
        title: "نظرها و خلاصه‌ها",
        summary: "خلاصه‌ی با ارجاع و بررسی ارجاع‌ها",
      },
    ],
  },
  {
    title: "مدل‌ها و کیفیت",
    pages: [
      {
        href: "/docs/llm",
        title: "مدل‌های زبانی",
        summary: "مسیریابی، کش، دفتر هزینه، برآورد و حالت آفلاین",
      },
      {
        href: "/docs/evaluation",
        title: "ارزیابی و فرضیه‌ها",
        summary: "H1 تا H5 و همه‌ی آزمایش‌ها با بازه‌ی اطمینان",
      },
      { href: "/docs/quality", title: "تست و کیفیت", summary: "هرم تست، دسترسی‌پذیری و کارایی" },
    ],
  },
  {
    title: "وضعیت پروژه",
    pages: [
      { href: "/docs/milestones", title: "مایل‌استون‌ها", summary: "هر معیار پذیرش با شاهدش" },
      {
        href: "/docs/decisions",
        title: "تصمیم‌ها (ADR)",
        summary: "۱۴ تصمیم معماری و اصلاحیه‌هایشان",
      },
      {
        href: "/docs/limitations",
        title: "محدودیت‌ها و کارهای باز",
        summary: "آنچه پاس نشده، به تعویق افتاده یا به مالک نیاز دارد",
      },
      {
        href: "/docs/reports",
        title: "گزارش‌های تولیدشده",
        summary: "همه‌ی گزارش‌ها با منبع و فرمان تولید",
      },
    ],
  },
];

export const DOCS_PAGES: DocPage[] = DOCS_NAV.flatMap((group) => group.pages);

export function neighbours(href: string): { previous?: DocPage; next?: DocPage } {
  const index = DOCS_PAGES.findIndex((p) => p.href === href);
  if (index < 0) return {};
  return {
    ...(index > 0 ? { previous: DOCS_PAGES[index - 1] } : {}),
    ...(index < DOCS_PAGES.length - 1 ? { next: DOCS_PAGES[index + 1] } : {}),
  };
}

/** The page a path belongs to (an ADR or a report belongs to its index page). */
export function pageOf(path: string): DocPage | undefined {
  return (
    DOCS_PAGES.find((p) => p.href === path) ??
    [...DOCS_PAGES].filter((p) => p.href !== "/docs" && path.startsWith(`${p.href}/`)).pop()
  );
}

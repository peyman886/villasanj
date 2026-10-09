/**
 * The documentation portal's pages, in reading order (sidebar, breadcrumbs, previous/next), in
 * both languages. A page lives at /docs/<slug> (Persian) and /en/docs/<slug> (English).
 */

import { docsRoot, type Locale } from "@/lib/i18n";

type Text = { fa: string; en: string };
type PageDef = { slug: string; title: Text; summary: Text };
type GroupDef = { title: Text; pages: PageDef[] };

export type DocPage = { href: string; slug: string; title: string; summary: string };
export type DocGroup = { title: string; pages: DocPage[] };

const NAV: GroupDef[] = [
  {
    title: { fa: "شروع", en: "Start here" },
    pages: [
      {
        slug: "",
        title: { fa: "نمای کلی", en: "Overview" },
        summary: {
          fa: "ویلاسنج در یک نگاه: وضعیت، سنجه‌ها و راه‌های ورود",
          en: "Villasanj at a glance: status, headline numbers and where to start",
        },
      },
      {
        slug: "overview",
        title: { fa: "خلاصه‌ی اجرایی", en: "Executive summary" },
        summary: {
          fa: "مسئله، هدف، دامنه‌ی چالش و محدودیت‌ها",
          en: "The problem, the goal, the challenge's scope and its limits",
        },
      },
      {
        slug: "demo",
        title: { fa: "راهنمای دمو و بازبینی", en: "Demo and review guide" },
        summary: {
          fa: "مسیر بازبینی، دموی آفلاین و سناریوی ۵ دقیقه‌ای",
          en: "A review path, the offline demo and the five-minute script",
        },
      },
    ],
  },
  {
    title: { fa: "معماری و داده", en: "Architecture and data" },
    pages: [
      {
        slug: "architecture",
        title: { fa: "معماری", en: "Architecture" },
        summary: {
          fa: "معماری شش‌ضلعی، زمینه‌های مستقل، جریان داده و مدل منبع",
          en: "Hexagonal architecture, bounded contexts, data flow and provenance",
        },
      },
      {
        slug: "catalog-ingestion",
        title: { fa: "جمع‌آوری و کاتالوگ", en: "Crawling and catalog" },
        summary: {
          fa: "خزش مسئولانه، snapshot، یکدست‌سازی داده و خط لوله‌ی عکس",
          en: "Polite crawling, snapshots, normalisation and the photo pipeline",
        },
      },
      {
        slug: "geo",
        title: { fa: "داده‌ی جغرافیایی", en: "Geodata" },
        summary: {
          fa: "PostGIS، خط ساحل، نقاط دیدنی، OSRM و نقشه‌ی آفلاین",
          en: "PostGIS, the coastline, points of interest, OSRM and the offline map",
        },
      },
    ],
  },
  {
    title: { fa: "هسته‌ی محصول", en: "Product core" },
    pages: [
      {
        slug: "entity-resolution",
        title: { fa: "تطبیق ویلاها", en: "Entity resolution" },
        summary: {
          fa: "از آگهی‌ها تا ویلای واقعی: blocking، ارزیابی، داور و صف انسانی",
          en: "From listings to real villas: blocking, evaluation, the judge and the human queue",
        },
      },
      {
        slug: "pricing",
        title: { fa: "قیمت و تقویم", en: "Prices and calendar" },
        summary: {
          fa: "قیمت هر پلتفرم با منبع، بازه‌ها و تقویم یکپارچه",
          en: "Each platform's sourced price, ranges and the merged calendar",
        },
      },
      {
        slug: "search-ranking",
        title: { fa: "جستجو و رتبه‌بندی", en: "Search and ranking" },
        summary: {
          fa: "فهم پرسش، محافظ‌ها، رتبه‌بندی شفاف و توضیح",
          en: "Query understanding, guardrails, transparent ranking and the explanation",
        },
      },
      {
        slug: "truth-check",
        title: { fa: "راستی‌آزمایی", en: "Truth check" },
        summary: {
          fa: "ادعاهای فاصله و امکانات، شاهد عکس و تفاوت پلتفرم‌ها",
          en: "Distance and amenity claims, photo evidence and cross-platform differences",
        },
      },
      {
        slug: "reviews",
        title: { fa: "نظرها و خلاصه‌ها", en: "Reviews and summaries" },
        summary: {
          fa: "خلاصه‌ی نظرها با ارجاع، و بررسی ارجاع‌ها",
          en: "Review summaries with citations, and how the citations are checked",
        },
      },
    ],
  },
  {
    title: { fa: "مدل‌ها و کیفیت", en: "Models and quality" },
    pages: [
      {
        slug: "llm",
        title: { fa: "مدل‌های زبانی", en: "Language models" },
        summary: {
          fa: "مسیریابی، کش، دفتر هزینه، برآورد و حالت آفلاین",
          en: "Routing, caching, the cost ledger, dry runs and offline mode",
        },
      },
      {
        slug: "evaluation",
        title: { fa: "ارزیابی و فرضیه‌ها", en: "Evaluation and hypotheses" },
        summary: {
          fa: "H1 تا H5 و همه‌ی آزمایش‌ها با بازه‌ی اطمینان",
          en: "H1 to H5 and every experiment, with confidence intervals",
        },
      },
      {
        slug: "quality",
        title: { fa: "تست و کیفیت", en: "Testing and quality" },
        summary: {
          fa: "هرم تست، دسترس‌پذیری و کارایی",
          en: "The test pyramid, accessibility and performance",
        },
      },
    ],
  },
  {
    title: { fa: "وضعیت پروژه", en: "Project status" },
    pages: [
      {
        slug: "milestones",
        title: { fa: "مایل‌استون‌ها", en: "Milestones" },
        summary: {
          fa: "هر معیار پذیرش با شاهدش",
          en: "Every acceptance criterion with its evidence",
        },
      },
      {
        slug: "decisions",
        title: { fa: "تصمیم‌های معماری", en: "Decisions (ADRs)" },
        summary: {
          fa: "۱۵ تصمیم معماری و اصلاحیه‌هایشان",
          en: "Fifteen architecture decisions and their amendments",
        },
      },
      {
        slug: "limitations",
        title: { fa: "محدودیت‌ها و کارهای باز", en: "Limitations and open work" },
        summary: {
          fa: "آنچه باز مانده، آنچه مالک بست، و محدودیت روش‌ها",
          en: "What is open, what the owner closed, and the methods' limits",
        },
      },
      {
        slug: "reports",
        title: { fa: "گزارش‌های تولیدشده", en: "Generated reports" },
        summary: {
          fa: "همه‌ی گزارش‌ها با منبع و فرمان تولید",
          en: "Every report with its source and the command that produced it",
        },
      },
    ],
  },
];

function hrefOf(slug: string, locale: Locale): string {
  return slug ? `${docsRoot(locale)}/${slug}` : docsRoot(locale);
}

/** The navigation in one language. */
export function docsNav(locale: Locale): DocGroup[] {
  return NAV.map((group) => ({
    title: group.title[locale],
    pages: group.pages.map((p) => ({
      href: hrefOf(p.slug, locale),
      slug: p.slug,
      title: p.title[locale],
      summary: p.summary[locale],
    })),
  }));
}

export function docsPages(locale: Locale): DocPage[] {
  return docsNav(locale).flatMap((group) => group.pages);
}

/** Persian navigation (kept for existing callers). */
export const DOCS_NAV: DocGroup[] = docsNav("fa");
export const DOCS_PAGES: DocPage[] = docsPages("fa");

export function neighbours(
  href: string,
  locale: Locale = "fa",
): { previous?: DocPage; next?: DocPage } {
  const pages = docsPages(locale);
  const index = pages.findIndex((p) => p.href === href);
  if (index < 0) return {};
  return {
    ...(index > 0 ? { previous: pages[index - 1] } : {}),
    ...(index < pages.length - 1 ? { next: pages[index + 1] } : {}),
  };
}

/** The page a path belongs to (an ADR or a report belongs to its index page). */
export function pageOf(path: string, locale: Locale = "fa"): DocPage | undefined {
  const pages = docsPages(locale);
  const root = docsRoot(locale);
  return (
    pages.find((p) => p.href === path) ??
    [...pages].filter((p) => p.href !== root && path.startsWith(`${p.href}/`)).pop()
  );
}

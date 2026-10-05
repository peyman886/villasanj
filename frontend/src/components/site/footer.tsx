import Link from "next/link";

import { LogoMark } from "@/components/site/logo";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-line bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm sm:px-6 md:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2">
            <LogoMark className="size-7" />
            <span className="font-bold">ویلاسنج</span>
          </div>
          <p className="mt-3 max-w-sm text-pretty text-fg-muted">
            یک ویلا، همه‌ی حقیقت. هر عدد منبع و زمان مشاهده دارد؛ چیزی که نمی‌دانیم را بازه یا
            «حداقل» نشان می‌دهیم، نه حدس.
          </p>
        </div>
        <nav aria-label="محصول" className="space-y-2">
          <p className="font-semibold">محصول</p>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/search"
          >
            جستجو
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/how-we-rank"
          >
            چطور رتبه‌بندی می‌کنیم
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/metrics"
          >
            سنجه‌ها
          </Link>
        </nav>
        <nav aria-label="مستندات" className="space-y-2">
          <p className="font-semibold">مستندات</p>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/docs"
          >
            گزارش فنی پروژه
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/docs/milestones"
          >
            مایل‌استون‌ها
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/review"
          >
            بازبینی‌های مالک
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/docs/demo"
          >
            راهنمای دمو
          </Link>
        </nav>
      </div>
      <p className="border-t border-line px-4 py-4 text-center text-xs text-fg-subtle">
        داده‌ی نقشه © مشارکت‌کنندگان OpenStreetMap (ODbL) · فقط جاباما و شب، با رعایت robots.txt و
        شرایط استفاده
      </p>
    </footer>
  );
}

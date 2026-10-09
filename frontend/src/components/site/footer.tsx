import Link from "next/link";

import { LogoMark } from "@/components/site/logo";
import { BRAND } from "@/lib/copy";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-line bg-surface">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 text-sm sm:px-6 md:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2">
            <LogoMark className="size-7" />
            <span className="font-bold">{BRAND.name}</span>
          </div>
          <p className="mt-3 max-w-sm text-pretty text-fg-muted">
            {BRAND.tagline}. هر عدد منبع و زمان دیدنش را دارد؛ آنچه را نمی‌دانیم با بازه یا «از»
            نشان می‌دهیم، نه با حدس.
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
            روش رتبه‌بندی
          </Link>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/metrics"
          >
            سنجه‌ها
          </Link>
        </nav>
        <nav aria-label="برای داوران" className="space-y-2">
          <p className="font-semibold">برای داوران</p>
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/docs"
          >
            مستندات فنی
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
          <Link
            className="focus-ring block w-fit rounded-sm text-fg-muted hover:text-fg"
            href="/en/docs"
            hrefLang="en"
            lang="en"
          >
            Documentation in English
          </Link>
        </nav>
      </div>
      <p className="border-t border-line px-4 py-4 text-center text-xs text-fg-subtle">
        داده‌ی نقشه © مشارکت‌کنندگان OpenStreetMap (ODbL) · داده فقط از جاباما و شب، با رعایت
        robots.txt و شرایط استفاده‌ی هر دو
      </p>
    </footer>
  );
}

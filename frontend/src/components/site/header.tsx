import { BookOpenText, Menu, Search } from "lucide-react";
import Link from "next/link";

import { LogoMark } from "@/components/site/logo";
import { buttonClass } from "@/components/ui/button";

const NAV = [
  { href: "/search", label: "جستجو" },
  { href: "/how-we-rank", label: "چطور رتبه‌بندی می‌کنیم" },
  { href: "/metrics", label: "سنجه‌ها" },
] as const;

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur supports-[backdrop-filter]:bg-canvas/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="focus-ring flex items-center gap-2 rounded-control">
          <LogoMark />
          <span className="text-lg font-bold text-fg">ویلاسنج</span>
        </Link>
        <nav aria-label="اصلی" className="hidden flex-1 items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="focus-ring rounded-control px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-sunken hover:text-fg"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <Link
          href="/docs"
          className={buttonClass("secondary", "sm", "ms-auto hidden md:inline-flex")}
        >
          <BookOpenText aria-hidden="true" className="size-4" />
          مستندات پروژه
        </Link>
        <details className="group relative ms-auto md:hidden">
          <summary
            aria-label="منو"
            className="focus-ring grid size-10 cursor-pointer list-none place-items-center rounded-control text-fg hover:bg-sunken [&::-webkit-details-marker]:hidden"
          >
            <Menu aria-hidden="true" className="size-5" />
          </summary>
          <nav
            aria-label="اصلی"
            className="absolute end-0 top-12 z-40 w-64 rounded-card border border-line bg-surface p-2 shadow-overlay"
          >
            <Link
              href="/search"
              className="focus-ring flex items-center gap-2 rounded-control px-3 py-2.5 text-sm hover:bg-sunken"
            >
              <Search aria-hidden="true" className="size-4 text-fg-muted" />
              جستجو
            </Link>
            {NAV.slice(1).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="focus-ring block rounded-control px-3 py-2.5 text-sm hover:bg-sunken"
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/docs"
              className="focus-ring mt-1 flex items-center gap-2 rounded-control border-t border-line px-3 py-2.5 text-sm font-medium text-accent hover:bg-brand-50"
            >
              <BookOpenText aria-hidden="true" className="size-4" />
              مستندات پروژه / گزارش فنی
            </Link>
          </nav>
        </details>
      </div>
    </header>
  );
}

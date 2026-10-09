import { BookOpenText } from "lucide-react";
import Link from "next/link";

import { LogoMark } from "@/components/site/logo";
import { ThemeToggle } from "@/components/site/theme-toggle";
import { BRAND } from "@/lib/copy";

/** The English documentation's header. The product is Persian; one link leads to it. */
export function EnglishHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur supports-[backdrop-filter]:bg-canvas/80">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/en/docs" className="focus-ring flex items-center gap-2 rounded-control">
          <LogoMark />
          <span className="text-lg font-bold text-fg">{BRAND.en.name}</span>
          <span className="hidden text-sm text-fg-muted sm:inline">Documentation</span>
        </Link>
        <div className="ms-auto flex items-center gap-1">
          <Link
            href="/"
            hrefLang="fa"
            className="focus-ring hidden items-center gap-1.5 rounded-control px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-sunken hover:text-fg sm:inline-flex"
          >
            <BookOpenText aria-hidden="true" className="size-4" />
            Open the product (Persian)
          </Link>
          <ThemeToggle en />
        </div>
      </div>
    </header>
  );
}

export function EnglishFooter() {
  return (
    <footer className="mt-24 border-t border-line bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-fg-muted sm:px-6">
        <div className="flex items-center gap-2">
          <LogoMark className="size-7" />
          <span className="font-bold text-fg">{BRAND.en.name}</span>
          <span>· {BRAND.en.tagline}</span>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link className="focus-ring rounded-sm hover:text-fg" href="/en/docs/demo">
            Demo guide
          </Link>
          <Link className="focus-ring rounded-sm hover:text-fg" href="/en/docs/milestones">
            Milestones
          </Link>
          <Link
            className="focus-ring rounded-sm hover:text-fg"
            href="/docs"
            hrefLang="fa"
            lang="fa"
          >
            مستندات فارسی
          </Link>
          <a
            className="focus-ring rounded-sm hover:text-fg"
            href="https://github.com/peyman886/villasanj"
            target="_blank"
            rel="noopener noreferrer"
          >
            Source on GitHub
          </a>
        </nav>
      </div>
      <p className="border-t border-line px-4 py-4 text-center text-xs text-fg-subtle">
        Map data © OpenStreetMap contributors (ODbL) · Data from Jabama and Shab only, within each
        site&apos;s robots.txt and terms of use
      </p>
    </footer>
  );
}

"use client";

import { ArrowLeft, ArrowRight, ChevronDown, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { DOCS_NAV, neighbours, pageOf } from "@/content/docs-nav";
import { cn } from "@/lib/cn";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const current = pageOf(path)?.href;
  return (
    <nav aria-label="مستندات" className="space-y-6">
      {DOCS_NAV.map((group) => (
        <div key={group.title}>
          <p className="px-3 text-xs font-semibold text-fg-subtle">{group.title}</p>
          <ul className="mt-2 space-y-0.5">
            {group.pages.map((page) => {
              const active = page.href === current;
              return (
                <li key={page.href}>
                  <Link
                    href={page.href}
                    {...(onNavigate ? { onClick: onNavigate } : {})}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "focus-ring block rounded-control px-3 py-1.5 text-sm transition-colors",
                      active
                        ? "bg-brand-50 font-medium text-brand-900"
                        : "text-fg-muted hover:bg-sunken hover:text-fg",
                    )}
                  >
                    {page.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function DocsSidebar() {
  return (
    <aside className="hidden lg:block">
      <div className="sticky top-24 max-h-[calc(100dvh-7rem)] overflow-y-auto pe-2 pb-10">
        <NavLinks />
      </div>
    </aside>
  );
}

/** Phones and tablets: the same navigation in a disclosure above the page. */
export function DocsMobileNav() {
  const ref = useRef<HTMLDetailsElement>(null);
  const path = usePathname();
  const current = pageOf(path);
  return (
    <details ref={ref} className="group rounded-card border border-line bg-surface lg:hidden">
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 rounded-card px-4 py-3 text-sm [&::-webkit-details-marker]:hidden">
        <Menu aria-hidden="true" className="size-4 text-fg-muted" />
        <span className="text-fg-muted">مستندات:</span>
        <span className="font-medium">{current?.title ?? "نمای کلی"}</span>
        <ChevronDown
          aria-hidden="true"
          className="ms-auto size-4 transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="border-t border-line p-3">
        <NavLinks onNavigate={() => ref.current?.removeAttribute("open")} />
      </div>
    </details>
  );
}

export function DocsPager() {
  const path = usePathname();
  const { previous, next } = neighbours(path);
  if (!previous && !next) return null;
  return (
    <nav
      aria-label="صفحه‌ی قبلی و بعدی"
      className="mt-16 grid gap-3 border-t border-line pt-8 sm:grid-cols-2"
    >
      {previous ? (
        <Link
          href={previous.href}
          className="focus-ring group rounded-card border border-line bg-surface p-4 transition-shadow hover:shadow-float"
        >
          <span className="flex items-center gap-1 text-xs text-fg-muted">
            <ArrowRight aria-hidden="true" className="size-3.5" />
            قبلی
          </span>
          <span className="mt-1 block font-medium group-hover:text-accent">{previous.title}</span>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link
          href={next.href}
          className="focus-ring group rounded-card border border-line bg-surface p-4 text-end transition-shadow hover:shadow-float"
        >
          <span className="flex items-center justify-end gap-1 text-xs text-fg-muted">
            بعدی
            <ArrowLeft aria-hidden="true" className="size-3.5" />
          </span>
          <span className="mt-1 block font-medium group-hover:text-accent">{next.title}</span>
        </Link>
      ) : null}
    </nav>
  );
}

type TocItem = { id: string; text: string; level: number };

/** The page's own headings, with the one being read highlighted. Built from the DOM after load. */
export function DocsToc() {
  const path = usePathname();
  const [items, setItems] = useState<TocItem[]>([]);
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    const headings = [...document.querySelectorAll<HTMLElement>("article h2[id], article h3[id]")];
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the headings exist only after render
    setItems(
      headings.map((h) => ({
        id: h.id,
        text: h.textContent?.trim() ?? "",
        level: h.tagName === "H2" ? 2 : 3,
      })),
    );
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px" },
    );
    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [path]);
  if (items.length < 3) return null;
  return (
    <nav
      aria-label="در این صفحه"
      className="sticky top-24 max-h-[calc(100dvh-7rem)] overflow-y-auto pb-10 text-sm"
    >
      <p className="text-xs font-semibold text-fg-subtle">در این صفحه</p>
      <ul className="mt-3 space-y-1 border-s border-line">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              className={cn(
                "focus-ring -ms-px block border-s-2 py-1 transition-colors",
                item.level === 3 ? "ps-6" : "ps-3",
                active === item.id
                  ? "border-brand-600 font-medium text-brand-900"
                  : "border-transparent text-fg-muted hover:text-fg",
              )}
            >
              {item.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

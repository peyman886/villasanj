"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { smoothScroll } from "@/lib/motion";

const LINE_PX = 210; // where a section lands after a jump: scroll-padding (80 px) + scroll-mt-28 (112 px)

/**
 * Sticky section links (M12 2.2): the section in view is marked, and following a link moves the
 * keyboard focus to that section's heading, not only the scroll position.
 */
export function AnchorNav({ sections }: { sections: readonly (readonly [string, string])[] }) {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    // A one-pixel band at the line under the sticky bars: the section covering it is the one in
    // view. In the gap between two sections nothing covers it and the last one stays marked.
    const elements = sections
      .map(([id]) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    const below = Math.max(0, window.innerHeight - LINE_PX - 1);
    const observer = new IntersectionObserver(
      (entries) => {
        const hit = entries.filter((e) => e.isIntersecting).at(-1);
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: `-${LINE_PX}px 0px -${below}px 0px` },
    );
    for (const el of elements) observer.observe(el);
    return () => observer.disconnect();
  }, [sections]);
  return (
    <nav
      aria-label="بخش‌های صفحه"
      className="sticky top-16 z-20 -mx-4 border-b border-line bg-canvas/95 px-4 backdrop-blur sm:-mx-6 sm:px-6"
    >
      <ul className="flex gap-1 overflow-x-auto py-1 text-sm">
        {sections.map(([id, label]) => (
          <li key={id}>
            <a
              href={`#${id}`}
              aria-current={active === id ? "location" : undefined}
              onClick={(event) => {
                const heading = document.getElementById(`${id}-title`);
                if (!heading) return;
                event.preventDefault();
                heading
                  .closest("section")
                  ?.scrollIntoView({ behavior: smoothScroll(), block: "start" });
                heading.focus({ preventScroll: true });
                history.replaceState(null, "", `#${id}`);
                setActive(id);
              }}
              className={cn(
                "focus-ring block rounded-control px-3 py-2 whitespace-nowrap transition-colors",
                active === id
                  ? "bg-brand-50 font-semibold text-brand-900"
                  : "text-fg-muted hover:bg-sunken hover:text-fg",
              )}
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

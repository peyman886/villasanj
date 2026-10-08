"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";

const LINE_PX = 210; // where a section lands after a jump: scroll-padding (80 px) + scroll-mt-28 (112 px)

/**
 * Sticky section links (M12 2.2): the section in view is marked, and following a link moves the
 * keyboard focus to that section's heading, not only the scroll position.
 */
export function AnchorNav({ sections }: { sections: readonly (readonly [string, string])[] }) {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    // The section in view is the last one whose top has passed the sticky header and this bar.
    const update = () => {
      let current: string | null = null;
      for (const [id] of sections) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= LINE_PX) current = id;
      }
      setActive(current);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
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
                heading.closest("section")?.scrollIntoView({ behavior: "smooth", block: "start" });
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

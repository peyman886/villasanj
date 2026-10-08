"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { faNum } from "@/lib/numbers";

const EVENT = "villasanj:review-filter";
type Filter = { anchors: string[]; label: string } | null;

/**
 * «۷ نظر»: one chip per summary point (M12 2.4, the Amazon pattern). Pressing it shows only the
 * reviews the point cites; pressing it again, or «همه‌ی نظرها», shows them all.
 */
export function CiteChip({ anchors, label }: { anchors: string[]; label: string }) {
  const [active, setActive] = useState(false);
  useEffect(() => {
    const listen = (event: Event) => {
      const detail = (event as CustomEvent<Filter>).detail;
      setActive(detail?.label === label);
    };
    window.addEventListener(EVENT, listen);
    return () => window.removeEventListener(EVENT, listen);
  }, [label]);
  return (
    <button
      type="button"
      aria-pressed={active}
      data-cite-chip=""
      data-anchors={anchors.join(" ")}
      onClick={() =>
        window.dispatchEvent(
          new CustomEvent<Filter>(EVENT, { detail: active ? null : { anchors, label } }),
        )
      }
      className="focus-ring ms-1 inline-flex items-center rounded-full border border-line-strong bg-surface px-2 text-xs whitespace-nowrap text-fg-muted tabular-nums hover:border-brand-400 hover:text-fg aria-pressed:border-brand-700 aria-pressed:bg-brand-50 aria-pressed:text-brand-900"
    >
      {faNum(anchors.length)} نظر
    </button>
  );
}

/** The review list, filtered by the chip last pressed (every review stays in the page). */
export function ReviewFilter({ children }: { children: ReactNode }) {
  const [filter, setFilter] = useState<Filter>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const listen = (event: Event) => setFilter((event as CustomEvent<Filter>).detail);
    window.addEventListener(EVENT, listen);
    return () => window.removeEventListener(EVENT, listen);
  }, []);
  useEffect(() => {
    const keep = filter ? new Set(filter.anchors) : null;
    for (const item of box.current?.querySelectorAll<HTMLElement>("li[id^='review-']") ?? []) {
      item.hidden = keep !== null && !keep.has(item.id);
    }
    if (filter) box.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [filter]);
  return (
    <div ref={box} className="scroll-mt-28">
      {filter ? (
        <p
          role="status"
          className="mb-2 flex items-center justify-between gap-2 rounded-control bg-brand-50 px-3 py-2 text-sm text-brand-900"
        >
          <span>
            {faNum(filter.anchors.length)} نظر درباره‌ی «{filter.label}»
          </span>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent<Filter>(EVENT, { detail: null }))}
            className="focus-ring rounded-sm font-medium underline underline-offset-4"
          >
            همه‌ی نظرها
          </button>
        </p>
      ) : null}
      {children}
    </div>
  );
}

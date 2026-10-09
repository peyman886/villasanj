"use client";

import { ChevronLeft, ChevronRight, House } from "lucide-react";
import { useRef, useState } from "react";

import { smoothScroll } from "@/lib/motion";
import { faNum } from "@/lib/numbers";

/**
 * A card's photos, hotlinked from the platform (no copy on our server). Swipe or the arrows move
 * one photo; in RTL "next" points left. A photo that fails to load leaves a calm placeholder.
 */
export function PhotoCarousel({ photos, label }: { photos: string[]; label: string }) {
  const strip = useRef<HTMLUListElement>(null);
  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const shown = photos.filter((url) => !failed.has(url));

  const go = (delta: number) => {
    const el = strip.current;
    if (!el) return;
    const next = Math.max(0, Math.min(shown.length - 1, index + delta));
    // RTL scroll offsets are negative in every current engine.
    el.scrollTo({ left: -next * el.clientWidth, behavior: smoothScroll() });
    setIndex(next);
  };

  return (
    <div className="group/carousel relative size-full overflow-hidden bg-gradient-to-br from-brand-100 to-sand-200">
      <House aria-hidden="true" className="absolute inset-0 m-auto size-10 text-brand-300" />
      <ul
        ref={strip}
        aria-label={`عکس‌های ${label}`}
        className="relative flex size-full snap-x snap-mandatory overflow-x-hidden [scrollbar-width:none] pointer-coarse:overflow-x-auto"
        onScroll={(e) => {
          const el = e.currentTarget;
          setIndex(Math.round(Math.abs(el.scrollLeft) / Math.max(1, el.clientWidth)));
        }}
      >
        {shown.map((url, i) => (
          <li key={url} className="size-full shrink-0 snap-start">
            {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
            <img
              src={url}
              alt={`عکس ${faNum(i + 1)} از ${faNum(shown.length)}`}
              loading={i === 0 ? "eager" : "lazy"}
              decoding="async"
              referrerPolicy="no-referrer"
              onError={() => setFailed((f) => new Set(f).add(url))}
              className="size-full object-cover"
            />
          </li>
        ))}
      </ul>
      {shown.length > 1 ? (
        <>
          <button
            type="button"
            onClick={() => go(-1)}
            disabled={index === 0}
            aria-label="عکس قبلی"
            className="focus-ring absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-full bg-surface/90 text-fg opacity-0 shadow-raised transition-opacity group-hover/carousel:opacity-100 focus-visible:opacity-100 disabled:hidden"
          >
            <ChevronRight aria-hidden="true" className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => go(1)}
            disabled={index >= shown.length - 1}
            aria-label="عکس بعدی"
            className="focus-ring absolute top-1/2 left-2 grid size-8 -translate-y-1/2 place-items-center rounded-full bg-surface/90 text-fg opacity-0 shadow-raised transition-opacity group-hover/carousel:opacity-100 focus-visible:opacity-100 disabled:hidden"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
          </button>
          <div aria-hidden="true" className="absolute inset-x-0 bottom-2 flex justify-center gap-1">
            {shown.map((url, i) => (
              <span
                key={url}
                className={`size-1.5 rounded-full ${i === index ? "bg-white" : "bg-white/55"}`}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

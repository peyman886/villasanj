import { Sparkles } from "lucide-react";

import { Sourced } from "@/components/sourced";
import { Skeleton } from "@/components/ui/states";
import { apiClient } from "@/lib/api/client";
import { COPY } from "@/lib/copy";
import { filtersBody, type Filters } from "@/lib/filters";
import { displaySegments, type SearchOut } from "@/lib/search";

type Explanation = NonNullable<SearchOut["explanation"]>;

const WORD_MS = 28; // the reveal of a cached explanation takes about a second

async function loadExplanation(
  query: string,
  drop: string[],
  area: number[] | null,
  filters: Filters,
): Promise<Explanation | null> {
  try {
    const { data } = await apiClient().POST("/search/explanation", {
      body: {
        query,
        drop,
        explain: true,
        ...(area ? { area } : {}),
        filters: filtersBody(filters),
      },
      cache: "no-store",
    });
    return data ?? null;
  } catch {
    return null;
  }
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <section
      aria-labelledby="why-title"
      className="border-t border-brand-100 bg-brand-50/60 px-4 py-3"
    >
      <h4 id="why-title" className="flex items-center gap-1.5 text-sm font-semibold text-brand-900">
        <Sparkles aria-hidden="true" className="size-4" />
        {COPY.whyFirst}
      </h4>
      {children}
    </section>
  );
}

/**
 * Why the first result fits, inside its card (M12 1.5). The text is the model's; every number in
 * it was placed and checked by code (ADR-0007). The words fade in one after another, a
 * presentation of an answer that has already arrived and been verified.
 */
export async function WhyFirst({
  query,
  drop,
  area,
  filters,
  now,
}: {
  query: string;
  drop: string[];
  area: number[] | null;
  filters: Filters;
  now: Date;
}) {
  const explanation = await loadExplanation(query, drop, area, filters);
  if (!explanation) return null;
  let word = 0;
  const delay = () => ({ animationDelay: `${word++ * WORD_MS}ms` });
  return (
    <Frame>
      <p className="mt-1 text-[0.9375rem] leading-7 text-pretty text-brand-950">
        {displaySegments(explanation.segments).map((segment, index) =>
          segment.slot && segment.provenance ? (
            <span key={index} className="animate-fade-in" style={delay()}>
              <Sourced
                id={`why-${index}`}
                label={segment.text}
                value={segment.text}
                provenance={segment.provenance}
                now={now}
              >
                {segment.text}
                {segment.tail}
              </Sourced>
            </span>
          ) : (
            segment.text.split(/(\s+)/).map((part, i) =>
              /^\s+$/.test(part) || part === "" ? (
                part
              ) : (
                <span key={`${index}-${i}`} className="animate-fade-in" style={delay()}>
                  {part}
                </span>
              ),
            )
          ),
        )}
      </p>
      <p className="mt-1 text-xs text-brand-800">
        {explanation.source === "template"
          ? "مدل زبانی در دسترس نبود؛ این متن را کد از همان داده‌ها ساخت."
          : "متن از مدل زبانی؛ هر عدد را کد گذاشته و بررسی کرده است."}
      </p>
    </Frame>
  );
}

export function WhyFirstSkeleton() {
  return (
    <Frame>
      <span role="status" className="sr-only">
        در حال نوشتن توضیح از روی داده‌ها…
      </span>
      <Skeleton className="mt-2 h-4 w-full bg-brand-100" />
      <Skeleton className="mt-2 h-4 w-2/3 bg-brand-100" />
    </Frame>
  );
}

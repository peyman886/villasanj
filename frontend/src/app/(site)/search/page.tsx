import { ChevronDown, RotateCcw, Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ResultCard, type CardContext } from "@/components/search/result-card";
import { SearchSplit, type Pin } from "@/components/search/split";
import { FilterPanel } from "@/components/search/filter-panel";
import { WhyFirst, WhyFirstSkeleton } from "@/components/search/why";
import { buttonClass } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Chip, ChipLink } from "@/components/ui/chip";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { apiClient } from "@/lib/api/client";
import { readBasemap } from "@/lib/basemap";
import { cn } from "@/lib/cn";
import { COPY } from "@/lib/copy";
import { filterChips, filterParams, filtersBody, filtersFrom, type Filters } from "@/lib/filters";
import { faDigits, faNum, pinToman, shortAmount } from "@/lib/numbers";
import {
  BASIS_TEXT,
  DATE_CAVEAT_TEXT,
  EXAMPLE_QUERIES,
  EXCLUSION_TEXT,
  MISSING_TEXT,
  budgetChoices,
  cardOffers,
  cheapestShown,
  driveBuckets,
  excludedTotal,
  headline,
  intentChips,
  stayText,
  type Basis,
  type Chip as IntentChip,
  type SearchOut,
} from "@/lib/search";

export const metadata: Metadata = { title: "جستجو" };

type SearchParams = Record<string, string | string[] | undefined>;
type Outcome = SearchOut | "llm_unavailable" | "error";

async function runSearch(
  query: string,
  drop: string[],
  area: number[] | null,
  filters: Filters,
): Promise<Outcome> {
  try {
    const { data, response } = await apiClient().POST("/search", {
      // The explanation streams in after the results.
      body: {
        query,
        drop,
        explain: false,
        ...(area ? { area } : {}),
        filters: filtersBody(filters),
      },
      cache: "no-store",
    });
    if (data) return data;
    return response.status === 503 ? "llm_unavailable" : "error";
  } catch {
    return "error";
  }
}

/** The map area from the URL: «west,south,east,north» in degrees, or null. */
function areaFrom(raw: string | string[] | undefined): number[] | null {
  const parts = (typeof raw === "string" ? raw : "").split(",").map(Number);
  const [w, s, e, n] = parts;
  if (parts.length !== 4 || parts.some((x) => !Number.isFinite(x))) return null;
  return w !== undefined && s !== undefined && e !== undefined && n !== undefined && w < e && s < n
    ? parts
    : null;
}

/** Params a link keeps besides the query and its edits: the filters and the map area. */
type Extra = [string, string][];

function searchHref(query: string, drop: string[] = [], extra: Extra = []): string {
  const params = new URLSearchParams({ q: query });
  for (const key of drop) params.append("drop", key);
  for (const [key, value] of extra) params.set(key, value);
  return `/search?${params}`;
}

function SearchBar({ query }: { query: string }) {
  return (
    <form action="/search" method="get" role="search" className="w-full max-w-3xl">
      <label htmlFor="q" className="sr-only">
        ویلای مورد نظرتان را توصیف کنید
      </label>
      <div className="flex gap-2 rounded-full border border-line-strong bg-surface p-1 ps-4 focus-within:border-brand-500">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Search aria-hidden="true" className="size-5 shrink-0 text-fg-subtle" />
          <input
            id="q"
            name="q"
            defaultValue={query}
            required
            placeholder="مثلاً ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد"
            className="h-9 min-w-0 flex-1 bg-transparent outline-none placeholder:text-fg-subtle"
          />
        </div>
        <button type="submit" className={buttonClass("primary", "sm", "h-9 rounded-full px-5")}>
          جستجو
        </button>
      </div>
    </form>
  );
}

export default async function SearchPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const area = areaFrom(params.area);
  const filters = filtersFrom(params);
  const drop = (Array.isArray(params.drop) ? params.drop : params.drop ? [params.drop] : []).slice(
    0,
    12,
  );
  const [result, basemap] = await Promise.all([
    query.length >= 2 ? runSearch(query, drop, area, filters) : Promise.resolve(null),
    readBasemap(),
  ]);
  const now = new Date();
  return (
    <div className="mx-auto max-w-7xl px-4 pt-4 pb-16 sm:px-6">
      <h1 className="sr-only">جستجوی ویلا</h1>
      <SearchBar query={query} />
      {result === null ? (
        <div className="mt-6 max-w-3xl">
          <p className="text-pretty text-fg-muted">
            ویلای مناسب را با زبان خودتان بنویسید: کجا، کی، چند نفر و تا چه قیمتی.
          </p>
          <Examples />
        </div>
      ) : null}
      {result === "llm_unavailable" ? (
        <div className="mt-8 max-w-3xl space-y-4">
          <Callout kind="degraded" title="فهمیدن این جستجو فعلاً ممکن نیست" live>
            <p>
              مدل زبانی‌ای که جمله را به شرط‌های جستجو تبدیل می‌کند در دسترس نیست، و این جمله قبلاً
              پرسیده نشده تا پاسخش در حافظه باشد. ویلاسنج شرطی را حدس نمی‌زند.
            </p>
            <p>جستجوهای نمونه از حافظه پاسخ می‌گیرند:</p>
          </Callout>
          <Examples />
        </div>
      ) : null}
      {result === "error" ? (
        <ErrorState title="جستجو انجام نشد" className="mt-8 max-w-3xl">
          {COPY.refreshFailed} سرور جستجو پاسخ نداد؛ کمی بعد دوباره امتحان کنید. اگر روی سیستم
          خودتان اجرا می‌کنید، <code className="ltr font-mono">make up</code> را بزنید.
        </ErrorState>
      ) : null}
      {result && typeof result !== "string" ? (
        <Results
          result={result}
          drop={drop}
          area={area}
          filters={filters}
          now={now}
          basemap={basemap?.pmtiles ?? null}
        />
      ) : null}
    </div>
  );
}

function Examples() {
  return (
    <section aria-label="نمونه‌ی جستجو" className="mt-4">
      <ul className="flex flex-wrap gap-2">
        {EXAMPLE_QUERIES.map((q) => (
          <li key={q}>
            <ChipLink href={searchHref(q)}>{q}</ChipLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** «تا ۲۰ میلیون: [کل سفر] / هر شب»: a reading of the budget the user can flip (D5). */
function BudgetChip({
  chip,
  basis,
  result,
  drop,
  extra,
}: {
  chip: IntentChip;
  basis: Basis;
  result: SearchOut;
  drop: string[];
  extra: Extra;
}) {
  const others = drop.filter((d) => !d.startsWith("basis:"));
  const counts = Object.fromEntries(budgetChoices(result).map((c) => [c.label, c.count]));
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-brand-300 bg-brand-50 py-0.5 ps-3 pe-1 text-sm text-brand-900">
      <span className="tabular-nums">{chip.text}</span>
      {basis.stated ? (
        <span>({BASIS_TEXT[basis.current]})</span>
      ) : (
        <span
          role="group"
          aria-label="بودجه برای"
          title="تا وقتی نگفته‌اید، کل سفر حساب شده (سخت‌گیرانه‌تر)."
          className="ms-1 inline-flex rounded-full bg-surface p-0.5 ring-1 ring-brand-200"
        >
          {(["whole_stay", "per_night"] as const).map((b) => {
            const current = basis.current === b;
            const count = counts[b === "whole_stay" ? "کل اقامت" : "هر شب"];
            return (
              <Link
                key={b}
                href={searchHref(result.query, [...others, `basis:${b}`], extra)}
                aria-current={current ? "true" : undefined}
                scroll={false}
                className={cn(
                  "focus-ring rounded-full px-2.5 py-0.5 text-xs transition-colors",
                  current
                    ? "bg-brand-800 font-semibold text-white"
                    : "text-brand-800 hover:bg-brand-50",
                )}
              >
                {BASIS_TEXT[b]}
                {!current && count !== undefined ? (
                  <span className="sr-only"> ({faNum(count)} ویلا)</span>
                ) : null}
              </Link>
            );
          })}
        </span>
      )}
      <Link
        href={searchHref(result.query, [...others, "budget"], extra)}
        aria-label={`حذف «${chip.text}» و جستجوی دوباره`}
        className="focus-ring grid size-6 place-items-center rounded-full text-fg-muted transition-colors hover:bg-sand-200 hover:text-fg"
      >
        <span aria-hidden="true">×</span>
      </Link>
    </span>
  );
}

function Results({
  result,
  drop,
  area,
  filters,
  now,
  basemap,
}: {
  result: SearchOut;
  drop: string[];
  area: number[] | null;
  filters: Filters;
  now: Date;
  basemap: string | null;
}) {
  const areaParam: Extra = area ? [["area", area.join(",")]] : [];
  const extra: Extra = [...filterParams(filters), ...areaParam];
  const chips = intentChips(result, drop);
  const notes = [
    ...(result.dates?.caveats ?? []).map((c) => DATE_CAVEAT_TEXT[c] ?? c),
    ...(result.unresolved_places.length > 0
      ? [`این مکان را نمی‌شناسیم و در جستجو لحاظ نشد: ${result.unresolved_places.join("، ")}`]
      : []),
    ...(result.unhandled.length > 0
      ? [
          `${result.unhandled.map((w) => `«${w}»`).join("، ")} را نمی‌سنجیم؛ اگر خود آگهی از آن نوشته باشد، در «چرا اینجا؟» آمده.`,
        ]
      : []),
  ];
  const stay = stayText(result);
  const intent = result.intent as { guest_parts?: number[] };
  const guests = (intent.guest_parts ?? []).reduce((a, b) => a + b, 0);
  const context: CardContext = {
    stay,
    now,
    villaHref: (villaId) => {
      const q = new URLSearchParams();
      if (result.dates) {
        q.set("in", result.dates.check_in);
        q.set("out", result.dates.check_out);
      }
      if (guests) q.set("guests", String(guests));
      const qs = q.toString();
      return `/villas/${villaId}${qs ? `?${qs}` : ""}`;
    },
  };
  const pins: Pin[] = result.results.flatMap((r) => {
    const top = headline(cardOffers(r));
    if (!r.location || !top?.total) return [];
    return [
      {
        id: r.listing_id,
        label: pinToman(top.total.low_toman),
        title: faDigits(r.title),
        lat: r.location.lat,
        lon: r.location.lon,
        radiusM: r.location.radius_m ?? 0,
      },
    ];
  });
  const cheapest = cheapestShown(result);
  const excluded = excludedTotal(result);
  return (
    <>
      <section aria-label="برداشت ما از جستجو" className="mt-3">
        <ul className="flex flex-wrap items-center gap-2">
          <li>
            <FilterPanel query={result.query} drop={drop} area={area} current={filters} />
          </li>
          {chips.map((chip) => (
            <li key={chip.key}>
              {chip.basis ? (
                <BudgetChip
                  chip={chip}
                  basis={chip.basis}
                  result={result}
                  drop={drop}
                  extra={extra}
                />
              ) : (
                <Chip
                  tone="brand"
                  removeHref={searchHref(result.query, [...drop, chip.key], extra)}
                  removeLabel={`حذف «${chip.text}» و جستجوی دوباره`}
                >
                  {chip.text}
                </Chip>
              )}
            </li>
          ))}
          {filterChips(filters).map((chip) => (
            <li key={chip.key} data-filter-chip="">
              <Chip
                removeHref={searchHref(result.query, drop, [
                  ...filterParams(chip.without),
                  ...areaParam,
                ])}
                removeLabel={`حذف فیلتر «${chip.text}»`}
              >
                {chip.text}
              </Chip>
            </li>
          ))}
          {area ? (
            <li data-filter-chip="">
              <Chip
                removeHref={searchHref(result.query, drop, filterParams(filters))}
                removeLabel="حذف «محدوده‌ی نقشه»"
              >
                محدوده‌ی نقشه
              </Chip>
            </li>
          ) : null}
          {drop.some((d) => !d.startsWith("basis:")) ? (
            <li>
              <Link
                href={searchHref(
                  result.query,
                  drop.filter((d) => d.startsWith("basis:")),
                  extra,
                )}
                className="focus-ring inline-flex items-center gap-1 rounded-control px-2 py-1 text-sm text-accent hover:bg-brand-50"
              >
                <RotateCcw aria-hidden="true" className="size-4" />
                بازگرداندن همه‌ی شرط‌ها
              </Link>
            </li>
          ) : null}
        </ul>
        {notes.map((n) => (
          <p key={n} className="mt-1 text-sm text-fg-muted">
            {n}
          </p>
        ))}
        {result.missing.length > 0 ? (
          <ul className="mt-3 max-w-3xl space-y-1 rounded-card border border-line bg-surface p-4 text-sm">
            {result.missing.map((m) => (
              <li key={m}>{MISSING_TEXT[m] ?? m}</li>
            ))}
          </ul>
        ) : null}
      </section>

      {result.results.length > 0 ? (
        <div className="mt-3">
          <SearchSplit pins={pins} basemap={basemap}>
            <section aria-labelledby="results-title">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 id="results-title" className="text-lg font-bold text-balance tabular-nums">
                  {faNum(result.total_results)} ویلا
                  {cheapest !== null ? (
                    <span className="font-normal text-fg-muted">
                      {" "}
                      · از {shortAmount(cheapest, "lower")}
                      {stay ? ` برای ${stay}` : ""}
                    </span>
                  ) : null}
                </h2>
                <div className="flex items-center gap-3 text-sm">
                  {excluded > 0 ? <ExcludedDrawer result={result} total={excluded} /> : null}
                  <Link
                    href="/how-we-rank"
                    className="focus-ring rounded-sm text-accent underline-offset-4 hover:underline"
                  >
                    {COPY.aboutRanking}
                  </Link>
                </div>
              </div>
              <p className="text-[0.8125rem] text-fg-muted">
                {COPY.feeSearch}
                {result.total_results > result.results.length
                  ? ` ${faNum(result.results.length)} ویلای اول نشان داده شده.`
                  : ""}
              </p>
              <ol className="mt-3 space-y-3">
                {result.results.map((r, index) => (
                  <ResultCard
                    key={r.listing_id}
                    result={r}
                    first={index === 0}
                    context={context}
                    explanation={
                      index === 0 && result.dates ? (
                        <Suspense fallback={<WhyFirstSkeleton />}>
                          <WhyFirst
                            query={result.query}
                            drop={drop}
                            area={area}
                            filters={filters}
                            now={now}
                          />
                        </Suspense>
                      ) : undefined
                    }
                  />
                ))}
              </ol>
            </section>
          </SearchSplit>
        </div>
      ) : result.missing.length === 0 ? (
        <EmptyState
          className="mt-6 max-w-3xl"
          title="با این شرط‌ها ویلایی پیدا نکردیم"
          action={
            chips[0] ? (
              <Link
                href={searchHref(result.query, [...drop, chips[0].key], extra)}
                className={buttonClass("secondary")}
              >
                بدون «{chips[0].text}» جستجو کن
              </Link>
            ) : null
          }
        >
          {Object.keys(result.excluded).length > 0
            ? `بیشترین دلیل: ${EXCLUSION_TEXT[Object.entries(result.excluded).sort((a, b) => b[1] - a[1])[0]?.[0] ?? ""] ?? ""}. یکی از شرط‌ها را بردارید.`
            : "یکی از شرط‌ها را بردارید."}
        </EmptyState>
      ) : null}
    </>
  );
}

/** «چرا N آگهی کنار گذاشته شد؟»: the reasons and the drive-time spread, one layer down (S5). */
function ExcludedDrawer({ result, total }: { result: SearchOut; total: number }) {
  const reasons = Object.entries(result.excluded).sort(([, a], [, b]) => b - a);
  const buckets = driveBuckets(result);
  return (
    <details className="group relative">
      <summary className="focus-ring inline-flex cursor-pointer list-none items-center gap-1 rounded-sm text-fg-muted hover:text-fg [&::-webkit-details-marker]:hidden">
        چرا {faNum(total)} آگهی کنار گذاشته شد؟
        <ChevronDown
          aria-hidden="true"
          className="size-4 transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="absolute end-0 z-20 mt-2 w-80 rounded-card border border-line bg-surface p-4 text-sm shadow-float">
        <ul className="space-y-1 tabular-nums">
          {reasons.map(([reason, count]) => (
            <li key={reason} className="flex justify-between gap-3">
              <span>{EXCLUSION_TEXT[reason] ?? reason}</span>
              <span className="text-fg-muted">{faNum(count)}</span>
            </li>
          ))}
        </ul>
        {buckets.length > 0 ? (
          <>
            <p className="mt-3 font-medium">زمان رانندگی از تهران (بدون ترافیک)</p>
            <ul className="mt-1 space-y-1 text-fg-muted tabular-nums">
              {buckets.map((b) => (
                <li key={b.hours} className="flex justify-between gap-3">
                  <span>تا {faNum(b.hours)} ساعت</span>
                  <span>{faNum(b.count)} آگهی</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </details>
  );
}

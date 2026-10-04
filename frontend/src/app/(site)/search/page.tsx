import {
  ArrowUpLeft,
  CarFront,
  ChevronDown,
  Info,
  RotateCcw,
  Search,
  Sparkles,
  Waves,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Sourced } from "@/components/sourced";
import { Badge } from "@/components/ui/badge";
import { buttonClass } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Chip, ChipLink } from "@/components/ui/chip";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { apiClient } from "@/lib/api/client";
import { faNumber, faToman } from "@/lib/listing";
import {
  CAUTION_TEXT,
  COMPONENT_TEXT,
  DATE_CAVEAT_TEXT,
  EXAMPLE_QUERIES,
  MISSING_TEXT,
  budgetChoices,
  displaySegments,
  driveCoverageText,
  exclusionSummary,
  intentChips,
  type SearchOut,
  type SearchResultOut,
} from "@/lib/search";

export const metadata: Metadata = { title: "جستجو" };

type SearchParams = Record<string, string | string[] | undefined>;
type Outcome = SearchOut | "llm_unavailable" | "error";

async function runSearch(query: string, drop: string[]): Promise<Outcome> {
  try {
    const { data, response } = await apiClient().POST("/search", {
      body: { query, drop, explain: false }, // the explanation streams in after the results
      cache: "no-store",
    });
    if (data) return data;
    return response.status === 503 ? "llm_unavailable" : "error";
  } catch {
    return "error";
  }
}

type Explanation = NonNullable<SearchOut["explanation"]>;

async function loadExplanation(query: string, drop: string[]): Promise<Explanation | null> {
  try {
    const { data } = await apiClient().POST("/search/explanation", {
      body: { query, drop, explain: true },
      cache: "no-store",
    });
    return data ?? null;
  } catch {
    return null;
  }
}

function searchHref(query: string, drop: string[] = []): string {
  const params = new URLSearchParams({ q: query });
  for (const key of drop) params.append("drop", key);
  return `/search?${params}`;
}

/** Why the first result fits: written around facts placed and checked by code (ADR-0007). */
async function WhySection({ query, drop, now }: { query: string; drop: string[]; now: Date }) {
  const explanation = await loadExplanation(query, drop);
  if (!explanation) return null;
  return (
    <section
      aria-labelledby="why-title"
      className="rounded-card border border-brand-200 bg-brand-50 p-5"
    >
      <div className="flex items-center gap-2">
        <Sparkles aria-hidden="true" className="size-5 text-brand-700" />
        <h2 id="why-title" className="font-semibold text-balance text-brand-950">
          چرا گزینه‌ی اول؟
        </h2>
        {explanation.source === "template" ? (
          <Badge tone="muted" className="ms-auto">
            متن از الگوی ثابت
          </Badge>
        ) : null}
      </div>
      <p className="mt-2 leading-8 text-pretty text-brand-950">
        {displaySegments(explanation.segments).map((segment, index) =>
          segment.slot && segment.provenance ? (
            <Sourced
              key={index}
              id={`why-${index}`}
              label={segment.text}
              value={segment.text}
              provenance={segment.provenance}
              now={now}
            >
              {segment.text}
              {segment.tail}
            </Sourced>
          ) : (
            <span key={index}>{segment.text}</span>
          ),
        )}
      </p>
      <p className="mt-3 text-xs text-brand-800">
        {explanation.source === "template"
          ? "مدل زبانی در دسترس نبود؛ این متن را کد از همان داده‌ها ساخت."
          : "متن را مدل زبانی نوشته؛ هر عدد را کد گذاشته و پیش از نمایش بررسی کرده است."}
      </p>
    </section>
  );
}

function WhySkeleton() {
  return (
    <div role="status" className="rounded-card border border-brand-200 bg-brand-50 p-5">
      <p className="font-semibold text-brand-950">چرا گزینه‌ی اول؟</p>
      <p className="mt-1 text-sm text-brand-800">در حال نوشتن توضیح از روی داده‌ها…</p>
      <Skeleton className="mt-3 h-4 w-full bg-brand-100" />
      <Skeleton className="mt-2 h-4 w-2/3 bg-brand-100" />
    </div>
  );
}

function SearchBar({ query }: { query: string }) {
  return (
    <form action="/search" method="get" role="search">
      <label htmlFor="q" className="sr-only">
        ویلای مورد نظرتان را توصیف کنید
      </label>
      <div className="flex gap-2 rounded-card border border-line-strong bg-surface p-1.5 shadow-raised focus-within:border-brand-500">
        <div className="flex min-w-0 flex-1 items-center gap-2 px-2">
          <Search aria-hidden="true" className="size-5 shrink-0 text-fg-subtle" />
          <input
            id="q"
            name="q"
            defaultValue={query}
            required
            placeholder="مثلاً ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد"
            className="h-10 min-w-0 flex-1 bg-transparent outline-none placeholder:text-fg-subtle"
          />
        </div>
        <button type="submit" className={buttonClass("primary", "md")}>
          جستجو
        </button>
      </div>
    </form>
  );
}

export default async function SearchPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const drop = (Array.isArray(params.drop) ? params.drop : params.drop ? [params.drop] : []).slice(
    0,
    12,
  );
  const result = query.length >= 2 ? await runSearch(query, drop) : null;
  const now = new Date();
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 pb-16 sm:px-6">
      <h1 className="text-2xl font-bold text-balance">جستجوی ویلا</h1>
      <p className="mt-1 text-pretty text-fg-muted">
        ویلای مناسب را با زبان خودتان بنویسید؛ قیمت نهایی، دلیل رتبه و منبع هر عدد را می‌بینید.
      </p>
      <div className="mt-5 max-w-3xl">
        <SearchBar query={query} />
      </div>
      {result === null ? <Examples /> : null}
      {result === "llm_unavailable" ? (
        <div className="mt-8 max-w-3xl space-y-4">
          <Callout kind="degraded" title="فهمیدن این جستجو فعلاً ممکن نیست" live>
            <p>
              مدل زبانی‌ای که جمله را به شرط‌های جستجو تبدیل می‌کند در دسترس نیست، و این جمله قبلاً
              پرسیده نشده تا پاسخش در حافظه باشد. ویلاسنج شرطی را حدس نمی‌زند.
            </p>
            <p>جستجوهای نمونه از حافظه پاسخ می‌گیرند:</p>
          </Callout>
          <Examples compact />
        </div>
      ) : null}
      {result === "error" ? (
        <ErrorState title="جستجو انجام نشد" className="mt-8 max-w-3xl">
          سرور جستجو پاسخ نداد. کمی بعد دوباره امتحان کنید؛ اگر روی سیستم خودتان اجرا می‌کنید،{" "}
          <code className="ltr font-mono">make up</code> را بزنید.
        </ErrorState>
      ) : null}
      {result && typeof result !== "string" ? (
        <Results result={result} drop={drop} now={now} />
      ) : null}
    </div>
  );
}

function Examples({ compact = false }: { compact?: boolean }) {
  return (
    <section aria-label="نمونه‌ی جستجو" className={compact ? "" : "mt-6"}>
      {compact ? null : <p className="text-sm text-fg-muted">نمونه‌ها:</p>}
      <ul className="mt-2 flex flex-wrap gap-2">
        {EXAMPLE_QUERIES.map((q) => (
          <li key={q}>
            <ChipLink href={searchHref(q)}>{q}</ChipLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Results({ result, drop, now }: { result: SearchOut; drop: string[]; now: Date }) {
  const chips = intentChips(result);
  const choices = budgetChoices(result);
  const excluded = exclusionSummary(result.excluded);
  const coverage = driveCoverageText(result);
  const notes = [
    ...(result.dates?.caveats ?? []).map((c) => DATE_CAVEAT_TEXT[c] ?? c),
    ...(result.unresolved_places.length > 0
      ? [`این مکان را نمی‌شناسیم و در جستجو لحاظ نشد: ${result.unresolved_places.join("، ")}`]
      : []),
  ];
  return (
    <>
      <section aria-label="برداشت از جستجو" className="mt-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-fg-muted">برداشت ما:</span>
          <ul className="contents">
            {chips.map((chip) => (
              <li key={chip.key}>
                <Chip
                  tone="brand"
                  removeHref={searchHref(result.query, [...drop, chip.key])}
                  removeLabel={`حذف «${chip.text}» و جستجوی دوباره`}
                >
                  {chip.text}
                </Chip>
              </li>
            ))}
          </ul>
          {drop.length > 0 ? (
            <Link
              href={searchHref(result.query)}
              className="focus-ring inline-flex items-center gap-1 rounded-control px-2 py-1 text-sm text-accent hover:bg-brand-50"
            >
              <RotateCcw aria-hidden="true" className="size-4" />
              بازگرداندن همه‌ی شرط‌ها
            </Link>
          ) : null}
        </div>
        {notes.map((n) => (
          <p key={n} className="mt-2 text-sm text-fg-muted">
            {n}
          </p>
        ))}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-5">
          {result.missing.length > 0 || choices.length > 0 ? (
            <section
              aria-label="پرسش"
              className="rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
            >
              <ul className="space-y-1.5">
                {result.missing.map((m) => (
                  <li key={m}>{MISSING_TEXT[m] ?? m}</li>
                ))}
              </ul>
              {choices.length > 0 ? (
                <div className="mt-1">
                  <p className="font-medium">
                    بودجه برای هر شب است یا کل اقامت؟ نتیجه‌ها فرق می‌کند:
                  </p>
                  <ul className="mt-3 flex flex-wrap gap-2">
                    {choices.map((c) => (
                      <li key={c.label}>
                        <Link
                          href={searchHref(c.query, drop)}
                          className={buttonClass("secondary", "sm", "border-amber-400 bg-surface")}
                        >
                          {c.label} ({faNumber(c.count)} ویلا)
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-amber-900">تا وقتی نگفته‌اید، سخت‌گیرانه‌تر حساب شده.</p>
                </div>
              ) : null}
            </section>
          ) : null}

          {result.results.length > 0 && result.dates ? (
            <Suspense fallback={<WhySkeleton />}>
              <WhySection query={result.query} drop={drop} now={now} />
            </Suspense>
          ) : null}

          {result.results.length > 0 ? (
            <section aria-labelledby="results-title">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="results-title" className="text-lg font-semibold text-balance">
                  {faNumber(result.total_results)} آگهی مناسب
                  {result.total_results > result.results.length
                    ? ` (${faNumber(result.results.length)} تای اول)`
                    : ""}
                </h2>
                <Link
                  href="/how-we-rank"
                  className="focus-ring rounded-sm text-sm text-accent underline-offset-4 hover:underline"
                >
                  چطور رتبه‌بندی می‌کنیم
                </Link>
              </div>
              <p className="mt-1 text-sm text-pretty text-fg-muted">
                هر ویلای واقعی یک بار می‌آید، با پیشنهاد پلتفرم دیگرش کنارش. اول آن‌هایی که امکانات
                خواسته‌شده‌شان تأیید شده، بعد بقیه؛ در هر گروه به ترتیب قیمت برای هر نفر و امتیاز
                مهمان‌ها.
              </p>
              <ol className="mt-4 space-y-3">
                {result.results.map((r, index) => (
                  <ResultCard key={r.listing_id} result={r} rank={index + 1} now={now} />
                ))}
              </ol>
            </section>
          ) : (
            <EmptyState
              title="ویلایی با همه‌ی این شرط‌ها پیدا نشد"
              action={
                chips[0] ? (
                  <Link
                    href={searchHref(result.query, [...drop, chips[0].key])}
                    className={buttonClass("secondary")}
                  >
                    بدون «{chips[0].text}» جستجو کن
                  </Link>
                ) : null
              }
            >
              یکی از شرط‌ها را بردارید؛ دلیل کنار گذاشتن هر آگهی در کناره آمده است.
            </EmptyState>
          )}
        </div>

        <aside aria-label="جزئیات جستجو" className="space-y-4 text-sm">
          {result.unhandled.length > 0 ? (
            <Callout kind="info" title="این خواسته‌ها را نمی‌سنجیم">
              {result.unhandled.map((w) => `«${w}»`).join("، ")} در رتبه‌بندی اثری ندارند؛ روی هر
              نتیجه می‌گوییم اگر خود آگهی از آن نوشته باشد.
            </Callout>
          ) : null}
          {coverage ? (
            <div className="rounded-card border border-line bg-surface p-4">
              <p className="flex items-center gap-2 font-medium">
                <CarFront aria-hidden="true" className="size-4 text-fg-muted" />
                زمان رانندگی از تهران
              </p>
              <p className="mt-1 text-fg-muted tabular-nums">{coverage}</p>
            </div>
          ) : null}
          {excluded.length > 0 ? (
            <div className="rounded-card border border-line bg-surface p-4">
              <p className="font-medium">کنار گذاشته شد</p>
              <ul className="mt-2 space-y-1 text-fg-muted">
                {excluded.map((line) => (
                  <li key={line} className="flex gap-2">
                    <span aria-hidden="true">•</span>
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex gap-2 rounded-card bg-sunken p-4 text-fg-muted">
            <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <p className="text-pretty">
              روی هر عدد بزنید تا منبع و زمان مشاهده‌اش را ببینید. قیمت‌ها «حداقل»اند چون کارمزدها
              منتشر نمی‌شوند.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}

function perPerson(result: SearchResultOut): string {
  const amount = faNumber(Math.floor(result.price_per_person_night_toman ?? 0));
  const exact = result.total !== null && result.total.high_toman === result.total.low_toman;
  return exact ? `${amount} تومان` : `حداقل ${amount} تومان`;
}

function ResultCard({ result, rank, now }: { result: SearchResultOut; rank: number; now: Date }) {
  const id = result.listing_id.replace(/[^a-z0-9]/gi, "-");
  const geo = result.geo;
  return (
    <li className="overflow-hidden rounded-card border border-line bg-surface shadow-raised">
      <div className="flex flex-col sm:flex-row">
        <div className="relative aspect-[16/9] shrink-0 bg-gradient-to-br from-brand-100 to-sand-200 sm:aspect-auto sm:w-48">
          {result.photo ? (
            // eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server
            <img
              src={result.photo}
              alt=""
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
              className="absolute inset-0 size-full object-cover"
            />
          ) : null}
          <span className="absolute start-2 top-2 grid size-7 place-items-center rounded-full bg-surface/95 text-xs font-semibold tabular-nums shadow-raised">
            {faNumber(rank)}
          </span>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-3 p-4 sm:flex-row sm:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="muted">{result.platform_name}</Badge>
              {result.also_on.map((o) => (
                <Badge key={o.listing_id} tone="brand">
                  + {o.platform_name}
                </Badge>
              ))}
            </div>
            <p className="font-semibold">
              <Link
                href={`/listings/${result.platform}/${result.external_id}`}
                className="focus-ring rounded-sm underline-offset-4 hover:text-accent hover:underline"
              >
                {result.title}
              </Link>
            </p>
            {geo && (geo.drive_s || geo.coast_m) ? (
              <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg-muted tabular-nums">
                {geo.drive_s ? (
                  <span className="flex items-center gap-1">
                    <CarFront aria-hidden="true" className="size-4" />
                    <Sourced
                      id={`geo-0-${id}`}
                      label="زمان رانندگی"
                      value={geo.drive_s.text}
                      provenance={geo.drive_s.provenance}
                      now={now}
                    >
                      {geo.drive_s.text}
                    </Sourced>
                  </span>
                ) : null}
                {geo.coast_m ? (
                  <span className="flex items-center gap-1">
                    <Waves aria-hidden="true" className="size-4" />
                    <Sourced
                      id={`geo-1-${id}`}
                      label="فاصله تا ساحل"
                      value={geo.coast_m.text}
                      provenance={geo.coast_m.provenance}
                      now={now}
                    >
                      {geo.coast_m.text}
                    </Sourced>
                  </span>
                ) : null}
              </p>
            ) : null}
            {result.mentions.length > 0 ? (
              <p className="text-sm text-fg-muted">
                <Sourced
                  id={`mentions-${id}`}
                  label="متن آگهی"
                  provenance={result.listing_provenance}
                  sourceName={result.platform_name}
                  now={now}
                >
                  در متن آگهی آمده: {result.mentions.map((w) => `«${w}»`).join("، ")}
                </Sourced>
              </p>
            ) : null}
            {result.cautions.length > 0 ? (
              <ul className="flex flex-wrap gap-1.5">
                {result.cautions.map((c) => (
                  <li key={c}>
                    <Badge tone="caution">{CAUTION_TEXT[c] ?? c}</Badge>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <div className="shrink-0 space-y-1 border-line text-start sm:w-60 sm:border-s sm:ps-4">
            <p className="text-xs text-fg-muted">کل اقامت در {result.platform_name}</p>
            <p className="text-lg leading-snug font-semibold whitespace-nowrap tabular-nums">
              {result.total ? (
                <Sourced
                  id={`total-${id}`}
                  label={`قیمت ${result.title}`}
                  value={faToman(result.total)}
                  provenance={result.total_provenance}
                  sourceName={result.platform_name}
                  now={now}
                >
                  {faToman(result.total)}
                </Sourced>
              ) : (
                <span className="text-base font-normal text-fg-muted">قیمت معلوم نیست</span>
              )}
            </p>
            {result.price_per_person_night_toman !== null && result.total ? (
              <p className="text-sm text-fg-muted tabular-nums">
                هر نفر هر شب{" "}
                <Sourced
                  id={`per-person-${id}`}
                  label={`قیمت هر نفر در هر شب ${result.title}`}
                  value={`${perPerson(result)}: مبلغ کل تقسیم بر تعداد نفر و شب`}
                  provenance={result.total_provenance}
                  sourceName={result.platform_name}
                  now={now}
                >
                  {perPerson(result)}
                </Sourced>
              </p>
            ) : null}
            {result.also_on.map((other) => (
              <p key={other.listing_id} className="text-sm text-fg-muted tabular-nums">
                {other.platform_name}:{" "}
                {other.total && other.status === "bookable" ? (
                  <Sourced
                    id={`also-${id}-${other.platform}`}
                    label={`قیمت همین ویلا در ${other.platform_name}`}
                    value={faToman(other.total)}
                    provenance={other.total_provenance}
                    sourceName={other.platform_name}
                    now={now}
                  >
                    {faToman(other.total)}
                  </Sourced>
                ) : (
                  "برای این تاریخ آزاد نبود"
                )}
              </p>
            ))}
            {result.villa_id && result.also_on.length > 0 ? (
              <Link
                href={`/villas/${result.villa_id}`}
                className="focus-ring inline-flex items-center gap-1 rounded-sm pt-1 text-sm font-medium text-accent hover:underline"
              >
                مقایسه کنار هم
                <ArrowUpLeft aria-hidden="true" className="size-4" />
              </Link>
            ) : null}
          </div>
        </div>
      </div>
      <details className="group border-t border-line bg-sunken/60 text-sm">
        <summary className="focus-ring flex cursor-pointer list-none items-center gap-1 px-4 py-2 text-fg-muted hover:text-fg [&::-webkit-details-marker]:hidden">
          چرا این رتبه؟
          <ChevronDown
            aria-hidden="true"
            className="size-4 transition-transform group-open:rotate-180"
          />
        </summary>
        <ul className="grid gap-2 px-4 pb-4 sm:grid-cols-2">
          {result.contributions.map((c) => {
            const share = c.weight > 0 ? Math.max(0, Math.min(1, c.points / c.weight)) : 0;
            return (
              <li key={c.component}>
                <div className="flex justify-between gap-2 text-xs text-fg-muted tabular-nums">
                  <span>{COMPONENT_TEXT[c.component] ?? c.component}</span>
                  <span>
                    {faNumber(Math.round(c.points * 100))} از {faNumber(Math.round(c.weight * 100))}
                  </span>
                </div>
                <div
                  className="mt-1 h-1.5 overflow-hidden rounded-full bg-sand-200"
                  aria-hidden="true"
                >
                  <div
                    className="h-full rounded-full bg-brand-500"
                    style={{ width: `${share * 100}%` }}
                  />
                </div>
              </li>
            );
          })}
          <li className="text-xs text-fg-muted tabular-nums sm:col-span-2">
            امکانات خواسته‌شده‌ی تأییدشده: {faNumber(result.confirmed_features)}
          </li>
        </ul>
      </details>
    </li>
  );
}

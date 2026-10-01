import type { Metadata } from "next";
import Link from "next/link";

import { Sourced } from "@/components/sourced";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { faNumber, faToman } from "@/lib/listing";
import {
  CAUTION_TEXT,
  COMPONENT_TEXT,
  DATE_CAVEAT_TEXT,
  EXAMPLE_QUERIES,
  MISSING_TEXT,
  budgetChoices,
  displaySegments,
  exclusionSummary,
  intentChips,
  type SearchOut,
  type SearchResultOut,
} from "@/lib/search";

export const metadata: Metadata = { title: "جستجو · ویلاسنج" };

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

type SearchParams = Record<string, string | string[] | undefined>;

async function runSearch(query: string): Promise<SearchOut | "error"> {
  try {
    const { data } = await apiClient().POST("/search", { body: { query }, cache: "no-store" });
    return data ?? "error";
  } catch {
    return "error";
  }
}

function searchHref(query: string): string {
  return `/search?${new URLSearchParams({ q: query })}`;
}

export default async function SearchPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const result = query.length >= 2 ? await runSearch(query) : null;
  const now = new Date();
  return (
    <main className="mx-auto max-w-4xl px-4 pt-6 pb-16 sm:px-6">
      <h1 className="text-2xl font-semibold text-balance">ویلاسنج</h1>
      <p className="mt-1 text-stone-600 text-pretty">
        ویلای مناسب را بنویسید؛ با قیمت نهایی، دلیل رتبه و منبع هر عدد.
      </p>
      <form action="/search" method="get" className="mt-4 flex gap-2" role="search">
        <label htmlFor="q" className="sr-only">
          جستجو
        </label>
        <input
          id="q"
          name="q"
          defaultValue={query}
          placeholder="مثلاً ویلای استخردار در رامسر برای ۶ نفر آخر هفته‌ی بعد"
          className={cn(
            "min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2",
            FOCUS,
          )}
        />
        <button
          type="submit"
          className={cn(
            "rounded-lg bg-emerald-800 px-4 py-2 font-medium text-white hover:bg-emerald-900",
            FOCUS,
          )}
        >
          جستجو
        </button>
      </form>
      {result === null ? <Examples /> : null}
      {result === "error" ? (
        <p className="mt-6 text-sm text-stone-600" role="alert">
          جستجو انجام نشد. API در دسترس است؟
        </p>
      ) : null}
      {result && result !== "error" ? <Results result={result} now={now} /> : null}
    </main>
  );
}

function Examples() {
  return (
    <section aria-label="نمونه‌ی جستجو" className="mt-6">
      <p className="text-sm text-stone-500">نمونه:</p>
      <ul className="mt-2 space-y-1.5">
        {EXAMPLE_QUERIES.map((q) => (
          <li key={q}>
            <Link
              href={searchHref(q)}
              className={cn("text-emerald-800 underline underline-offset-4", FOCUS)}
            >
              {q}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Results({ result, now }: { result: SearchOut; now: Date }) {
  const chips = intentChips(result);
  const choices = budgetChoices(result);
  const excluded = exclusionSummary(result.excluded);
  return (
    <>
      <section aria-label="برداشت از جستجو" className="mt-6">
        <ul className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li
              key={chip}
              className="rounded-full border border-stone-300 bg-white px-3 py-1 text-sm"
            >
              {chip}
            </li>
          ))}
        </ul>
        {(result.dates?.caveats ?? []).map((c) => (
          <p key={c} className="mt-2 text-sm text-stone-600">
            {DATE_CAVEAT_TEXT[c] ?? c}
          </p>
        ))}
        {result.unresolved_places.length > 0 ? (
          <p className="mt-2 text-sm text-stone-600">
            این مکان را نمی‌شناسیم و در جستجو لحاظ نشد: {result.unresolved_places.join("، ")}
          </p>
        ) : null}
      </section>
      {result.missing.length > 0 || choices.length > 0 ? (
        <section
          aria-label="پرسش"
          className="mt-4 rounded-lg border border-stone-300 bg-white p-4 text-sm"
        >
          <ul className="space-y-1.5">
            {result.missing.map((m) => (
              <li key={m}>{MISSING_TEXT[m] ?? m}</li>
            ))}
          </ul>
          {choices.length > 0 ? (
            <div className="mt-1">
              <p>بودجه برای هر شب است یا کل اقامت؟ نتیجه‌ها فرق می‌کند:</p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {choices.map((c) => (
                  <li key={c.label}>
                    <Link
                      href={searchHref(c.query)}
                      className={cn(
                        "inline-block rounded-md border border-emerald-700 px-3 py-1 text-emerald-900 hover:bg-emerald-50",
                        FOCUS,
                      )}
                    >
                      {c.label} ({faNumber(c.count)} آگهی)
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-stone-500">تا وقتی نگفته‌اید، سخت‌گیرانه‌تر حساب شده.</p>
            </div>
          ) : null}
        </section>
      ) : null}
      {result.explanation ? (
        <section aria-labelledby="why-title" className="mt-6 rounded-lg bg-emerald-50 p-4">
          <h2 id="why-title" className="font-semibold text-balance">
            چرا گزینه‌ی اول؟
          </h2>
          <p className="mt-1.5 leading-8 text-pretty">
            {displaySegments(result.explanation.segments).map((segment, index) =>
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
          {result.explanation.source === "template" ? (
            <p className="mt-2 text-xs text-stone-600">این توضیح از قالب ثابت ساخته شد.</p>
          ) : null}
        </section>
      ) : null}
      {result.results.length > 0 ? (
        <section aria-labelledby="results-title" className="mt-8">
          <h2 id="results-title" className="text-lg font-semibold text-balance">
            {faNumber(result.total_results)} آگهی مناسب
            {result.total_results > result.results.length
              ? ` (${faNumber(result.results.length)} تای اول)`
              : ""}
          </h2>
          <p className="mt-1 text-sm text-pretty text-stone-600">
            اول آگهی‌هایی که امکانات خواسته‌شده‌شان تأیید شده، بعد بقیه؛ در هر گروه به ترتیب قیمت
            برای هر نفر و امتیاز مهمان‌ها. نتیجه‌ها هنوز در سطح آگهی است: یک ویلا ممکن است در دو
            پلتفرم دو بار بیاید.
          </p>
          <ol className="mt-4 space-y-3">
            {result.results.map((r, index) => (
              <ResultCard key={r.listing_id} result={r} rank={index + 1} now={now} />
            ))}
          </ol>
        </section>
      ) : null}
      {excluded.length > 0 ? (
        <section aria-label="کنار گذاشته‌ها" className="mt-6 text-sm text-stone-600">
          <p>کنار گذاشته شد:</p>
          <ul className="mt-1 list-disc ps-5">
            {excluded.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}
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
  return (
    <li className="flex gap-3 rounded-lg border border-stone-200 bg-white p-3">
      {result.photo ? (
        // eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server
        <img
          src={result.photo}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="size-24 shrink-0 rounded-md bg-stone-200 object-cover sm:size-28"
        />
      ) : null}
      <div className="min-w-0 flex-1 space-y-1 text-sm">
        <p className="font-medium">
          <span className="text-stone-500 tabular-nums">{faNumber(rank)}. </span>
          <Link
            href={`/listings/${result.platform}/${result.external_id}`}
            className={cn("underline-offset-4 hover:underline", FOCUS)}
          >
            {result.title}
          </Link>
          <span className="ms-2 text-xs font-normal text-stone-500">{result.platform_name}</span>
        </p>
        <p className="tabular-nums">
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
            <span className="text-stone-500">قیمت معلوم نیست</span>
          )}
          {result.price_per_person_night_toman !== null && result.total ? (
            <span className="ms-2 text-stone-500">
              (هر نفر هر شب{" "}
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
              )
            </span>
          ) : null}
        </p>
        {result.cautions.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5 text-xs">
            {result.cautions.map((c) => (
              <li key={c} className="rounded bg-stone-100 px-1.5 py-0.5 text-stone-700">
                {CAUTION_TEXT[c] ?? c}
              </li>
            ))}
          </ul>
        ) : null}
        <details className="text-xs text-stone-600">
          <summary className={cn("cursor-pointer", FOCUS)}>چرا این رتبه؟</summary>
          <ul className="mt-1 space-y-0.5 tabular-nums">
            {result.contributions.map((c) => (
              <li key={c.component}>
                {COMPONENT_TEXT[c.component] ?? c.component}: {faNumber(Math.round(c.points * 100))}{" "}
                از {faNumber(Math.round(c.weight * 100))} امتیاز
              </li>
            ))}
            <li>امکانات خواسته‌شده‌ی تأییدشده: {faNumber(result.confirmed_features)}</li>
          </ul>
        </details>
      </div>
    </li>
  );
}

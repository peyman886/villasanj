import { Check, ChevronDown, MapPin, Star } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { PhotoCarousel } from "@/components/search/carousel";
import { Sourced } from "@/components/sourced";
import { cn } from "@/lib/cn";
import { COPY, onPlatforms } from "@/lib/copy";
import {
  areaText,
  distanceRange,
  durationRange,
  faDigits,
  faNum,
  priceFrom,
  rating,
  shortAmount,
} from "@/lib/numbers";
import { toneOf } from "@/lib/platforms";
import {
  CAUTION_TEXT,
  COMPONENT_TEXT,
  FEATURE_TEXT,
  cardOffers,
  headline,
  type SearchResultOut,
} from "@/lib/search";

/** Where a requested feature's evidence comes from, said in a few words (never «تأیید» for host words). */
export const EVIDENCE_TEXT = {
  photo: "در عکس‌ها دیده شد",
  map: "روی نقشه تأیید شد",
  amenities: "در فهرست امکانات آگهی",
} as const;

const QUIET_CAUTIONS = new Set(["may_exceed_budget"]); // «از» already says it (S9)

export type CardContext = {
  stay: string | null; // «۲ شب، ۶ نفر»
  villaHref: (villaId: string) => string; // keeps the search's dates and guests
  now: Date;
};

/** «۳ خوابه ∙ تا ۸ مهمان ∙ ۲۲۰ تا ۳۰۰ متر»: the facts line of a card and of its map pin. */
export function cardFacts(result: SearchResultOut): string {
  return [
    result.bedrooms !== null ? `${faNum(result.bedrooms)} خوابه` : null,
    result.max_capacity !== null ? `تا ${faNum(result.max_capacity)} مهمان` : null,
    areaText([result.area_m2, ...result.also_on.map((o) => o.area_m2)]),
  ]
    .filter(Boolean)
    .join(" ∙ ");
}

/** Where a result's card links: the villa page (with the stay) or the single listing. */
export function cardHref(result: SearchResultOut, context: CardContext): string {
  return result.villa_id
    ? context.villaHref(result.villa_id)
    : `/listings/${result.platform}/${result.external_id}`;
}

/**
 * One result. Wide screens: a fixed photo frame beside a fixed-height body, so every card in the
 * list has the same size whatever the photos' shapes. The body reads top to bottom: facts, name,
 * location, the requested feature we confirmed; then rating and each platform's own price
 * (never merged, rule 3) on one side and the headline price with the one button on the other.
 */
export function ResultCard({
  result,
  first,
  context,
  explanation,
}: {
  result: SearchResultOut;
  first: boolean;
  context: CardContext;
  explanation?: ReactNode;
}) {
  const id = result.listing_id.replace(/[^a-z0-9]/gi, "-");
  const title = faDigits(result.title);
  const offers = cardOffers(result);
  const top = headline(offers);
  const multi = offers.length > 1;
  const href = cardHref(result, context);
  const facts = cardFacts(result);
  const geo = result.geo;
  const highlights = result.confirmed.slice(0, 2);
  const cautions = result.cautions.filter((c) => !QUIET_CAUTIONS.has(c));
  return (
    <li
      data-result={result.listing_id}
      className="overflow-hidden rounded-card border border-line bg-surface shadow-raised transition-[border-color,box-shadow] duration-150 data-[active]:border-brand-400 data-[active]:shadow-float data-[selected]:border-accent-solid data-[selected]:shadow-float data-[selected]:ring-1 data-[selected]:ring-accent-solid"
    >
      <article
        aria-labelledby={`title-${id}`}
        className="grid sm:h-64 sm:grid-cols-[minmax(13rem,2fr)_minmax(0,3fr)]"
      >
        <div className="relative aspect-[16/10] sm:aspect-auto sm:h-full">
          <PhotoCarousel
            photos={result.photos.length ? result.photos : result.photo ? [result.photo] : []}
            label={title}
          />
          {first ? (
            <span className="pointer-events-none absolute start-3 top-3 rounded-full bg-surface/95 px-2.5 py-1 text-xs font-semibold text-brand-900 shadow-raised">
              {COPY.bestMatch}
            </span>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-col p-4 sm:ps-5">
          {facts ? (
            <p className="truncate text-[0.8125rem] text-fg-muted tabular-nums">{facts}</p>
          ) : null}
          <h3 id={`title-${id}`} className="mt-0.5 text-lg leading-snug font-bold">
            <Link
              href={href}
              title={title}
              className="focus-ring line-clamp-1 rounded-sm underline-offset-4 hover:text-accent hover:underline"
            >
              {title}
            </Link>
          </h3>
          {geo && (geo.coast_m || geo.drive_s) ? (
            <p className="mt-1 flex min-w-0 items-center gap-1.5 text-sm text-fg-muted tabular-nums">
              <MapPin aria-hidden="true" className="size-4 shrink-0 text-fg-subtle" />
              <span className="truncate">
                {geo.coast_m ? (
                  <Sourced
                    quiet
                    id={`coast-${id}`}
                    label="فاصله تا دریا"
                    value={`${geo.coast_m.text} (فاصله‌ی خط مستقیم از محدوده‌ی تقریبی آگهی تا ساحل، OpenStreetMap)`}
                    provenance={geo.coast_m.provenance}
                    now={context.now}
                  >
                    {distanceRange(geo.coast_m.low, geo.coast_m.high)} تا دریا
                  </Sourced>
                ) : null}
                {geo.coast_m && geo.drive_s ? <span aria-hidden="true"> ∙ </span> : null}
                {geo.drive_s ? (
                  <Sourced
                    quiet
                    id={`drive-${id}`}
                    label="زمان رانندگی"
                    value={geo.drive_s.text}
                    provenance={geo.drive_s.provenance}
                    now={context.now}
                  >
                    {durationRange(geo.drive_s.low, geo.drive_s.high)} از تهران
                  </Sourced>
                ) : null}
              </span>
            </p>
          ) : null}
          {highlights.length ? (
            <ul className="mt-2.5 flex min-w-0 flex-wrap gap-1.5 overflow-hidden text-xs sm:max-h-6">
              {highlights.map((h) => (
                <li
                  key={h.feature}
                  className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 leading-none text-brand-900"
                >
                  <Check aria-hidden="true" className="size-3.5 shrink-0" />
                  <span className="font-semibold">{FEATURE_TEXT[h.feature] ?? h.feature}</span>
                  <span className="text-brand-800">{EVIDENCE_TEXT[h.source]}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mt-auto flex flex-wrap items-end justify-between gap-x-4 gap-y-3 pt-4">
            <div className="min-w-0 space-y-1.5 text-[0.8125rem]">
              {result.rating !== null && result.rating_count ? (
                <p className="flex items-center gap-1 tabular-nums">
                  <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
                  <span className="font-semibold">{rating(result.rating)}</span>
                  <span className="text-fg-muted">
                    ({faNum(result.rating_count)} امتیاز در {result.platform_name})
                  </span>
                </p>
              ) : null}
              {multi ? (
                <OfferRows offers={offers} id={id} now={context.now} />
              ) : (
                <p className="text-fg-muted">
                  فقط {onPlatforms("", top?.platformName ?? result.platform_name)}
                </p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2 text-end">
              <div>
                {top?.total ? (
                  <p className="text-xl leading-tight font-extrabold tabular-nums">
                    <Sourced
                      quiet
                      id={`price-${id}`}
                      label={`قیمت ${title} در ${top.platformName}`}
                      value={priceFrom(top.total)}
                      provenance={top.provenance}
                      sourceName={top.platformName}
                      now={context.now}
                    >
                      {priceFrom(top.total)}
                    </Sourced>
                  </p>
                ) : (
                  <p className="text-base text-fg-muted">قیمت معلوم نیست</p>
                )}
                <p className="text-xs text-fg-muted tabular-nums">
                  {[
                    context.stay ? `برای ${context.stay}` : null,
                    multi ? onPlatforms(faNum(offers.length)) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <Link
                href={href}
                className="focus-ring inline-flex h-10 items-center rounded-control bg-accent-solid px-5 text-sm font-semibold whitespace-nowrap text-white shadow-raised transition-colors hover:bg-accent-solid-hover active:scale-[0.98]"
              >
                {multi ? COPY.compareOffers : "دیدن ویلا"}
                <span className="sr-only">: {title}</span>
              </Link>
            </div>
          </div>
        </div>
      </article>
      {explanation}
      <details className="group border-t border-line text-sm">
        <summary className="focus-ring flex cursor-pointer list-none items-center gap-1 px-4 py-1.5 text-fg-muted hover:text-fg [&::-webkit-details-marker]:hidden">
          چرا اینجا؟
          <ChevronDown
            aria-hidden="true"
            className="size-4 transition-transform group-open:rotate-180"
          />
        </summary>
        <div className="space-y-3 px-4 pb-4">
          <ul className="grid gap-2 sm:grid-cols-2">
            {result.contributions.map((c) => {
              const share = c.weight > 0 ? Math.max(0, Math.min(1, c.points / c.weight)) : 0;
              return (
                <li key={c.component}>
                  <div className="flex justify-between gap-2 text-xs text-fg-muted tabular-nums">
                    <span>{COMPONENT_TEXT[c.component] ?? c.component}</span>
                    <span>
                      {faNum(Math.round(c.points * 100))} از {faNum(Math.round(c.weight * 100))}
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
          </ul>
          <p className="text-xs text-fg-muted tabular-nums">
            امکانات خواسته‌شده‌ی تأییدشده: {faNum(result.confirmed_features)}
            {result.confirmed.length > 1
              ? ` (${result.confirmed
                  .map((c) => `${FEATURE_TEXT[c.feature] ?? c.feature}: ${EVIDENCE_TEXT[c.source]}`)
                  .join("، ")})`
              : ""}
          </p>
          {cautions.length ? (
            <ul className="space-y-0.5 text-xs text-fg-muted">
              {cautions.map((c) => (
                <li key={c}>{CAUTION_TEXT[c] ?? c}</li>
              ))}
            </ul>
          ) : null}
          {result.mentions.length > 0 ? (
            <p className="text-xs text-fg-muted">
              <Sourced
                id={`mentions-${id}`}
                label="متن آگهی"
                provenance={result.listing_provenance}
                sourceName={result.platform_name}
                now={context.now}
              >
                در متن آگهی آمده: {result.mentions.map((w) => `«${w}»`).join("، ")}
              </Sourced>
            </p>
          ) : null}
        </div>
      </details>
    </li>
  );
}

/** Each platform's own price on its own line, jabama first: «● جاباما ۸٫۵ میلیون ارزان‌تر». */
function OfferRows({
  offers,
  id,
  now,
}: {
  offers: ReturnType<typeof cardOffers>;
  id: string;
  now: Date;
}) {
  return (
    <ul data-offers="" className="space-y-1 tabular-nums">
      {offers.map((o) => (
        <li key={o.listingId} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cn("size-2 shrink-0 rounded-full", toneOf(o.platform).solid)}
          />
          <span className="w-12 shrink-0 text-fg-muted">{o.platformName}</span>
          {o.bookable && o.total ? (
            <Sourced
              quiet
              id={`offer-${id}-${o.platform}`}
              label={`قیمت در ${o.platformName}`}
              value={priceFrom(o.total)}
              provenance={o.provenance}
              sourceName={o.platformName}
              now={now}
              className={cn(o.cheaper ? "font-bold text-fg" : "text-fg-muted")}
            >
              {shortAmount(o.total.low_toman, "lower")}
            </Sourced>
          ) : (
            <span className="text-fg-subtle">{COPY.unavailable}</span>
          )}
          {o.cheaper ? (
            <span className="rounded-full bg-brand-50 px-1.5 py-0.5 text-[0.6875rem] leading-none font-semibold text-brand-800">
              {COPY.cheaper}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

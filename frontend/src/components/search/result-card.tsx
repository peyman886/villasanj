import { ChevronDown, Star } from "lucide-react";
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

/**
 * One result, Torob style: the cheaper platform's own price as «از X» and «در ۲ پلتفرم» under
 * it, then each platform's own offer in one row (prices are never merged, rule 3). One CTA.
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
  const href = result.villa_id
    ? context.villaHref(result.villa_id)
    : `/listings/${result.platform}/${result.external_id}`;
  const specs = [
    result.bedrooms !== null ? `${faNum(result.bedrooms)} خوابه` : null,
    result.max_capacity !== null ? `تا ${faNum(result.max_capacity)} مهمان` : null,
    areaText([result.area_m2, ...result.also_on.map((o) => o.area_m2)]),
  ].filter(Boolean);
  const geo = result.geo;
  const highlight = result.confirmed[0];
  const cautions = result.cautions.filter((c) => !QUIET_CAUTIONS.has(c));
  return (
    <li
      data-result={result.listing_id}
      className="overflow-hidden rounded-card border border-line bg-surface transition-colors duration-100 data-[active]:border-brand-500 data-[active]:ring-1 data-[active]:ring-brand-500"
    >
      <article aria-labelledby={`title-${id}`} className="flex flex-col sm:flex-row">
        <div className="relative aspect-[4/3] shrink-0 sm:aspect-auto sm:w-[38%] sm:min-h-52">
          <PhotoCarousel
            photos={result.photos.length ? result.photos : result.photo ? [result.photo] : []}
            label={title}
          />
          <div className="pointer-events-none absolute start-2 top-2 flex flex-wrap gap-1.5">
            {first ? (
              <span className="rounded-full bg-brand-gradient px-2.5 py-0.5 text-xs font-semibold text-white shadow-raised">
                {COPY.bestMatch}
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5 p-4">
          <h3 id={`title-${id}`} className="text-lg leading-snug font-bold text-balance">
            <Link
              href={href}
              className="focus-ring rounded-sm underline-offset-4 hover:text-accent hover:underline"
            >
              {title}
            </Link>
          </h3>
          {specs.length ? (
            <p className="text-sm text-fg-muted tabular-nums">{specs.join(" ∙ ")}</p>
          ) : null}
          {geo && (geo.coast_m || geo.drive_s) ? (
            <p className="text-sm text-fg-muted tabular-nums">
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
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            {highlight ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-0.5 text-brand-900">
                <span className="font-semibold">
                  {FEATURE_TEXT[highlight.feature] ?? highlight.feature}
                </span>
                <span aria-hidden="true">·</span>
                <span>{EVIDENCE_TEXT[highlight.source]}</span>
              </span>
            ) : null}
            {result.rating !== null && result.rating_count ? (
              <span className="inline-flex items-center gap-1 tabular-nums">
                <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
                <span className="font-semibold">{rating(result.rating)}</span>
                <span className="text-fg-muted">
                  · {faNum(result.rating_count)} امتیاز در {result.platform_name}
                </span>
              </span>
            ) : null}
          </div>

          <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-2">
            <div className="min-w-0">
              {top?.total ? (
                <p className="text-[1.375rem] leading-tight font-bold tabular-nums">
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
              <p className="text-[0.8125rem] text-fg-muted tabular-nums">
                {context.stay ? `برای ${context.stay} · ` : ""}
                {multi
                  ? onPlatforms(faNum(offers.length))
                  : onPlatforms("", top?.platformName ?? result.platform_name)}
              </p>
              {multi ? <OfferRow offers={offers} id={id} now={context.now} /> : null}
            </div>
            <Link
              href={href}
              className="focus-ring inline-flex h-10 shrink-0 items-center rounded-control border border-brand-700 px-4 text-sm font-semibold text-brand-800 transition-colors hover:bg-brand-50"
            >
              {multi ? COPY.compareOffers : "جزئیات ویلا"}
            </Link>
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

/** «جاباما ۸٫۵ میلیون ارزان‌تر | شب ۹٫۲ میلیون»: each platform's own price, jabama first. */
function OfferRow({
  offers,
  id,
  now,
}: {
  offers: ReturnType<typeof cardOffers>;
  id: string;
  now: Date;
}) {
  return (
    <ul
      data-offers=""
      className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] tabular-nums"
    >
      {offers.map((o, index) => (
        <li key={o.listingId} className="flex items-center gap-1.5">
          {index > 0 ? (
            <span aria-hidden="true" className="me-1.5 text-line-strong">
              |
            </span>
          ) : null}
          <span
            aria-hidden="true"
            className={cn("size-2 rounded-full", toneOf(o.platform).solid)}
          />
          <span className="text-fg-muted">{o.platformName}</span>
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
            <span className="rounded-full bg-brand-50 px-1.5 text-xs font-semibold text-brand-800">
              {COPY.cheaper}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

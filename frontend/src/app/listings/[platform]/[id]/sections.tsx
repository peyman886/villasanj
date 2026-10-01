import Link from "next/link";
import type { ReactNode } from "react";

import { Sourced } from "@/components/sourced";
import type {
  CalendarNight,
  Geo,
  GeoRange,
  Listing,
  Offer,
  Review,
  Scenario,
} from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { faPropertyType } from "@/lib/labeling";
import {
  AVAILABILITY_TEXT,
  CAVEAT_TEXT,
  STATUS_TEXT,
  WEEKDAY_HEADERS,
  calendarWeeks,
  faAge,
  faDay,
  faDayOfMonth,
  faMillions,
  faNumber,
  faStayed,
  faToman,
  offerText,
} from "@/lib/listing";

export type ScenarioOffers = { scenario: Scenario; offers: (Offer | null)[] };

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";
const MAX_PHOTOS = 6;
const MAX_REVIEWS = 20;

function SectionTitle({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="text-lg font-semibold text-balance">
      {children}
    </h2>
  );
}

export function Header({ listing, geo, now }: { listing: Listing; geo: Geo | null; now: Date }) {
  const facts: [string, number | null, string][] = [
    ["اتاق خواب", listing.bedrooms, ""],
    ["سرویس بهداشتی", listing.bathrooms, ""],
    ["متراژ", listing.area_m2, " متر"],
    ["ظرفیت پایه", listing.base_capacity, " نفر"],
    ["حداکثر ظرفیت", listing.max_capacity, " نفر"],
  ];
  const place = [listing.city, listing.locality].filter(Boolean).join("، ");
  return (
    <header>
      <p className="text-sm text-stone-500">
        <Link href="/" className={cn("underline-offset-4 hover:underline", FOCUS)}>
          ویلاسنج
        </Link>{" "}
        / آگهی در {listing.platform_name}
      </p>
      <h1 className="mt-2 text-2xl font-semibold text-balance">{listing.title}</h1>
      <p className="mt-1 text-stone-600">
        {place || "محل منتشر نشده"} · {faPropertyType(listing.property_type)}
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {facts.map(([label, value, suffix], index) => (
          <div key={label} className="rounded-lg border border-stone-200 bg-white p-3">
            <dt className="text-xs text-stone-500">{label}</dt>
            <dd className="mt-1 font-medium tabular-nums">
              {value === null ? (
                <span className="text-stone-500">منتشر نشده</span>
              ) : (
                <Sourced
                  id={`fact-${index}`}
                  label={label}
                  provenance={listing.provenance}
                  sourceName={listing.platform_name}
                  now={now}
                >
                  {faNumber(value)}
                  {suffix}
                </Sourced>
              )}
            </dd>
          </div>
        ))}
        <div className="rounded-lg border border-stone-200 bg-white p-3">
          <dt className="text-xs text-stone-500">امتیاز در {listing.platform_name}</dt>
          <dd className="mt-1 font-medium tabular-nums">
            {listing.rating === null ? (
              <span className="text-stone-500">بدون امتیاز</span>
            ) : (
              <Sourced
                id="fact-rating"
                label="امتیاز"
                provenance={listing.provenance}
                sourceName={listing.platform_name}
                now={now}
              >
                {faNumber(listing.rating)} از ۵
              </Sourced>
            )}
            {listing.rating_count ? (
              <span className="ms-1 text-xs font-normal text-stone-500">
                ({faNumber(listing.rating_count)} رأی)
              </span>
            ) : null}
          </dd>
        </div>
      </dl>
      <GeoFacts geo={geo} now={now} />
      <p className="mt-4 max-w-prose text-sm text-pretty text-stone-600">
        این صفحه‌ی یک آگهی است و قیمت و تقویمش فقط مال همین آگهی است. صفحه‌ی ویلا که همه‌ی آگهی‌های
        یک ویلا را کنار هم می‌گذارد، بعد از تطبیق آگهی‌ها ساخته می‌شود.{" "}
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className={cn("text-emerald-800 underline underline-offset-4", FOCUS)}
        >
          دیدن آگهی در {listing.platform_name}
        </a>
      </p>
    </header>
  );
}

/** Distance to the coast and free-flow drive time, from OpenStreetMap (ADR-0013). */
export function GeoFacts({ geo, now }: { geo: Geo | null; now: Date }) {
  if (!geo || (!geo.coast_m && !geo.drive_s)) return null;
  const facts: [string, string, GeoRange | null][] = [
    ["coast", "فاصله تا ساحل", geo.coast_m],
    ["drive", "زمان رانندگی", geo.drive_s],
  ];
  return (
    <dl className="mt-3 grid gap-3 sm:grid-cols-2">
      {facts.map(([key, label, range]) =>
        range ? (
          <div key={key} className="rounded-lg border border-stone-200 bg-white p-3">
            <dt className="text-xs text-stone-500">{label}</dt>
            <dd className="mt-1 text-sm font-medium tabular-nums">
              <Sourced
                id={`geo-${key}`}
                label={label}
                value={range.text}
                provenance={range.provenance}
                now={now}
              >
                {range.text}
              </Sourced>
              {range.radius_assumed ? (
                <span className="mt-1 block text-xs font-normal text-stone-500">
                  پلتفرم دقت نقطه را اعلام نکرده؛ تا ۵۰۰ متر خطا فرض شده.
                </span>
              ) : null}
            </dd>
          </div>
        ) : null,
      )}
    </dl>
  );
}

export function Photos({ listing }: { listing: Listing }) {
  const photos = listing.photos.slice(0, MAX_PHOTOS);
  if (photos.length === 0) {
    return <p className="mt-6 text-sm text-stone-500">این آگهی عکسی منتشر نکرده است.</p>;
  }
  return (
    <section aria-label="عکس‌ها" className="mt-6">
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {photos.map((url, index) => (
          <li key={url}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
              className={cn("block overflow-hidden rounded-lg bg-stone-200", FOCUS)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
              <img
                src={url}
                alt={`عکس ${faNumber(index + 1)} از ${faNumber(listing.photos.length)}`}
                loading="lazy"
                decoding="async"
                referrerPolicy="no-referrer"
                className="aspect-[4/3] w-full object-cover"
              />
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-stone-500">
        عکس‌ها مستقیم از سرور {listing.platform_name} نمایش داده می‌شوند.
      </p>
    </section>
  );
}

function OfferCell({
  offer,
  id,
  label,
  common,
  listing,
  now,
}: {
  offer: Offer | null;
  id: string;
  label: string;
  common: Set<string>;
  listing: Listing;
  now: Date;
}) {
  if (offer === null) return <span className="text-stone-500">پاسخی دریافت نشد</span>;
  const own = offer.caveats.filter((c) => !common.has(c));
  return (
    <div className="space-y-1">
      <p className="font-medium tabular-nums">
        {offer.total ? (
          <Sourced
            id={id}
            label={label}
            value={faToman(offer.total)}
            provenance={offer.provenance}
            sourceName={listing.platform_name}
            now={now}
          >
            {offerText(offer)}
          </Sourced>
        ) : (
          <span className="font-normal text-stone-600">{offerText(offer)}</span>
        )}
      </p>
      {offer.total && offer.status !== "bookable" ? (
        <p className="text-xs text-stone-600">{STATUS_TEXT[offer.status] ?? offer.status}</p>
      ) : null}
      <p className="text-xs text-stone-500">
        مشاهده {faAge(offer.provenance.oldest_input_at, now)}
        {offer.stale ? (
          <span className="ms-2 rounded bg-stone-200 px-1.5 py-0.5 text-stone-700">قدیمی</span>
        ) : null}
      </p>
      {own.length > 0 ? (
        <ul className="list-disc ps-4 text-xs text-stone-600">
          {own.map((c) => (
            <li key={c}>{CAVEAT_TEXT[c] ?? c}</li>
          ))}
        </ul>
      ) : null}
      {offer.nights.length > 0 ? (
        <details className="text-xs">
          <summary className={cn("cursor-pointer text-stone-600", FOCUS)}>جزئیات شب‌ها</summary>
          <ul className="mt-1 space-y-1">
            {offer.nights.map((n) => (
              <li key={n.night} className="tabular-nums">
                {faDay(n.night)}:{" "}
                <Sourced
                  id={`${id}-${n.night}`}
                  label={`قیمت شب ${faDay(n.night)}`}
                  value={faToman(n.price)}
                  provenance={n.price_provenance}
                  sourceName={listing.platform_name}
                  now={now}
                >
                  {faToman(n.price)}
                </Sourced>
                {n.extra_guests > 0 ? (
                  <>
                    {" "}
                    + {faNumber(n.extra_guests)} نفر اضافه ×{" "}
                    <Sourced
                      id={`${id}-${n.night}-extra`}
                      label={`هزینه‌ی نفر اضافه در شب ${faDay(n.night)}`}
                      value={faToman(n.extra_guest_price)}
                      provenance={n.extra_guest_provenance}
                      sourceName={listing.platform_name}
                      now={now}
                    >
                      {faToman(n.extra_guest_price)}
                    </Sourced>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

export function OffersSection({
  listing,
  scenarios,
  now,
}: {
  listing: Listing;
  scenarios: ScenarioOffers[];
  now: Date;
}) {
  const guests = scenarios[0]?.scenario.guests ?? [];
  // Caveats every priced offer shares are said once, under the table.
  const priced = scenarios.flatMap((s) => s.offers).filter((o) => o !== null && o.total !== null);
  const common = new Set(
    (priced[0]?.caveats ?? []).filter((c) => priced.every((o) => o?.caveats.includes(c))),
  );
  return (
    <section aria-labelledby="offers-title" className="mt-10">
      <SectionTitle id="offers-title">قیمت نهایی برای هر سناریو</SectionTitle>
      <p className="mt-1 max-w-prose text-sm text-pretty text-stone-600">
        جمع قیمت شب‌ها و هزینه‌ی نفر اضافه برای همین آگهی، از آخرین مشاهده‌ی تقویم. روی هر مبلغ
        بزنید تا منبع و زمان مشاهده‌اش را ببینید.
      </p>
      {scenarios.length === 0 ? (
        <p className="mt-4 text-sm text-stone-500">سناریویی تعریف نشده است.</p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-stone-200 bg-white">
          <table className="w-full min-w-[32rem] text-start text-sm">
            <caption className="sr-only">قیمت نهایی این آگهی برای هر سناریو و تعداد نفر</caption>
            <thead className="bg-stone-100 text-stone-600">
              <tr>
                <th scope="col" className="p-3 text-start font-medium">
                  سناریو
                </th>
                {guests.map((g) => (
                  <th key={g} scope="col" className="p-3 text-start font-medium tabular-nums">
                    {faNumber(g)} نفر
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200">
              {scenarios.map(({ scenario, offers: row }) => (
                <tr key={scenario.slug} className="align-top">
                  <th scope="row" className="p-3 text-start font-medium">
                    {scenario.name}
                    <span className="mt-0.5 block text-xs font-normal text-stone-500">
                      {faDay(scenario.check_in)} تا {faDay(scenario.check_out)}
                    </span>
                  </th>
                  {row.map((offer, index) => (
                    <td key={scenario.guests[index]} className="p-3">
                      <OfferCell
                        offer={offer}
                        id={`offer-${scenario.slug}-${scenario.guests[index]}`}
                        label={`قیمت ${scenario.name} برای ${faNumber(scenario.guests[index])} نفر`}
                        common={common}
                        listing={listing}
                        now={now}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {common.size > 0 ? (
        <ul className="mt-3 list-disc ps-5 text-sm text-pretty text-stone-600">
          {[...common].map((c) => (
            <li key={c}>{CAVEAT_TEXT[c] ?? c}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

const CELL_TONE: Record<string, string> = {
  available: "border-emerald-200 bg-emerald-50",
  unknown: "border-stone-200 bg-white",
};

function NightCell({ night, listing, now }: { night: CalendarNight; listing: Listing; now: Date }) {
  const price = night.price;
  return (
    <Sourced
      id={`night-${night.night}`}
      label={`شب ${faDay(night.night)}`}
      value={[
        AVAILABILITY_TEXT[night.availability] ?? night.availability,
        price ? faToman(price) : "قیمت منتشر نشده",
        night.min_nights ? `حداقل ${faNumber(night.min_nights)} شب` : null,
      ]
        .filter(Boolean)
        .join("، ")}
      provenance={night.provenance}
      sourceName={listing.platform_name}
      now={now}
      className={cn(
        "block w-full rounded-md border p-1 text-center no-underline sm:p-1.5",
        CELL_TONE[night.availability] ?? "border-stone-200 bg-stone-100 text-stone-700",
      )}
    >
      <span className="block font-medium tabular-nums">{faDayOfMonth(night.night)}</span>
      <span className="block text-[0.625rem] leading-tight sm:text-[0.7rem]">
        {AVAILABILITY_TEXT[night.availability] ?? night.availability}
      </span>
      {price ? (
        <span className="block text-[0.625rem] leading-tight tabular-nums sm:text-[0.7rem]">
          {faMillions(price.low_toman)}
        </span>
      ) : null}
      {night.is_holiday ? (
        <span className="block text-[0.7rem] leading-tight font-medium">تعطیل</span>
      ) : null}
    </Sourced>
  );
}

export function CalendarSection({
  listing,
  nights,
  start,
  days,
  now,
}: {
  listing: Listing;
  nights: CalendarNight[];
  start: string;
  days: number;
  now: Date;
}) {
  const weeks = calendarWeeks(nights, start, days);
  return (
    <section aria-labelledby="calendar-title" className="mt-10">
      <SectionTitle id="calendar-title">تقویم {faNumber(days)} شب آینده</SectionTitle>
      <p className="mt-1 max-w-prose text-sm text-pretty text-stone-600">
        هر خانه آخرین مشاهده‌ی همان شب است، نه وضعیت قطعی. قیمت هر شب به میلیون تومان است و مبلغ
        دقیقش در منبع هر خانه آمده. «پر یا بسته» یعنی پلتفرم نگفته رزرو شده یا میزبان بسته است.
      </p>
      {nights.length === 0 ? (
        <p className="mt-4 text-sm text-stone-500">برای این بازه مشاهده‌ای از تقویم نداریم.</p>
      ) : (
        <table className="mt-4 w-full table-fixed border-separate border-spacing-1 text-xs sm:text-sm">
          <caption className="sr-only">تقویم آزاد و پر بودن شب‌ها با قیمت هر شب</caption>
          <thead>
            <tr>
              {WEEKDAY_HEADERS.map((name) => (
                <th key={name} scope="col" className="py-1 font-normal text-stone-500">
                  <span aria-hidden="true" className="sm:hidden">
                    {name[0]}
                  </span>
                  <span className="max-sm:sr-only">{name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map((week) => (
              <tr key={week.find((c) => c !== null)?.day}>
                {week.map((cell, index) => (
                  <td key={cell?.day ?? `empty-${index}`} className="p-0 align-top">
                    {cell === null ? null : cell.night === null ? (
                      <div className="rounded-md border border-dashed border-stone-300 p-1 text-center text-stone-600 sm:p-1.5">
                        <span className="block tabular-nums">{faDayOfMonth(cell.day)}</span>
                        <span className="block text-[0.7rem] leading-tight">بی‌داده</span>
                      </div>
                    ) : (
                      <NightCell night={cell.night} listing={listing} now={now} />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function ReviewsSection({
  listing,
  reviews,
  now,
}: {
  listing: Listing;
  reviews: Review[];
  now: Date;
}) {
  const shown = reviews.slice(0, MAX_REVIEWS);
  return (
    <section aria-labelledby="reviews-title" className="mt-10">
      <SectionTitle id="reviews-title">نظرهای مهمان‌ها</SectionTitle>
      <p className="mt-1 max-w-prose text-sm text-pretty text-stone-600">
        نظرهایی که صفحه‌ی آگهی در {listing.platform_name} نشان می‌داد ({faNumber(reviews.length)}{" "}
        نظر)؛ نام نویسنده‌ها ذخیره نمی‌شود.
      </p>
      {shown.length === 0 ? (
        <p className="mt-4 text-sm text-stone-500">نظری ذخیره نشده است.</p>
      ) : (
        <ol className="mt-4 divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {shown.map((review, index) => (
            <li key={review.id} className="p-4">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                {review.rating === null ? (
                  <span className="text-stone-500">بدون امتیاز</span>
                ) : (
                  <span className="font-medium tabular-nums">
                    <Sourced
                      id={`review-${index}`}
                      label="امتیاز این نظر"
                      provenance={review.provenance}
                      sourceName={listing.platform_name}
                      now={now}
                    >
                      {faNumber(review.rating)} از ۵
                    </Sourced>
                  </span>
                )}
                <span className="text-stone-500">{faStayed(review)}</span>
                {review.host_replied ? (
                  <span className="text-xs text-stone-500">میزبان پاسخ داده</span>
                ) : null}
              </div>
              {review.text ? (
                <p className="mt-1.5 text-pretty">{review.text}</p>
              ) : (
                <p className="mt-1.5 text-sm text-stone-500">بدون متن</p>
              )}
            </li>
          ))}
        </ol>
      )}
      {reviews.length > shown.length ? (
        <p className="mt-2 text-sm text-stone-500">
          و {faNumber(reviews.length - shown.length)} نظر دیگر در صفحه‌ی آگهی.
        </p>
      ) : null}
    </section>
  );
}

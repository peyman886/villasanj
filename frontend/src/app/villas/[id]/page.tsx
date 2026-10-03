import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { notFound } from "next/navigation";

import { ListingMap } from "@/components/listing-map";
import { Sourced } from "@/components/sourced";
import {
  apiClient,
  type Claims,
  type Listing,
  type Offer,
  type Scenario,
  type Villa,
  type VillaNight,
  type VillaReview,
} from "@/lib/api/client";
import { readBasemap } from "@/lib/basemap";
import { cn } from "@/lib/cn";
import { faPropertyType } from "@/lib/labeling";
import {
  AVAILABILITY_TEXT,
  CLAIM_TARGET_TEXT,
  addDays,
  faDay,
  faMillions,
  faNumber,
  faStayed,
  faToman,
  iranToday,
} from "@/lib/listing";

import { FEATURE_TEXT } from "@/lib/search";

import {
  ClaimsSection,
  OfferCell,
  ReviewSummarySkeleton,
  SummaryCard,
  reviewAnchor,
} from "../../listings/[platform]/[id]/sections";

export const metadata: Metadata = { title: "ویلا · ویلاسنج" };

const NO_STORE = { cache: "no-store" } as const;
const CALENDAR_DAYS = 30;
const ASSUMED_RADIUS_M = 500;
const MAX_REVIEWS = 40; // as many as a summary reads, so every citation has its review
const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

const FIELD_TEXT: Record<string, string> = {
  property_type: "نوع",
  bedrooms: "اتاق خواب",
  bathrooms: "سرویس بهداشتی",
  area_m2: "متراژ",
  base_capacity: "ظرفیت پایه",
  max_capacity: "حداکثر ظرفیت",
};

type ScenarioOffers = { scenario: Scenario; byGuests: { guests: number; offers: Offer[] }[] };

async function load(id: string, now: Date) {
  const api = apiClient();
  const path = { villa_id: id };
  const villa = await api.GET("/villas/{villa_id}", { params: { path }, ...NO_STORE });
  if (!villa.data) return null;
  const start = iranToday(now);
  const [scenarios, calendar, reviews, claims] = await Promise.all([
    api.GET("/scenarios", NO_STORE),
    api.GET("/villas/{villa_id}/calendar", {
      params: { path, query: { start, end: addDays(start, CALENDAR_DAYS) } },
      ...NO_STORE,
    }),
    api.GET("/villas/{villa_id}/reviews", { params: { path }, ...NO_STORE }),
    Promise.all(
      villa.data.members.map(async (m) => {
        const { data } = await api.GET("/listings/{platform}/{external_id}/claims", {
          params: { path: { platform: m.platform, external_id: m.id.split(":")[1] ?? "" } },
          ...NO_STORE,
        });
        return [m, data ?? null] as const;
      }),
    ),
  ]);
  const offers: ScenarioOffers[] = await Promise.all(
    (scenarios.data ?? []).map(async (scenario) => ({
      scenario,
      byGuests: await Promise.all(
        scenario.guests.map(async (guests) => {
          const { data } = await api.GET("/villas/{villa_id}/offers", {
            params: {
              path,
              query: { check_in: scenario.check_in, check_out: scenario.check_out, guests },
            },
            ...NO_STORE,
          });
          return { guests, offers: data ?? [] };
        }),
      ),
    })),
  );
  return {
    villa: villa.data,
    offers,
    calendar: calendar.data ?? [],
    reviews: reviews.data ?? [],
    claims: claims as (readonly [Listing, Claims | null])[],
  };
}

function SectionTitle({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-lg font-semibold text-balance">
      {children}
    </h2>
  );
}

function memberOf(villa: Villa, platform: string): Listing | undefined {
  return villa.members.find((m) => m.platform === platform);
}

const STATEMENT_SOURCE_TEXT: Record<string, string> = {
  amenities: "فهرست امکانات",
  description: "توضیحات",
  distances: "بخش فاصله‌ها",
};

function Inconsistencies({ villa, now }: { villa: Villa; now: Date }) {
  if (villa.inconsistencies.length === 0) return null;
  return (
    <section
      aria-labelledby="inconsistencies-title"
      className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4"
    >
      <h2 id="inconsistencies-title" className="font-medium text-amber-900">
        ادعاهایی که آگهی‌ها یکسان نمی‌گویند
      </h2>
      <p className="mt-1 text-sm text-pretty text-stone-700">
        هر آگهی گفته‌ی خودش را دارد و از اینجا معلوم نیست کدام درست است؛ پیش از رزرو از میزبان
        بپرسید.
      </p>
      <ul className="mt-2 space-y-1 text-sm">
        {villa.inconsistencies.map((x) => {
          const subject =
            x.kind === "feature"
              ? (FEATURE_TEXT[x.subject] ?? x.subject)
              : `فاصله تا ${CLAIM_TARGET_TEXT[x.subject] ?? x.subject}`;
          return (
            <li key={`${x.kind}-${x.subject}`}>
              {subject}:{" "}
              {x.statements.map((said, index) => {
                const member = memberOf(villa, said.platform);
                const name = member?.platform_name ?? said.platform;
                const text =
                  said.says === null
                    ? (said.published ?? "")
                    : said.says === "has"
                      ? "دارد"
                      : "ندارد";
                const where = STATEMENT_SOURCE_TEXT[said.source] ?? said.source;
                return (
                  <span key={said.platform}>
                    {index > 0 ? " · " : ""}
                    {name}{" "}
                    <Sourced
                      id={`inconsistency-${x.kind}-${x.subject}-${said.platform}`}
                      label={`${subject} در ${name}`}
                      provenance={said.provenance}
                      sourceName={name}
                      now={now}
                    >
                      {text}
                    </Sourced>{" "}
                    <span className="text-stone-600">
                      ({where}
                      {said.span && said.source === "description" ? `: «${said.span}»` : ""})
                    </span>
                  </span>
                );
              })}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Conflicts({ villa, now }: { villa: Villa; now: Date }) {
  if (villa.conflicts.length === 0) {
    return (
      <p className="mt-3 text-sm text-stone-600">
        آگهی‌ها در نوع، اتاق، متراژ و ظرفیت ناهمخوانی ندارند.
      </p>
    );
  }
  return (
    <section
      aria-labelledby="conflicts-title"
      className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4"
    >
      <h2 id="conflicts-title" className="font-medium text-amber-900">
        جاهایی که آگهی‌ها با هم نمی‌خوانند
      </h2>
      <ul className="mt-2 space-y-1 text-sm">
        {villa.conflicts.map((c) => (
          <li key={c.field}>
            {FIELD_TEXT[c.field] ?? c.field}:{" "}
            {Object.entries(c.values).map(([platform, value], index) => {
              const member = memberOf(villa, platform);
              const text =
                c.field === "property_type"
                  ? faPropertyType(String(value))
                  : faNumber(Number(value)) + (c.field === "area_m2" ? " متر" : "");
              return (
                <span key={platform}>
                  {index > 0 ? " · " : ""}
                  {member?.platform_name ?? platform}{" "}
                  {member ? (
                    <Sourced
                      id={`conflict-${c.field}-${platform}`}
                      label={`${FIELD_TEXT[c.field] ?? c.field} در ${member.platform_name}`}
                      provenance={member.provenance}
                      sourceName={member.platform_name}
                      now={now}
                    >
                      {text}
                    </Sourced>
                  ) : (
                    text
                  )}
                </span>
              );
            })}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Offers({ villa, offers, now }: { villa: Villa; offers: ScenarioOffers[]; now: Date }) {
  return (
    <section aria-labelledby="offers-title" className="mt-10">
      <SectionTitle id="offers-title">قیمت نهایی در هر پلتفرم</SectionTitle>
      <p className="mt-1 max-w-prose text-sm text-pretty text-stone-600">
        قیمت هر پلتفرم جدا حساب می‌شود و هیچ‌وقت با دیگری ترکیب نمی‌شود؛ هر عدد منبع و زمان
        مشاهده‌اش را دارد.
      </p>
      <div className="mt-4 space-y-6">
        {offers.map(({ scenario, byGuests }) => (
          <div key={scenario.slug}>
            <h3 className="font-medium">
              {scenario.name}{" "}
              <span className="text-sm font-normal text-stone-600 tabular-nums">
                ({faDay(scenario.check_in)} تا {faDay(scenario.check_out)})
              </span>
            </h3>
            <div className="mt-2 overflow-x-auto rounded-lg border border-stone-200 bg-white">
              <table className="w-full min-w-[32rem] text-start text-sm">
                <thead className="bg-stone-100 text-stone-600">
                  <tr>
                    <th scope="col" className="p-2.5 text-start font-medium">
                      پلتفرم
                    </th>
                    {byGuests.map((g) => (
                      <th key={g.guests} scope="col" className="p-2.5 text-start font-medium">
                        {faNumber(g.guests)} نفر
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200 align-top">
                  {villa.members.map((member) => (
                    <tr key={member.id}>
                      <th scope="row" className="p-2.5 text-start font-medium">
                        {member.platform_name}
                      </th>
                      {byGuests.map((g) => {
                        const offer = g.offers.find((o) => o.listing_id === member.id) ?? null;
                        return (
                          <td key={g.guests} className="p-2.5">
                            <OfferCell
                              offer={offer}
                              id={`offer-${scenario.slug}-${g.guests}-${member.platform}`}
                              label={`قیمت ${scenario.name} برای ${faNumber(g.guests)} نفر در ${member.platform_name}`}
                              common={new Set()}
                              listing={member}
                              now={now}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Calendar({ villa, nights, now }: { villa: Villa; nights: VillaNight[]; now: Date }) {
  const hidden = nights.filter((n) => n.hidden).length;
  return (
    <section aria-labelledby="calendar-title" className="mt-10">
      <SectionTitle id="calendar-title">تقویم هر دو پلتفرم</SectionTitle>
      <p className="mt-1 max-w-prose text-sm text-pretty text-stone-600">
        هر شب همان‌طور که هر پلتفرم نشان داده بود. «پنهان» یعنی شبی که در یک پلتفرم آزاد و در دیگری
        پر بود (با کمتر از ۶ ساعت فاصله‌ی مشاهده): {faNumber(hidden)} شب از{" "}
        {faNumber(nights.length)} شب پیش رو.
      </p>
      <div className="mt-3 overflow-x-auto rounded-lg border border-stone-200 bg-white">
        <table className="w-full min-w-[28rem] text-start text-sm tabular-nums">
          <thead className="bg-stone-100 text-stone-600">
            <tr>
              <th scope="col" className="p-2 text-start font-medium">
                شب
              </th>
              {villa.members.map((m) => (
                <th key={m.platform} scope="col" className="p-2 text-start font-medium">
                  {m.platform_name}
                </th>
              ))}
              <th scope="col" className="p-2 text-start font-medium">
                <span className="sr-only">شب پنهان</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200">
            {nights.map((n) => (
              <tr key={n.night} className={n.hidden ? "bg-emerald-50" : undefined}>
                <th scope="row" className="p-2 text-start font-normal">
                  {faDay(n.night)}
                </th>
                {villa.members.map((m) => {
                  const seen = n.by_platform[m.platform];
                  if (!seen)
                    return (
                      <td key={m.platform} className="p-2 text-stone-500">
                        —
                      </td>
                    );
                  const text = `${AVAILABILITY_TEXT[seen.availability] ?? seen.availability}${
                    seen.price ? ` · ${faMillions(seen.price.low_toman)} م` : ""
                  }`;
                  return (
                    <td key={m.platform} className="p-2">
                      <Sourced
                        id={`night-${n.night}-${m.platform}`}
                        label={`شب ${faDay(n.night)} در ${m.platform_name}`}
                        {...(seen.price ? { value: faToman(seen.price) } : {})}
                        provenance={seen.provenance}
                        sourceName={m.platform_name}
                        now={now}
                      >
                        {text}
                      </Sourced>
                    </td>
                  );
                })}
                <td className="p-2 text-xs font-medium text-emerald-900">
                  {n.hidden ? "پنهان" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-stone-600">«م» یعنی میلیون تومان برای یک شب.</p>
    </section>
  );
}

const villaReviewKey = (review: VillaReview) => `${review.platform}:${review.id}`;

/** Pros and cons over every platform's reviews, streamed in (one cached LLM call). */
async function VillaReviewSummary({
  villaId,
  order,
}: {
  villaId: string;
  order: Record<string, number>;
}) {
  let summary = null;
  try {
    const { data } = await apiClient().GET("/villas/{villa_id}/review-summary", {
      params: { path: { villa_id: villaId } },
      ...NO_STORE,
    });
    summary = data ?? null;
  } catch {
    summary = null;
  }
  return (
    <SummaryCard
      summary={summary}
      order={order}
      {...(summary
        ? { title: `خلاصه‌ی ${faNumber(summary.reviews_given)} نظر اخیر از همه‌ی پلتفرم‌ها` }
        : {})}
    />
  );
}

function Reviews({ villa, reviews, now }: { villa: Villa; reviews: VillaReview[]; now: Date }) {
  const shown = reviews.slice(0, MAX_REVIEWS);
  const order = Object.fromEntries(shown.map((r, index) => [villaReviewKey(r), index + 1]));
  return (
    <section aria-labelledby="reviews-title" className="mt-10">
      <SectionTitle id="reviews-title">نظرهای مهمان‌ها در همه‌ی پلتفرم‌ها</SectionTitle>
      <p className="mt-1 text-sm text-stone-600">
        {villa.members
          .map(
            (m) =>
              `${m.platform_name}: ${faNumber(reviews.filter((r) => r.platform === m.platform).length)} نظر`,
          )
          .join(" · ")}
      </p>
      <Suspense fallback={<ReviewSummarySkeleton />}>
        <VillaReviewSummary villaId={villa.id} order={order} />
      </Suspense>
      <ol className="mt-3 divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {shown.map((review, index) => {
          const member = memberOf(villa, review.platform);
          return (
            <li
              key={villaReviewKey(review)}
              id={reviewAnchor(villaReviewKey(review))}
              className="scroll-mt-4 p-4 text-sm"
            >
              <span className="sr-only">نظر {faNumber(index + 1)}</span>
              <p className="flex flex-wrap gap-x-3 text-xs text-stone-600">
                <span className="rounded bg-stone-100 px-1.5 py-0.5 text-stone-700">
                  {member?.platform_name ?? review.platform}
                </span>
                {review.rating === null ? (
                  <span>بدون امتیاز</span>
                ) : (
                  <Sourced
                    id={`villa-review-${index}`}
                    label="امتیاز این نظر"
                    provenance={review.provenance}
                    {...(member ? { sourceName: member.platform_name } : {})}
                    now={now}
                  >
                    {faNumber(review.rating)} از ۵
                  </Sourced>
                )}
                <span>{faStayed(review)}</span>
              </p>
              <p className="mt-1.5 text-pretty">{review.text ?? "بدون متن"}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default async function VillaPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const now = new Date();
  const [data, basemap] = await Promise.all([load(id, now), readBasemap()]);
  if (data === null) notFound();
  const { villa } = data;
  const first = villa.members[0];
  const mapped =
    villa.members.find((m) => m.location?.radius_m) ?? villa.members.find((m) => m.location);
  return (
    <main className="mx-auto max-w-5xl px-4 pt-6 pb-16 sm:px-6">
      <p className="text-sm text-stone-500">
        <Link href="/" className={cn("underline-offset-4 hover:underline", FOCUS)}>
          ویلاسنج
        </Link>
      </p>
      <h1 className="mt-1 text-2xl font-semibold text-balance">{first?.title ?? "ویلا"}</h1>
      <p className="mt-1 text-sm text-pretty text-stone-600">
        یک ویلای واقعی در {faNumber(villa.members.length)} آگهی:{" "}
        {villa.members.map((m, index) => (
          <span key={m.id}>
            {index > 0 ? "، " : ""}
            <Link
              href={`/listings/${m.platform}/${m.id.split(":")[1]}`}
              className={cn("underline underline-offset-4", FOCUS)}
            >
              {m.platform_name}
            </Link>
          </span>
        ))}
        . اینکه این آگهی‌ها یک ویلا هستند را تطبیق خودکار و برچسب‌های انسانی تعیین کرده‌اند.
      </p>
      <Conflicts villa={villa} now={now} />
      <Inconsistencies villa={villa} now={now} />
      {mapped?.location ? (
        <ListingMap
          lat={mapped.location.lat}
          lon={mapped.location.lon}
          radiusM={mapped.location.radius_m ?? ASSUMED_RADIUS_M}
          assumed={mapped.location.radius_m === null}
          basemap={basemap?.pmtiles ?? null}
        />
      ) : null}
      <Offers villa={villa} offers={data.offers} now={now} />
      <Calendar villa={villa} nights={data.calendar} now={now} />
      {data.claims.map(([member, claims]) => (
        <div key={member.id}>
          <ClaimsSection
            listing={member}
            claims={claims}
            now={now}
            idPrefix={`${member.platform}-`}
          />
        </div>
      ))}
      <Reviews villa={villa} reviews={data.reviews} now={now} />
    </main>
  );
}

import { ChevronDown, MapPin, Star } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ListingMap } from "@/components/listing-map";
import { ClaimsSection } from "@/components/listing/claims";
import { OfferCell } from "@/components/listing/offers";
import {
  ReviewItem,
  ReviewSummarySkeleton,
  SummaryCard,
  SummaryUnavailable,
  type SummaryOutcome,
} from "@/components/listing/reviews";
import { Sourced } from "@/components/sourced";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { DataTable } from "@/components/ui/table";
import { BookingCard, type Stay } from "@/components/villa/booking-card";
import { VillaGallery } from "@/components/villa/gallery";
import { MatchEvidence, type MatchPair } from "@/components/villa/match-evidence";
import { Specs } from "@/components/villa/specs";
import { SplitCalendar } from "@/components/villa/split-calendar";
import {
  apiClient,
  type Claims,
  type Listing,
  type Offer,
  type Scenario,
  type Villa,
  type VillaReview,
} from "@/lib/api/client";
import { readBasemap } from "@/lib/basemap";
import { addDays, daysBetween } from "@/lib/calendar";
import { COPY, oneVillaIn } from "@/lib/copy";
import { CLAIM_TARGET_TEXT, faDay, iranToday } from "@/lib/listing";
import { faDigits, faNum, rating } from "@/lib/numbers";
import { platformRank } from "@/lib/platforms";
import { FEATURE_TEXT } from "@/lib/search";

export const metadata: Metadata = { title: "ویلا" };

const NO_STORE = { cache: "no-store" } as const;
const CALENDAR_DAYS = 60;
const ASSUMED_RADIUS_M = 500;
const MAX_REVIEWS = 40; // as many as a summary reads, so every citation has its review
const MAX_STAY_NIGHTS = 30;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

type SearchParams = Record<string, string | string[] | undefined>;
type ScenarioOffers = { scenario: Scenario; byGuests: { guests: number; offers: Offer[] }[] };

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);

/** The stay from the URL (inherited from the search), else the first sample scenario. */
function stayFrom(params: SearchParams, scenarios: Scenario[], maxGuests: number): Stay {
  const first = scenarios[0];
  const fallback: Stay = {
    checkIn: first?.check_in ?? "",
    checkOut: first?.check_out ?? "",
    guests: first?.guests[0] ?? 4,
  };
  const checkIn = one(params.in);
  const checkOut = one(params.out);
  const guests = Number(one(params.guests));
  const datesOk =
    checkIn !== undefined &&
    checkOut !== undefined &&
    ISO_DAY.test(checkIn) &&
    ISO_DAY.test(checkOut) &&
    daysBetween(checkIn, checkOut) > 0 &&
    daysBetween(checkIn, checkOut) <= MAX_STAY_NIGHTS;
  return {
    checkIn: datesOk ? checkIn : fallback.checkIn,
    checkOut: datesOk ? checkOut : fallback.checkOut,
    guests:
      Number.isInteger(guests) && guests >= 1
        ? Math.min(guests, Math.max(maxGuests, 1))
        : fallback.guests,
  };
}

async function load(id: string, params: SearchParams, now: Date) {
  const api = apiClient();
  const path = { villa_id: id };
  const villa = await api.GET("/villas/{villa_id}", { params: { path }, ...NO_STORE });
  if (!villa.data) return null;
  const start = iranToday(now);
  const members = [...villa.data.members].sort(
    (a, b) => platformRank(a.platform) - platformRank(b.platform),
  );
  const maxGuests = Math.max(...members.map((m) => m.max_capacity ?? m.base_capacity ?? 0), 1);
  const scenarios = (await api.GET("/scenarios", NO_STORE)).data ?? [];
  const stay = stayFrom(params, scenarios, Math.max(maxGuests, 20));
  const [match, calendar, reviews, claims, offers, samples] = await Promise.all([
    api.GET("/villas/{villa_id}/match", { params: { path }, ...NO_STORE }),
    api.GET("/villas/{villa_id}/calendar", {
      params: { path, query: { start, end: addDays(start, CALENDAR_DAYS) } },
      ...NO_STORE,
    }),
    api.GET("/villas/{villa_id}/reviews", { params: { path }, ...NO_STORE }),
    Promise.all(
      members.map(async (m) => {
        const { data } = await api.GET("/listings/{platform}/{external_id}/claims", {
          params: { path: { platform: m.platform, external_id: m.id.split(":")[1] ?? "" } },
          ...NO_STORE,
        });
        return [m, data ?? null] as const;
      }),
    ),
    stay.checkIn
      ? api.GET("/villas/{villa_id}/offers", {
          params: {
            path,
            query: { check_in: stay.checkIn, check_out: stay.checkOut, guests: stay.guests },
          },
          ...NO_STORE,
        })
      : Promise.resolve({ data: [] as Offer[] }),
    Promise.all(
      scenarios.map(async (scenario) => ({
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
    ),
  ]);
  return {
    villa: { ...villa.data, members },
    match: (match.data ?? []) as MatchPair[],
    calendar: calendar.data ?? [],
    calendarStart: start,
    reviews: reviews.data ?? [],
    claims: claims as (readonly [Listing, Claims | null])[],
    offers: offers.data ?? [],
    samples: samples as ScenarioOffers[],
    stay,
    maxGuests: Math.max(maxGuests, stay.guests),
  };
}

const SECTIONS = [
  ["stay", "اقامت"],
  ["location", "مکان"],
  ["calendar", "تقویم"],
  ["prices", "قیمت‌ها"],
  ["reviews", "نظرها"],
  ["truth", "حقیقت‌سنجی"],
] as const;

function AnchorNav() {
  return (
    <nav
      aria-label="بخش‌های صفحه"
      className="sticky top-16 z-20 -mx-4 border-b border-line bg-canvas/95 px-4 backdrop-blur sm:-mx-6 sm:px-6"
    >
      <ul className="flex gap-1 overflow-x-auto py-1 text-sm">
        {SECTIONS.map(([id, label]) => (
          <li key={id}>
            <a
              href={`#${id}`}
              className="focus-ring block rounded-control px-3 py-2 whitespace-nowrap text-fg-muted hover:bg-sunken hover:text-fg"
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SectionTitle({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={`${id}-title`} className="text-xl font-bold text-balance">
      {children}
    </h2>
  );
}

const STATEMENT_SOURCE_TEXT: Record<string, string> = {
  amenities: "فهرست امکانات",
  description: "توضیحات",
  distances: "بخش فاصله‌ها",
};

function Inconsistencies({ villa, now }: { villa: Villa; now: Date }) {
  if (villa.inconsistencies.length === 0) return null;
  const nameOf = (p: string) => villa.members.find((m) => m.platform === p)?.platform_name ?? p;
  return (
    <Callout kind="caution" title="آنچه دو آگهی یکسان نمی‌گویند">
      <p>هر آگهی گفته‌ی خودش را دارد؛ پیش از رزرو از میزبان بپرسید.</p>
      <ul className="space-y-1.5">
        {villa.inconsistencies.map((x) => {
          const subject =
            x.kind === "feature"
              ? (FEATURE_TEXT[x.subject] ?? x.subject)
              : `فاصله تا ${CLAIM_TARGET_TEXT[x.subject] ?? x.subject}`;
          return (
            <li key={`${x.kind}-${x.subject}`} className="flex flex-wrap gap-x-3 gap-y-1">
              <span className="font-semibold">{subject}:</span>
              {x.statements.map((said) => {
                const name = nameOf(said.platform);
                const text =
                  said.says === null
                    ? (said.published ?? "")
                    : said.says === "has"
                      ? "دارد"
                      : "ندارد";
                return (
                  <span key={said.platform}>
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
                    <span className="text-fg-muted">
                      ({STATEMENT_SOURCE_TEXT[said.source] ?? said.source}
                      {said.span && said.source === "description" ? `: «${said.span}»` : ""})
                    </span>
                  </span>
                );
              })}
            </li>
          );
        })}
      </ul>
    </Callout>
  );
}

/** «قیمت‌های نمونه»: the sample stays for 4 and 8 people, closed on load (V7, V8). */
function SamplePrices({
  villa,
  samples,
  now,
}: {
  villa: Villa;
  samples: ScenarioOffers[];
  now: Date;
}) {
  if (samples.length === 0) return null;
  const fees = new Set(["fees_unknown"]); // said once, in the booking card
  return (
    <details className="group rounded-card border border-line bg-surface" data-drawer="samples">
      <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 font-semibold [&::-webkit-details-marker]:hidden">
        {COPY.samplePrices}
        <ChevronDown
          aria-hidden="true"
          className="size-4 text-fg-muted transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="space-y-5 px-4 pb-4">
        {samples.map(({ scenario, byGuests }) => (
          <div key={scenario.slug}>
            <h3 className="text-sm font-semibold">
              {scenario.name}{" "}
              <span className="font-normal text-fg-muted">
                ({faDay(scenario.check_in)} تا {faDay(scenario.check_out)})
              </span>
            </h3>
            <DataTable className="mt-2" caption={`${COPY.samplePrices}: ${scenario.name}`}>
              <thead>
                <tr>
                  <th scope="col">پلتفرم</th>
                  {byGuests.map((g) => (
                    <th key={g.guests} scope="col">
                      {faNum(g.guests)} نفر
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="align-top">
                {villa.members.map((member) => (
                  <tr key={member.id}>
                    <th scope="row" className="font-medium">
                      {member.platform_name}
                    </th>
                    {byGuests.map((g) => (
                      <td key={g.guests}>
                        <OfferCell
                          offer={g.offers.find((o) => o.listing_id === member.id) ?? null}
                          id={`sample-${scenario.slug}-${g.guests}-${member.platform}`}
                          label={`${scenario.name} برای ${faNum(g.guests)} نفر در ${member.platform_name}`}
                          common={fees}
                          listing={member}
                          now={now}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        ))}
      </div>
    </details>
  );
}

const villaReviewKey = (review: VillaReview) => `${review.platform}:${review.id}`;

async function fetchVillaSummary(villaId: string): Promise<SummaryOutcome> {
  try {
    const { data, response } = await apiClient().GET("/villas/{villa_id}/review-summary", {
      params: { path: { villa_id: villaId } },
      ...NO_STORE,
    });
    return { summary: data ?? null, unavailable: response.status === 503 };
  } catch {
    return { summary: null, unavailable: false };
  }
}

async function VillaReviewSummary({
  villaId,
  order,
}: {
  villaId: string;
  order: Record<string, number>;
}) {
  const { summary, unavailable } = await fetchVillaSummary(villaId);
  if (unavailable) return <SummaryUnavailable />;
  return (
    <SummaryCard
      summary={summary}
      order={order}
      {...(summary
        ? { title: `خلاصه‌ی ${faNum(summary.reviews_given)} نظر اخیر از همه‌ی پلتفرم‌ها` }
        : {})}
    />
  );
}

function Reviews({ villa, reviews, now }: { villa: Villa; reviews: VillaReview[]; now: Date }) {
  const shown = reviews.slice(0, MAX_REVIEWS);
  const order = Object.fromEntries(shown.map((r, index) => [villaReviewKey(r), index + 1]));
  return (
    <section id="reviews" aria-labelledby="reviews-title" className="scroll-mt-28 space-y-4">
      <div>
        <SectionTitle id="reviews">نظرها</SectionTitle>
        <p className="mt-1 text-sm text-fg-muted">
          {villa.members
            .map(
              (m) =>
                `${m.platform_name}: ${faNum(reviews.filter((r) => r.platform === m.platform).length)} نظر`,
            )
            .join(" · ")}
        </p>
      </div>
      <Suspense fallback={<ReviewSummarySkeleton />}>
        <VillaReviewSummary villaId={villa.id} order={order} />
      </Suspense>
      <ol className="divide-y divide-line rounded-card border border-line bg-surface">
        {shown.map((review, index) => {
          const member = villa.members.find((m) => m.platform === review.platform);
          return (
            <ReviewItem
              key={villaReviewKey(review)}
              review={review}
              index={index}
              idPrefix={`${review.platform}:`}
              badge={<Badge tone="muted">{member?.platform_name ?? review.platform}</Badge>}
              sourceName={member?.platform_name ?? review.platform}
              now={now}
            />
          );
        })}
      </ol>
    </section>
  );
}

export default async function VillaPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const [{ id }, params] = await Promise.all([props.params, props.searchParams]);
  const now = new Date();
  const [data, basemap] = await Promise.all([load(id, params, now), readBasemap()]);
  if (!data) notFound();
  const { villa } = data;
  const first = villa.members[0];
  const mapped = villa.members.find((m) => m.location);
  const place = first ? [first.locality, first.city].filter(Boolean).join("، ") : "";
  const names = Object.fromEntries(villa.members.map((m) => [m.platform, m.platform_name]));
  const textReviews = data.reviews.filter((r) => r.text).length;
  const multi = villa.members.length > 1;
  return (
    <div className="mx-auto max-w-6xl px-4 pt-6 pb-16 sm:px-6">
      <nav aria-label="مسیر" className="text-sm text-fg-muted">
        <Link href="/" className="focus-ring rounded-sm hover:text-fg">
          ویلاسنج
        </Link>
        <span aria-hidden="true" className="mx-2 text-fg-subtle">
          /
        </span>
        <Link href="/search" className="focus-ring rounded-sm hover:text-fg">
          جستجو
        </Link>
        <span aria-hidden="true" className="mx-2 text-fg-subtle">
          /
        </span>
        <span>ویلا</span>
      </nav>
      <header className="mt-3">
        <h1 className="text-2xl font-bold text-balance sm:text-3xl">
          {first ? faDigits(first.title) : "ویلا"}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="flex items-center gap-1.5 text-fg-muted">
            <MapPin aria-hidden="true" className="size-4 shrink-0" />
            {place || "محل منتشر نشده"}
          </span>
          {villa.rating !== null ? (
            <span className="flex items-center gap-1.5 tabular-nums">
              <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
              <span className="font-semibold">{rating(villa.rating)}</span>
              <span className="text-fg-muted">
                · {faNum(villa.rating_count)} امتیاز · {faNum(textReviews)} نظر
              </span>
            </span>
          ) : null}
          {multi ? (
            <a
              href="#match"
              data-match-badge=""
              className="focus-ring inline-flex items-center gap-1.5 rounded-full bg-brand-gradient px-3 py-1 font-semibold text-white shadow-raised hover:opacity-95"
            >
              {oneVillaIn(faNum(villa.members.length))}
              <span aria-hidden="true">·</span>
              <span className="underline underline-offset-4">{COPY.whySure}</span>
            </a>
          ) : null}
        </div>
      </header>
      <div className="mt-5">
        <VillaGallery gallery={villa.gallery} />
      </div>
      <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-12">
          <AnchorNav />
          <Specs villa={villa} now={now} />
          {multi && data.match.length > 0 ? (
            <MatchEvidence pairs={data.match} members={villa.members} />
          ) : null}
          <Inconsistencies villa={villa} now={now} />
          {mapped?.location ? (
            <section id="location" aria-labelledby="location-title" className="scroll-mt-28">
              <SectionTitle id="location">مکان</SectionTitle>
              <div className="mt-3">
                <ListingMap
                  lat={mapped.location.lat}
                  lon={mapped.location.lon}
                  radiusM={mapped.location.radius_m ?? ASSUMED_RADIUS_M}
                  assumed={mapped.location.radius_m === null}
                  basemap={basemap?.pmtiles ?? null}
                />
              </div>
            </section>
          ) : null}
          <section id="calendar" aria-labelledby="calendar-title" className="scroll-mt-28">
            <SectionTitle id="calendar">
              تقویم {multi ? "هر دو پلتفرم" : first?.platform_name}
            </SectionTitle>
            <p className="mt-1 text-sm text-fg-muted">
              هر روز آخرین مشاهده‌ی هر پلتفرم است. روز ورود و روز خروج را بزنید تا قیمت‌ها برای همان
              سفر حساب شود.
            </p>
            <div className="mt-3 rounded-card border border-line bg-surface p-4">
              <SplitCalendar
                nights={data.calendar}
                names={names}
                start={data.calendarStart}
                days={CALENDAR_DAYS}
                checkIn={data.stay.checkIn}
                checkOut={data.stay.checkOut}
                guests={data.stay.guests}
                nowIso={now.toISOString()}
              />
            </div>
          </section>
          <section id="prices" aria-labelledby="prices-title" className="scroll-mt-28 space-y-3">
            <SectionTitle id="prices">قیمت‌ها</SectionTitle>
            <p className="text-sm text-fg-muted">
              قیمت سفر شما در کارت «{COPY.platforms}» آمده؛ قیمت چند سفر نمونه برای مقایسه:
            </p>
            <SamplePrices villa={villa} samples={data.samples} now={now} />
          </section>
          <Reviews villa={villa} reviews={data.reviews} now={now} />
          <section id="truth" aria-labelledby="truth-title" className="scroll-mt-28 space-y-6">
            <SectionTitle id="truth">حقیقت‌سنجی</SectionTitle>
            {data.claims.map(([member, claims]) => (
              <ClaimsSection
                key={member.id}
                listing={member}
                claims={claims}
                now={now}
                idPrefix={`${member.platform}-`}
              />
            ))}
          </section>
        </div>
        <aside aria-label={COPY.platforms} className="lg:sticky lg:top-24 lg:self-start">
          {data.stay.checkIn ? (
            <BookingCard
              members={villa.members}
              offers={data.offers}
              stay={data.stay}
              maxGuests={data.maxGuests}
              nights={data.calendar}
              calendar={{ start: data.calendarStart, days: CALENDAR_DAYS }}
              now={now}
            />
          ) : null}
        </aside>
      </div>
    </div>
  );
}

import { ArrowUpLeft, EyeOff, Layers, MapPin, Star } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ListingMap } from "@/components/listing-map";
import { ClaimsSection } from "@/components/listing/claims";
import { Gallery } from "@/components/listing/gallery";
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
import { Section } from "@/components/ui/card";
import { DataTable } from "@/components/ui/table";
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
  faToman,
  iranToday,
} from "@/lib/listing";
import { FEATURE_TEXT } from "@/lib/search";

export const metadata: Metadata = { title: "ویلا" };

const NO_STORE = { cache: "no-store" } as const;
const CALENDAR_DAYS = 30;
const ASSUMED_RADIUS_M = 500;
const MAX_REVIEWS = 40; // as many as a summary reads, so every citation has its review

const FIELDS: { key: keyof Listing & string; label: string; suffix?: string }[] = [
  { key: "property_type", label: "نوع" },
  { key: "bedrooms", label: "اتاق خواب" },
  { key: "bathrooms", label: "سرویس بهداشتی" },
  { key: "area_m2", label: "متراژ", suffix: " متر" },
  { key: "base_capacity", label: "ظرفیت پایه", suffix: " نفر" },
  { key: "max_capacity", label: "حداکثر ظرفیت", suffix: " نفر" },
];

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

function memberOf(villa: Villa, platform: string): Listing | undefined {
  return villa.members.find((m) => m.platform === platform);
}

function fieldText(key: string, value: unknown, suffix = ""): string {
  if (value === null || value === undefined) return "—";
  if (key === "property_type") return faPropertyType(String(value));
  return `${faNumber(Number(value))}${suffix}`;
}

/** Each platform's own facts side by side; a row the listings disagree on is marked. */
function Specs({ villa, now }: { villa: Villa; now: Date }) {
  const conflicting = new Set(villa.conflicts.map((c) => c.field));
  return (
    <Section
      id="specs"
      title="مشخصات به گفته‌ی هر پلتفرم"
      description="هیچ مقداری میانگین یا ترکیب نمی‌شود؛ جایی که آگهی‌ها فرق دارند علامت خورده است."
    >
      <DataTable caption="مشخصات ویلا در هر پلتفرم" minWidth="28rem">
        <thead>
          <tr>
            <th scope="col">مشخصه</th>
            {villa.members.map((m) => (
              <th key={m.id} scope="col">
                {m.platform_name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FIELDS.map((field) => {
            const conflict = conflicting.has(field.key);
            return (
              <tr key={field.key} className={cn(conflict && "bg-amber-50/60")}>
                <th scope="row" className="font-medium">
                  <span className="flex items-center gap-2">
                    {field.label}
                    {conflict ? <Badge tone="caution">ناهمخوان</Badge> : null}
                  </span>
                </th>
                {villa.members.map((m) => {
                  const value = m[field.key];
                  const text = fieldText(field.key, value, field.suffix);
                  return (
                    <td key={m.id}>
                      {value === null || value === undefined ? (
                        <span className="text-fg-subtle">منتشر نشده</span>
                      ) : (
                        <Sourced
                          id={`conflict-${field.key}-${m.platform}`}
                          label={`${field.label} در ${m.platform_name}`}
                          provenance={m.provenance}
                          sourceName={m.platform_name}
                          now={now}
                        >
                          {text}
                        </Sourced>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </DataTable>
    </Section>
  );
}

const STATEMENT_SOURCE_TEXT: Record<string, string> = {
  amenities: "فهرست امکانات",
  description: "توضیحات",
  distances: "بخش فاصله‌ها",
};

function Inconsistencies({ villa, now }: { villa: Villa; now: Date }) {
  if (villa.inconsistencies.length === 0) return null;
  return (
    <section aria-labelledby="inconsistencies-title">
      <Callout
        kind="caution"
        title={<span id="inconsistencies-title">ادعاهایی که آگهی‌ها یکسان نمی‌گویند</span>}
      >
        <p>
          هر آگهی گفته‌ی خودش را دارد و از اینجا معلوم نیست کدام درست است؛ پیش از رزرو از میزبان
          بپرسید.
        </p>
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
                      <span className="text-amber-900/80">
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
      </Callout>
    </section>
  );
}

function Offers({ villa, offers, now }: { villa: Villa; offers: ScenarioOffers[]; now: Date }) {
  return (
    <Section
      id="offers"
      title="قیمت نهایی در هر پلتفرم"
      description="قیمت هر پلتفرم جدا حساب می‌شود و هیچ‌وقت با دیگری ترکیب نمی‌شود؛ هر عدد منبع و زمان مشاهده‌اش را دارد."
    >
      <div className="space-y-6">
        {offers.map(({ scenario, byGuests }) => (
          <div key={scenario.slug}>
            <h3 className="font-semibold">
              {scenario.name}{" "}
              <span className="text-sm font-normal text-fg-muted tabular-nums">
                ({faDay(scenario.check_in)} تا {faDay(scenario.check_out)})
              </span>
            </h3>
            <DataTable className="mt-2" caption={`قیمت ${scenario.name} در هر پلتفرم`}>
              <thead>
                <tr>
                  <th scope="col">پلتفرم</th>
                  {byGuests.map((g) => (
                    <th key={g.guests} scope="col">
                      {faNumber(g.guests)} نفر
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
                    {byGuests.map((g) => {
                      const offer = g.offers.find((o) => o.listing_id === member.id) ?? null;
                      return (
                        <td key={g.guests}>
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
            </DataTable>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Calendar({ villa, nights, now }: { villa: Villa; nights: VillaNight[]; now: Date }) {
  const hidden = nights.filter((n) => n.hidden).length;
  return (
    <Section
      id="calendar"
      title="تقویم هر دو پلتفرم"
      description={
        <>
          هر شب همان‌طور که هر پلتفرم نشان داده بود. «پنهان» یعنی شبی که در یک پلتفرم آزاد و در
          دیگری پر بود (با کمتر از ۶ ساعت فاصله‌ی مشاهده):{" "}
          <strong className="font-semibold text-fg">
            {faNumber(hidden)} شب از {faNumber(nights.length)}
          </strong>{" "}
          شب پیش رو.
        </>
      }
    >
      <DataTable caption="تقویم شب به شب در هر پلتفرم" minWidth="26rem">
        <thead>
          <tr>
            <th scope="col">شب</th>
            {villa.members.map((m) => (
              <th key={m.platform} scope="col">
                {m.platform_name}
              </th>
            ))}
            <th scope="col">
              <span className="sr-only">شب پنهان</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {nights.map((n) => (
            <tr key={n.night} className={n.hidden ? "bg-brand-50" : undefined}>
              <th scope="row" className="font-normal whitespace-nowrap">
                {faDay(n.night)}
              </th>
              {villa.members.map((m) => {
                const seen = n.by_platform[m.platform];
                if (!seen)
                  return (
                    <td key={m.platform} className="text-fg-subtle">
                      —
                    </td>
                  );
                const free = seen.availability === "available";
                return (
                  <td key={m.platform}>
                    <span className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className={cn(
                          "size-2 shrink-0 rounded-full",
                          free ? "bg-brand-500" : "bg-sand-400",
                        )}
                      />
                      <Sourced
                        id={`night-${n.night}-${m.platform}`}
                        label={`شب ${faDay(n.night)} در ${m.platform_name}`}
                        {...(seen.price ? { value: faToman(seen.price) } : {})}
                        provenance={seen.provenance}
                        sourceName={m.platform_name}
                        now={now}
                      >
                        {AVAILABILITY_TEXT[seen.availability] ?? seen.availability}
                        {seen.price ? ` · ${faMillions(seen.price.low_toman)} م` : ""}
                      </Sourced>
                    </span>
                  </td>
                );
              })}
              <td>
                {n.hidden ? (
                  <Badge tone="brand" icon={<EyeOff aria-hidden="true" className="size-3" />}>
                    پنهان
                  </Badge>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="mt-2 text-xs text-fg-muted">«م» یعنی میلیون تومان برای یک شب.</p>
    </Section>
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

/** Pros and cons over every platform's reviews, streamed in (one cached LLM call). */
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
        ? { title: `خلاصه‌ی ${faNumber(summary.reviews_given)} نظر اخیر از همه‌ی پلتفرم‌ها` }
        : {})}
    />
  );
}

function Reviews({ villa, reviews, now }: { villa: Villa; reviews: VillaReview[]; now: Date }) {
  const shown = reviews.slice(0, MAX_REVIEWS);
  const order = Object.fromEntries(shown.map((r, index) => [villaReviewKey(r), index + 1]));
  return (
    <Section
      id="reviews"
      title="نظرهای مهمان‌ها در همه‌ی پلتفرم‌ها"
      description={villa.members
        .map(
          (m) =>
            `${m.platform_name}: ${faNumber(reviews.filter((r) => r.platform === m.platform).length)} نظر`,
        )
        .join(" · ")}
    >
      <Suspense fallback={<ReviewSummarySkeleton />}>
        <VillaReviewSummary villaId={villa.id} order={order} />
      </Suspense>
      <ol className="mt-4 divide-y divide-line rounded-card border border-line bg-surface">
        {shown.map((review, index) => {
          const member = memberOf(villa, review.platform);
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
    </Section>
  );
}

function PriceCard({ villa, offers, now }: { villa: Villa; offers: ScenarioOffers[]; now: Date }) {
  const first = offers[0];
  const group = first?.byGuests[0];
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-float">
      {villa.rating !== null ? (
        <p className="flex items-center gap-1.5 text-sm">
          <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
          <span className="font-semibold tabular-nums">{faNumber(villa.rating)}</span>
          <span className="text-fg-muted">
            ({faNumber(villa.rating_count)} رأی در همه‌ی پلتفرم‌ها)
          </span>
        </p>
      ) : null}
      {first && group ? (
        <>
          <p className="mt-4 text-sm text-fg-muted">
            {first.scenario.name} برای {faNumber(group.guests)} نفر
          </p>
          <ul className="mt-3 space-y-4">
            {villa.members.map((m) => (
              <li key={m.id} className="border-t border-line pt-3 first:border-0 first:pt-0">
                <p className="mb-1 text-xs font-medium text-fg-muted">{m.platform_name}</p>
                <OfferCell
                  offer={group.offers.find((o) => o.listing_id === m.id) ?? null}
                  id={`aside-${first.scenario.slug}-${group.guests}-${m.platform}`}
                  label={`قیمت ${first.scenario.name} برای ${faNumber(group.guests)} نفر در ${m.platform_name}`}
                  common={new Set()}
                  listing={m}
                  now={now}
                />
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <div className="mt-5 space-y-2 border-t border-line pt-4">
        {villa.members.map((m) => (
          <Link
            key={m.id}
            href={`/listings/${m.platform}/${m.id.split(":")[1]}`}
            className="focus-ring flex items-center justify-between rounded-control px-2 py-1.5 text-sm hover:bg-sunken"
          >
            آگهی در {m.platform_name}
            <ArrowUpLeft aria-hidden="true" className="size-4 text-fg-muted" />
          </Link>
        ))}
      </div>
    </div>
  );
}

export default async function VillaPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const now = new Date();
  const [data, basemap] = await Promise.all([load(id, now), readBasemap()]);
  if (!data) notFound();
  const { villa } = data;
  const first = villa.members[0];
  const mapped = villa.members.find((m) => m.location);
  const photos = [...new Set(villa.members.flatMap((m) => m.photos))];
  const place = first ? [first.locality, first.city].filter(Boolean).join("، ") : "";
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
      <header className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" icon={<Layers aria-hidden="true" className="size-3.5" />}>
            یک ویلا در {faNumber(villa.members.length)} آگهی
          </Badge>
          {villa.members.map((m) => (
            <Badge key={m.id} tone="muted">
              {m.platform_name}
            </Badge>
          ))}
        </div>
        <h1 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
          {first?.title ?? "ویلا"}
        </h1>
        <p className="mt-2 flex items-center gap-1.5 text-fg-muted">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          {place || "محل منتشر نشده"}
        </p>
        <p className="mt-3 max-w-3xl text-sm text-pretty text-fg-muted">
          آگهی‌های این ویلا:{" "}
          {villa.members.map((m, index) => (
            <span key={m.id}>
              {index > 0 ? "، " : ""}
              <Link
                href={`/listings/${m.platform}/${m.id.split(":")[1]}`}
                className="focus-ring rounded-sm text-accent underline underline-offset-4"
              >
                {m.platform_name}
              </Link>
            </span>
          ))}
          . اینکه این آگهی‌ها یک ویلا هستند را قواعد تطبیق، داور مدل‌زبانی (فقط برای رد) و برچسب‌های
          انسانی تعیین کرده‌اند.
        </p>
      </header>
      <div className="mt-6">
        <Gallery
          photos={photos}
          platformName={villa.members.map((m) => m.platform_name).join(" و ")}
        />
      </div>
      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-12">
          <Specs villa={villa} now={now} />
          <Inconsistencies villa={villa} now={now} />
          {mapped?.location ? (
            <Section id="map" title="موقعیت">
              <ListingMap
                lat={mapped.location.lat}
                lon={mapped.location.lon}
                radiusM={mapped.location.radius_m ?? ASSUMED_RADIUS_M}
                assumed={mapped.location.radius_m === null}
                basemap={basemap?.pmtiles ?? null}
              />
            </Section>
          ) : null}
          <Offers villa={villa} offers={data.offers} now={now} />
          <Calendar villa={villa} nights={data.calendar} now={now} />
          {data.claims.map(([member, claims]) => (
            <ClaimsSection
              key={member.id}
              listing={member}
              claims={claims}
              now={now}
              idPrefix={`${member.platform}-`}
            />
          ))}
          <Reviews villa={villa} reviews={data.reviews} now={now} />
        </div>
        <aside aria-label="قیمت در یک نگاه" className="lg:sticky lg:top-24 lg:self-start">
          <PriceCard villa={villa} offers={data.offers} now={now} />
        </aside>
      </div>
    </div>
  );
}

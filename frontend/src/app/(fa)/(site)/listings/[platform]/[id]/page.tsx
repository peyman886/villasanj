import { ArrowUpLeft, ExternalLink, Layers, MapPin } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ListingMap } from "@/components/listing-map";
import { CalendarSection } from "@/components/listing/calendar";
import { ClaimsSection } from "@/components/listing/claims";
import { ListingFacts } from "@/components/listing/facts";
import { Gallery } from "@/components/listing/gallery";
import {
  OfferCell,
  OffersSection,
  commonCaveats,
  type ScenarioOffers,
} from "@/components/listing/offers";
import {
  ReviewSummarySection,
  ReviewSummarySkeleton,
  ReviewsSection,
} from "@/components/listing/reviews";
import { Badge } from "@/components/ui/badge";
import { buttonClass } from "@/components/ui/button";
import { Section } from "@/components/ui/card";
import {
  apiClient,
  type CalendarNight,
  type Claims,
  type Geo,
  type Listing,
  type Review,
} from "@/lib/api/client";
import { readBasemap } from "@/lib/basemap";
import { faPropertyType } from "@/lib/labeling";
import { addDays, faDay, faNumber, iranToday } from "@/lib/listing";
import { faDigits } from "@/lib/numbers";

export const metadata: Metadata = { title: "آگهی" };

const CALENDAR_DAYS = 60;
const ASSUMED_RADIUS_M = 500; // a pin without a published radius (ADR-0013, assumption A14)
const NO_STORE = { cache: "no-store" } as const; // observations change; never serve stale ones

type PageData = {
  listing: Listing;
  scenarios: ScenarioOffers[];
  calendar: CalendarNight[];
  calendarStart: string;
  reviews: Review[];
  geo: Geo | null;
  claims: Claims | null;
};

async function load(platform: string, externalId: string, now: Date): Promise<PageData | null> {
  const api = apiClient();
  const path = { platform, external_id: externalId };
  const listing = await api.GET("/listings/{platform}/{external_id}", {
    params: { path },
    ...NO_STORE,
  });
  if (!listing.data) return null;
  const start = iranToday(now);
  const [scenarios, calendar, reviews, geo, claims] = await Promise.all([
    api.GET("/scenarios", NO_STORE),
    api.GET("/listings/{platform}/{external_id}/calendar", {
      params: { path, query: { start, end: addDays(start, CALENDAR_DAYS) } },
      ...NO_STORE,
    }),
    api.GET("/listings/{platform}/{external_id}/reviews", { params: { path }, ...NO_STORE }),
    api.GET("/listings/{platform}/{external_id}/geo", { params: { path }, ...NO_STORE }),
    api.GET("/listings/{platform}/{external_id}/claims", { params: { path }, ...NO_STORE }),
  ]);
  const offers = await Promise.all(
    (scenarios.data ?? []).map(async (scenario) => ({
      scenario,
      offers: await Promise.all(
        scenario.guests.map(async (guests) => {
          const offer = await api.GET("/listings/{platform}/{external_id}/offer", {
            params: {
              path,
              query: { check_in: scenario.check_in, check_out: scenario.check_out, guests },
            },
            ...NO_STORE,
          });
          return offer.data ?? null;
        }),
      ),
    })),
  );
  return {
    listing: listing.data,
    scenarios: offers,
    calendar: calendar.data ?? [],
    calendarStart: start,
    reviews: reviews.data ?? [],
    geo: geo.data ?? null,
    claims: claims.data ?? null,
  };
}

/** The first scenario's offers at a glance, beside the page on wide screens. */
function PriceCard({
  listing,
  scenarios,
  villaId,
  now,
}: {
  listing: Listing;
  scenarios: ScenarioOffers[];
  villaId: string | null;
  now: Date;
}) {
  const first = scenarios[0];
  const common = commonCaveats(scenarios.flatMap((s) => s.offers));
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-float">
      {first ? (
        <>
          <p className="text-sm text-fg-muted">{first.scenario.name}</p>
          <p className="text-xs text-fg-subtle">
            {faDay(first.scenario.check_in)} تا {faDay(first.scenario.check_out)}
          </p>
          <ul className="mt-4 space-y-4">
            {first.offers.map((offer, index) => (
              <li
                key={first.scenario.guests[index]}
                className="border-t border-line pt-3 first:border-0 first:pt-0"
              >
                <p className="mb-1 text-xs text-fg-muted">
                  {faNumber(first.scenario.guests[index])} نفر
                </p>
                <OfferCell
                  offer={offer}
                  id={`aside-${first.scenario.slug}-${first.scenario.guests[index]}`}
                  label={`قیمت ${first.scenario.name} برای ${faNumber(first.scenario.guests[index])} نفر`}
                  common={common}
                  listing={listing}
                  now={now}
                />
              </li>
            ))}
          </ul>
          <a
            href="#offers-title"
            className="focus-ring mt-4 inline-block rounded-sm text-sm text-accent hover:underline"
          >
            همه‌ی سناریوها
          </a>
        </>
      ) : (
        <p className="text-sm text-fg-muted">سناریوی قیمتی تعریف نشده است.</p>
      )}
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className={buttonClass("secondary", "md", "mt-5 w-full")}
      >
        دیدن آگهی در {listing.platform_name}
        <ExternalLink aria-hidden="true" className="size-4" />
      </a>
      {villaId ? (
        <Link href={`/villas/${villaId}`} className={buttonClass("primary", "md", "mt-2 w-full")}>
          مقایسه با پلتفرم دیگر
          <ArrowUpLeft aria-hidden="true" className="size-4" />
        </Link>
      ) : null}
    </div>
  );
}

export default async function ListingPage(props: {
  params: Promise<{ platform: string; id: string }>;
}) {
  const { platform, id } = await props.params;
  const now = new Date();
  const [data, basemap, villa] = await Promise.all([
    load(platform, id, now),
    readBasemap(),
    apiClient()
      .GET("/villas/of/{platform}/{external_id}", {
        params: { path: { platform, external_id: id } },
        ...NO_STORE,
      })
      .then((r) => r.data ?? null)
      .catch(() => null),
  ]);
  if (data === null) notFound();
  const { listing } = data;
  const multi = villa && villa.members > 1 ? villa.villa_id : null;
  const place = [listing.locality, listing.city].filter(Boolean).join("، ");
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
        <span>آگهی در {listing.platform_name}</span>
      </nav>
      <header className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="muted">{listing.platform_name}</Badge>
          <Badge tone="neutral">{faPropertyType(listing.property_type)}</Badge>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
          {faDigits(listing.title)}
        </h1>
        <p className="mt-2 flex items-center gap-1.5 text-fg-muted">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          {place || "محل منتشر نشده"}
        </p>
      </header>
      {multi ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-card border border-brand-200 bg-brand-50 p-4 text-sm text-brand-950">
          <Layers aria-hidden="true" className="size-5 shrink-0 text-brand-700" />
          <p className="flex-1 text-pretty">
            همین ویلا در پلتفرم دیگری هم آگهی شده است؛ قیمت و تقویم هر دو را کنار هم ببینید.
          </p>
          <Link href={`/villas/${multi}`} className={buttonClass("primary", "sm")}>
            صفحه‌ی ویلا
          </Link>
        </div>
      ) : null}
      <div className="mt-6">
        <Gallery photos={listing.photos} platformName={listing.platform_name} />
      </div>
      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-12">
          <Section
            id="facts"
            title="مشخصات"
            description="آنچه آگهی منتشر کرده؛ روی هر عدد بزنید تا منبعش را ببینید. این صفحه‌ی یک آگهی است و قیمت و تقویمش فقط مال همین آگهی است."
          >
            <ListingFacts listing={listing} geo={data.geo} now={now} />
          </Section>
          {listing.location ? (
            <Section id="map" title="موقعیت">
              <ListingMap
                lat={listing.location.lat}
                lon={listing.location.lon}
                radiusM={listing.location.radius_m ?? ASSUMED_RADIUS_M}
                assumed={listing.location.radius_m === null}
                basemap={basemap?.pmtiles ?? null}
              />
            </Section>
          ) : null}
          <ClaimsSection listing={listing} claims={data.claims} now={now} />
          <OffersSection listing={listing} scenarios={data.scenarios} now={now} />
          <CalendarSection
            listing={listing}
            nights={data.calendar}
            start={data.calendarStart}
            days={CALENDAR_DAYS}
            now={now}
          />
          <ReviewsSection
            listing={listing}
            reviews={data.reviews}
            now={now}
            summary={
              <Suspense fallback={<ReviewSummarySkeleton />}>
                <ReviewSummarySection platform={platform} id={id} />
              </Suspense>
            }
          />
        </div>
        <aside aria-label="قیمت در یک نگاه" className="lg:sticky lg:top-24 lg:self-start">
          <PriceCard listing={listing} scenarios={data.scenarios} villaId={multi} now={now} />
        </aside>
      </div>
    </div>
  );
}

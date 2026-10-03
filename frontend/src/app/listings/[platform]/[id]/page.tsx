import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import {
  apiClient,
  type CalendarNight,
  type Claims,
  type Geo,
  type Listing,
  type Review,
} from "@/lib/api/client";
import { ListingMap } from "@/components/listing-map";
import { readBasemap } from "@/lib/basemap";
import { addDays, iranToday } from "@/lib/listing";

import {
  CalendarSection,
  ClaimsSection,
  Header,
  OffersSection,
  Photos,
  ReviewSummarySection,
  ReviewSummarySkeleton,
  ReviewsSection,
  type ScenarioOffers,
} from "./sections";

export const metadata: Metadata = { title: "آگهی · ویلاسنج" };

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
  return (
    <main className="mx-auto max-w-5xl px-4 pt-6 pb-16 sm:px-6">
      <Header listing={listing} geo={data.geo} now={now} />
      {villa && villa.members > 1 ? (
        <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-pretty">
          همین ویلا در پلتفرم دیگری هم آگهی شده است.{" "}
          <Link
            href={`/villas/${villa.villa_id}`}
            className="font-medium text-emerald-900 underline underline-offset-4"
          >
            قیمت‌ها و تقویم هر دو را کنار هم ببینید
          </Link>
        </p>
      ) : null}
      {listing.location ? (
        <ListingMap
          lat={listing.location.lat}
          lon={listing.location.lon}
          radiusM={listing.location.radius_m ?? ASSUMED_RADIUS_M}
          assumed={listing.location.radius_m === null}
          basemap={basemap?.pmtiles ?? null}
        />
      ) : null}
      <Photos listing={listing} />
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
            <ReviewSummarySection
              platform={platform}
              id={id}
              order={Object.fromEntries(data.reviews.map((r, index) => [r.id, index + 1]))}
            />
          </Suspense>
        }
      />
    </main>
  );
}

import { ChevronDown, Clock } from "lucide-react";

import { Sourced } from "@/components/sourced";
import { Badge } from "@/components/ui/badge";
import { Section } from "@/components/ui/card";
import { DataTable } from "@/components/ui/table";
import type { Listing, Offer, Scenario } from "@/lib/api/client";
import {
  CAVEAT_TEXT,
  STATUS_TEXT,
  faAge,
  faDay,
  faNumber,
  faShare,
  faToman,
  offerText,
} from "@/lib/listing";

export type ScenarioOffers = { scenario: Scenario; offers: (Offer | null)[] };

/** One all-in offer: the total with its source, each person's share, its age and caveats. */
export function OfferCell({
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
  if (offer === null) return <span className="text-fg-subtle">پاسخی دریافت نشد</span>;
  const own = offer.caveats.filter((c) => !common.has(c));
  const bookable = offer.status === "bookable";
  return (
    <div className="space-y-1.5">
      <p className={bookable ? "font-semibold tabular-nums" : "tabular-nums text-fg-muted"}>
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
          <span className="font-normal">{offerText(offer)}</span>
        )}
      </p>
      {offer.per_person && offer.guests > 1 ? (
        <p className="text-xs text-fg-muted tabular-nums">
          هر نفر{" "}
          <Sourced
            id={`${id}-share`}
            label={`سهم هر نفر، ${label}`}
            value={`${faShare(offer.per_person)}: جمع تقسیم بر ${faNumber(offer.guests)} نفر`}
            provenance={offer.provenance}
            sourceName={listing.platform_name}
            now={now}
          >
            {faShare(offer.per_person)}
          </Sourced>
        </p>
      ) : null}
      {offer.total && !bookable ? (
        <Badge tone="caution">{STATUS_TEXT[offer.status] ?? offer.status}</Badge>
      ) : null}
      <p className="flex items-center gap-1 text-xs text-fg-subtle">
        <Clock aria-hidden="true" className="size-3" />
        مشاهده {faAge(offer.provenance.oldest_input_at, now)}
        {offer.stale ? (
          <Badge tone="caution" className="ms-1">
            قدیمی
          </Badge>
        ) : null}
      </p>
      {own.length > 0 ? (
        <ul className="list-disc ps-4 text-xs text-fg-muted">
          {own.map((c) => (
            <li key={c}>{CAVEAT_TEXT[c] ?? c}</li>
          ))}
        </ul>
      ) : null}
      {offer.nights.length > 0 ? (
        <details className="group text-xs">
          <summary className="focus-ring inline-flex cursor-pointer list-none items-center gap-1 rounded-sm text-accent [&::-webkit-details-marker]:hidden">
            جزئیات شب‌ها
            <ChevronDown
              aria-hidden="true"
              className="size-3 transition-transform group-open:rotate-180"
            />
          </summary>
          <ul className="mt-1.5 space-y-1">
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

/** Caveats every priced offer shares are said once, under the table. */
export function commonCaveats(offers: (Offer | null)[]): Set<string> {
  const priced = offers.filter((o): o is Offer => o !== null && o.total !== null);
  return new Set(
    (priced[0]?.caveats ?? []).filter((c) => priced.every((o) => o.caveats.includes(c))),
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
  const common = commonCaveats(scenarios.flatMap((s) => s.offers));
  return (
    <Section
      id="offers"
      title="قیمت نهایی برای هر سناریو"
      description="جمع قیمت شب‌ها و هزینه‌ی نفر اضافه برای همین آگهی، از آخرین مشاهده‌ی تقویم. روی هر مبلغ بزنید تا منبع و زمان مشاهده‌اش را ببینید."
    >
      {scenarios.length === 0 ? (
        <p className="text-sm text-fg-muted">سناریویی تعریف نشده است.</p>
      ) : (
        <DataTable caption="قیمت نهایی این آگهی برای هر سناریو و تعداد نفر">
          <thead>
            <tr>
              <th scope="col">سناریو</th>
              {guests.map((g) => (
                <th key={g} scope="col">
                  {faNumber(g)} نفر
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map(({ scenario, offers: row }) => (
              <tr key={scenario.slug} className="align-top">
                <th scope="row" className="font-medium">
                  {scenario.name}
                  <span className="mt-0.5 block text-xs font-normal text-fg-muted">
                    {faDay(scenario.check_in)} تا {faDay(scenario.check_out)}
                  </span>
                </th>
                {row.map((offer, index) => (
                  <td key={scenario.guests[index]}>
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
        </DataTable>
      )}
      {common.size > 0 ? (
        <ul className="mt-3 space-y-1 text-sm text-pretty text-fg-muted">
          {[...common].map((c) => (
            <li key={c} className="flex gap-2">
              <span aria-hidden="true">•</span>
              {CAVEAT_TEXT[c] ?? c}
            </li>
          ))}
        </ul>
      ) : null}
    </Section>
  );
}

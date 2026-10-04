import { Bath, BedDouble, CarFront, Maximize, Star, UserPlus, Users, Waves } from "lucide-react";
import type { ReactNode } from "react";

import { Sourced } from "@/components/sourced";
import type { Geo, Listing } from "@/lib/api/client";
import { faNumber } from "@/lib/listing";

type Fact = { key: string; label: string; icon: ReactNode; value: ReactNode };

// dt and dd are direct children of the tile (a <div> group inside the <dl>); the icon is
// decoration inside the term.
function FactTile({ fact }: { fact: Fact }) {
  return (
    <div className="relative min-h-[3.75rem] rounded-card border border-line bg-surface p-3 ps-15">
      <dt className="text-xs text-fg-muted">
        <span
          aria-hidden="true"
          className="absolute start-3 top-3 grid size-9 place-items-center rounded-full bg-sunken text-fg-muted"
        >
          {fact.icon}
        </span>
        {fact.label}
      </dt>
      <dd className="mt-0.5 min-w-0 font-medium tabular-nums">{fact.value}</dd>
    </div>
  );
}

const ICON = "size-4";

/** The listing's structured facts, each opening its source; unknown is said, never guessed. */
export function ListingFacts({
  listing,
  geo,
  now,
  idPrefix = "",
}: {
  listing: Listing;
  geo: Geo | null;
  now: Date;
  idPrefix?: string;
}) {
  const plain: [string, string, number | null, string, ReactNode][] = [
    [
      "bedrooms",
      "اتاق خواب",
      listing.bedrooms,
      "",
      <BedDouble key="i" aria-hidden="true" className={ICON} />,
    ],
    [
      "bathrooms",
      "سرویس بهداشتی",
      listing.bathrooms,
      "",
      <Bath key="i" aria-hidden="true" className={ICON} />,
    ],
    [
      "area",
      "متراژ",
      listing.area_m2,
      " متر",
      <Maximize key="i" aria-hidden="true" className={ICON} />,
    ],
    [
      "base",
      "ظرفیت پایه",
      listing.base_capacity,
      " نفر",
      <Users key="i" aria-hidden="true" className={ICON} />,
    ],
    [
      "max",
      "حداکثر ظرفیت",
      listing.max_capacity,
      " نفر",
      <UserPlus key="i" aria-hidden="true" className={ICON} />,
    ],
  ];
  const facts: Fact[] = plain.map(([key, label, value, suffix, icon], index) => ({
    key,
    label,
    icon,
    value:
      value === null ? (
        <span className="font-normal text-fg-subtle">منتشر نشده</span>
      ) : (
        <Sourced
          id={`${idPrefix}fact-${index}`}
          label={label}
          provenance={listing.provenance}
          sourceName={listing.platform_name}
          now={now}
        >
          {faNumber(value)}
          {suffix}
        </Sourced>
      ),
  }));
  facts.push({
    key: "rating",
    label: `امتیاز در ${listing.platform_name}`,
    icon: <Star aria-hidden="true" className={`${ICON} fill-amber-400 text-amber-500`} />,
    value:
      listing.rating === null ? (
        <span className="font-normal text-fg-subtle">بدون امتیاز</span>
      ) : (
        <>
          <Sourced
            id={`${idPrefix}fact-rating`}
            label="امتیاز"
            provenance={listing.provenance}
            sourceName={listing.platform_name}
            now={now}
          >
            {faNumber(listing.rating)} از ۵
          </Sourced>
          {listing.rating_count ? (
            <span className="ms-1 text-xs font-normal text-fg-muted">
              ({faNumber(listing.rating_count)} رأی)
            </span>
          ) : null}
        </>
      ),
  });
  for (const [key, label, range, Icon] of [
    ["coast", "فاصله تا ساحل", geo?.coast_m ?? null, Waves],
    ["drive", "رانندگی از تهران", geo?.drive_s ?? null, CarFront],
  ] as const) {
    if (!range) continue;
    facts.push({
      key,
      label,
      icon: <Icon aria-hidden="true" className={ICON} />,
      value: (
        <>
          <Sourced
            id={`${idPrefix}geo-${key}`}
            label={label}
            value={range.text}
            provenance={range.provenance}
            now={now}
          >
            {range.text}
          </Sourced>
          {range.radius_assumed ? (
            <span className="mt-0.5 block text-xs font-normal text-fg-muted">
              پلتفرم دقت نقطه را اعلام نکرده؛ تا ۵۰۰ متر خطا فرض شده.
            </span>
          ) : null}
        </>
      ),
    });
  }
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {facts.map((fact) => (
        <FactTile key={fact.key} fact={fact} />
      ))}
    </dl>
  );
}

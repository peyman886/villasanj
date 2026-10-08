import { MapPin, Star } from "lucide-react";
import Link from "next/link";

import type { Listing, Offer } from "@/lib/api/client";
import { bookingRows } from "@/lib/booking";
import { cn } from "@/lib/cn";
import { COPY, oneVillaIn } from "@/lib/copy";
import { faDigits, faNum, rating, shortToman } from "@/lib/numbers";
import { platformRank, toneOf } from "@/lib/platforms";

/**
 * A villa found on both platforms, with each platform's own price for the sample stay side by side
 * (the gap is the point; prices are never merged). The first photo is hotlinked.
 */
export function HomeVillaCard({
  id,
  members,
  offers,
  stayText,
}: {
  id: string;
  members: Listing[];
  offers: Offer[];
  stayText: string;
}) {
  const sorted = [...members].sort((a, b) => platformRank(a.platform) - platformRank(b.platform));
  const first = sorted[0];
  if (!first) return null;
  const photo = sorted.flatMap((m) => m.photos)[0];
  const rated = sorted.filter((m) => m.rating && m.rating_count);
  const votes = rated.reduce((n, m) => n + (m.rating_count ?? 0), 0);
  const avg = votes
    ? rated.reduce((s, m) => s + (m.rating ?? 0) * (m.rating_count ?? 0), 0) / votes
    : null;
  const rows = bookingRows(sorted, offers).sort(
    (a, b) => platformRank(a.listing.platform) - platformRank(b.listing.platform),
  );
  return (
    <Link
      href={`/villas/${id}`}
      className="focus-ring group flex w-full flex-col overflow-hidden rounded-card border border-line bg-surface transition-colors hover:border-brand-400"
    >
      <div className="relative aspect-[4/3] bg-gradient-to-br from-brand-100 to-sand-200">
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server
          <img
            src={photo}
            alt=""
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            className="absolute inset-0 size-full object-cover"
          />
        ) : null}
        <span className="absolute start-3 top-3 rounded-full bg-brand-gradient px-2.5 py-0.5 text-xs font-semibold text-white shadow-raised">
          {oneVillaIn(faNum(members.length))}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <p className="line-clamp-1 font-bold group-hover:text-accent">{faDigits(first.title)}</p>
        <p className="flex items-center gap-3 text-sm text-fg-muted">
          <span className="flex items-center gap-1">
            <MapPin aria-hidden="true" className="size-4 shrink-0" />
            {[first.locality, first.city].filter(Boolean).join("، ") || "بدون نشانی"}
          </span>
          {avg !== null ? (
            <span className="flex items-center gap-1 tabular-nums">
              <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
              {rating(avg)}
              <span className="text-fg-subtle">· {faNum(votes)} امتیاز</span>
            </span>
          ) : null}
        </p>
        <ul className="mt-auto space-y-1 border-t border-line pt-2 text-sm tabular-nums">
          {rows.map((row) => (
            <li key={row.listing.id} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-fg-muted">
                <span
                  aria-hidden="true"
                  className={cn("size-2 rounded-full", toneOf(row.listing.platform).solid)}
                />
                {row.listing.platform_name}
              </span>
              {row.bookable && row.offer?.total ? (
                <span className={cn(row.cheaper ? "font-bold" : "text-fg-muted")}>
                  از {shortToman(row.offer.total.low_toman, "lower")}{" "}
                  {row.cheaper ? (
                    <span className="ms-1.5 rounded-full bg-brand-50 px-1.5 text-xs font-semibold text-brand-800">
                      {COPY.cheaper}
                    </span>
                  ) : null}
                </span>
              ) : (
                <span className="text-fg-subtle">{COPY.unavailable}</span>
              )}
            </li>
          ))}
        </ul>
        <p className="text-xs text-fg-subtle">{stayText}</p>
      </div>
    </Link>
  );
}

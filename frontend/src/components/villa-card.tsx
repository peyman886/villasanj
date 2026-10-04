import { BedDouble, House, MapPin, Star, Users } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { Listing } from "@/lib/api/client";
import { faNumber } from "@/lib/listing";

/** A canonical villa as a card: its best photo, where it is, and every platform it is on. */
export function VillaCard({ id, members }: { id: string; members: Listing[] }) {
  const first = members[0];
  if (!first) return null;
  const photo = members.flatMap((m) => m.photos)[0];
  const rated = members.filter((m) => m.rating && m.rating_count);
  const votes = rated.reduce((n, m) => n + (m.rating_count ?? 0), 0);
  const rating = votes
    ? rated.reduce((s, m) => s + (m.rating ?? 0) * (m.rating_count ?? 0), 0) / votes
    : null;
  return (
    <Link
      href={`/villas/${id}`}
      className="focus-ring group flex flex-col overflow-hidden rounded-card border border-line bg-surface shadow-raised transition-shadow duration-150 hover:shadow-float"
    >
      <div className="relative aspect-[4/3] bg-gradient-to-br from-brand-100 to-sand-200">
        <House aria-hidden="true" className="absolute inset-0 m-auto size-10 text-brand-300" />
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
        <div className="absolute start-3 top-3 flex flex-wrap gap-1.5">
          {members.map((m) => (
            <Badge key={m.id} tone="muted" className="bg-surface/95 shadow-raised">
              {m.platform_name}
            </Badge>
          ))}
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="line-clamp-1 font-semibold text-fg group-hover:text-accent">{first.title}</p>
        <p className="flex items-center gap-1 text-sm text-fg-muted">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          {[first.locality, first.city].filter(Boolean).join("، ") || "بدون نشانی"}
        </p>
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-sm text-fg-muted tabular-nums">
          {first.bedrooms !== null ? (
            <span className="flex items-center gap-1">
              <BedDouble aria-hidden="true" className="size-4" />
              {faNumber(first.bedrooms)} خواب
            </span>
          ) : null}
          {first.base_capacity !== null ? (
            <span className="flex items-center gap-1">
              <Users aria-hidden="true" className="size-4" />
              {faNumber(first.base_capacity)} نفر
            </span>
          ) : null}
          {rating !== null ? (
            <span className="flex items-center gap-1">
              <Star aria-hidden="true" className="size-4 fill-amber-400 text-amber-500" />
              {faNumber(Math.round(rating * 10) / 10)}
              <span className="text-fg-subtle">({faNumber(votes)} نظر)</span>
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}
